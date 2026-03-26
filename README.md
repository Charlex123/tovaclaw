# Tova

Open-source AI agent framework for building intelligent assistants. Built with [LangGraph](https://github.com/langchain-ai/langgraph) and designed to work with **any** backend, database, and LLM provider.

Tova is a conversational AI platform that can handle:
- **Healthcare** — medication search, appointment booking, order management
- **Travel** — flights, trains, buses, car hire with live price search and booking links
- **Email** — IMAP/SMTP email management with AI categorization and drafting
- **Productivity** — todos, notes, summarization, event planning
- **Enterprise** — CCTV monitoring, vehicle/fleet tracking, emergency management
- **Custom AI Training** — upload any dataset (JSON, CSV, PDF, TXT) and query it via RAG

Every feature is modular. Enable only what you need — zero overhead for unused modules.

## How It Works

Tova uses a **provider pattern** — implement a few interfaces to connect the AI agent to your own systems:

```
Your App → Tova Agent → Your Backend (via providers)
                ↓
           Your Database (via providers)
```

### Core Providers

| Provider | Purpose | Required? |
|----------|---------|-----------|
| `BaseBackend` | Write operations — create orders, book appointments | Yes |
| `BaseStore` | Read operations — user profiles, order history, conversations | Yes |
| `BaseAuth` | Token verification — verify user identity | Yes |
| `BaseNotifier` | Push notifications — notify users of events | No |

### Feature Providers (Optional)

| Provider | Purpose |
|----------|---------|
| `BaseTravelProvider` | Flight, train, bus, car hire search |
| `BaseEmailProvider` | Email management (IMAP/SMTP) |
| `BaseCalendarProvider` | Calendar and event management |
| `BaseTelephony` | Phone calls and SMS (Twilio) |
| `BaseVideoStream` | CCTV / video monitoring |
| `BaseGeolocationProvider` | Vehicle/fleet GPS tracking |
| `BaseVectorStore` | Vector embeddings for RAG |
| `BaseFileStore` | File upload and storage |

Features auto-enable when their provider is supplied to `create_app()`.

## Quick Start

### Option 1: Standalone Mode (No Code Required)

Run Tova instantly with just environment variables:

```bash
pip install tova

# Run with Claude
ANTHROPIC_API_KEY=sk-ant-... python -m tova_core.standalone

# Run with GPT
LLM_PROVIDER=openai OPENAI_API_KEY=sk-... python -m tova_core.standalone

# Run with Gemini
LLM_PROVIDER=google GOOGLE_API_KEY=... python -m tova_core.standalone

# Run with local LLM (Ollama, vLLM, LM Studio)
LLM_PROVIDER=local LOCAL_LLM_BASE_URL=http://localhost:11434/v1 python -m tova_core.standalone
```

Standalone mode includes:
- SQLite storage (no database setup needed)
- Session-based auth (no signup required)
- Travel search (flights, trains, buses)
- Email management (connect via `/auth/email/connect`)
- All productivity tools (todos, notes, events)

### Option 2: Custom Integration

```python
from tova_core.app import create_app
from tova_core.providers.backend import BaseBackend
from tova_core.providers.store import BaseStore
from tova_core.providers.auth import BaseAuth

class MyBackend(BaseBackend):
    async def search_products(self, query, latitude=0, longitude=0, **kwargs):
        return await my_db.search_products(query)

    async def create_order(self, data):
        return await my_api.create_order(data)

    async def execute_order(self, order_id):
        return await my_api.execute_order(order_id)

    async def cancel_order(self, order_id, reason=""):
        return await my_api.cancel_order(order_id, reason)

class MyStore(BaseStore):
    async def get_user(self, user_id):
        return await my_db.get_user(user_id)

    async def save_conversation(self, conversation_id, user_id, messages, title=""):
        await my_db.upsert_conversation(conversation_id, user_id, messages, title)

    async def load_conversation(self, conversation_id):
        return await my_db.get_conversation_messages(conversation_id)

    async def list_conversations(self, user_id, limit=20):
        return await my_db.list_user_conversations(user_id, limit)

    async def generate_id(self):
        return str(uuid.uuid4())

class MyAuth(BaseAuth):
    async def verify_token(self, token):
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]

app = create_app(
    backend_factory=lambda token: MyBackend(auth_token=token),
    store=MyStore(),
    auth=MyAuth(),
)

# Run with: uvicorn main:app --port 8000
```

### Adding Feature Providers

```python
from tova_core.providers.builtin.travel_search import FlightSearchProvider

app = create_app(
    backend_factory=lambda token: MyBackend(token),
    store=MyStore(),
    auth=MyAuth(),
    travel_provider=FlightSearchProvider(),
)
```

## Authentication Modes

Standalone mode supports four auth modes via `TOVA_AUTH`:

| Mode | Use Case | Config |
|------|----------|--------|
| `session` (default) | Web apps — cookie-based, no signup required | Auto-configured |
| `none` | Local/dev — single fixed user | `TOVA_USER_ID=local_user` |
| `apikey` | API access — key:user pairs | `TOVA_API_KEYS=key1:alice,key2:bob` |
| `jwt` | Production — Auth0, Supabase, etc. | `TOVA_JWT_SECRET=...` |

## Custom Agents

Define specialized AI agents with their own tools, prompts, and behaviors:

```python
from tova_core.models.agent import AgentConfig

agent = AgentConfig(
    name="travel-assistant",
    system_prompt="You help users find and compare travel options...",
    tools=["search_flights", "search_trains", "compare_transport"],
)
```

## API Endpoints

### Core

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agent/chat` | POST | Conversational AI agent |
| `/agent/execute` | POST | Execute a scheduled action |
| `/agent/conversations` | GET | List conversations |
| `/agent/conversation/{id}` | GET | Get conversation history |
| `/health` | GET | Health check |

### Auth & Email

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/email/connect` | POST | Connect email (IMAP credentials) |
| `/auth/email/status` | GET | Check email connection status |
| `/auth/email/disconnect` | POST | Disconnect email |
| `/auth/email/providers` | GET | List supported email providers |

## Agent Tools

Tova comes with 70+ tools that agents can use:

| Category | Tools |
|----------|-------|
| **Healthcare** | Search products, create/execute/cancel orders, book appointments, check balance |
| **Travel** | Search flights/trains/buses/car hire, compare transport, find nearest airports/stations, save travel plans |
| **Email** | List/read/categorize/draft/send emails, summarize threads |
| **Todos** | Create/list/update/complete todos, suggest priorities |
| **Notes** | Create notes, summarize text/URLs/documents, extract key points |
| **Events** | Create/list/update events, suggest times, send reminders |
| **Emergency** | Report/list/escalate emergencies, trigger calls, send alerts |
| **CCTV** | List cameras, get snapshots, analyze frames, detect anomalies |
| **Vehicles** | Track positions, fleet overview, geofence violations, route calculation |
| **Datasets** | Ingest documents, query datasets (RAG), list datasets |
| **Phone** | Make calls, check call status, send SMS |

## LLM Providers

```bash
# Claude (default)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# GPT
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Gemini
LLM_PROVIDER=google
GOOGLE_API_KEY=...

# Local (Ollama, vLLM, LM Studio)
LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
AGENT_MODEL=llama3.3
```

## Architecture

```
tova_core/
├── providers/              # Abstract interfaces
│   ├── backend.py          # BaseBackend — write operations
│   ├── store.py            # BaseStore — read operations
│   ├── auth.py             # BaseAuth — authentication
│   ├── notifier.py         # BaseNotifier — notifications
│   ├── travel.py           # BaseTravelProvider — transport search
│   ├── email.py            # BaseEmailProvider — email management
│   ├── calendar.py         # BaseCalendarProvider — events
│   ├── telephony.py        # BaseTelephony — calls & SMS
│   ├── video_stream.py     # BaseVideoStream — CCTV
│   ├── geolocation.py      # BaseGeolocationProvider — GPS tracking
│   ├── vector_store.py     # BaseVectorStore — embeddings
│   ├── file_store.py       # BaseFileStore — file storage
│   └── builtin/            # Built-in implementations
│       ├── store.py        # SQLiteStore
│       ├── auth.py         # Session, JWT, APIKey, NoAuth
│       ├── travel_search.py # SerpAPI + Amadeus flight search
│       ├── imap_email.py   # IMAP/SMTP email (encrypted credentials)
│       └── ...
├── agents/
│   ├── order_agent.py      # Patient-facing conversational agent
│   ├── execution_agent.py  # Scheduler-facing execution agent
│   └── runtime.py          # Agent runtime with Brain Box injection
├── tools/                  # 70+ LangGraph tools
│   ├── registry.py         # Tool registry — builds tools from providers
│   ├── travel_tools.py     # Flights, trains, buses, car hire
│   ├── email_tools.py      # Email management
│   ├── todo_tools.py       # Task management
│   ├── notes_tools.py      # Notes & summarization
│   ├── event_tools.py      # Calendar events
│   ├── emergency_tools.py  # Emergency tracking
│   ├── cctv_tools.py       # Video monitoring
│   ├── vehicle_tools.py    # Fleet tracking
│   ├── dataset_tools.py    # RAG dataset queries
│   └── ...
├── rag/                    # RAG pipeline
│   ├── ingest.py           # Document ingestion (PDF, CSV, JSON, TXT)
│   ├── chunker.py          # Text splitting
│   ├── embedder.py         # Multi-provider embeddings
│   └── retriever.py        # Vector similarity search
├── memory/                 # Brain Box — per-feature per-user memory
├── realtime/               # Background workers
│   ├── emergency_monitor.py
│   ├── video_processor.py
│   └── gps_tracker.py
├── models/                 # Pydantic schemas
├── prompts/                # System prompts (customizable)
├── scheduler/              # Task scheduling
├── crypto.py               # Fernet encryption for credentials
├── standalone.py           # Zero-code launcher
├── app.py                  # FastAPI application factory
├── config.py               # Settings (env vars)
└── llm.py                  # LLM provider factory
```

## Examples

- **[Minimal](examples/minimal/)** — In-memory providers for quick testing
- **[Nostra Health](examples/nostra/)** — Production implementation with Firestore + Node.js backend

## License

MIT
