"""
Workforce tools — Tova creates and manages AI agent workforces for organizations.

Enables Tova to:
1. Create specialized agents for any department or role
2. Build workflows from industry templates or custom definitions
3. Assign tasks to agents and monitor execution
4. Delegate work between agents
5. Manage the entire organizational AI workforce

Industry coverage:
- HR: onboarding, leave, recruitment, performance reviews
- Finance: invoices, expenses, budgeting, audit
- Marketing: content, campaigns, social, SEO
- Sales: leads, pipeline, proposals, CRM
- Engineering: code review, deployments, incident response
- Support: ticket triage, knowledge base, escalation
- Operations: procurement, inventory, logistics
- Legal: contract review, compliance, document management
- Any custom workflow the user defines
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore
from tova_core.workforce.engine import (
    WorkforceEngine,
    INDUSTRY_TEMPLATES,
    WorkflowDefinition,
    TaskAssignment,
)

logger = logging.getLogger(__name__)


def build_workforce_tools(
    store: BaseStore,
    workforce_engine: WorkforceEngine,
) -> list:
    """Build workforce management tools for organizational AI."""

    @tool
    async def create_workforce_agent(
        user_id: str,
        name: str,
        role: str,
        department: str = "general",
        capabilities: str = "",
        tools: str = "",
        workflow_instructions: str = "",
    ) -> dict:
        """Create a specialized AI agent for an organization.

        Creates an autonomous agent with a specific role, department, and capabilities.
        The agent gets its own system prompt, tools, and memory — tailored for its job.

        WHEN TO USE:
        - User says "I need an agent for..." or "Create an agent that..."
        - User describes a role or department need
        - When building a team of agents for a workflow
        - Any organizational task that needs a dedicated AI worker

        Examples:
        - "Create an HR agent for employee onboarding"
        - "I need a marketing agent that writes social media content"
        - "Build a finance agent to process invoices"
        - "Create a data analyst agent for our sales team"

        Args:
            user_id: The organization/user creating the agent
            name: Agent name (e.g., "Sarah - HR Coordinator", "InvoiceBot")
            role: Job role (e.g., "HR Coordinator", "Content Writer", "Data Analyst")
            department: Department: hr, finance, marketing, sales, engineering, support, operations, legal, custom
            capabilities: Comma-separated list of what this agent can do
            tools: Comma-separated tool names (empty = auto-select based on role)
            workflow_instructions: Specific workflow steps this agent should follow
        """
        try:
            cap_list = [c.strip() for c in capabilities.split(",") if c.strip()] if capabilities else None
            tool_list = [t.strip() for t in tools.split(",") if t.strip()] if tools else None

            agent = await workforce_engine.create_workforce_agent(
                user_id=user_id,
                name=name,
                role=role,
                department=department,
                capabilities=cap_list,
                tools=tool_list,
                workflow_instructions=workflow_instructions,
            )

            return {
                "success": True,
                "agent_id": agent.id,
                "name": agent.name,
                "role": role,
                "department": department,
                "tools": agent.get_tool_names(),
                "brain_boxes": agent.brain_boxes,
                "message": (
                    f"Agent '{name}' created as {role} in {department} department. "
                    f"Equipped with {len(agent.get_tool_names())} tools. "
                    f"Chat with it at /agents/{agent.id}/chat or assign it to a workflow."
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_workflow_templates() -> dict:
        """List all available industry workflow templates.

        Shows pre-built workflows for HR, Finance, Marketing, Sales,
        Engineering, Support, and Operations. Use these as starting points
        for organizational automation.
        """
        templates = []
        for template_id, template in INDUSTRY_TEMPLATES.items():
            templates.append({
                "id": template_id,
                "name": template["name"],
                "description": template["description"],
                "category": template["category"],
                "roles_needed": template["roles"],
                "steps_count": len(template["steps"]),
            })

        categories = {}
        for t in templates:
            cat = t["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(t)

        return {
            "templates": templates,
            "by_category": categories,
            "total": len(templates),
            "guidance": (
                "Present these templates organized by category. "
                "When the user picks one, use setup_workflow to deploy it. "
                "This will create the necessary agents and workflow."
            ),
        }

    @tool
    async def setup_workflow(
        user_id: str,
        template_id: str = "",
        custom_name: str = "",
        custom_description: str = "",
        custom_steps: str = "",
        department: str = "",
    ) -> dict:
        """Set up a complete workflow — creates all required agents and the workflow definition.

        Two modes:
        1. From template: Pass template_id to use a pre-built industry workflow
        2. Custom: Pass custom_name, custom_description, and custom_steps

        This is the ONE-CLICK way to deploy an entire AI team for a business process.

        Args:
            user_id: Organization/user setting up the workflow
            template_id: ID from list_workflow_templates (e.g., "employee_onboarding", "invoice_processing")
            custom_name: Name for a custom workflow
            custom_description: Description of custom workflow
            custom_steps: JSON array of custom steps, each with: name, role, instruction
                          e.g., '[{"name":"Research","role":"Researcher","instruction":"Research the topic..."}]'
            department: Department category for custom workflows
        """
        try:
            created_agents = []

            if template_id:
                # Create from template
                template = INDUSTRY_TEMPLATES.get(template_id)
                if not template:
                    return {
                        "error": f"Unknown template '{template_id}'",
                        "available": list(INDUSTRY_TEMPLATES.keys()),
                    }

                # Create agents for each role
                for role in template["roles"]:
                    agent = await workforce_engine.create_workforce_agent(
                        user_id=user_id,
                        name=f"{role}",
                        role=role,
                        department=template["category"],
                    )
                    created_agents.append({
                        "id": agent.id,
                        "name": agent.name,
                        "role": role,
                        "tools": agent.get_tool_names(),
                    })

                # Create the workflow
                workflow = await workforce_engine.create_workflow_from_template(
                    user_id=user_id,
                    template_id=template_id,
                )

                # Assign agents to workflow steps
                for step in workflow.steps:
                    for agent_info in created_agents:
                        if agent_info["role"] == step.agent_role:
                            step.agent_id = agent_info["id"]
                            break

                return {
                    "success": True,
                    "workflow_id": workflow.id,
                    "workflow_name": workflow.name,
                    "description": workflow.description,
                    "agents_created": created_agents,
                    "steps": [{"name": s.name, "role": s.agent_role, "agent_id": s.agent_id} for s in workflow.steps],
                    "message": (
                        f"Workflow '{workflow.name}' deployed with {len(created_agents)} AI agents. "
                        f"Use run_workflow to execute it, or delegate_task to assign individual tasks."
                    ),
                }

            elif custom_name and custom_steps:
                # Custom workflow
                try:
                    steps_data = json.loads(custom_steps)
                except json.JSONDecodeError:
                    return {"error": "custom_steps must be valid JSON array"}

                # Create agents for each unique role
                roles_seen = set()
                for step in steps_data:
                    role = step.get("role", "")
                    if role and role not in roles_seen:
                        roles_seen.add(role)
                        agent = await workforce_engine.create_workforce_agent(
                            user_id=user_id,
                            name=role,
                            role=role,
                            department=department or "custom",
                        )
                        created_agents.append({
                            "id": agent.id,
                            "name": agent.name,
                            "role": role,
                        })

                workflow = await workforce_engine.create_custom_workflow(
                    user_id=user_id,
                    name=custom_name,
                    description=custom_description,
                    steps=steps_data,
                    category=department or "custom",
                )

                return {
                    "success": True,
                    "workflow_id": workflow.id,
                    "workflow_name": workflow.name,
                    "agents_created": created_agents,
                    "steps_count": len(workflow.steps),
                    "message": f"Custom workflow '{custom_name}' created with {len(created_agents)} agents.",
                }

            else:
                return {"error": "Provide either template_id OR (custom_name + custom_steps)"}

        except Exception as e:
            return {"error": str(e)}

    @tool
    async def delegate_task(
        user_id: str,
        agent_id: str,
        instruction: str,
        context: str = "",
        priority: str = "normal",
    ) -> dict:
        """Delegate a specific task to a workforce agent.

        Sends an instruction to a specific agent and gets back the result.
        Use this to assign ad-hoc work to any agent in the workforce.

        Args:
            user_id: The user delegating the task
            agent_id: ID of the agent to assign the task to
            instruction: Clear instruction of what the agent should do
            context: Additional context or data for the task (JSON string)
            priority: normal, high, or urgent
        """
        try:
            input_data = {}
            if context:
                try:
                    input_data = json.loads(context)
                except json.JSONDecodeError:
                    input_data = {"context": context}

            priority_map = {"normal": 0, "high": 1, "urgent": 2}

            task = await workforce_engine.delegate_task(
                user_id=user_id,
                agent_id=agent_id,
                instruction=instruction,
                input_data=input_data,
                priority=priority_map.get(priority, 0),
            )

            return {
                "task_id": task.id,
                "agent_id": task.agent_id,
                "agent_name": task.agent_name,
                "status": task.status.value,
                "result": task.output_data if task.output_data else None,
                "error": task.error if task.error else None,
                "message": (
                    f"Task assigned to {task.agent_name or task.agent_id}. "
                    f"Status: {task.status.value}."
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_workforce(
        user_id: str,
    ) -> dict:
        """List all AI agents in the user's workforce.

        Shows all agents with their roles, departments, status, and capabilities.

        Args:
            user_id: The organization/user whose workforce to list
        """
        try:
            agents = await store.list_agents(user_id)
            workforce = []
            departments = {}

            for a in agents:
                meta = a.get("metadata", {})
                dept = meta.get("department", a.get("category", "general"))
                role = meta.get("role", a.get("description", ""))
                agent_type = meta.get("type", "general")

                agent_info = {
                    "id": a.get("id", ""),
                    "name": a.get("name", ""),
                    "role": role,
                    "department": dept,
                    "status": a.get("status", "active"),
                    "tools_count": len(a.get("tools", [])),
                    "type": agent_type,
                    "created_at": a.get("created_at", ""),
                }
                workforce.append(agent_info)

                if dept not in departments:
                    departments[dept] = []
                departments[dept].append(agent_info)

            return {
                "workforce": workforce,
                "by_department": departments,
                "total_agents": len(workforce),
                "departments": list(departments.keys()),
            }
        except NotImplementedError:
            return {"workforce": [], "total_agents": 0}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def run_workflow(
        user_id: str,
        workflow_id: str = "",
        template_id: str = "",
        input_data: str = "",
    ) -> dict:
        """Execute a workflow — runs all agents in sequence/parallel.

        Either provide a workflow_id (previously created) or a template_id
        to create and run in one step.

        Args:
            user_id: The user running the workflow
            workflow_id: ID of a saved workflow to execute
            template_id: Or, run directly from a template
            input_data: JSON string of input data for the workflow
        """
        try:
            inputs = {}
            if input_data:
                try:
                    inputs = json.loads(input_data)
                except json.JSONDecodeError:
                    inputs = {"input": input_data}

            if template_id:
                workflow = await workforce_engine.create_workflow_from_template(
                    user_id=user_id,
                    template_id=template_id,
                )
            elif workflow_id:
                # Load from stored workflows
                try:
                    todos = await store.list_todos(user_id)
                    wf_data = None
                    for t in todos:
                        meta = t.get("metadata", {})
                        if meta.get("type") == "workflow_definition" and meta.get("workflow_id") == workflow_id:
                            wf_data = json.loads(t.get("description", "{}"))
                            break
                    if not wf_data:
                        return {"error": f"Workflow '{workflow_id}' not found"}
                    workflow = WorkflowDefinition.from_dict(wf_data)
                except Exception as e:
                    return {"error": f"Could not load workflow: {e}"}
            else:
                return {"error": "Provide workflow_id or template_id"}

            execution = await workforce_engine.execute_workflow(
                workflow=workflow,
                user_id=user_id,
                input_data=inputs,
            )

            return {
                "execution_id": execution.id,
                "workflow": execution.workflow_name,
                "status": execution.status.value,
                "steps_completed": len([t for t in execution.tasks if t.status.value == "completed"]),
                "steps_total": len(execution.tasks),
                "tasks": [t.to_dict() for t in execution.tasks],
                "error": execution.error if execution.error else None,
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def monitor_workforce(
        user_id: str,
    ) -> dict:
        """Get a real-time overview of the AI workforce — active agents, running tasks, recent executions.

        Args:
            user_id: The organization to monitor
        """
        try:
            agents = await store.list_agents(user_id)
            executions = workforce_engine.list_executions()

            active_agents = [a for a in agents if a.get("status") == "active"]
            running_tasks = [
                e for e in executions
                if e.get("status") == "running"
            ]
            completed_tasks = [
                e for e in executions
                if e.get("status") == "completed"
            ]
            failed_tasks = [
                e for e in executions
                if e.get("status") == "failed"
            ]

            return {
                "overview": {
                    "total_agents": len(agents),
                    "active_agents": len(active_agents),
                    "running_workflows": len(running_tasks),
                    "completed_workflows": len(completed_tasks),
                    "failed_workflows": len(failed_tasks),
                },
                "recent_executions": executions[-10:],
                "agents_by_status": {
                    "active": len([a for a in agents if a.get("status") == "active"]),
                    "paused": len([a for a in agents if a.get("status") == "paused"]),
                    "archived": len([a for a in agents if a.get("status") == "archived"]),
                },
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def add_agent_to_workflow(
        user_id: str,
        workflow_id: str,
        agent_name: str,
        agent_role: str,
        department: str,
        step_name: str,
        instruction: str,
        position: str = "end",
        after_step: str = "",
        capabilities: str = "",
        tools: str = "",
    ) -> dict:
        """Add a new AI agent and step to an existing workflow.

        Dynamically expands a workflow — creates the agent, inserts a new step,
        and reconnects the DAG automatically.

        WHEN TO USE:
        - "Add a reviewer to the pipeline"
        - "Insert a QA step after the writing step"
        - "I need another agent in this workflow"
        - "Add a compliance check at the beginning"

        Args:
            user_id: Workflow owner
            workflow_id: ID of the workflow to modify
            agent_name: Name for the new agent (e.g., "QA Reviewer")
            agent_role: Role (e.g., "Quality Assurance Reviewer")
            department: Department (hr, finance, marketing, etc.)
            step_name: Name for the new workflow step (e.g., "Quality review")
            instruction: What this agent should do in the workflow
            position: Where to insert: "start", "end", or "after"
            after_step: Step ID or name to insert after (when position="after")
            capabilities: Comma-separated capabilities (optional)
            tools: Comma-separated tool names (auto-select if empty)
        """
        try:
            cap_list = [c.strip() for c in capabilities.split(",") if c.strip()] if capabilities else None
            tool_list = [t.strip() for t in tools.split(",") if t.strip()] if tools else None

            agent, workflow = await workforce_engine.add_agent_to_workflow(
                user_id=user_id,
                workflow_id=workflow_id,
                agent_name=agent_name,
                agent_role=agent_role,
                department=department,
                step_name=step_name,
                instruction=instruction,
                position=position,
                after_step=after_step,
                capabilities=cap_list,
                tools=tool_list,
            )

            return {
                "success": True,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "agent_role": agent_role,
                "workflow_id": workflow.id,
                "workflow_name": workflow.name,
                "total_steps": len(workflow.steps),
                "steps": [
                    {"id": s.id, "name": s.name, "role": s.agent_role, "agent_id": s.agent_id}
                    for s in workflow.steps
                ],
                "message": (
                    f"Agent '{agent_name}' added to workflow '{workflow.name}' "
                    f"at position: {position}. Workflow now has {len(workflow.steps)} steps."
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def remove_workflow_step(
        user_id: str,
        workflow_id: str,
        step_id: str,
    ) -> dict:
        """Remove a step from a workflow.

        The workflow automatically reconnects — steps before and after the removed
        step are linked together.

        Args:
            user_id: Workflow owner
            workflow_id: ID of the workflow to modify
            step_id: ID or name of the step to remove
        """
        try:
            workflow = await workforce_engine.remove_step_from_workflow(
                user_id=user_id,
                workflow_id=workflow_id,
                step_id=step_id,
            )

            return {
                "success": True,
                "workflow_id": workflow.id,
                "workflow_name": workflow.name,
                "remaining_steps": len(workflow.steps),
                "steps": [
                    {"id": s.id, "name": s.name, "role": s.agent_role}
                    for s in workflow.steps
                ],
                "message": f"Step removed. Workflow '{workflow.name}' now has {len(workflow.steps)} steps.",
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def reorder_workflow(
        user_id: str,
        workflow_id: str,
        step_order: str,
    ) -> dict:
        """Reorder the steps in a workflow.

        Provide the step IDs in the desired execution order.
        Dependencies are automatically rebuilt as a linear chain.

        Args:
            user_id: Workflow owner
            workflow_id: ID of the workflow to reorder
            step_order: Comma-separated step IDs in desired order (e.g., "step_3,step_1,step_2")
        """
        try:
            order = [s.strip() for s in step_order.split(",") if s.strip()]

            workflow = await workforce_engine.reorder_workflow_steps(
                user_id=user_id,
                workflow_id=workflow_id,
                step_order=order,
            )

            return {
                "success": True,
                "workflow_id": workflow.id,
                "workflow_name": workflow.name,
                "new_order": [
                    {"id": s.id, "name": s.name, "role": s.agent_role}
                    for s in workflow.steps
                ],
                "message": f"Workflow '{workflow.name}' reordered with {len(workflow.steps)} steps.",
            }
        except Exception as e:
            return {"error": str(e)}

    return [
        create_workforce_agent,
        list_workflow_templates,
        setup_workflow,
        delegate_task,
        list_workforce,
        run_workflow,
        monitor_workforce,
        add_agent_to_workflow,
        remove_workflow_step,
        reorder_workflow,
    ]
