"""
Workforce Engine — multi-agent orchestration for organizations.

Enables Tova to create, manage, and orchestrate teams of AI agents that
work together to accomplish complex organizational workflows.

Architecture:
    WorkforceEngine
    ├── Agent Registry (all agents for an org/user)
    ├── Workflow Engine (chains, parallel, conditional)
    ├── Task Queue (assign, execute, track)
    ├── Delegation (agent-to-agent handoff)
    └── Execution Monitor (status, logs, retries)

Design patterns:
    - DAG-based workflow execution (like Airflow, but for AI agents)
    - Event-driven delegation (agent A finishes → triggers agent B)
    - Parallel fan-out/fan-in (multiple agents work simultaneously)
    - Hierarchical supervision (manager agents oversee worker agents)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Any

from tova_core.models.agent import AgentConfig, AgentStatus, AgentTrigger, TriggerType, ToolConfig
from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)


# ── Workflow Models ────────────────────────────────────────────────


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING = "waiting"  # Waiting on dependency


class WorkflowStepType(str, Enum):
    AGENT = "agent"           # Run an agent
    PARALLEL = "parallel"     # Run multiple agents in parallel
    CONDITION = "condition"   # Branch based on previous output
    HUMAN = "human"           # Wait for human approval
    TRANSFORM = "transform"   # Transform data between steps


@dataclass
class TaskAssignment:
    """A single task assigned to an agent."""
    id: str = ""
    agent_id: str = ""
    agent_name: str = ""
    instruction: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0  # 0=normal, 1=high, 2=urgent
    depends_on: list[str] = field(default_factory=list)  # Task IDs this depends on
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    retries: int = 0
    max_retries: int = 2

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "instruction": self.instruction,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "status": self.status.value,
            "priority": self.priority,
            "depends_on": self.depends_on,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "retries": self.retries,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaskAssignment:
        return cls(
            id=data.get("id", ""),
            agent_id=data.get("agent_id", ""),
            agent_name=data.get("agent_name", ""),
            instruction=data.get("instruction", ""),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            status=TaskStatus(data.get("status", "pending")),
            priority=data.get("priority", 0),
            depends_on=data.get("depends_on", []),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            error=data.get("error", ""),
            retries=data.get("retries", 0),
            max_retries=data.get("max_retries", 2),
        )


@dataclass
class WorkflowStep:
    """A step in a workflow definition."""
    id: str = ""
    name: str = ""
    type: WorkflowStepType = WorkflowStepType.AGENT
    agent_id: str = ""           # For AGENT type
    agent_role: str = ""         # For dynamic agent selection by role
    instruction: str = ""
    parallel_steps: list[dict] = field(default_factory=list)  # For PARALLEL type
    condition: str = ""          # For CONDITION type
    branches: dict[str, str] = field(default_factory=dict)    # condition_value → next_step_id
    depends_on: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    output_key: str = ""         # Key to store output in workflow context

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "instruction": self.instruction,
            "parallel_steps": self.parallel_steps,
            "condition": self.condition,
            "branches": self.branches,
            "depends_on": self.depends_on,
            "timeout_seconds": self.timeout_seconds,
            "output_key": self.output_key,
        }


@dataclass
class WorkflowDefinition:
    """A reusable workflow template."""
    id: str = ""
    name: str = ""
    description: str = ""
    category: str = "general"    # hr, finance, marketing, engineering, sales, ops, custom
    steps: list[WorkflowStep] = field(default_factory=list)
    input_schema: dict[str, str] = field(default_factory=dict)  # Expected inputs
    created_by: str = ""
    created_at: str = ""
    org_id: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "steps": [s.to_dict() for s in self.steps],
            "input_schema": self.input_schema,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "org_id": self.org_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> WorkflowDefinition:
        steps = []
        for s in data.get("steps", []):
            steps.append(WorkflowStep(
                id=s.get("id", ""),
                name=s.get("name", ""),
                type=WorkflowStepType(s.get("type", "agent")),
                agent_id=s.get("agent_id", ""),
                agent_role=s.get("agent_role", ""),
                instruction=s.get("instruction", ""),
                parallel_steps=s.get("parallel_steps", []),
                condition=s.get("condition", ""),
                branches=s.get("branches", {}),
                depends_on=s.get("depends_on", []),
                timeout_seconds=s.get("timeout_seconds", 300),
                output_key=s.get("output_key", ""),
            ))
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            steps=steps,
            input_schema=data.get("input_schema", {}),
            created_by=data.get("created_by", ""),
            created_at=data.get("created_at", ""),
            org_id=data.get("org_id", ""),
        )


@dataclass
class WorkflowExecution:
    """A running instance of a workflow."""
    id: str = ""
    workflow_id: str = ""
    workflow_name: str = ""
    status: TaskStatus = TaskStatus.PENDING
    current_step: str = ""
    context: dict[str, Any] = field(default_factory=dict)  # Shared state across steps
    tasks: list[TaskAssignment] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    started_by: str = ""
    org_id: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "current_step": self.current_step,
            "context": self.context,
            "tasks": [t.to_dict() for t in self.tasks],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "started_by": self.started_by,
            "org_id": self.org_id,
            "error": self.error,
        }


# ── Industry Workflow Templates ────────────────────────────────────


INDUSTRY_TEMPLATES: dict[str, dict] = {
    # ── HR ──
    "employee_onboarding": {
        "name": "Employee Onboarding",
        "description": "Automated new hire onboarding: collect docs, set up accounts, assign training, schedule orientation",
        "category": "hr",
        "roles": ["HR Coordinator", "IT Setup Agent", "Training Agent", "Compliance Agent"],
        "steps": [
            {"name": "Collect employee details", "role": "HR Coordinator", "instruction": "Collect the new employee's full name, role, department, start date, and emergency contacts. Verify all required documents (ID, tax forms, bank details)."},
            {"name": "Provision accounts", "role": "IT Setup Agent", "instruction": "Create email account, Slack workspace access, and all required software licenses for the new employee based on their role and department."},
            {"name": "Assign training modules", "role": "Training Agent", "instruction": "Based on the employee's role and department, assign the appropriate onboarding training modules, compliance courses, and set deadlines."},
            {"name": "Compliance verification", "role": "Compliance Agent", "instruction": "Verify all legal documents are signed, background check is complete, and regulatory requirements are met for the employee's role."},
        ],
    },
    "leave_management": {
        "name": "Leave Request Processing",
        "description": "Automated leave request: validate balance, check team coverage, approve/escalate, update calendar",
        "category": "hr",
        "roles": ["Leave Processor", "Coverage Checker"],
        "steps": [
            {"name": "Validate leave request", "role": "Leave Processor", "instruction": "Check the employee's leave balance, validate dates, ensure no blackout periods, and verify the leave type is appropriate."},
            {"name": "Check team coverage", "role": "Coverage Checker", "instruction": "Verify that the team has adequate coverage during the requested leave period. Flag if too many team members are off simultaneously."},
        ],
    },
    # ── Finance ──
    "invoice_processing": {
        "name": "Invoice Processing",
        "description": "Automated invoice workflow: extract data, validate, match PO, route for approval, schedule payment",
        "category": "finance",
        "roles": ["Invoice Extractor", "Validator", "Approval Router", "Payment Scheduler"],
        "steps": [
            {"name": "Extract invoice data", "role": "Invoice Extractor", "instruction": "Extract vendor name, invoice number, line items, amounts, tax, and total from the uploaded invoice document."},
            {"name": "Validate and match", "role": "Validator", "instruction": "Validate invoice amounts, check for duplicates, and match against purchase orders. Flag discrepancies."},
            {"name": "Route for approval", "role": "Approval Router", "instruction": "Based on the invoice amount and department, route to the appropriate approver. Under $1000 auto-approve, $1000-$10000 manager, above $10000 director."},
            {"name": "Schedule payment", "role": "Payment Scheduler", "instruction": "Once approved, schedule payment according to the vendor's payment terms and the company's payment cycle."},
        ],
    },
    "expense_reporting": {
        "name": "Expense Report Processing",
        "description": "Automated expense reports: categorize, validate receipts, check policy, approve, reimburse",
        "category": "finance",
        "roles": ["Expense Categorizer", "Policy Checker", "Approver"],
        "steps": [
            {"name": "Categorize expenses", "role": "Expense Categorizer", "instruction": "Review submitted expenses, categorize each item (travel, meals, supplies, etc.), extract amounts and dates from receipts."},
            {"name": "Policy compliance check", "role": "Policy Checker", "instruction": "Verify each expense against company policy — check per-diem limits, receipt requirements, approved vendors, and flagged categories."},
            {"name": "Approve and process", "role": "Approver", "instruction": "Review the categorized and validated expense report. Approve compliant items, flag violations, and submit for reimbursement."},
        ],
    },
    # ── Marketing ──
    "content_pipeline": {
        "name": "Content Creation Pipeline",
        "description": "End-to-end content: research → write → edit → design brief → publish",
        "category": "marketing",
        "roles": ["Researcher", "Content Writer", "Editor", "Publisher"],
        "steps": [
            {"name": "Research topic", "role": "Researcher", "instruction": "Research the assigned topic thoroughly. Gather key facts, statistics, competitor content, trending angles, and SEO keywords."},
            {"name": "Write content", "role": "Content Writer", "instruction": "Using the research, write engaging content optimized for the target platform (blog, social, email). Include CTAs and follow brand voice guidelines."},
            {"name": "Edit and optimize", "role": "Editor", "instruction": "Review content for grammar, clarity, brand voice, SEO optimization, and factual accuracy. Suggest improvements and approve for publishing."},
            {"name": "Publish and distribute", "role": "Publisher", "instruction": "Format the approved content for the target platform, schedule publishing, set up tracking links, and distribute across channels."},
        ],
    },
    "campaign_management": {
        "name": "Marketing Campaign Management",
        "description": "Campaign lifecycle: plan → create assets → launch → monitor → report",
        "category": "marketing",
        "roles": ["Campaign Planner", "Creative Agent", "Analytics Agent"],
        "steps": [
            {"name": "Plan campaign", "role": "Campaign Planner", "instruction": "Define campaign objectives, target audience, channels, budget allocation, timeline, and success metrics (KPIs)."},
            {"name": "Create assets", "role": "Creative Agent", "instruction": "Generate ad copy, email templates, social media posts, and landing page content based on the campaign plan. Follow brand guidelines."},
            {"name": "Monitor and optimize", "role": "Analytics Agent", "instruction": "Track campaign performance across channels. Analyze metrics (CTR, conversion, CPA), identify winning variants, and recommend optimizations."},
        ],
    },
    # ── Sales ──
    "lead_qualification": {
        "name": "Lead Qualification Pipeline",
        "description": "Automated lead scoring: enrich data, score leads, prioritize, assign to reps",
        "category": "sales",
        "roles": ["Lead Enricher", "Lead Scorer", "Assignment Agent"],
        "steps": [
            {"name": "Enrich lead data", "role": "Lead Enricher", "instruction": "Research the lead's company, role, company size, industry, and recent news. Enrich the CRM record with LinkedIn, website, and funding data."},
            {"name": "Score and qualify", "role": "Lead Scorer", "instruction": "Score the lead based on ICP fit, engagement signals, company size, budget indicators, and timing. Classify as hot/warm/cold."},
            {"name": "Assign to rep", "role": "Assignment Agent", "instruction": "Based on lead score, territory, industry, and rep capacity, assign the lead to the best-fit sales rep. Send notification with lead brief."},
        ],
    },
    # ── Engineering ──
    "code_review_pipeline": {
        "name": "Code Review & Deploy",
        "description": "Automated code review: lint, test, security scan, review, deploy",
        "category": "engineering",
        "roles": ["Code Analyzer", "Security Scanner", "Deploy Agent"],
        "steps": [
            {"name": "Analyze code quality", "role": "Code Analyzer", "instruction": "Run static analysis, check code style, identify complexity issues, test coverage gaps, and potential bugs in the submitted code changes."},
            {"name": "Security scan", "role": "Security Scanner", "instruction": "Scan for security vulnerabilities — SQL injection, XSS, hardcoded secrets, dependency vulnerabilities, and OWASP top 10 issues."},
            {"name": "Deploy", "role": "Deploy Agent", "instruction": "If all checks pass, deploy to staging environment. Run integration tests. If staging passes, promote to production with rollback plan."},
        ],
    },
    # ── Customer Support ──
    "ticket_triage": {
        "name": "Support Ticket Triage",
        "description": "Automated ticket handling: classify, prioritize, route, suggest resolution",
        "category": "support",
        "roles": ["Ticket Classifier", "Resolution Agent", "Escalation Agent"],
        "steps": [
            {"name": "Classify ticket", "role": "Ticket Classifier", "instruction": "Analyze the support ticket content. Classify by type (bug, feature request, billing, how-to), severity (critical/high/medium/low), and product area."},
            {"name": "Suggest resolution", "role": "Resolution Agent", "instruction": "Search knowledge base for similar issues. Draft a response with the solution. If no solution exists, prepare escalation summary."},
            {"name": "Escalate if needed", "role": "Escalation Agent", "instruction": "For unresolved or critical tickets, escalate to the appropriate team lead with full context, attempted solutions, and recommended next steps."},
        ],
    },
    # ── Operations ──
    "procurement": {
        "name": "Procurement Workflow",
        "description": "Purchase request: spec → vendor search → compare quotes → approve → order",
        "category": "operations",
        "roles": ["Spec Analyst", "Vendor Finder", "Procurement Manager"],
        "steps": [
            {"name": "Analyze requirements", "role": "Spec Analyst", "instruction": "Review the purchase request. Clarify specifications, quantities, delivery timeline, and budget constraints."},
            {"name": "Find vendors", "role": "Vendor Finder", "instruction": "Search for qualified vendors. Request quotes, compare pricing, delivery times, and reliability ratings. Present top 3 options."},
            {"name": "Approve and order", "role": "Procurement Manager", "instruction": "Review vendor comparison. Select the best option based on price, quality, and delivery. Generate purchase order and track delivery."},
        ],
    },
}


# ── Workforce Engine ───────────────────────────────────────────────


class WorkforceEngine:
    """Orchestrates teams of AI agents to accomplish organizational workflows.

    The engine:
    1. Creates specialized agents from role descriptions
    2. Builds workflow DAGs from templates or custom definitions
    3. Executes workflows — sequential, parallel, or conditional
    4. Delegates tasks between agents
    5. Monitors execution and handles failures
    """

    def __init__(self, store: BaseStore, agent_runtime: object | None = None):
        self.store = store
        self.agent_runtime = agent_runtime
        self._executions: dict[str, WorkflowExecution] = {}

    # ── Agent Factory ──────────────────────────────────────────

    async def create_workforce_agent(
        self,
        user_id: str,
        name: str,
        role: str,
        department: str = "general",
        capabilities: list[str] | None = None,
        tools: list[str] | None = None,
        workflow_instructions: str = "",
    ) -> AgentConfig:
        """Create a specialized workforce agent for an organization.

        The agent is built with:
        - A role-specific system prompt
        - Appropriate tools for its function
        - Workflow awareness (knows its place in the pipeline)
        """
        # Build role-specific system prompt
        system_prompt = self._build_role_prompt(name, role, department, capabilities, workflow_instructions)

        # Auto-select tools based on role/department
        tool_list = list(tools or [])
        if not tool_list:
            tool_list = self._suggest_tools_for_role(role, department)

        # Always include web search and file tools for workforce agents
        essential_tools = ["search_web", "extract_file_content", "list_files"]
        for et in essential_tools:
            if et not in tool_list:
                tool_list.append(et)

        agent = AgentConfig(
            name=name,
            description=f"{role} — {department} department",
            system_prompt=system_prompt,
            personality=f"Professional, efficient, detail-oriented {role.lower()}",
            greeting=f"I'm {name}, your {role}. How can I help?",
            tools=[ToolConfig(tool_name=t) for t in tool_list],
            brain_boxes=self._suggest_brain_boxes(department),
            trigger=AgentTrigger(type=TriggerType.EVENT),
            category=department,
            created_by=user_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            metadata={
                "role": role,
                "department": department,
                "capabilities": capabilities or [],
                "type": "workforce",
            },
        )

        # Persist
        agent_data = agent.to_dict()
        agent_data["user_id"] = user_id
        agent_id = await self.store.save_agent(user_id, agent_data)
        agent.id = agent_id

        return agent

    def _build_role_prompt(
        self,
        name: str,
        role: str,
        department: str,
        capabilities: list[str] | None,
        workflow_instructions: str,
    ) -> str:
        parts = [
            f"You are {name}, a specialized AI {role} in the {department} department.",
            f"\n## Your Role\nYou are a {role}. You work as part of an AI workforce that handles "
            f"organizational tasks autonomously. You are professional, thorough, and results-oriented.",
        ]

        if capabilities:
            parts.append(
                "\n## Your Capabilities\n" +
                "\n".join(f"- {c}" for c in capabilities)
            )

        if workflow_instructions:
            parts.append(f"\n## Workflow Instructions\n{workflow_instructions}")

        parts.append(
            "\n## Rules\n"
            "- Complete tasks thoroughly — don't leave work half-done\n"
            "- When you need information, use your tools to search for it\n"
            "- Provide structured, actionable output that the next agent or human can act on\n"
            "- If you encounter a blocker, clearly describe the issue and what's needed to resolve it\n"
            "- Always include your reasoning and sources\n"
            "- NEVER say 'I don't know' — search the web if you're unsure\n"
            "- Format output as structured data when appropriate (JSON, tables, bullet points)"
        )

        return "\n".join(parts)

    def _suggest_tools_for_role(self, role: str, department: str) -> list[str]:
        """Auto-suggest tools based on the agent's role and department."""
        role_lower = role.lower()
        dept_lower = department.lower()

        tools = []

        # Department-specific tools
        dept_tools = {
            "hr": ["create_todo", "list_todos", "create_event", "send_email", "create_note"],
            "finance": ["extract_file_content", "create_note", "create_todo", "search_web"],
            "marketing": ["search_web", "create_note", "send_email", "create_todo"],
            "sales": ["search_web", "send_email", "create_todo", "create_event", "create_note"],
            "engineering": ["extract_file_content", "list_files", "create_note", "search_web"],
            "support": ["search_web", "send_email", "create_note", "create_todo"],
            "operations": ["search_web", "create_todo", "create_note", "create_event"],
        }
        tools.extend(dept_tools.get(dept_lower, ["search_web", "create_note"]))

        # Role-specific additions
        if any(w in role_lower for w in ["writer", "content", "editor", "creative"]):
            tools.extend(["search_web", "create_note"])
        if any(w in role_lower for w in ["analyst", "data", "research"]):
            tools.extend(["search_web", "extract_file_content", "query_dataset"])
        if any(w in role_lower for w in ["email", "outreach", "communication"]):
            tools.extend(["send_email", "draft_email", "list_emails"])
        if any(w in role_lower for w in ["scheduler", "calendar", "coordinator"]):
            tools.extend(["create_event", "list_events"])
        if any(w in role_lower for w in ["monitor", "security", "surveillance"]):
            tools.extend(["list_cameras", "get_camera_snapshot"])
        if any(w in role_lower for w in ["fleet", "vehicle", "logistics"]):
            tools.extend(["get_vehicle_position", "fleet_overview"])

        return list(dict.fromkeys(tools))  # Deduplicate preserving order

    def _suggest_brain_boxes(self, department: str) -> list[str]:
        dept_lower = department.lower()
        mapping = {
            "hr": ["todos", "events", "notes"],
            "finance": ["notes", "datasets"],
            "marketing": ["notes", "email"],
            "sales": ["email", "events", "notes"],
            "engineering": ["notes", "files", "datasets"],
            "support": ["email", "notes", "todos"],
            "operations": ["todos", "notes", "events"],
        }
        return mapping.get(dept_lower, ["notes", "todos"])

    # ── Workflow Builder ───────────────────────────────────────

    async def create_workflow_from_template(
        self,
        user_id: str,
        template_id: str,
        org_id: str = "",
        customizations: dict | None = None,
    ) -> WorkflowDefinition:
        """Create a workflow from an industry template."""
        template = INDUSTRY_TEMPLATES.get(template_id)
        if not template:
            raise ValueError(f"Unknown template: {template_id}. Available: {list(INDUSTRY_TEMPLATES.keys())}")

        steps = []
        for i, step_data in enumerate(template["steps"]):
            steps.append(WorkflowStep(
                id=f"step_{i+1}",
                name=step_data["name"],
                type=WorkflowStepType.AGENT,
                agent_role=step_data["role"],
                instruction=step_data["instruction"],
                depends_on=[f"step_{i}"] if i > 0 else [],
                output_key=f"step_{i+1}_output",
            ))

        workflow = WorkflowDefinition(
            id=str(uuid.uuid4())[:8],
            name=template["name"],
            description=template["description"],
            category=template["category"],
            steps=steps,
            created_by=user_id,
            created_at=datetime.now().isoformat(),
            org_id=org_id,
        )

        # Persist
        try:
            await self.store.save_todo(user_id, {
                "title": f"Workflow: {workflow.name}",
                "description": json.dumps(workflow.to_dict()),
                "category": "workflow",
                "status": "active",
                "metadata": {"type": "workflow_definition", "workflow_id": workflow.id},
            })
        except (NotImplementedError, Exception) as e:
            logger.warning(f"Could not persist workflow: {e}")

        return workflow

    async def create_custom_workflow(
        self,
        user_id: str,
        name: str,
        description: str,
        steps: list[dict],
        category: str = "custom",
        org_id: str = "",
    ) -> WorkflowDefinition:
        """Create a custom workflow from user-defined steps."""
        workflow_steps = []
        for i, s in enumerate(steps):
            workflow_steps.append(WorkflowStep(
                id=s.get("id", f"step_{i+1}"),
                name=s.get("name", f"Step {i+1}"),
                type=WorkflowStepType(s.get("type", "agent")),
                agent_id=s.get("agent_id", ""),
                agent_role=s.get("role", s.get("agent_role", "")),
                instruction=s.get("instruction", ""),
                parallel_steps=s.get("parallel_steps", []),
                condition=s.get("condition", ""),
                branches=s.get("branches", {}),
                depends_on=s.get("depends_on", [f"step_{i}"] if i > 0 else []),
                output_key=s.get("output_key", f"step_{i+1}_output"),
            ))

        workflow = WorkflowDefinition(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            category=category,
            steps=workflow_steps,
            created_by=user_id,
            created_at=datetime.now().isoformat(),
            org_id=org_id,
        )

        try:
            await self.store.save_todo(user_id, {
                "title": f"Workflow: {workflow.name}",
                "description": json.dumps(workflow.to_dict()),
                "category": "workflow",
                "status": "active",
                "metadata": {"type": "workflow_definition", "workflow_id": workflow.id},
            })
        except (NotImplementedError, Exception) as e:
            logger.warning(f"Could not persist workflow: {e}")

        return workflow

    # ── Workflow Execution ─────────────────────────────────────

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        user_id: str,
        input_data: dict | None = None,
    ) -> WorkflowExecution:
        """Execute a workflow — runs agents step by step.

        For each step:
        1. Find or create the agent for the role
        2. Build the task with context from previous steps
        3. Run the agent via AgentRuntime
        4. Store output in workflow context
        5. Move to next step (or parallel fan-out)
        """
        execution = WorkflowExecution(
            id=str(uuid.uuid4())[:8],
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status=TaskStatus.RUNNING,
            context=dict(input_data or {}),
            started_at=datetime.now().isoformat(),
            started_by=user_id,
            org_id=workflow.org_id,
        )
        self._executions[execution.id] = execution

        try:
            for step in workflow.steps:
                execution.current_step = step.name

                if step.type == WorkflowStepType.PARALLEL:
                    # Fan-out: run parallel steps concurrently
                    parallel_tasks = []
                    for ps in step.parallel_steps:
                        parallel_tasks.append(
                            self._execute_step(user_id, ps, execution)
                        )
                    results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
                    for i, r in enumerate(results):
                        if isinstance(r, dict):
                            key = step.parallel_steps[i].get("output_key", f"parallel_{i}")
                            execution.context[key] = r
                else:
                    result = await self._execute_step(user_id, step.to_dict(), execution)
                    if step.output_key:
                        execution.context[step.output_key] = result

            execution.status = TaskStatus.COMPLETED
            execution.completed_at = datetime.now().isoformat()

        except Exception as e:
            execution.status = TaskStatus.FAILED
            execution.error = str(e)
            logger.error(f"Workflow '{workflow.name}' failed at step '{execution.current_step}': {e}")

        return execution

    async def _execute_step(
        self,
        user_id: str,
        step_data: dict,
        execution: WorkflowExecution,
    ) -> dict:
        """Execute a single workflow step via the AgentRuntime."""
        instruction = step_data.get("instruction", "")
        role = step_data.get("agent_role", step_data.get("role", ""))
        agent_id = step_data.get("agent_id", "")

        # Build context-aware instruction
        context_summary = json.dumps(execution.context, default=str)[:2000]
        full_instruction = (
            f"{instruction}\n\n"
            f"[WORKFLOW CONTEXT: {context_summary}]"
        )

        # Create task record
        task = TaskAssignment(
            id=str(uuid.uuid4())[:8],
            agent_id=agent_id,
            agent_name=role,
            instruction=instruction,
            input_data=execution.context,
            status=TaskStatus.RUNNING,
            created_at=datetime.now().isoformat(),
            started_at=datetime.now().isoformat(),
        )
        execution.tasks.append(task)

        # Execute via runtime
        if self.agent_runtime and agent_id:
            try:
                agent_data = await self.store.get_agent(agent_id)
                if agent_data:
                    agent_config = AgentConfig.from_dict(agent_data)
                    result = await self.agent_runtime.run(
                        agent_config=agent_config,
                        user_message=full_instruction,
                        user_id=user_id,
                    )
                    task.status = TaskStatus.COMPLETED
                    task.output_data = result
                    task.completed_at = datetime.now().isoformat()
                    return result
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                raise

        # Fallback: return the instruction as a pending human task
        task.status = TaskStatus.WAITING
        return {
            "status": "awaiting_execution",
            "step": step_data.get("name", ""),
            "role": role,
            "instruction": instruction,
            "note": "Agent runtime not configured — this step needs manual execution or agent assignment.",
        }

    # ── Task Management ────────────────────────────────────────

    async def delegate_task(
        self,
        user_id: str,
        agent_id: str,
        instruction: str,
        input_data: dict | None = None,
        priority: int = 0,
    ) -> TaskAssignment:
        """Delegate a single task to a specific agent."""
        task = TaskAssignment(
            id=str(uuid.uuid4())[:8],
            agent_id=agent_id,
            instruction=instruction,
            input_data=input_data or {},
            status=TaskStatus.QUEUED,
            priority=priority,
            created_at=datetime.now().isoformat(),
        )

        # Execute immediately if runtime is available
        if self.agent_runtime:
            try:
                agent_data = await self.store.get_agent(agent_id)
                if agent_data:
                    agent_config = AgentConfig.from_dict(agent_data)
                    task.status = TaskStatus.RUNNING
                    task.started_at = datetime.now().isoformat()

                    result = await self.agent_runtime.run(
                        agent_config=agent_config,
                        user_message=instruction,
                        user_id=user_id,
                        context=input_data,
                    )
                    task.status = TaskStatus.COMPLETED
                    task.output_data = result
                    task.completed_at = datetime.now().isoformat()
                    task.agent_name = agent_config.name
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)

        return task

    # ── Workflow Modification ─────────────────────────────────

    async def add_agent_to_workflow(
        self,
        user_id: str,
        workflow_id: str,
        agent_name: str,
        agent_role: str,
        department: str,
        step_name: str,
        instruction: str,
        position: str = "end",
        after_step: str = "",
        capabilities: list[str] | None = None,
        tools: list[str] | None = None,
    ) -> tuple[AgentConfig, WorkflowDefinition]:
        """Add a new agent and step to an existing workflow.

        Creates the agent, then inserts a new step into the workflow definition.

        Args:
            user_id: Workflow owner
            workflow_id: ID of the workflow to modify
            agent_name: Name for the new agent
            agent_role: Role for the new agent
            department: Department for the new agent
            step_name: Name for the new workflow step
            instruction: What this step should do
            position: Where to insert — "start", "end", or "after"
            after_step: Step ID to insert after (when position="after")
            capabilities: Agent capabilities
            tools: Agent tool names (auto-select if empty)

        Returns:
            Tuple of (created agent, updated workflow)
        """
        # Load workflow
        workflow = await self._load_workflow(user_id, workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        # Create the agent
        agent = await self.create_workforce_agent(
            user_id=user_id,
            name=agent_name,
            role=agent_role,
            department=department,
            capabilities=capabilities,
            tools=tools,
            workflow_instructions=instruction,
        )

        # Build the new step
        step_id = f"step_{len(workflow.steps) + 1}"
        new_step = WorkflowStep(
            id=step_id,
            name=step_name,
            type=WorkflowStepType.AGENT,
            agent_id=agent.id,
            agent_role=agent_role,
            instruction=instruction,
            output_key=f"{step_id}_output",
        )

        # Insert at the right position
        if position == "start":
            # New step depends on nothing; first existing step now depends on new step
            new_step.depends_on = []
            if workflow.steps:
                workflow.steps[0].depends_on = [step_id]
            workflow.steps.insert(0, new_step)
        elif position == "after" and after_step:
            # Insert after a specific step
            insert_idx = None
            for i, s in enumerate(workflow.steps):
                if s.id == after_step or s.name.lower() == after_step.lower():
                    insert_idx = i + 1
                    new_step.depends_on = [s.id]
                    break
            if insert_idx is None:
                raise ValueError(f"Step '{after_step}' not found in workflow")
            # Update the step after the insertion point to depend on new step
            if insert_idx < len(workflow.steps):
                old_next = workflow.steps[insert_idx]
                old_next.depends_on = [step_id]
            workflow.steps.insert(insert_idx, new_step)
        else:
            # Append to end
            if workflow.steps:
                new_step.depends_on = [workflow.steps[-1].id]
            workflow.steps.append(new_step)

        # Persist updated workflow
        await self._save_workflow(user_id, workflow)

        return agent, workflow

    async def remove_step_from_workflow(
        self,
        user_id: str,
        workflow_id: str,
        step_id: str,
    ) -> WorkflowDefinition:
        """Remove a step from a workflow and reconnect the DAG.

        The step before connects to the step after, maintaining the chain.
        """
        workflow = await self._load_workflow(user_id, workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        remove_idx = None
        for i, s in enumerate(workflow.steps):
            if s.id == step_id or s.name.lower() == step_id.lower():
                remove_idx = i
                break

        if remove_idx is None:
            raise ValueError(f"Step '{step_id}' not found")

        removed = workflow.steps.pop(remove_idx)

        # Reconnect: steps that depended on the removed step now depend on its parent
        parent_deps = removed.depends_on
        for step in workflow.steps:
            if removed.id in step.depends_on:
                step.depends_on = [d for d in step.depends_on if d != removed.id]
                step.depends_on.extend(parent_deps)

        await self._save_workflow(user_id, workflow)
        return workflow

    async def reorder_workflow_steps(
        self,
        user_id: str,
        workflow_id: str,
        step_order: list[str],
    ) -> WorkflowDefinition:
        """Reorder workflow steps by providing the step IDs in desired order."""
        workflow = await self._load_workflow(user_id, workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        step_map = {s.id: s for s in workflow.steps}
        reordered = []
        for sid in step_order:
            if sid in step_map:
                reordered.append(step_map[sid])

        # Add any steps not in the order list at the end
        for s in workflow.steps:
            if s.id not in step_order:
                reordered.append(s)

        # Rebuild dependencies as a linear chain
        for i, step in enumerate(reordered):
            step.depends_on = [reordered[i - 1].id] if i > 0 else []

        workflow.steps = reordered
        await self._save_workflow(user_id, workflow)
        return workflow

    async def _load_workflow(self, user_id: str, workflow_id: str) -> WorkflowDefinition | None:
        """Load a workflow definition from the store."""
        try:
            todos = await self.store.list_todos(user_id)
            for t in todos:
                meta = t.get("metadata", {})
                if meta.get("type") == "workflow_definition" and meta.get("workflow_id") == workflow_id:
                    wf_data = json.loads(t.get("description", "{}"))
                    return WorkflowDefinition.from_dict(wf_data)
        except Exception as e:
            logger.warning(f"Failed to load workflow {workflow_id}: {e}")
        return None

    async def _save_workflow(self, user_id: str, workflow: WorkflowDefinition) -> None:
        """Persist a workflow definition back to the store."""
        try:
            # Delete old version if exists, then save new
            todos = await self.store.list_todos(user_id)
            for t in todos:
                meta = t.get("metadata", {})
                if meta.get("type") == "workflow_definition" and meta.get("workflow_id") == workflow.id:
                    try:
                        await self.store.delete_todo(user_id, t.get("id", ""))
                    except Exception:
                        pass
                    break

            await self.store.save_todo(user_id, {
                "title": f"Workflow: {workflow.name}",
                "description": json.dumps(workflow.to_dict()),
                "category": "workflow",
                "status": "active",
                "metadata": {"type": "workflow_definition", "workflow_id": workflow.id},
            })
        except Exception as e:
            logger.warning(f"Could not persist workflow: {e}")

    # ── Monitoring ─────────────────────────────────────────────

    def get_execution(self, execution_id: str) -> WorkflowExecution | None:
        return self._executions.get(execution_id)

    def list_executions(self, org_id: str = "") -> list[dict]:
        execs = self._executions.values()
        if org_id:
            execs = [e for e in execs if e.org_id == org_id]
        return [e.to_dict() for e in execs]

    def get_templates(self) -> dict[str, dict]:
        return INDUSTRY_TEMPLATES
