import { useState } from "react";
import { motion } from "framer-motion";
import CodeBlock from "./CodeBlock";

interface Example {
  id: string;
  title: string;
  language: string;
  filename: string;
  code: string;
}

const examples: Example[] = [
  {
    id: "backend",
    title: "Custom Backend",
    language: "python",
    filename: "my_backend.py",
    code: `from tova_core.providers.backend import BaseBackend

class EcommerceBackend(BaseBackend):
    def __init__(self, auth_token: str):
        self.token = auth_token
        self.client = ShopClient(token=auth_token)

    async def get_user(self) -> dict:
        return await self.client.get_user_profile()

    async def search_products(self, query: str) -> list:
        results = await self.client.product_search(query)
        return [
            {"id": r.id, "name": r.name, "price": r.price}
            for r in results
        ]

    async def create_order(self, order: dict) -> dict:
        validated = await self.validate_inventory(order)
        return await self.client.submit_order(validated)`,
  },
  {
    id: "tools",
    title: "Custom Tools",
    language: "python",
    filename: "my_tools.py",
    code: `from tova_core.tools.base import ToolDefinition, ToolRegistry

registry = ToolRegistry()

@registry.register
class LookupOrder(ToolDefinition):
    name = "lookup_order"
    description = "Look up order status by order ID"

    async def execute(self, order_id: str) -> dict:
        order = await self.backend.get_order(
            order_id=order_id,
        )
        return {
            "status": order.status,
            "shipped": order.is_shipped,
            "estimated_delivery": order.eta,
        }`,
  },
  {
    id: "agent",
    title: "Custom Agent",
    language: "python",
    filename: "support_agent.py",
    code: `from tova_core.agents.runtime import AgentRuntime
from tova_core.models.agent import AgentConfig, AgentTrigger

config = AgentConfig(
    name="SupportAgent",
    instructions="""You are a customer support agent.
    Help users track orders, process returns,
    and escalate issues to a human when needed.""",
    tools=["lookup_order", "search_products",
           "initiate_return", "escalate_ticket"],
    model="claude-sonnet-4-20250514",
    triggers=[AgentTrigger(type="event", value="ticket_created")],
    memory={"enabled": True, "namespaces": ["support"]},
)

agent = AgentRuntime(config=config, backend=my_backend)
response = await agent.chat("Where is my order #1234?")`,
  },
  {
    id: "standalone",
    title: "Standalone",
    language: "python",
    filename: "run.py",
    code: `from tova_core.standalone import create_standalone_app

# Zero-config: SQLite + session auth + all built-in tools
app = create_standalone_app(
    llm_provider="anthropic",
    # Optional feature providers
    enable_travel=True,      # flights, trains, buses
    enable_email=True,       # IMAP/SMTP management
    enable_telephony=True,   # Twilio calls & SMS
    enable_video=True,       # CCTV / video analysis
)

# Includes: 70+ tools, Brain Box memory, RAG,
# real-time workers, scheduler, and REST API
# Run with: uvicorn run:app --port 8000`,
  },
  {
    id: "email",
    title: "Email & Travel",
    language: "python",
    filename: "providers.py",
    code: `from tova_core.providers.email import BaseEmailProvider
from tova_core.providers.travel import BaseTravelProvider

class MyEmail(BaseEmailProvider):
    async def list_emails(self, folder, limit):
        return await self.imap.fetch(folder, limit)

    async def send_email(self, to, subject, body):
        return await self.smtp.send(to, subject, body)

class MyTravel(BaseTravelProvider):
    async def search_flights(self, origin, dest, date):
        return await self.amadeus.search(origin, dest, date)

    async def search_trains(self, origin, dest, date):
        return await self.rail_api.search(origin, dest, date)

# Pass to create_app
app = create_app(
    email_provider=MyEmail(),
    travel_provider=MyTravel(),
    # ... other providers
)`,
  },
  {
    id: "brainbox",
    title: "Brain Box",
    language: "python",
    filename: "memory.py",
    code: `from tova_core.memory.brain_box import BrainBox

brain = BrainBox(store=my_store)

# Per-feature, per-user memory namespaces
await brain.remember(
    user_id="user_123",
    feature="email",
    key="preferred_tone",
    value="professional",
    category="preference",
    ttl=86400 * 30,  # 30 days
)

# Recall across features
context = await brain.build_context(
    user_id="user_123",
    features=["email", "todos", "calendar"],
)
# Returns all relevant memories for prompt injection

# Share between features
await brain.share_to(
    user_id="user_123",
    from_feature="email",
    to_feature="calendar",
    key="preferred_tone",
)`,
  },
  {
    id: "rag",
    title: "RAG / Datasets",
    language: "python",
    filename: "rag_setup.py",
    code: `from tova_core.rag.ingest import DocumentIngestor
from tova_core.rag.retriever import VectorRetriever
from tova_core.providers.builtin.vector_store import ChromaStore

# Ingest documents into vector store
ingestor = DocumentIngestor(
    vector_store=ChromaStore(collection="docs"),
    embeddings_provider="openai",
    chunk_size=512,
    chunk_overlap=50,
)

await ingestor.ingest("policies.pdf")
await ingestor.ingest("products.csv")

# Query via similarity search
retriever = VectorRetriever(store=ChromaStore("docs"))
results = await retriever.query(
    "What is the return policy for electronics?",
    top_k=5,
)
# Results injected into agent context automatically`,
  },
  {
    id: "sdk-chat",
    title: "SDK: Chat",
    language: "typescript",
    filename: "chat.ts",
    code: `import { TovaClient } from "@tovaclaw/sdk";

const client = new TovaClient({
  baseUrl: "http://localhost:8000",
  token: userJwt,
});

// Send a message and handle the response
const res = await client.chat({
  message: "Find flights from Lagos to London next Friday",
  conversation_id: "conv_abc123",
});

switch (res.action) {
  case "flight_results":
    renderFlightCards(res.data?.results);
    break;
  case "email_draft":
    showEmailPreview(res.data);
    break;
  case "confirmation_needed":
    showConfirmDialog(res.reply);
    break;
  default:
    showMessage(res.reply);
}`,
  },
];

export default function UsageExamples() {
  const [active, setActive] = useState("backend");
  const activeExample = examples.find((e) => e.id === active)!;

  return (
    <section id="examples" className="relative py-24 px-6">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Build with real examples
          </h2>
          <p className="text-neutral-400 max-w-xl mx-auto">
            From custom backends to scheduled tasks, see how TovaClaw fits your
            workflow.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          {/* Tab bar */}
          <div className="flex flex-wrap gap-1 mb-6 p-1 bg-white/[0.02] border border-white/5 rounded-xl">
            {examples.map((ex) => (
              <button
                key={ex.id}
                onClick={() => setActive(ex.id)}
                className={`px-4 py-2 text-sm rounded-lg transition-all ${
                  active === ex.id
                    ? "bg-white/10 text-white font-medium"
                    : "text-neutral-500 hover:text-neutral-300 hover:bg-white/5"
                }`}
              >
                {ex.title}
              </button>
            ))}
          </div>

          {/* Code block */}
          <CodeBlock
            code={activeExample.code}
            language={activeExample.language}
            filename={activeExample.filename}
          />
        </motion.div>
      </div>
    </section>
  );
}
