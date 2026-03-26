import { useState, useCallback } from "react";
import FeatureSidebar from "./FeatureSidebar";
import ChatPanel from "./ChatPanel";
import ContextSidebar from "./ContextSidebar";
import LiveMonitors from "./LiveMonitors";
import type { Message } from "./MessageBubble";

/* ---------- Demo responses keyed by keyword ---------- */
interface DemoResponse {
  content: string;
  action?: string;
  data?: unknown;
}

const demoResponses: { keywords: string[]; response: DemoResponse }[] = [
  {
    keywords: ["flight", "fly", "flights", "london", "lagos"],
    response: {
      content:
        "I found 4 flights from Lagos (LOS) to London (LHR) for next Friday. Here are the best options:",
      action: "flight_results",
      data: {
        results: [
          { airline: "British Airways", flight_no: "BA76", departure: "LOS", arrival: "LHR", dep_time: "08:30", arr_time: "14:45", duration: "6h 15m", price: "$842", stops: 0 },
          { airline: "Virgin Atlantic", flight_no: "VS42", departure: "LOS", arrival: "LHR", dep_time: "11:15", arr_time: "17:20", duration: "6h 05m", price: "$798", stops: 0 },
          { airline: "Turkish Airlines", flight_no: "TK1234", departure: "LOS", arrival: "LHR", dep_time: "06:00", arr_time: "15:30", duration: "9h 30m", price: "$612", stops: 1 },
          { airline: "Ethiopian Airlines", flight_no: "ET507", departure: "LOS", arrival: "LHR", dep_time: "23:45", arr_time: "11:00", duration: "11h 15m", price: "$589", stops: 1 },
        ],
      },
    },
  },
  {
    keywords: ["email", "unread", "inbox", "mail"],
    response: {
      content: "Here are your latest emails:",
      action: "email_list",
      data: {
        emails: [
          { from: "team@company.com", subject: "Q1 Review Meeting Notes", date: "10:30 AM", preview: "Hi all, please find attached the notes from...", read: false },
          { from: "cto@company.com", subject: "Re: Architecture Decision", date: "9:15 AM", preview: "I agree with the microservices approach. Let's...", read: false },
          { from: "newsletter@dev.to", subject: "Weekly Digest: Top AI Articles", date: "8:00 AM", preview: "This week's trending articles about AI agents...", read: true },
          { from: "support@aws.com", subject: "Your AWS Invoice for March", date: "Yesterday", preview: "Your bill for the current billing period is...", read: true },
        ],
      },
    },
  },
  {
    keywords: ["todo", "task", "create a todo", "finish", "report"],
    response: {
      content: "I've added your task. Here's your current list:",
      action: "todo_list",
      data: {
        todos: [
          { id: "1", title: "Finish quarterly report", completed: false, priority: "high", due: "Mar 28" },
          { id: "2", title: "Review PR #421 — auth refactor", completed: false, priority: "medium", due: "Mar 27" },
          { id: "3", title: "Update API documentation", completed: false, priority: "low" },
          { id: "4", title: "Deploy staging environment", completed: true, priority: "high", due: "Mar 25" },
          { id: "5", title: "Send team weekly update", completed: true, priority: "medium", due: "Mar 24" },
        ],
      },
    },
  },
  {
    keywords: ["order", "track", "#4521", "status"],
    response: {
      content: "Here's the status of your order:",
      action: "order_status",
      data: {
        order_id: "#4521",
        status: "shipped",
        items: [
          { name: "Wireless Keyboard", quantity: 1, price: "$89.99" },
          { name: "USB-C Hub", quantity: 2, price: "$49.98" },
        ],
        total: "$139.97",
        estimated_delivery: "March 28, 2026",
      },
    },
  },
  {
    keywords: ["meeting", "schedule", "3pm", "tomorrow"],
    response: {
      content: "Done! I've scheduled the meeting for tomorrow.",
      action: "event_created",
      data: {
        title: "Team Sync Meeting",
        date: "March 27, 2026",
        time: "3:00 PM - 3:30 PM",
        location: "Google Meet",
        attendees: ["team@company.com", "cto@company.com"],
        description: "Weekly team sync to discuss progress and blockers.",
      },
    },
  },
  {
    keywords: ["laptop", "search", "product", "$1000", "under"],
    response: {
      content: "Here are 4 laptops under $1,000 that match your criteria:",
      action: "product_results",
      data: {
        results: [
          { id: "p1", name: "MacBook Air M3 (8GB)", price: "$999", category: "Laptops", in_stock: true },
          { id: "p2", name: "ThinkPad E14 Gen 5", price: "$749", category: "Laptops", in_stock: true },
          { id: "p3", name: "Dell Inspiron 16", price: "$699", category: "Laptops", in_stock: true },
          { id: "p4", name: "ASUS Vivobook 15 OLED", price: "$599", category: "Laptops", in_stock: false },
        ],
      },
    },
  },
  {
    keywords: ["emergency", "alert", "fire", "security"],
    response: {
      content: "Emergency alert has been filed and escalated.",
      action: "emergency_alert",
      data: {
        id: "EMR-2026-0047",
        type: "Security Breach",
        severity: "high",
        description: "Unauthorized access detected at main entrance. CCTV confirms unrecognized individual at 14:32.",
        location: "Building A — Main Entrance",
        reported_at: "2 minutes ago",
        status: "active",
      },
    },
  },
  {
    keywords: ["draft", "write", "compose", "reply"],
    response: {
      content: "I've drafted a reply based on the conversation context:",
      action: "email_draft",
      data: {
        to: "cto@company.com",
        subject: "Re: Architecture Decision",
        body: "Hi,\n\nThanks for the feedback on the microservices approach. I've updated the RFC with the following changes:\n\n1. Added API gateway layer as discussed\n2. Revised the event bus to use Kafka instead of RabbitMQ\n3. Included the monitoring stack (Grafana + Prometheus)\n\nLet me know if you'd like to review before the next architecture meeting.\n\nBest regards,\nCharles",
      },
    },
  },
  {
    keywords: ["note", "notes", "jot", "remember this"],
    response: {
      content: "Here are your recent notes:",
      action: "notes_list",
      data: {
        notes: [
          { id: "n1", title: "API Gateway Design Notes", preview: "Use Kong or Traefik for rate limiting, auth forwarding...", created: "Mar 25", tags: ["architecture", "backend"] },
          { id: "n2", title: "Quarterly Goals Q2", preview: "1. Ship v2 API 2. Migrate to Kubernetes 3. SOC2 cert...", created: "Mar 22", tags: ["planning"] },
          { id: "n3", title: "Meeting with investors", preview: "Key points: ARR growth 40%, expand to EU market...", created: "Mar 20", tags: ["business"] },
        ],
      },
    },
  },
  {
    keywords: ["file", "upload", "document", "download"],
    response: {
      content: "Here are your recent files:",
      action: "file_list",
      data: {
        files: [
          { name: "Q1-report-final.pdf", size: "2.4 MB", type: "pdf", uploaded: "Mar 25", shared: true },
          { name: "architecture-diagram.png", size: "890 KB", type: "image", uploaded: "Mar 23", shared: false },
          { name: "dataset-users.csv", size: "12.1 MB", type: "csv", uploaded: "Mar 20", shared: true },
          { name: "onboarding-guide.docx", size: "1.1 MB", type: "document", uploaded: "Mar 18", shared: true },
        ],
      },
    },
  },
  {
    keywords: ["camera", "cctv", "surveillance", "footage"],
    response: {
      content: "CCTV system overview — 4 cameras online:",
      action: "cctv_status",
      data: {
        cameras: [
          { id: "cam-1", name: "Main Entrance", status: "online", lastEvent: "Person detected 3m ago", fps: 30 },
          { id: "cam-2", name: "Parking Lot B", status: "online", lastEvent: "Vehicle entered 12m ago", fps: 25 },
          { id: "cam-3", name: "Server Room", status: "online", lastEvent: "No events", fps: 15 },
          { id: "cam-4", name: "Warehouse East", status: "offline", lastEvent: "Connection lost 2h ago", fps: 0 },
        ],
      },
    },
  },
  {
    keywords: ["vehicle", "fleet", "gps", "car", "truck", "driver"],
    response: {
      content: "Fleet tracking overview — 3 vehicles active:",
      action: "fleet_status",
      data: {
        vehicles: [
          { id: "v1", plate: "ABC-1234", driver: "James O.", speed: "62 km/h", status: "moving", location: "Ikeja, Lagos", battery: "78%" },
          { id: "v2", plate: "DEF-5678", driver: "Sarah K.", speed: "0 km/h", status: "parked", location: "Victoria Island", battery: "95%" },
          { id: "v3", plate: "GHI-9012", driver: "Mike T.", speed: "85 km/h", status: "speeding", location: "Lekki Expressway", battery: "42%" },
        ],
      },
    },
  },
  {
    keywords: ["call", "phone", "dial", "ring", "sms", "text message"],
    response: {
      content: "I'll place the call now. Here's the status:",
      action: "call_status",
      data: {
        call_id: "call-20260326-001",
        to: "+234 801 234 5678",
        status: "ringing",
        type: "outbound",
        started_at: "Just now",
        via: "Twilio",
      },
    },
  },
];

function findDemoResponse(message: string): DemoResponse {
  const lower = message.toLowerCase();
  for (const demo of demoResponses) {
    if (demo.keywords.some((kw) => lower.includes(kw))) {
      return demo.response;
    }
  }
  return {
    content: `I can help with that! As a TovaClaw agent, I have access to 70+ tools including email management, travel search, order tracking, todo lists, calendar events, CCTV monitoring, and more. Could you be more specific about what you'd like to do?`,
  };
}

/* ---------- Demo state ---------- */
const demoConversations = [
  { id: "conv1", title: "Flight search to London", lastMessage: "Found 4 flights...", time: "Just now" },
  { id: "conv2", title: "Order tracking #4521", lastMessage: "Your order has shipped", time: "2h ago" },
  { id: "conv3", title: "Weekly report todos", lastMessage: "Added 3 tasks", time: "Yesterday" },
];

const demoMemories = [
  { key: "preferred_tone", value: "Professional and concise", feature: "email" },
  { key: "home_airport", value: "LOS (Lagos)", feature: "travel" },
  { key: "timezone", value: "Africa/Lagos (WAT)", feature: "general" },
  { key: "priority_contacts", value: "team@company.com, cto@company.com", feature: "email" },
];

let messageCounter = 0;

export default function ChatApp() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [activeFeature, setActiveFeature] = useState("chat");
  const [activeConversation, setActiveConversation] = useState<string | null>(null);

  const handleSend = useCallback((text: string) => {
    const userMsg: Message = {
      id: `msg-${++messageCounter}`,
      role: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsTyping(true);

    // Simulate agent response
    const delay = 800 + Math.random() * 1200;
    setTimeout(() => {
      const demo = findDemoResponse(text);
      const assistantMsg: Message = {
        id: `msg-${++messageCounter}`,
        role: "assistant",
        content: demo.content,
        action: demo.action,
        data: demo.data,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsTyping(false);
    }, delay);
  }, []);

  return (
    <div className="h-screen bg-[#0a0a0a] text-neutral-200 flex flex-col overflow-hidden">
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Feature icons */}
        <FeatureSidebar
          activeFeature={activeFeature}
          onSelectFeature={setActiveFeature}
        />

        {/* Center: Chat */}
        <ChatPanel
          messages={messages}
          onSend={handleSend}
          isTyping={isTyping}
        />

        {/* Right: Context */}
        <ContextSidebar
          conversations={demoConversations}
          activeConversation={activeConversation}
          onSelectConversation={setActiveConversation}
          memories={demoMemories}
          activeFeatures={["Email", "Travel", "Orders", "Todos", "Calendar", "CCTV"]}
        />
      </div>

      {/* Bottom: Live monitors */}
      <LiveMonitors />
    </div>
  );
}
