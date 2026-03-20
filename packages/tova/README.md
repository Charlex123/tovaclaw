# Tova

Open-source AI agent framework for healthcare order automation. Built with [LangGraph](https://github.com/langchain-ai/langgraph) and designed to work with **any** backend, database, and LLM provider.

Tova is a conversational AI agent that helps patients:
- Search for and order medications, medical devices, and lab tests
- Book appointments with doctors and nurses
- Manage orders and track delivery
- Handle recurring prescriptions

## How It Works

Tova uses a **provider pattern** — you implement a few interfaces to connect the AI agent to your own backend and database:

```
Your App → Tova Agent → Your Backend (via providers)
                ↓
           Your Database (via providers)
```

### Providers You Implement

| Provider | Purpose | Required? |
|----------|---------|-----------|
| `BaseBackend` | Write operations — create orders, book appointments, process payments | Yes |
| `BaseStore` | Read operations — user profiles, order history, conversations | Yes |
| `BaseAuth` | Token verification — verify user identity | Yes |
| `BaseNotifier` | Push notifications — notify users of events | No |

## Quick Start

### 1. Install

```bash
pip install tova

# With your preferred LLM provider
pip install "tova[anthropic]"   # Claude
pip install "tova[openai]"      # GPT
pip install "tova[google]"      # Gemini
```

### 2. Implement Providers

```python
from tova_core.providers.backend import BaseBackend
from tova_core.providers.store import BaseStore
from tova_core.providers.auth import BaseAuth

class MyBackend(BaseBackend):
    async def search_products(self, query, latitude=0, longitude=0, **kwargs):
        # Search your product catalog
        return await my_db.search_products(query)

    async def create_order(self, data):
        # Create an order in your system
        return await my_api.create_order(data)

    async def execute_order(self, order_id):
        return await my_api.execute_order(order_id)

    async def cancel_order(self, order_id, reason=""):
        return await my_api.cancel_order(order_id, reason)

    async def check_balance(self, user_id):
        return {"balance": 100.00, "currency": "USD"}

    async def process_payment(self, data):
        return await my_payment.charge(data)

class MyStore(BaseStore):
    async def get_user(self, user_id):
        return await my_db.get_user(user_id)

    async def get_balance(self, user_id):
        return await my_db.get_wallet(user_id)

    async def get_orders(self, user_id, **kwargs):
        return await my_db.list_orders(user_id)

    async def get_order(self, order_id):
        return await my_db.get_order(order_id)

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
```

### 3. Create and Run

```python
from tova_core.app import create_app

app = create_app(
    backend_factory=lambda token: MyBackend(auth_token=token),
    store=MyStore(),
    auth=MyAuth(),
)

# Run with: uvicorn main:app --port 8000
```

### 4. Chat

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "I need paracetamol", "latitude": 6.45, "longitude": 3.42}'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agent/chat` | POST | Conversational order management |
| `/agent/execute` | POST | Execute a scheduled order |
| `/agent/conversations` | GET | List user's conversations |
| `/agent/conversation/{id}` | GET | Get conversation history |
| `/health` | GET | Health check |

## LLM Providers

Tova supports multiple LLM providers via environment variables:

```bash
# Claude (default)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
AGENT_MODEL=claude-sonnet-4-6

# GPT
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
AGENT_MODEL=gpt-4o

# Gemini
LLM_PROVIDER=google
GOOGLE_API_KEY=...
AGENT_MODEL=gemini-2.0-flash

# Local (Ollama, vLLM, LM Studio)
LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
AGENT_MODEL=llama3.3
```

## Custom System Prompt

Override the default prompt to customize Tova's behavior for your platform:

```python
app = create_app(
    backend_factory=lambda token: MyBackend(token),
    store=MyStore(),
    auth=MyAuth(),
    system_prompt="""You are a health assistant for MyHealthApp.
    Currency is USD. ...your custom instructions...""",
)
```

## Examples

- **[Minimal](examples/minimal/)** — In-memory providers for quick testing
- **[Nostra Health](examples/nostra/)** — Production implementation with Firestore + Node.js backend

## Architecture

```
tova_core/
├── providers/          # Abstract interfaces you implement
│   ├── backend.py      # BaseBackend — write operations
│   ├── store.py        # BaseStore — read operations
│   ├── auth.py         # BaseAuth — token verification
│   └── notifier.py     # BaseNotifier — notifications (optional)
├── agents/
│   ├── order_agent.py  # Patient-facing conversational agent
│   └── execution_agent.py  # Scheduler-facing execution agent
├── tools/
│   ├── registry.py     # Builds LangGraph tools from providers
│   └── helpers.py      # Proximity, date, and utility helpers
├── prompts/
│   └── default.py      # Default system prompts (customizable)
├── models/
│   └── schemas.py      # Pydantic request/response models
├── app.py              # FastAPI application factory
├── config.py           # Settings (env vars)
└── llm.py              # LLM provider factory
```

## License

MIT
