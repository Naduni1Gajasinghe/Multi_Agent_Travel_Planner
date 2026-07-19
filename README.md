# TripWeaver — MCP-Based Multi-Agent Travel Planner

TripWeaver is a conversational multi-agent travel planning assistant. A traveller describes what they need in natural language, and a graph of specialised agents — General QA, Hotel, and Flight — interprets the intent, reaches live external services through **MCP (Model Context Protocol)** servers, and returns a coherent, formatted response.

**Live demo:** https://tripweaver-frontend-w2hd.onrender.com

**Cold start notice:** This app runs on Render's free tier. If services have been idle for 15+ minutes, the *first* message may take 30–90 seconds to respond while the backend and MCP servers wake up. Subsequent messages respond in a few seconds. This is expected behaviour, not a bug.

---

## 1. Architecture

```
                     User (Gradio Chat UI)
                              │
                              ▼
                     FastAPI Backend (main.py)
                              │
                              ▼
              LangGraph Intent Router (agents/graph.py)
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
            Hotel Agent  General QA   Flight Agent
                 │                         │
                 ▼                         ▼
         Hotel MCP Server          Flight MCP Server
        (MCP/hotel_service.py)   (MCP/flight_service.py)
                 │                         │
                 └───────────┬─────────────┘
                              ▼
                   External Travel Data API (Convex)
```

Agents never call external services directly — every hotel/flight fact comes from an MCP tool call. This means a new service (e.g. activities, weather) can be added purely as a new MCP server without touching agent logic.

### Tech stack

| Component | Technology |
|---|---|
| Backend / API | Python, FastAPI |
| Agent orchestration | LangGraph (`StateGraph`) |
| LLM / tool calling | LangChain, OpenAI (`gpt-4o-mini`) |
| External service bridge | MCP (Model Context Protocol) via `langchain-mcp-adapters` |
| Frontend | Gradio |
| Deployment | Render (4 independent web services) |

---

## 2. Project structure

```
MultiAgent_travel_Planner/
├── agents/
│   ├── entity.py        # Shared LangGraph state schema (GraphState)
│   ├── graph.py          # StateGraph definition and routing edges
│   ├── llm.py             # LLM initialisation (ChatOpenAI)
│   ├── mcp_tools.py       # MCP client — connects agents to MCP servers
│   ├── nodes.py           # Node functions: router, hotel_node, flight_node, unknown_node, generate_response
│   ├── prompts.py         # System prompts for extraction and fallback
│   └── tools.py           # (legacy, unused — superseded by mcp_tools.py)
├── MCP/
│   ├── hotel_service.py   # MCP server exposing hotel list/search/book tools
│   ├── flight_service.py  # MCP server exposing flight list/search/book tools
│   ├── client.py          # Standalone CLI MCP test client (dev use only)
│   └── requirments.txt    # Dependencies for the MCP servers
├── entity.py              # FastAPI request/response models (ChatRequest, ChatResponse)
├── main.py                # FastAPI app — /chat endpoint, invokes the LangGraph
├── frontend.py             # Gradio chat interface
├── requirments.txt         # Dependencies for backend + frontend
└── .env                    # Local environment variables (never committed)
```

---

## 3. Environment variables

| Variable | Used by | Description |
|---|---|---|
| `OPENAI_API_KEY` | backend | OpenAI API key for the LLM |
| `HOTEL_MCP_URL` | backend | Full URL to the deployed hotel MCP server, ending in `/mcp` |
| `FLIGHT_MCP_URL` | backend | Full URL to the deployed flight MCP server, ending in `/mcp` |
| `TRAVEL_PLANNER_API_URL` | frontend | Full URL to the deployed backend's `/chat` endpoint |
| `PORT` | all services | Set automatically by Render; each service binds to it |

None of these are hardcoded anywhere in the source — they are read via `os.environ` at runtime, with `localhost` fallbacks for local development.

---

## 4. Running locally

We'll need **3 terminals**, each with the matching virtual environment activated.

### 4.1 Set up environments

```bash
# Root project (backend + frontend)
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirments.txt

# MCP servers (separate environment)
cd MCP
python -m venv env
env\Scripts\activate           # Windows
pip install -r requirments.txt
cd ..
```

### 4.2 Add local environment variables

Create a `.env` file in the project root:
```
OPENAI_API_KEY=your-key-here
```

### 4.3 Start all services, in order

**Terminal 1 — Hotel MCP server:**
```bash
cd MCP
env\Scripts\activate
python hotel_service.py
```

**Terminal 2 — Flight MCP server:**
```bash
cd MCP
env\Scripts\activate
python flight_service.py
```

**Terminal 3 — Backend:**
```bash
venv\Scripts\activate
python main.py
```

**Terminal 4 — Frontend:**
```bash
venv\Scripts\activate
python frontend.py
```

The Gradio UI will be available at `http://127.0.0.1:7860` (or whatever port Gradio reports), talking to the backend at `http://127.0.0.1:8000`.

---

## 5. MCP server setup guide

Each MCP server is a standalone `FastMCP` process exposing a small set of tools over HTTP (`streamable_http` transport).

### Hotel server (`MCP/hotel_service.py`)
Exposes:
- `get_all_hotels()` — full hotel list
- `search_hotels(city, checkIn?, checkOut?)` — filtered search
- `book_hotel(hotel_id, guest_name, guest_email, check_in_date, check_out_date, room_type)` — booking

### Flight server (`MCP/flight_service.py`)
Exposes:
- `get_all_flights()` — full flight list
- `search_flights(origin, destination, date?)` — filtered search
- `book_flight(flight_id, passenger_name, passenger_email)` — booking

Both servers:
- Bind to `0.0.0.0` and read `PORT` from the environment (required for cloud deployment)
- Wrap every outbound HTTP call in a try/except, returning a structured `{"error": True, "message": ...}` dict instead of crashing, so a failing upstream API degrades gracefully instead of taking down the server

### Connecting agents to MCP servers

`agents/mcp_tools.py` uses `langchain_mcp_adapters.client.MultiServerMCPClient` to connect to both servers by URL and expose their tools as native LangChain tools:

```python
MCP_SERVERS = {
    "hotel-service": {"url": os.environ.get("HOTEL_MCP_URL", "http://localhost:8001/mcp"), "transport": "streamable_http"},
    "flight-service": {"url": os.environ.get("FLIGHT_MCP_URL", "http://localhost:8002/mcp"), "transport": "streamable_http"},
}
```

`agents/nodes.py` calls `get_mcp_tools()` and invokes tools by name (`get_all_hotels`, `search_hotels`, `book_hotel`, etc.) — the agent code never talks to the external Convex API directly.

---

## 6. Deployment (Render)

The app is deployed as **4 independent Render web services**, all from the same GitHub repo.

| Service | Root Directory | Start Command | Env Vars |
|---|---|---|---|
| Hotel MCP server | `MCP` | `python hotel_service.py` | — |
| Flight MCP server | `MCP` | `python flight_service.py` | — |
| Backend | *(repo root)* | `python main.py` | `OPENAI_API_KEY`, `HOTEL_MCP_URL`, `FLIGHT_MCP_URL` |
| Frontend | *(repo root)* | `python frontend.py` | `TRAVEL_PLANNER_API_URL` |

**Build command for all four:** `pip install -r requirments.txt`

### Deployment order matters
1. Deploy the two MCP servers first and copy their live URLs.
2. Deploy the backend, setting `HOTEL_MCP_URL`/`FLIGHT_MCP_URL` to those URLs **with `/mcp` appended**.
3. Deploy the frontend, setting `TRAVEL_PLANNER_API_URL` to the backend's URL **with `/chat` appended**.

### Common pitfalls encountered during deployment
- **Wrong bind address:** `FastMCP` defaults to `127.0.0.1`, which Render cannot detect as an open port. Both MCP servers explicitly bind to `host="0.0.0.0"`.
- **Missing dependency:** `langchain-mcp-adapters` must be listed in the root `requirments.txt` (used by the backend), not just the `MCP/requirments.txt`.
- **Incomplete URLs:** environment variables must include the scheme (`https://`) and correct path (`/mcp`, `/chat`) — a bare domain will raise `ValueError: unknown url type`.
- **Short timeouts:** the frontend's HTTP timeout was increased to 90 seconds to tolerate cold-start chains across multiple free-tier services.

---

## 7. User guide

Open the live app and type a natural-language request. No need to specify which agent to use — the router figures out intent automatically.

**Examples:**
- `show me all hotels`
- `show me hotels in Bangkok`
- `hotels in Mumbai from 2026-08-01 to 2026-08-05`
- `find flights from CMB to BKK`
- `show me all flights`
- `book hotel <hotel_id> for John Doe, john@example.com, check in 2026-08-01, check out 2026-08-05, double room`
- `book flight <flight_id> for Jane Smith, jane@example.com`

If required details are missing (e.g. a booking without an email), the agent will ask a follow-up question instead of guessing.

If a hotel or flight service is temporarily unavailable, the app returns a clear message (e.g. *"Hotel service is currently unavailable..."*) rather than crashing — the rest of the conversation remains usable.

---

## 8. Known limitations / stretch goals not implemented

- No streaming token-by-token responses yet (frontend currently waits for the full reply)
- No visible "Searching hotels…" / "Booking…" activity indicators in the UI
- No conversation memory across turns beyond the last few exchanged messages
- No Docker/CI setup
- Frontend styling is functional but not custom-themed

---

## 9. Credits

Built as part of an AI Engineering program enhancement sprint, extending a baseline linear multi-agent workflow into an MCP-integrated, intent-routed, deployed application.
