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
from tova_core.models.agent import AgentConfig

config = AgentConfig(
    name="SupportAgent",
    instructions="""You are a customer support agent.
    Help users track orders, process returns,
    answer product questions, and escalate issues
    to a human when needed.""",
    tools=["lookup_order", "search_products",
           "initiate_return", "escalate_ticket"],
    model="claude-sonnet-4-20250514",
)

agent = AgentRuntime(config=config, backend=my_backend)
response = await agent.chat("Where is my order #1234?")`,
  },
  {
    id: "scheduler",
    title: "Scheduled Tasks",
    language: "python",
    filename: "scheduler.py",
    code: `from tova_core.scheduler import AgentScheduler, Schedule

scheduler = AgentScheduler(store=my_store)

# Send weekly digest to users
scheduler.register(
    Schedule(
        name="weekly_digest",
        cron="0 9 * * 1",  # Every Monday at 9 AM
        agent_config="DigestAgent",
        action="generate_and_send_digest",
    )
)

# Event-driven: react to new support tickets
scheduler.on_event(
    event="ticket_created",
    agent_config="SupportAgent",
    action="auto_triage_and_respond",
)

await scheduler.start()`,
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
  message: "Find me ibuprofen near me",
  conversation_id: "conv_abc123",
  latitude: 6.4541,
  longitude: 3.3947,
});

if (res.action === "product_results") {
  // Render product cards from structured data
  const products = res.data?.results;
  console.log(res.reply, products);
}

// Continue the conversation
const followUp = await client.chat({
  message: "Order the first one",
  conversation_id: res.conversation_id,
});`,
  },
  {
    id: "sdk-conversations",
    title: "SDK: Conversations",
    language: "typescript",
    filename: "conversations.ts",
    code: `import { TovaClient } from "@tovaclaw/sdk";

const client = new TovaClient({
  baseUrl: "http://localhost:8000",
  token: userJwt,
});

// List all conversations
const { conversations } = await client.listConversations();
conversations.forEach((c) => {
  console.log(c.id, c.title, c.message_count);
});

// Load a specific conversation's messages
const detail = await client.getConversation("conv_abc123");
detail.messages.forEach((msg) => {
  console.log(msg.role, msg.content);
  if (msg.action) {
    console.log("Action:", msg.action, msg.data);
  }
});`,
  },
  {
    id: "sdk-execute",
    title: "SDK: Execute",
    language: "typescript",
    filename: "execute.ts",
    code: `import { TovaClient, TovaError } from "@tovaclaw/sdk";

const client = new TovaClient({
  baseUrl: "http://localhost:8000",
  token: serviceToken,
});

// Programmatically execute an order
const result = await client.execute({
  order_id: "order_xyz789",
});

if (result.success) {
  console.log("Order fulfilled:", result.message);
  console.log("Tools used:", result.tools_used);
  if (result.alternatives_found) {
    console.log("Alternatives were suggested");
  }
}

// Health check
const health = await client.health();
console.log(health.status, health.version);`,
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
            From custom backends to scheduled tasks, see how Tova fits your
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
