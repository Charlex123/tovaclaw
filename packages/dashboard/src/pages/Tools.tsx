import { useState } from "react";
import { motion } from "framer-motion";
import {
  Wrench,
  Search,
  Mail,
  Plane,
  CheckSquare,
  FileText,
  Calendar,
  AlertTriangle,
  Video,
  Car,
  Database,
  Phone,
  Upload,
  Globe,
  Bot,
  Palette,
  Code,
  Cpu,
} from "lucide-react";
import type { ReactNode } from "react";

interface ToolCategory {
  id: string;
  name: string;
  icon: ReactNode;
  tools: ToolItem[];
}

interface ToolItem {
  name: string;
  description: string;
}

const categories: ToolCategory[] = [
  {
    id: "core",
    name: "Core / Orders",
    icon: <Wrench className="w-4 h-4" />,
    tools: [
      { name: "search_products", description: "Search products, medicines, and supplies" },
      { name: "search_services", description: "Search lab tests and diagnostics" },
      { name: "search_practitioners", description: "Find doctors and specialists" },
      { name: "create_order", description: "Create a new order" },
      { name: "execute_order", description: "Execute and fulfill an order" },
      { name: "cancel_order", description: "Cancel an existing order" },
      { name: "get_order_history", description: "Retrieve past orders" },
      { name: "book_appointment", description: "Book an appointment" },
      { name: "check_balance", description: "Check user wallet balance" },
      { name: "calculate_delivery_fee", description: "Estimate delivery cost" },
    ],
  },
  {
    id: "email",
    name: "Email",
    icon: <Mail className="w-4 h-4" />,
    tools: [
      { name: "list_emails", description: "List emails from a folder" },
      { name: "read_email", description: "Read a specific email" },
      { name: "categorize_email", description: "Categorize email by type" },
      { name: "draft_reply", description: "Draft a reply to an email" },
      { name: "send_email", description: "Send an email" },
      { name: "summarize_thread", description: "Summarize an email thread" },
    ],
  },
  {
    id: "travel",
    name: "Travel",
    icon: <Plane className="w-4 h-4" />,
    tools: [
      { name: "search_flights", description: "Search available flights" },
      { name: "search_trains", description: "Search train routes" },
      { name: "search_buses", description: "Search bus routes" },
      { name: "search_car_hire", description: "Search car rental options" },
      { name: "compare_transport", description: "Compare transport modes" },
      { name: "find_nearest_airport", description: "Find closest airport" },
      { name: "save_travel_plan", description: "Save a travel itinerary" },
    ],
  },
  {
    id: "todos",
    name: "Todos",
    icon: <CheckSquare className="w-4 h-4" />,
    tools: [
      { name: "create_todo", description: "Create a new task" },
      { name: "list_todos", description: "List all tasks" },
      { name: "update_todo", description: "Update task details" },
      { name: "complete_todo", description: "Mark task as done" },
      { name: "suggest_priorities", description: "AI-suggested task priorities" },
    ],
  },
  {
    id: "notes",
    name: "Notes",
    icon: <FileText className="w-4 h-4" />,
    tools: [
      { name: "create_note", description: "Create a new note" },
      { name: "summarize_text", description: "Summarize text content" },
      { name: "summarize_url", description: "Summarize a web page" },
      { name: "extract_key_points", description: "Extract key points" },
      { name: "save_note", description: "Save note to store" },
    ],
  },
  {
    id: "events",
    name: "Events",
    icon: <Calendar className="w-4 h-4" />,
    tools: [
      { name: "create_event", description: "Create a calendar event" },
      { name: "list_events", description: "List upcoming events" },
      { name: "update_event", description: "Modify an event" },
      { name: "suggest_event_time", description: "AI-suggested meeting time" },
      { name: "send_reminder", description: "Send event reminder" },
    ],
  },
  {
    id: "emergency",
    name: "Emergency",
    icon: <AlertTriangle className="w-4 h-4" />,
    tools: [
      { name: "report_emergency", description: "Report a new emergency" },
      { name: "list_emergencies", description: "List active emergencies" },
      { name: "escalate_emergency", description: "Escalate severity level" },
      { name: "acknowledge_emergency", description: "Acknowledge an alert" },
      { name: "send_emergency_alert", description: "Broadcast emergency alert" },
    ],
  },
  {
    id: "cctv",
    name: "CCTV / Video",
    icon: <Video className="w-4 h-4" />,
    tools: [
      { name: "list_cameras", description: "List available cameras" },
      { name: "get_snapshot", description: "Capture a frame" },
      { name: "analyze_frame", description: "AI analysis of a frame" },
      { name: "detect_anomalies", description: "Detect unusual activity" },
    ],
  },
  {
    id: "vehicle",
    name: "Vehicle / Fleet",
    icon: <Car className="w-4 h-4" />,
    tools: [
      { name: "get_vehicle_position", description: "Get GPS position" },
      { name: "fleet_overview", description: "Overview of all vehicles" },
      { name: "check_geofence_violation", description: "Check boundary violations" },
      { name: "calculate_route", description: "Calculate optimal route" },
    ],
  },
  {
    id: "dataset",
    name: "RAG / Datasets",
    icon: <Database className="w-4 h-4" />,
    tools: [
      { name: "query_dataset", description: "Query via vector similarity" },
      { name: "list_datasets", description: "List ingested datasets" },
      { name: "ingest_document", description: "Ingest PDF, CSV, or JSON" },
    ],
  },
  {
    id: "phone",
    name: "Phone / SMS",
    icon: <Phone className="w-4 h-4" />,
    tools: [
      { name: "make_call", description: "Initiate a phone call" },
      { name: "check_call_status", description: "Check call status" },
      { name: "send_sms", description: "Send an SMS message" },
    ],
  },
  {
    id: "files",
    name: "Files",
    icon: <Upload className="w-4 h-4" />,
    tools: [
      { name: "upload_file", description: "Upload a file" },
      { name: "list_files", description: "List stored files" },
      { name: "download_file", description: "Download a file" },
      { name: "delete_file", description: "Delete a file" },
      { name: "share_file", description: "Generate a share link" },
    ],
  },
  {
    id: "web",
    name: "Web Search",
    icon: <Globe className="w-4 h-4" />,
    tools: [
      { name: "search_web", description: "General web search" },
      { name: "search_accommodations", description: "Search hotels and stays" },
      { name: "search_attractions", description: "Search things to do" },
      { name: "search_restaurants", description: "Search places to eat" },
    ],
  },
  {
    id: "agents",
    name: "Agent Management",
    icon: <Bot className="w-4 h-4" />,
    tools: [
      { name: "create_agent", description: "Create a custom agent" },
      { name: "update_agent", description: "Update agent config" },
      { name: "delete_agent", description: "Remove an agent" },
      { name: "list_agents", description: "List all custom agents" },
    ],
  },
  {
    id: "creative",
    name: "Creative Generation",
    icon: <Palette className="w-4 h-4" />,
    tools: [
      { name: "generate_image", description: "Generate an image from text prompt" },
      { name: "edit_image", description: "Edit or modify an existing image" },
      { name: "generate_video", description: "Generate a video from text or image" },
      { name: "generate_audio", description: "Generate audio/speech from text" },
      { name: "text_to_speech", description: "Convert text to natural speech" },
    ],
  },
  {
    id: "code",
    name: "Code & Dev",
    icon: <Code className="w-4 h-4" />,
    tools: [
      { name: "execute_code", description: "Run code in sandboxed environment" },
      { name: "analyze_code", description: "Static analysis and review" },
      { name: "generate_code", description: "Generate code from description" },
      { name: "explain_code", description: "Explain code functionality" },
    ],
  },
  {
    id: "document",
    name: "Document Processing",
    icon: <FileText className="w-4 h-4" />,
    tools: [
      { name: "extract_text", description: "OCR and text extraction from images" },
      { name: "parse_document", description: "Parse PDF, DOCX, XLSX structures" },
      { name: "translate_text", description: "Translate text between languages" },
      { name: "generate_report", description: "Generate formatted reports" },
    ],
  },
  {
    id: "model",
    name: "Model & ML",
    icon: <Cpu className="w-4 h-4" />,
    tools: [
      { name: "classify_intent", description: "Classify user intent with ML model" },
      { name: "detect_anomaly", description: "Run anomaly detection on data" },
      { name: "predict_preference", description: "Predict user preferences" },
      { name: "score_urgency", description: "Score message urgency (1-10)" },
      { name: "cluster_behavior", description: "Cluster user behavior patterns" },
    ],
  },
];

export default function Tools() {
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>("core");

  const totalTools = categories.reduce(
    (sum, cat) => sum + cat.tools.length,
    0
  );

  const filteredCategories = search
    ? categories
        .map((cat) => ({
          ...cat,
          tools: cat.tools.filter(
            (t) =>
              t.name.includes(search.toLowerCase()) ||
              t.description.toLowerCase().includes(search.toLowerCase())
          ),
        }))
        .filter((cat) => cat.tools.length > 0)
    : categories;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-neutral-500">
          {totalTools} tools across {categories.length} categories. Tools are
          auto-registered based on enabled providers.
        </p>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter tools..."
            className="w-56 pl-9 pr-4 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-neutral-300 placeholder:text-neutral-600 focus:outline-none focus:border-blue-500/50 transition-all"
          />
        </div>
      </div>

      <div className="space-y-2">
        {filteredCategories.map((category, i) => {
          const isExpanded = expanded === category.id || !!search;
          return (
            <motion.div
              key={category.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              className="rounded-xl border border-white/5 bg-white/[0.02] overflow-hidden"
            >
              <button
                onClick={() =>
                  setExpanded(isExpanded && !search ? null : category.id)
                }
                className="w-full flex items-center justify-between p-4 hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center text-cyan-400">
                    {category.icon}
                  </div>
                  <span className="text-white font-medium text-sm">
                    {category.name}
                  </span>
                  <span className="text-xs text-neutral-600">
                    {category.tools.length} tools
                  </span>
                </div>
                <svg
                  className={`w-4 h-4 text-neutral-500 transition-transform ${
                    isExpanded ? "rotate-180" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              {isExpanded && (
                <div className="border-t border-white/5 px-4 pb-3">
                  {category.tools.map((tool) => (
                    <div
                      key={tool.name}
                      className="flex items-center justify-between py-2.5 border-b border-white/5 last:border-0"
                    >
                      <code className="text-sm font-mono text-cyan-400">
                        {tool.name}
                      </code>
                      <span className="text-xs text-neutral-500">
                        {tool.description}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
