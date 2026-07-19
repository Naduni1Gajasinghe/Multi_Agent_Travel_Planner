from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from entity import ChatRequest, ChatResponse
from agents.graph import graph

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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):

    recent_pairs = conversation_history_messages[-3:]
    flattened_messages = []
    for user_msg, assistant_msg in recent_pairs:
        flattened_messages.append(user_msg)
        flattened_messages.append(assistant_msg)
    flattened_messages.append(request.message)

    initial_state = {
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)