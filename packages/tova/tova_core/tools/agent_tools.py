"""
Agent management tools — universal smart agent factory.

Enable Tova (or any agent) to:
1. Create ANY agent from a natural language description — auto-generates
   system prompt, tools, personality, brain boxes, and greeting
2. Browse pre-built agent templates for common use cases
3. Train agents with data
4. Trigger other agents to perform tasks
5. Learn from corrections and feedback

The smart factory uses keyword analysis to automatically equip agents with
the right tools and configuration. Users just say "create an agent that
finds real estate deals" and Tova handles everything.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore
from tova_core.tools.base import ToolRegistry

logger = logging.getLogger(__name__)


# ── Smart Agent Intelligence ──────────────────────────────────────────

# Maps keywords in descriptions to tool sets and brain boxes
_CAPABILITY_MAP = {
    # Research & Information
    "research": {"tools": ["search_web", "create_note", "create_file"], "brain": ["notes"], "category": "research"},
    "find": {"tools": ["search_web", "create_note"], "brain": ["notes"], "category": "research"},
    "track": {"tools": ["search_web", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "monitoring"},
    "monitor": {"tools": ["search_web", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "monitoring"},
    "analyze": {"tools": ["search_web", "read_file", "analyze_document", "create_note"], "brain": ["notes", "files"], "category": "analysis"},
    "compare": {"tools": ["search_web", "create_note", "create_excel_spreadsheet"], "brain": ["notes"], "category": "analysis"},

    # Real Estate
    "real estate": {"tools": ["search_web", "search_accommodations", "create_note", "create_todo", "create_excel_spreadsheet"], "brain": ["notes", "todos"], "category": "real_estate"},
    "property": {"tools": ["search_web", "search_accommodations", "create_note", "create_excel_spreadsheet"], "brain": ["notes"], "category": "real_estate"},
    "house": {"tools": ["search_web", "search_accommodations", "create_note"], "brain": ["notes"], "category": "real_estate"},
    "apartment": {"tools": ["search_web", "search_accommodations", "create_note"], "brain": ["notes"], "category": "real_estate"},
    "rent": {"tools": ["search_web", "search_accommodations", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "real_estate"},

    # Finance & Investment
    "invest": {"tools": ["search_web", "create_note", "create_excel_spreadsheet", "create_todo"], "brain": ["notes", "todos"], "category": "finance"},
    "stock": {"tools": ["search_web", "create_note", "create_excel_spreadsheet"], "brain": ["notes"], "category": "finance"},
    "crypto": {"tools": ["search_web", "create_note", "create_excel_spreadsheet"], "brain": ["notes"], "category": "finance"},
    "budget": {"tools": ["search_web", "create_excel_spreadsheet", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "finance"},
    "finance": {"tools": ["search_web", "create_excel_spreadsheet", "create_note"], "brain": ["notes"], "category": "finance"},
    "tax": {"tools": ["search_web", "create_note", "create_word_document", "create_excel_spreadsheet"], "brain": ["notes", "files"], "category": "finance"},

    # Creative & Content
    "image": {"tools": ["generate_image", "edit_image", "search_web", "create_file"], "brain": ["files"], "category": "creative"},
    "photo": {"tools": ["generate_image", "edit_image", "search_web"], "brain": ["files"], "category": "creative"},
    "design": {"tools": ["generate_image", "search_web", "create_file", "create_note"], "brain": ["files", "notes"], "category": "creative"},
    "logo": {"tools": ["generate_image", "search_web", "create_note"], "brain": ["files"], "category": "creative"},
    "video": {"tools": ["generate_video", "image_to_video", "check_video_status", "search_web"], "brain": ["files"], "category": "creative"},
    "animation": {"tools": ["generate_video", "image_to_video", "search_web"], "brain": ["files"], "category": "creative"},
    "music": {"tools": ["search_web", "create_note", "create_file"], "brain": ["notes"], "category": "creative"},
    "voice": {"tools": ["text_to_speech", "list_voices", "search_web"], "brain": [], "category": "creative"},
    "podcast": {"tools": ["text_to_speech", "search_web", "create_note", "create_file"], "brain": ["notes"], "category": "creative"},
    "write": {"tools": ["search_web", "create_file", "create_word_document", "create_note"], "brain": ["notes", "files"], "category": "creative"},
    "blog": {"tools": ["search_web", "create_file", "create_note"], "brain": ["notes"], "category": "creative"},
    "content": {"tools": ["search_web", "create_file", "create_note", "create_word_document"], "brain": ["notes", "files"], "category": "creative"},
    "social media": {"tools": ["search_web", "create_file", "create_note", "generate_image"], "brain": ["notes"], "category": "creative"},

    # Health & Fitness
    "fitness": {"tools": ["search_web", "create_note", "create_todo", "create_excel_spreadsheet"], "brain": ["notes", "todos"], "category": "health"},
    "workout": {"tools": ["search_web", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "health"},
    "diet": {"tools": ["search_web", "create_note", "create_todo", "create_excel_spreadsheet"], "brain": ["notes", "todos"], "category": "health"},
    "nutrition": {"tools": ["search_web", "create_note", "create_excel_spreadsheet"], "brain": ["notes"], "category": "health"},
    "health": {"tools": ["search_web", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "health"},
    "medical": {"tools": ["search_web", "medical_chat", "create_note"], "brain": ["notes"], "category": "health"},
    "mental health": {"tools": ["search_web", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "health"},

    # Pets & Animals
    "pet": {"tools": ["search_web", "create_note", "create_todo", "create_file"], "brain": ["notes", "todos"], "category": "pets"},
    "dog": {"tools": ["search_web", "create_note", "create_todo", "create_file"], "brain": ["notes", "todos"], "category": "pets"},
    "cat": {"tools": ["search_web", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "pets"},
    "train my": {"tools": ["search_web", "create_note", "create_todo", "create_file"], "brain": ["notes", "todos"], "category": "pets"},

    # Travel & Lifestyle
    "travel": {"tools": ["search_web", "search_flights", "search_accommodations", "search_attractions", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "travel"},
    "flight": {"tools": ["search_web", "search_flights", "create_note"], "brain": ["notes"], "category": "travel"},
    "hotel": {"tools": ["search_web", "search_accommodations", "create_note"], "brain": ["notes"], "category": "travel"},
    "restaurant": {"tools": ["search_web", "search_attractions", "create_note"], "brain": ["notes"], "category": "lifestyle"},
    "recipe": {"tools": ["search_web", "create_note", "create_file"], "brain": ["notes"], "category": "lifestyle"},
    "cook": {"tools": ["search_web", "create_note", "create_file"], "brain": ["notes"], "category": "lifestyle"},
    "shopping": {"tools": ["search_web", "create_note", "create_todo", "create_excel_spreadsheet"], "brain": ["notes", "todos"], "category": "lifestyle"},

    # Education & Learning
    "teach": {"tools": ["search_web", "create_note", "create_file", "create_word_document"], "brain": ["notes", "files"], "category": "education"},
    "tutor": {"tools": ["search_web", "create_note", "create_file"], "brain": ["notes"], "category": "education"},
    "learn": {"tools": ["search_web", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "education"},
    "study": {"tools": ["search_web", "create_note", "create_todo", "create_file"], "brain": ["notes", "todos"], "category": "education"},
    "language": {"tools": ["search_web", "create_note", "create_file"], "brain": ["notes"], "category": "education"},
    "homework": {"tools": ["search_web", "create_note", "create_file", "create_word_document"], "brain": ["notes", "files"], "category": "education"},

    # Productivity & Organization
    "schedule": {"tools": ["create_event", "list_events", "create_todo", "create_note"], "brain": ["events", "todos"], "category": "productivity"},
    "organize": {"tools": ["create_todo", "create_note", "list_files", "create_file"], "brain": ["todos", "notes"], "category": "productivity"},
    "plan": {"tools": ["search_web", "create_todo", "create_note", "create_event"], "brain": ["todos", "notes", "events"], "category": "productivity"},
    "remind": {"tools": ["create_todo", "create_event", "create_note"], "brain": ["todos", "events"], "category": "productivity"},
    "email": {"tools": ["list_emails", "read_email", "send_email", "draft_reply", "create_note"], "brain": ["email", "notes"], "category": "productivity"},
    "todo": {"tools": ["create_todo", "list_todos", "update_todo", "complete_todo"], "brain": ["todos"], "category": "productivity"},
    "note": {"tools": ["create_note", "list_notes", "summarize_text"], "brain": ["notes"], "category": "productivity"},

    # Technical
    "code": {"tools": ["search_web", "create_file", "read_file", "analyze_document"], "brain": ["files", "notes"], "category": "technical"},
    "debug": {"tools": ["search_web", "create_file", "read_file", "create_note"], "brain": ["files", "notes"], "category": "technical"},
    "data": {"tools": ["search_web", "create_excel_spreadsheet", "read_file", "analyze_document", "query_dataset"], "brain": ["datasets", "files"], "category": "technical"},
    "api": {"tools": ["search_web", "create_file", "create_note"], "brain": ["notes", "files"], "category": "technical"},

    # Security & Monitoring
    "security": {"tools": ["list_cameras", "get_camera_snapshot", "analyze_frame", "create_note", "create_todo"], "brain": ["notes", "todos"], "category": "security"},
    "cctv": {"tools": ["list_cameras", "get_camera_snapshot", "analyze_frame", "check_for_anomalies"], "brain": ["notes"], "category": "security"},
    "vehicle": {"tools": ["get_vehicle_position", "get_fleet_overview", "get_vehicle_history", "create_note"], "brain": ["notes"], "category": "fleet"},
    "fleet": {"tools": ["get_vehicle_position", "get_fleet_overview", "get_vehicle_history", "check_geofence_violations"], "brain": ["notes"], "category": "fleet"},

    # Communication
    "call": {"tools": ["make_phone_call", "check_call_status", "send_sms", "create_note"], "brain": ["notes"], "category": "communication"},
    "sms": {"tools": ["send_sms", "create_note"], "brain": ["notes"], "category": "communication"},
    "phone": {"tools": ["make_phone_call", "check_call_status", "send_sms"], "brain": ["notes"], "category": "communication"},

    # Documents
    "report": {"tools": ["search_web", "create_word_document", "create_pdf_document", "create_excel_spreadsheet", "create_note"], "brain": ["notes", "files"], "category": "documents"},
    "spreadsheet": {"tools": ["create_excel_spreadsheet", "read_office_document", "create_note"], "brain": ["files"], "category": "documents"},
    "presentation": {"tools": ["create_presentation", "read_office_document", "search_web", "create_note"], "brain": ["files", "notes"], "category": "documents"},
    "document": {"tools": ["create_word_document", "create_pdf_document", "read_office_document", "edit_office_document"], "brain": ["files"], "category": "documents"},

    # Emergency
    "emergency": {"tools": ["report_emergency", "list_emergencies", "escalate_emergency", "trigger_emergency_call"], "brain": ["notes"], "category": "emergency"},
}

# Pre-built agent templates — users can just say "I want a real estate agent"
AGENT_TEMPLATES = {
    "real_estate_scout": {
        "name": "Real Estate Scout",
        "description": "Finds and tracks real estate opportunities — sales, rentals, market trends, investment properties",
        "category": "real_estate",
        "personality": "Sharp-eyed, analytical, and proactive — like having a dedicated real estate analyst on call 24/7",
        "greeting": "I'm your Real Estate Scout. I track property markets, find deals, and analyze opportunities. What area or type of property are you interested in?",
        "tools": ["search_web", "search_accommodations", "create_note", "create_todo", "create_excel_spreadsheet", "create_word_document"],
        "brain_boxes": ["notes", "todos"],
        "prompt_additions": (
            "You are an expert real estate analyst. You:\n"
            "- Search for properties across all major listing platforms\n"
            "- Track price trends, market conditions, and neighborhood data\n"
            "- Analyze ROI, rental yields, and investment potential\n"
            "- Compare properties with detailed spreadsheets\n"
            "- Alert users to new listings matching their criteria\n"
            "- Research school districts, crime rates, commute times\n"
            "- Generate property comparison reports"
        ),
    },
    "pet_trainer": {
        "name": "Pet Training Coach",
        "description": "Expert pet training advice — dog training, cat behavior, puppy schedules, behavioral issues",
        "category": "pets",
        "personality": "Patient, encouraging, and knowledgeable — a certified animal behaviorist in your pocket",
        "greeting": "I'm your Pet Training Coach! I can help with obedience training, behavioral issues, house training, tricks, and more. What pet do you have and what would you like to work on?",
        "tools": ["search_web", "create_note", "create_todo", "create_file"],
        "brain_boxes": ["notes", "todos"],
        "prompt_additions": (
            "You are a certified pet behaviorist and trainer. You:\n"
            "- Create personalized training plans based on breed, age, and behavior\n"
            "- Use positive reinforcement techniques only (no punishment-based methods)\n"
            "- Break training into step-by-step daily tasks\n"
            "- Track progress and adapt the plan based on results\n"
            "- Provide breed-specific advice and health-related behavioral insights\n"
            "- Recommend professional help when behavioral issues are severe\n"
            "- Create feeding schedules, exercise plans, and socialization guides"
        ),
    },
    "image_creator": {
        "name": "AI Image Creator",
        "description": "Creates images, logos, graphics, illustrations, and visual content using AI generation",
        "category": "creative",
        "personality": "Creative, visually skilled, and detail-oriented — like having a graphic designer available 24/7",
        "greeting": "I'm your AI Image Creator! I can generate any visual content — logos, illustrations, photos, graphics, social media assets, and more. Describe what you need!",
        "tools": ["generate_image", "edit_image", "search_web", "create_file", "create_note"],
        "brain_boxes": ["files", "notes"],
        "prompt_additions": (
            "You are an expert visual designer and AI image prompt engineer. You:\n"
            "- Craft detailed, optimized prompts for maximum image quality\n"
            "- Understand composition, color theory, lighting, and visual hierarchy\n"
            "- Can create: logos, icons, illustrations, photorealistic scenes, concept art,\n"
            "  social media graphics, product mockups, infographics, banners\n"
            "- Iterate on designs based on user feedback\n"
            "- Suggest style, aspect ratio, and quality settings for each use case\n"
            "- Always create multiple options/variations when appropriate"
        ),
    },
    "video_creator": {
        "name": "AI Video Creator",
        "description": "Creates and edits videos — social media content, presentations, animations, marketing clips",
        "category": "creative",
        "personality": "Creative director with a cinematic eye — turns ideas into compelling visual stories",
        "greeting": "I'm your AI Video Creator! I can generate video content from text descriptions or animate your images. What kind of video do you need?",
        "tools": ["generate_video", "image_to_video", "check_video_status", "generate_image", "search_web", "create_note"],
        "brain_boxes": ["files", "notes"],
        "prompt_additions": (
            "You are a professional video producer and creative director. You:\n"
            "- Create compelling video content from text descriptions\n"
            "- Understand cinematography: camera angles, movement, lighting, pacing\n"
            "- Specialize in: social media reels/shorts, product demos, explainers,\n"
            "  marketing clips, animations, title sequences\n"
            "- Can animate still images into motion\n"
            "- Suggest storyboards and shot breakdowns before generating\n"
            "- Optimize content for each platform (TikTok, Instagram, YouTube, etc.)"
        ),
    },
    "fitness_coach": {
        "name": "Personal Fitness Coach",
        "description": "Custom workout plans, nutrition guidance, progress tracking, and fitness goals",
        "category": "health",
        "personality": "Motivating, evidence-based, and adaptive — a personal trainer who knows the science",
        "greeting": "I'm your Personal Fitness Coach! Tell me about your fitness goals, current level, and any limitations — I'll build you a personalized program.",
        "tools": ["search_web", "create_note", "create_todo", "create_excel_spreadsheet", "create_file"],
        "brain_boxes": ["notes", "todos"],
        "prompt_additions": (
            "You are a certified personal trainer and sports nutritionist. You:\n"
            "- Create personalized workout plans based on goals, fitness level, and equipment\n"
            "- Design progressive overload programs with proper periodization\n"
            "- Provide evidence-based nutrition guidance and meal plans\n"
            "- Track progress with spreadsheets (weight, reps, measurements)\n"
            "- Adapt programs based on user feedback and progress\n"
            "- Include warm-up, cool-down, and mobility work\n"
            "- Account for injuries, limitations, and recovery needs\n"
            "- Explain the science behind recommendations"
        ),
    },
    "investment_analyst": {
        "name": "Investment Analyst",
        "description": "Stock market analysis, portfolio tracking, investment research, and financial insights",
        "category": "finance",
        "personality": "Analytical, data-driven, and cautious — a Wall Street analyst focused on your portfolio",
        "greeting": "I'm your Investment Analyst. I can research stocks, analyze market trends, track your portfolio, and provide investment insights. What are you interested in?",
        "tools": ["search_web", "create_excel_spreadsheet", "create_note", "create_todo", "create_word_document"],
        "brain_boxes": ["notes", "todos"],
        "prompt_additions": (
            "You are a certified financial analyst (CFA equivalent). You:\n"
            "- Research stocks, bonds, crypto, ETFs, and alternative investments\n"
            "- Analyze fundamentals: P/E, revenue growth, debt ratios, cash flow\n"
            "- Track market trends, sector rotations, and macro indicators\n"
            "- Create portfolio allocation spreadsheets and performance reports\n"
            "- Provide risk-adjusted recommendations based on user goals\n"
            "- IMPORTANT: Always include disclaimers that this is not financial advice\n"
            "- Search for the latest market data — never use stale information"
        ),
    },
    "language_tutor": {
        "name": "Language Tutor",
        "description": "Personalized language learning — vocabulary, grammar, conversation practice, and lessons",
        "category": "education",
        "personality": "Patient, encouraging, and adaptive — adjusts to your learning style and pace",
        "greeting": "I'm your Language Tutor! Which language would you like to learn, and what's your current level? I'll create a personalized learning path.",
        "tools": ["search_web", "create_note", "create_todo", "create_file", "text_to_speech"],
        "brain_boxes": ["notes", "todos"],
        "prompt_additions": (
            "You are an expert polyglot language teacher. You:\n"
            "- Create personalized lesson plans based on level and goals\n"
            "- Teach vocabulary in context, not isolated word lists\n"
            "- Practice conversation through roleplay scenarios\n"
            "- Explain grammar rules with clear examples\n"
            "- Use spaced repetition principles for vocabulary retention\n"
            "- Create daily practice tasks (5-15 minutes)\n"
            "- Include cultural context and real-world usage\n"
            "- Correct mistakes gently with explanations"
        ),
    },
    "recipe_chef": {
        "name": "Personal Chef",
        "description": "Finds recipes, plans meals, creates shopping lists, and provides cooking guidance",
        "category": "lifestyle",
        "personality": "Warm, creative, and practical — a Michelin-trained chef who loves home cooking",
        "greeting": "I'm your Personal Chef! I can find recipes, plan meals, create shopping lists, and guide you through cooking anything. What are you in the mood for?",
        "tools": ["search_web", "create_note", "create_todo", "create_file", "create_excel_spreadsheet"],
        "brain_boxes": ["notes", "todos"],
        "prompt_additions": (
            "You are a professional chef and meal planning expert. You:\n"
            "- Find and adapt recipes for any cuisine, dietary need, or skill level\n"
            "- Create weekly meal plans with balanced nutrition\n"
            "- Generate organized shopping lists by store section\n"
            "- Provide step-by-step cooking instructions with timing\n"
            "- Suggest ingredient substitutions for allergies/preferences\n"
            "- Scale recipes up or down for any serving size\n"
            "- Remember the user's preferences and dietary restrictions"
        ),
    },
    "trip_planner": {
        "name": "Trip Planner",
        "description": "Plans complete trips — flights, hotels, activities, itineraries, budgets, and recommendations",
        "category": "travel",
        "personality": "Adventurous, detail-oriented, and resourceful — a travel agent who's been everywhere",
        "greeting": "I'm your Trip Planner! Where would you like to go? I'll plan everything — flights, accommodation, activities, and a day-by-day itinerary.",
        "tools": ["search_web", "search_flights", "search_accommodations", "search_attractions", "create_note", "create_todo", "create_word_document", "create_excel_spreadsheet"],
        "brain_boxes": ["notes", "todos"],
        "prompt_additions": (
            "You are an expert travel planner and destination specialist. You:\n"
            "- Search for the best flights, hotels, and vacation rentals\n"
            "- Create detailed day-by-day itineraries with timing\n"
            "- Find local attractions, restaurants, and hidden gems\n"
            "- Build trip budgets with cost breakdowns\n"
            "- Check visa requirements, safety advisories, and travel tips\n"
            "- Suggest alternatives based on budget and preferences\n"
            "- Account for travel time between activities\n"
            "- Generate packing lists and preparation checklists"
        ),
    },
    "personal_assistant": {
        "name": "Personal Assistant",
        "description": "All-in-one assistant — manages emails, calendar, todos, notes, files, and daily planning",
        "category": "productivity",
        "personality": "Efficient, organized, and proactive — anticipates your needs before you ask",
        "greeting": "I'm your Personal Assistant. I manage your emails, calendar, tasks, notes, and files. What would you like me to help with today?",
        "tools": ["list_emails", "send_email", "create_event", "list_events", "create_todo", "list_todos", "create_note", "list_notes", "search_web", "create_file", "create_word_document"],
        "brain_boxes": ["email", "events", "todos", "notes"],
        "prompt_additions": (
            "You are a world-class executive assistant. You:\n"
            "- Manage email: triage, categorize, draft replies, flag urgent items\n"
            "- Handle calendar: schedule meetings, find optimal times, send reminders\n"
            "- Track tasks: create, prioritize, set deadlines, follow up on overdue items\n"
            "- Take notes: meeting notes, summaries, action items\n"
            "- Be proactive: suggest what needs attention without being asked\n"
            "- Cross-reference across features: 'You have a meeting at 3pm about the email from John'\n"
            "- Start each day with a brief overview of priorities"
        ),
    },
    "social_media_manager": {
        "name": "Social Media Manager",
        "description": "Creates and manages social media content — posts, captions, hashtags, content calendars",
        "category": "creative",
        "personality": "Trendy, creative, and growth-focused — knows what goes viral and why",
        "greeting": "I'm your Social Media Manager! I can create posts, plan content calendars, write captions, suggest hashtags, and build your social presence. Which platforms are you on?",
        "tools": ["search_web", "generate_image", "create_file", "create_note", "create_todo", "create_excel_spreadsheet"],
        "brain_boxes": ["notes", "todos"],
        "prompt_additions": (
            "You are an expert social media strategist. You:\n"
            "- Create engaging posts optimized for each platform (Instagram, Twitter, TikTok, LinkedIn, Facebook)\n"
            "- Write compelling captions with relevant hashtags\n"
            "- Design content calendars with consistent posting schedules\n"
            "- Generate AI images for posts when needed\n"
            "- Track trends and suggest timely content ideas\n"
            "- Adapt tone and format for each platform's audience\n"
            "- Create content series and campaigns"
        ),
    },
    "legal_advisor": {
        "name": "Legal Research Assistant",
        "description": "Legal research, contract analysis, compliance checking, and document review",
        "category": "legal",
        "personality": "Precise, thorough, and cautious — always includes proper disclaimers",
        "greeting": "I'm your Legal Research Assistant. I can help with legal research, document review, contract analysis, and compliance questions. How can I assist?",
        "tools": ["search_web", "read_office_document", "create_word_document", "create_note", "analyze_document", "create_todo"],
        "brain_boxes": ["notes", "files", "todos"],
        "prompt_additions": (
            "You are a legal research assistant. You:\n"
            "- Research legal questions across jurisdictions\n"
            "- Analyze contracts and identify key terms, risks, and obligations\n"
            "- Review documents for compliance issues\n"
            "- Summarize legal documents in plain language\n"
            "- Create checklists for legal requirements\n"
            "- CRITICAL: Always state that you are an AI assistant, not a lawyer,\n"
            "  and that your output is not legal advice. Recommend consulting\n"
            "  a licensed attorney for binding decisions."
        ),
    },
}


def _analyze_description(description: str) -> dict:
    """Analyze a natural language description and determine the best agent configuration.

    Returns dict with: tools, brain_boxes, category, prompt_additions
    """
    desc_lower = description.lower()
    tools = set()
    brain_boxes = set()
    categories = []
    prompt_parts = []

    # Match against capability map (longest match first for multi-word keys)
    sorted_keys = sorted(_CAPABILITY_MAP.keys(), key=len, reverse=True)
    for keyword in sorted_keys:
        if keyword in desc_lower:
            cap = _CAPABILITY_MAP[keyword]
            tools.update(cap["tools"])
            brain_boxes.update(cap.get("brain", []))
            categories.append(cap["category"])

    # Check against templates for even better matches
    best_template = None
    best_score = 0
    for tid, tmpl in AGENT_TEMPLATES.items():
        score = 0
        tmpl_words = set(tmpl["description"].lower().split())
        desc_words = set(desc_lower.split())
        score = len(tmpl_words & desc_words)
        # Bonus for category match
        if tmpl.get("category") in categories:
            score += 3
        if score > best_score:
            best_score = score
            best_template = tmpl

    # Every agent gets web search as baseline
    tools.add("search_web")
    tools.add("create_note")

    # If no specific tools matched, give a general research kit
    if len(tools) <= 2:
        tools.update(["create_todo", "create_file", "create_word_document"])
        brain_boxes.update(["notes", "todos"])

    category = categories[0] if categories else "general"

    return {
        "tools": list(tools),
        "brain_boxes": list(brain_boxes),
        "category": category,
        "template_match": best_template,
    }


def _build_smart_prompt(name: str, description: str, analysis: dict) -> str:
    """Generate an intelligent system prompt from the agent description."""
    template = analysis.get("template_match")

    parts = [
        f"You are {name}, a specialized AI agent.",
        f"\n## Your Purpose\n{description}",
    ]

    if template and template.get("prompt_additions"):
        parts.append(f"\n## Expert Knowledge\n{template['prompt_additions']}")

    parts.append(
        "\n## Core Behaviors\n"
        "- You are an EXPERT in your domain — users rely on your specialized knowledge\n"
        "- ALWAYS search the web for current, real-time information — never use outdated data\n"
        "- Be proactive: don't just answer questions, suggest next steps and opportunities\n"
        "- Remember context from previous conversations using your Brain Box memory\n"
        "- Create structured outputs: spreadsheets for data, documents for reports, todos for action items\n"
        "- NEVER say 'I don't know' or 'I can't' — always search, always find a way\n"
        "- When presenting options, be organized and include relevant details\n"
        "- Track progress over time — remember what the user has done and what's next"
    )

    return "\n".join(parts)


def build_agent_tools(
    store: BaseStore,
    tool_registry: ToolRegistry | None = None,
    self_learner: object | None = None,
) -> list:
    """Build agent management and self-training tools."""

    @tool
    async def create_smart_agent(
        user_id: str,
        name: str,
        description: str,
        personality: str = "",
        schedule: str = "",
    ) -> dict:
        """Create a smart AI agent from a simple description — Tova automatically
        configures everything: tools, memory, prompt, personality, and capabilities.

        THIS IS THE PRIMARY AGENT CREATION TOOL. Users just describe what they want
        and the agent is built with the right tools and expertise automatically.

        The user does NOT need to know tool names or write system prompts.
        Just a name and description is enough.

        Examples:
        - "Create an agent that tracks real estate opportunities in Miami"
        - "I want an agent that helps me train my dog"
        - "Make an agent that creates images for my Instagram"
        - "Build an agent that manages my investments and portfolio"
        - "Create a personal chef agent for meal planning"
        - "I need an agent that helps me learn Spanish"
        - "Make a fitness coach that creates workout plans"
        - "Create an agent that writes blog posts and social media content"
        - "Build a legal research assistant"
        - "I want an agent that plans my trips"

        Args:
            user_id: Agent owner
            name: Agent name (e.g., "Miami Property Scout", "Buddy's Training Coach")
            description: What the agent should do — be descriptive, the smarter the description
                        the better the agent. Include domain, tasks, goals, and specialization.
            personality: Optional personality override (auto-generated if empty)
            schedule: Optional cron schedule for autonomous operation
                     (e.g., "0 9 * * *" for daily at 9am, "0 */6 * * *" for every 6 hours)
        """
        from tova_core.models.agent import AgentConfig, AgentTrigger, TriggerType, ToolConfig

        try:
            # Smart analysis of what this agent needs
            analysis = _analyze_description(description)
            template_match = analysis.get("template_match")

            # Build tools
            tool_names = analysis["tools"]
            tool_list = [ToolConfig(tool_name=t) for t in tool_names]

            # Build system prompt
            system_prompt = _build_smart_prompt(name, description, analysis)

            # Personality — use template if matched, user override if provided
            if personality:
                agent_personality = personality
            elif template_match:
                agent_personality = template_match.get("personality", "")
            else:
                agent_personality = f"Expert, proactive, and helpful — specialized in everything related to: {description[:100]}"

            # Greeting
            if template_match:
                greeting = template_match.get("greeting", f"Hi! I'm {name}. {description}. How can I help?")
            else:
                greeting = f"Hi! I'm {name}. I specialize in: {description}. What would you like to work on?"

            # Brain boxes
            brain_boxes = analysis["brain_boxes"]

            # Trigger
            trigger_type = TriggerType.SCHEDULED if schedule else TriggerType.MANUAL
            trigger = AgentTrigger(
                type=trigger_type,
                cron=schedule or None,
            )

            agent = AgentConfig(
                name=name,
                description=description,
                system_prompt=system_prompt,
                personality=agent_personality,
                greeting=greeting,
                tools=tool_list,
                brain_boxes=brain_boxes,
                trigger=trigger,
                category=analysis["category"],
                created_by=user_id,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                metadata={
                    "type": "smart_agent",
                    "auto_configured": True,
                    "matched_template": template_match["name"] if template_match else None,
                },
            )

            agent_data = agent.to_dict()
            agent_data["user_id"] = user_id
            agent_id = await store.save_agent(user_id, agent_data)

            return {
                "success": True,
                "agent_id": agent_id,
                "name": name,
                "description": description,
                "category": analysis["category"],
                "tools_assigned": tool_names,
                "tools_count": len(tool_names),
                "brain_boxes": brain_boxes,
                "personality": agent_personality,
                "scheduled": bool(schedule),
                "template_matched": template_match["name"] if template_match else None,
                "message": (
                    f"Agent '{name}' created with {len(tool_names)} tools and "
                    f"{len(brain_boxes)} memory modules. "
                    f"Chat with it at /agents/{agent_id}/chat"
                    f"{f' — runs automatically on schedule: {schedule}' if schedule else ''}."
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_agent_templates() -> dict:
        """List all pre-built agent templates that users can deploy instantly.

        Shows ready-made agents for common use cases: real estate, fitness,
        cooking, travel, investments, content creation, pet training, and more.

        Use this when users want to see what's available or need inspiration.
        """
        templates = []
        for template_id, tmpl in AGENT_TEMPLATES.items():
            templates.append({
                "id": template_id,
                "name": tmpl["name"],
                "description": tmpl["description"],
                "category": tmpl["category"],
                "tools_count": len(tmpl["tools"]),
                "personality": tmpl["personality"],
            })

        # Group by category
        by_category = {}
        for t in templates:
            cat = t["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(t)

        return {
            "templates": templates,
            "by_category": by_category,
            "total": len(templates),
            "categories": list(by_category.keys()),
            "guidance": (
                "Present these templates organized by category. "
                "When the user picks one, use deploy_agent_template to create it instantly. "
                "Users can also describe any custom agent and use create_smart_agent."
            ),
        }

    @tool
    async def deploy_agent_template(
        user_id: str,
        template_id: str,
        custom_name: str = "",
        custom_instructions: str = "",
        schedule: str = "",
    ) -> dict:
        """Deploy a pre-built agent template instantly.

        Creates a fully configured agent from a template — ready to use immediately.

        Args:
            user_id: Agent owner
            template_id: Template ID from list_agent_templates
            custom_name: Override the default name (optional)
            custom_instructions: Additional instructions to customize the agent (optional)
            schedule: Optional cron schedule for autonomous operation
        """
        from tova_core.models.agent import AgentConfig, AgentTrigger, TriggerType, ToolConfig

        try:
            template = AGENT_TEMPLATES.get(template_id)
            if not template:
                return {
                    "error": f"Template '{template_id}' not found",
                    "available": list(AGENT_TEMPLATES.keys()),
                }

            name = custom_name or template["name"]
            tool_list = [ToolConfig(tool_name=t) for t in template["tools"]]
            brain_boxes = template["brain_boxes"]

            # Build prompt
            prompt_parts = [
                f"You are {name}, a specialized AI agent.",
                f"\n## Your Purpose\n{template['description']}",
            ]
            if template.get("prompt_additions"):
                prompt_parts.append(f"\n## Expert Knowledge\n{template['prompt_additions']}")
            if custom_instructions:
                prompt_parts.append(f"\n## Custom Instructions\n{custom_instructions}")
            prompt_parts.append(
                "\n## Core Behaviors\n"
                "- ALWAYS search the web for current information\n"
                "- NEVER say 'I don't know' — always find a way\n"
                "- Be proactive and suggest next steps\n"
                "- Remember context across conversations\n"
                "- Create structured outputs when appropriate"
            )

            trigger_type = TriggerType.SCHEDULED if schedule else TriggerType.MANUAL
            trigger = AgentTrigger(type=trigger_type, cron=schedule or None)

            agent = AgentConfig(
                name=name,
                description=template["description"],
                system_prompt="\n".join(prompt_parts),
                personality=template["personality"],
                greeting=template["greeting"],
                tools=tool_list,
                brain_boxes=brain_boxes,
                trigger=trigger,
                category=template["category"],
                created_by=user_id,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                metadata={
                    "type": "template_agent",
                    "template_id": template_id,
                },
            )

            agent_data = agent.to_dict()
            agent_data["user_id"] = user_id
            agent_id = await store.save_agent(user_id, agent_data)

            return {
                "success": True,
                "agent_id": agent_id,
                "name": name,
                "template": template_id,
                "description": template["description"],
                "tools_count": len(template["tools"]),
                "brain_boxes": brain_boxes,
                "message": (
                    f"Agent '{name}' deployed from template '{template_id}'! "
                    f"Chat with it at /agents/{agent_id}/chat"
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def customize_agent(
        user_id: str,
        agent_id: str,
        add_tools: str = "",
        remove_tools: str = "",
        add_brain_boxes: str = "",
        new_personality: str = "",
        additional_instructions: str = "",
        schedule: str = "",
    ) -> dict:
        """Customize an existing agent — add/remove tools, change personality, add instructions.

        Use this to fine-tune any agent after creation.

        Args:
            user_id: Agent owner
            agent_id: ID of the agent to customize
            add_tools: Comma-separated tool names to add
            remove_tools: Comma-separated tool names to remove
            add_brain_boxes: Comma-separated brain box features to add
            new_personality: New personality description (replaces existing)
            additional_instructions: Extra instructions to append to the system prompt
            schedule: New cron schedule (empty string to keep current, "none" to disable)
        """
        from tova_core.models.agent import AgentConfig, AgentTrigger, TriggerType, ToolConfig

        try:
            agent_data = await store.get_agent(agent_id)
            if not agent_data:
                return {"error": f"Agent '{agent_id}' not found"}
            if agent_data.get("created_by") != user_id and agent_data.get("user_id") != user_id:
                return {"error": "You don't own this agent"}

            agent = AgentConfig.from_dict(agent_data)
            changes = []

            # Add tools
            if add_tools:
                existing = set(agent.get_tool_names())
                for t in add_tools.split(","):
                    t = t.strip()
                    if t and t not in existing:
                        agent.tools.append(ToolConfig(tool_name=t))
                        changes.append(f"Added tool: {t}")

            # Remove tools
            if remove_tools:
                remove_set = {t.strip() for t in remove_tools.split(",") if t.strip()}
                agent.tools = [t for t in agent.tools if t.tool_name not in remove_set]
                changes.append(f"Removed tools: {', '.join(remove_set)}")

            # Add brain boxes
            if add_brain_boxes:
                for b in add_brain_boxes.split(","):
                    b = b.strip()
                    if b and b not in agent.brain_boxes:
                        agent.brain_boxes.append(b)
                        changes.append(f"Added memory: {b}")

            # Personality
            if new_personality:
                agent.personality = new_personality
                changes.append("Updated personality")

            # Additional instructions
            if additional_instructions:
                agent.system_prompt += f"\n\n## Additional Instructions\n{additional_instructions}"
                changes.append("Added custom instructions")

            # Schedule
            if schedule:
                if schedule.lower() == "none":
                    agent.trigger = AgentTrigger(type=TriggerType.MANUAL)
                    changes.append("Disabled schedule")
                else:
                    agent.trigger = AgentTrigger(type=TriggerType.SCHEDULED, cron=schedule)
                    changes.append(f"Set schedule: {schedule}")

            agent.updated_at = datetime.now().isoformat()

            # Save back
            updated_data = agent.to_dict()
            updated_data["user_id"] = user_id
            updated_data["id"] = agent_id
            await store.save_agent(user_id, updated_data)

            return {
                "success": True,
                "agent_id": agent_id,
                "name": agent.name,
                "changes": changes,
                "tools_count": len(agent.get_tool_names()),
                "brain_boxes": agent.brain_boxes,
                "message": f"Agent '{agent.name}' updated: {', '.join(changes)}.",
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def create_agent_for_user(
        user_id: str,
        name: str,
        description: str,
        system_prompt: str,
        personality: str = "",
        greeting: str = "",
        tools: str = "",
        brain_boxes: str = "",
        trigger_type: str = "manual",
        trigger_cron: str = "",
    ) -> dict:
        """Create a fully custom AI agent with explicit configuration.

        Use this ONLY when the user wants manual control over every detail.
        For most cases, use create_smart_agent instead — it auto-configures everything.

        Args:
            user_id: The user who will own this agent
            name: Agent name
            description: What this agent does
            system_prompt: The agent's core instructions
            personality: Short personality description
            greeting: First message when conversation starts
            tools: Comma-separated tool names
            brain_boxes: Comma-separated feature memory namespaces
            trigger_type: manual, scheduled, event
            trigger_cron: Cron expression if trigger_type=scheduled
        """
        from tova_core.models.agent import AgentConfig, AgentTrigger, TriggerType, ToolConfig

        try:
            tool_list = [
                ToolConfig(tool_name=t.strip())
                for t in tools.split(",") if t.strip()
            ] if tools else []

            brain_list = [b.strip() for b in brain_boxes.split(",") if b.strip()] if brain_boxes else []

            trigger = AgentTrigger(
                type=TriggerType(trigger_type),
                cron=trigger_cron or None,
            )

            agent = AgentConfig(
                name=name,
                description=description,
                system_prompt=system_prompt,
                personality=personality,
                greeting=greeting,
                tools=tool_list,
                brain_boxes=brain_list,
                trigger=trigger,
                created_by=user_id,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )

            agent_data = agent.to_dict()
            agent_data["user_id"] = user_id
            agent_id = await store.save_agent(user_id, agent_data)

            return {
                "success": True,
                "agent_id": agent_id,
                "name": name,
                "description": description,
                "tools_count": len(tool_list),
                "brain_boxes": brain_list,
                "trigger_type": trigger_type,
                "message": f"Agent '{name}' created! Chat at /agents/{agent_id}/chat",
            }
        except NotImplementedError:
            return {"error": "Agent storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_available_tools() -> dict:
        """List all available tools that can be given to agents.

        Use this to see what capabilities are available in the system.
        """
        if not tool_registry:
            return {"tools": [], "note": "Tool registry not configured"}

        catalog = tool_registry.to_catalog()
        flat_tools = []
        for category_group in catalog:
            cat = category_group.get("category", "general")
            for t in category_group.get("tools", []):
                flat_tools.append({
                    "name": t.get("name", ""),
                    "description": t.get("description", "")[:100],
                    "category": cat,
                })

        return {"tools": flat_tools, "count": len(flat_tools)}

    @tool
    async def train_with_data(
        user_id: str,
        data: str,
        data_type: str = "json",
        feature: str = "general",
        description: str = "",
    ) -> dict:
        """Train Tova or any agent with new data. The data is stored in Brain Box memory
        and available for all future conversations.

        Accepts any format: JSON, arrays, key-value text, plain text, CSV.

        Args:
            user_id: The user providing the training data
            data: The data to learn from (JSON, text, CSV, key-value pairs)
            data_type: Format hint: json, text, csv, key_value
            feature: Which feature area: general, todos, email, events, etc.
            description: What this data represents
        """
        if not self_learner:
            from tova_core.learning.storage import get_brain_store
            brain = get_brain_store()
            ns = f"brain_{feature}"

            try:
                parsed = json.loads(data) if data_type == "json" else data
            except json.JSONDecodeError:
                parsed = data

            count = 0
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    v_str = json.dumps(v, default=str) if not isinstance(v, str) else v
                    await brain.save(namespace=ns, user_id=user_id, key=k, value=v_str,
                               category="fact", metadata={"source": "user_training", "description": description})
                    count += 1
            elif isinstance(parsed, list):
                for i, item in enumerate(parsed):
                    key = str(item.get("name", item.get("id", f"item_{i}"))) if isinstance(item, dict) else f"item_{i}"
                    val = json.dumps(item, default=str) if isinstance(item, dict) else str(item)
                    await brain.save(namespace=ns, user_id=user_id, key=key, value=val,
                               category="fact", metadata={"source": "user_training"})
                    count += 1
            else:
                lines = [l.strip() for l in str(parsed).split("\n") if l.strip()]
                for i, line in enumerate(lines):
                    for sep in [":", "=", " - "]:
                        if sep in line:
                            parts = line.split(sep, 1)
                            await brain.save(namespace=ns, user_id=user_id,
                                       key=parts[0].strip(), value=parts[1].strip(),
                                       category="fact", metadata={"source": "user_training"})
                            count += 1
                            break
                    else:
                        await brain.save(namespace=ns, user_id=user_id,
                                   key=f"knowledge_{i}", value=line,
                                   category="fact", metadata={"source": "user_training"})
                        count += 1

            return {
                "success": True,
                "items_learned": count,
                "feature": feature,
                "message": f"Learned {count} items. Available in all future conversations.",
            }

        try:
            parsed = json.loads(data) if data_type == "json" else data
        except json.JSONDecodeError:
            parsed = data

        result = await self_learner.learn_from_data(
            user_id=user_id, data=parsed, data_type=data_type, feature=feature,
        )

        return {
            "success": True,
            "items_learned": result.get("items_learned", 0),
            "feature": feature,
            "message": f"Learned {result.get('items_learned', 0)} items.",
        }

    @tool
    async def recall_training(
        user_id: str,
        feature: str = "general",
        query: str = "",
    ) -> dict:
        """Recall what has been learned/trained for a specific feature.

        Args:
            user_id: The user whose training data to recall
            feature: Which feature area to check
            query: Optional search query to find specific knowledge
        """
        from tova_core.learning.storage import get_brain_store
        brain = get_brain_store()
        ns = f"brain_{feature}"

        if query:
            memories = await brain.search(ns, user_id, query)
        else:
            memories = await brain.load(ns, user_id)

        return {
            "feature": feature,
            "memories": [
                {"key": m.get("key", ""), "value": m.get("value", ""), "category": m.get("category", "")}
                for m in memories
            ],
            "count": len(memories),
        }

    @tool
    async def correct_knowledge(
        user_id: str,
        wrong_info: str,
        correct_info: str,
        feature: str = "general",
    ) -> dict:
        """Correct something an agent got wrong. Corrections are permanent
        and always override previous knowledge.

        Args:
            user_id: The user providing the correction
            wrong_info: What was wrong
            correct_info: What the correct information is
            feature: Which feature area
        """
        from tova_core.learning.storage import get_brain_store
        brain = get_brain_store()

        await brain.save(
            namespace=f"brain_{feature}",
            user_id=user_id,
            key=f"correction_{wrong_info[:50].replace(' ', '_')}",
            value=f"WRONG: {wrong_info} → CORRECT: {correct_info}",
            category="correction",
            relevance_score=1.0,
            metadata={"permanent": True, "source": "user_correction"},
        )

        return {
            "success": True,
            "message": "Correction stored permanently.",
            "wrong": wrong_info,
            "correct": correct_info,
        }

    @tool
    async def list_user_agents(user_id: str) -> dict:
        """List all agents created for/by a user.

        Args:
            user_id: The user whose agents to list
        """
        try:
            agents = await store.list_agents(user_id)
            return {
                "agents": [
                    {
                        "id": a.get("id", ""),
                        "name": a.get("name", ""),
                        "description": a.get("description", ""),
                        "category": a.get("category", "general"),
                        "status": a.get("status", "active"),
                        "tools": [t.get("tool_name", "") for t in a.get("tools", [])],
                        "brain_boxes": a.get("brain_boxes", []),
                        "trigger_type": a.get("trigger", {}).get("type", "manual"),
                        "type": a.get("metadata", {}).get("type", "custom"),
                    }
                    for a in agents
                ],
                "count": len(agents),
            }
        except NotImplementedError:
            return {"agents": [], "count": 0}
        except Exception as e:
            return {"error": str(e)}

    return [
        create_smart_agent,
        list_agent_templates,
        deploy_agent_template,
        customize_agent,
        create_agent_for_user,
        list_available_tools,
        train_with_data,
        recall_training,
        correct_knowledge,
        list_user_agents,
    ]
