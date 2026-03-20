# Tova

Open-source multi-agent AI framework built with [LangGraph](https://github.com/langchain-ai/langgraph). Pluggable providers, multi-LLM support, and a flexible tool system let you build conversational AI for **any domain** — e-commerce, customer support, healthcare, fintech, or anything else.

## Features

- **Custom agents** — Define agents with their own tools, prompts, personality, and workflows via `AgentConfig`
- **Pluggable providers** — Implement a few interfaces to connect any backend, database, and auth system
- **Multi-LLM support** — Claude, GPT, Gemini, or local models (Ollama, vLLM, LM Studio)
- **Tool registry** — Register your own tools and attach them to any agent
- **Agent memory** — Persistent context across conversations
- **Scheduler** — Cron-based and event-driven agent execution
- **Built-in order & appointment workflows** — Ready-to-use agents for common patterns

## How It Works

Tova uses a **provider pattern** — you implement a few interfaces to connect agents to your own systems:

```
Your App → Tova Agents → Your Backend (via providers)
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
        return await my_db.search_products(query)

    async def create_order(self, data):
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
  -d '{"message": "Find me a laptop under $1000"}'
```

## Custom Agents

Define agents with their own tools, personality, and triggers:

```python
from tova_core.models.agent import AgentConfig, AgentTrigger, TriggerType, ToolConfig
from tova_core.agents.runtime import AgentRuntime
from tova_core.tools.base import ToolRegistry

# Register your tools
registry = ToolRegistry()
registry.register(my_search_tool)
registry.register(my_order_tool)

# Define an agent
agent = AgentConfig(
    name="SupportAgent",
    description="Handles customer support inquiries",
    system_prompt="You are a customer support agent...",
    tools=[ToolConfig(tool_name="search_products"), ToolConfig(tool_name="lookup_order")],
    trigger=AgentTrigger(type=TriggerType.MANUAL),
)

# Run it
runtime = AgentRuntime(tool_registry=registry, store=my_store)
result = await runtime.run(agent_config=agent, user_message="Where is my order?", user_id="user_123")
```

## Scheduler

Run agents on cron schedules or in response to events:

```python
from tova_core.scheduler.engine import AgentScheduler

scheduler = AgentScheduler(runtime=runtime)
scheduler.register(weekly_digest_agent)
scheduler.register(ticket_triage_agent)

await scheduler.start()

# Or trigger manually
await scheduler.trigger_event("ticket_created", {"ticket_id": "T-1234"})
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agent/chat` | POST | Conversational agent endpoint |
| `/agent/execute` | POST | Execute a scheduled order |
| `/agent/conversations` | GET | List user's conversations |
| `/agent/conversation/{id}` | GET | Get conversation history |
| `/health` | GET | Health check |

## LLM Providers

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

## Examples

- **[Minimal](examples/minimal/)** — In-memory e-commerce example for quick testing
- **[Healthcare](examples/healthcare/)** — Healthcare order automation with Firestore + Node.js backend

## Architecture

```
tova_core/
├── providers/          # Abstract interfaces you implement
│   ├── backend.py      # BaseBackend — write operations
│   ├── store.py        # BaseStore — read operations
│   ├── auth.py         # BaseAuth — token verification
│   └── notifier.py     # BaseNotifier — notifications (optional)
├── agents/
│   ├── runtime.py      # AgentRuntime — runs any agent from AgentConfig
│   ├── order_agent.py  # Built-in order management agent
│   └── execution_agent.py  # Built-in order fulfillment agent
├── models/
│   ├── agent.py        # AgentConfig — full agent definition
│   └── schemas.py      # Pydantic request/response models
├── tools/
│   ├── base.py         # ToolRegistry + ToolDefinition
│   ├── registry.py     # Built-in order/service tools
│   └── helpers.py      # Proximity, date, and utility helpers
├── memory/
│   └── store.py        # AgentMemory — persistent context
├── scheduler/
│   └── engine.py       # AgentScheduler — cron + event triggers
├── prompts/
│   └── default.py      # Default system prompts (customizable)
├── app.py              # FastAPI application factory
├── config.py           # Settings (env vars)
└── llm.py              # LLM provider factory
```

## License

MIT
