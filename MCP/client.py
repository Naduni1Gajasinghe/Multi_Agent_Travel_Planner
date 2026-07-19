import os
import asyncio
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

load_dotenv(override=True)

MCP_SERVERS = {
    "hotel-service": {
        "url": "http://localhost:8001/mcp",
        "transport": "streamable_http",
    },
    "flight-service": {
        "url": "http://localhost:8002/mcp",
        "transport": "streamable_http",
    }
}

async def chat():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("Error: OPENAI_API_KEY is not set.")
        return

    os.environ["OPENAI_API_KEY"] = api_key

    client = MultiServerMCPClient(MCP_SERVERS)

    tools = await client.get_tools()

    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent = create_agent(model, tools)

    try:
        while True:
            user_text = input("You: ").strip()

            if user_text.lower() in ["exit", "quit", "bye"]:
                print("AI: Goodbye!")
                break

            if not user_text:
                continue

            result = await agent.ainvoke({
                "messages": [
                    {
                        "role": "user",
                        "content": user_text
                    }
                ]
            })

            assistant_text = result["messages"][-1].content
            print(f"AI: {assistant_text}\n")

    except KeyboardInterrupt:
        print("\nAI: Chat stopped.")
    except EOFError:
        print("\nAI: Chat ended.")


if __name__ == "__main__":
    asyncio.run(chat())