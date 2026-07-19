import json
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from entity import ChatRequest, ChatResponse
from agents.graph import graph
from agents.nodes import (
    router,
    hotel_node,
    flight_node,
    generate_response,
    _wants_coverage_list,
    _get_real_coverage_context,
)
from agents.llm import llm
from agents.prompts import get_system_prompt_for_unknown_node
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

conversation_history_messages = []

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def hello():
    return {"message": "Hello, World!"}


def _build_initial_state(message: str, history_pairs):
    flattened_messages = []
    for user_msg, assistant_msg in history_pairs:
        flattened_messages.append(user_msg)
        flattened_messages.append(assistant_msg)
    flattened_messages.append(message)

    return {
        "messages": flattened_messages,
        "intent": "",
        "sub_action": "",
        "city": None,
        "check_in": None,
        "check_out": None,
        "origin": None,
        "destination": None,
        "flight_date": None,
        "hotel_id": None,
        "guest_name": None,
        "guest_email": None,
        "room_type": None,
        "flight_id": None,
        "passenger_name": None,
        "passenger_email": None,
        "hotel_results": [],
        "flight_results": [],
        "response_text": "",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    recent_pairs = conversation_history_messages[-3:]
    initial_state = _build_initial_state(request.message, recent_pairs)

    try:
        result = await graph.ainvoke(initial_state)
    except Exception as e:
        return ChatResponse(
            response=f"Something went wrong while processing your request: {e}",
            hotels=None,
            flights=None,
        )

    response_text = result.get("response_text", "Something went wrong. Please try again.")
    conversation_history_messages.append((request.message, response_text))

    return ChatResponse(
        response=response_text,
        hotels=result.get("hotel_results", []) or None,
        flights=result.get("flight_results", []) or None,
    )


def _chunk_text(text: str, words_per_chunk: int = 3):
    """Reveal already-known text progressively in small word groups.
    Used for hotel/flight results, which are fully computed before formatting
    (not generated token-by-token by the LLM), so this simulates a streaming
    feel for consistency with the general-QA path, which streams real tokens."""
    words = text.split(" ")
    for i in range(0, len(words), words_per_chunk):
        piece = " ".join(words[i:i + words_per_chunk])
        if i + words_per_chunk < len(words):
            piece += " "
        yield piece


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    recent_pairs = conversation_history_messages[-3:]
    state = _build_initial_state(request.message, recent_pairs)

    async def event_generator():
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        final_text = ""
        hotels = None
        flights = None

        try:
            yield sse({"type": "activity", "text": "Understanding your request..."})

            router_update = await asyncio.to_thread(router, state)
            state.update(router_update)
            intent = state.get("intent", "unknown")
            sub_action = state.get("sub_action", "general")

            if intent == "hotel":
                yield sse({
                    "type": "activity",
                    "text": "Booking your hotel..." if sub_action == "book" else "Searching hotel suggestions...",
                })
                node_update = await hotel_node(state)
                state.update(node_update)
                state.update(generate_response(state))
                final_text = state.get("response_text", "")
                hotels = state.get("hotel_results") or None
                for chunk in _chunk_text(final_text):
                    yield sse({"type": "token", "text": chunk})
                    await asyncio.sleep(0.02)

            elif intent == "flight":
                yield sse({
                    "type": "activity",
                    "text": "Booking your flight..." if sub_action == "book" else "Searching flight options...",
                })
                node_update = await flight_node(state)
                state.update(node_update)
                state.update(generate_response(state))
                final_text = state.get("response_text", "")
                flights = state.get("flight_results") or None
                for chunk in _chunk_text(final_text):
                    yield sse({"type": "token", "text": chunk})
                    await asyncio.sleep(0.02)

            else:
                user_message = state["messages"][-1]
                history_messages = state["messages"][:-1]
                system_prompt = get_system_prompt_for_unknown_node("\n".join(history_messages))

                if _wants_coverage_list(user_message):
                    yield sse({"type": "activity", "text": "Checking what's available..."})
                    coverage_context = await _get_real_coverage_context()
                    system_prompt += coverage_context
                else:
                    yield sse({"type": "activity", "text": "Thinking..."})

                invocation_messages = [SystemMessage(content=system_prompt)]
                for i in range(0, len(history_messages), 2):
                    invocation_messages.append(HumanMessage(content=history_messages[i]))
                    if i + 1 < len(history_messages):
                        invocation_messages.append(AIMessage(content=history_messages[i + 1]))
                invocation_messages.append(HumanMessage(content=user_message))

                try:
                    async for chunk in llm.astream(invocation_messages):
                        token = getattr(chunk, "content", "") or ""
                        if token:
                            final_text += token
                            yield sse({"type": "token", "text": token})
                except Exception as e:
                    final_text = f"I couldn't understand your request clearly. Error: {e}"
                    yield sse({"type": "token", "text": final_text})

            if hotels:
                yield sse({"type": "data", "hotels": hotels})
            if flights:
                yield sse({"type": "data", "flights": flights})

            conversation_history_messages.append((request.message, final_text))
            yield sse({"type": "done"})

        except Exception as e:
            yield sse({"type": "error", "text": f"Something went wrong: {e}"})
            yield sse({"type": "done"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)