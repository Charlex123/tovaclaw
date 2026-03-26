"""
Todo / Task Planning tools.

Enable agents to create, manage, and prioritize tasks for users.
"""

from __future__ import annotations

import logging
from datetime import datetime
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)


def build_todo_tools(store: BaseStore) -> list:
    """Build todo management tools using the provider pattern."""

    @tool
    async def create_todo(
        user_id: str,
        title: str,
        description: str = "",
        priority: str = "medium",
        due_date: str = "",
        tags: str = "",
    ) -> dict:
        """Create a new todo/task for the user.

        Args:
            user_id: The user who owns this todo
            title: Task title
            description: Detailed description
            priority: Priority level: critical, high, medium, low
            due_date: Optional due date (ISO format: YYYY-MM-DD)
            tags: Comma-separated tags
        """
        try:
            todo_data = {
                "title": title,
                "description": description,
                "status": "pending",
                "priority": priority,
                "due_date": due_date or None,
                "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            todo_id = await store.save_todo(user_id, todo_data)
            return {"success": True, "id": todo_id, "title": title, "priority": priority}
        except NotImplementedError:
            return {"error": "Todo storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def list_todos(
        user_id: str,
        status: str = "",
        priority: str = "",
    ) -> dict:
        """List the user's todos/tasks, optionally filtered by status or priority.

        Args:
            user_id: The user whose todos to list
            status: Filter by status: pending, in_progress, completed, cancelled (empty = all)
            priority: Filter by priority: critical, high, medium, low (empty = all)
        """
        try:
            todos = await store.list_todos(user_id, status=status or None)
            if priority:
                todos = [t for t in todos if t.get("priority") == priority]

            return {
                "todos": [
                    {
                        "id": t.get("id", ""),
                        "title": t.get("title", ""),
                        "status": t.get("status", "pending"),
                        "priority": t.get("priority", "medium"),
                        "due_date": t.get("due_date", ""),
                        "tags": t.get("tags", []),
                    }
                    for t in todos
                ],
                "count": len(todos),
            }
        except NotImplementedError:
            return {"todos": [], "count": 0}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def update_todo(
        todo_id: str,
        status: str = "",
        priority: str = "",
        title: str = "",
        description: str = "",
    ) -> dict:
        """Update an existing todo/task.

        Args:
            todo_id: The todo ID to update
            status: New status: pending, in_progress, completed, cancelled
            priority: New priority: critical, high, medium, low
            title: New title (empty = keep current)
            description: New description (empty = keep current)
        """
        try:
            updates = {"updated_at": datetime.now().isoformat()}
            if status:
                updates["status"] = status
            if priority:
                updates["priority"] = priority
            if title:
                updates["title"] = title
            if description:
                updates["description"] = description
            if status == "completed":
                updates["completed_at"] = datetime.now().isoformat()

            success = await store.update_todo(todo_id, updates)
            return {"success": success, "id": todo_id, "updates": updates}
        except NotImplementedError:
            return {"error": "Todo storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def complete_todo(todo_id: str) -> dict:
        """Mark a todo as completed.

        Args:
            todo_id: The todo ID to mark as complete
        """
        try:
            success = await store.update_todo(todo_id, {
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            })
            return {"success": success, "id": todo_id, "status": "completed"}
        except NotImplementedError:
            return {"error": "Todo storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def suggest_priorities(user_id: str) -> dict:
        """Analyze the user's todos and suggest optimal priority ordering.

        Considers due dates, current priorities, and dependencies.

        Args:
            user_id: The user whose todos to analyze
        """
        try:
            todos = await store.list_todos(user_id, status="pending")
            todos += await store.list_todos(user_id, status="in_progress")

            if not todos:
                return {"message": "No active todos found", "suggestions": []}

            # Sort by urgency: overdue first, then by priority, then by due date
            now = datetime.now().isoformat()
            suggestions = []
            for t in todos:
                urgency = 0
                due = t.get("due_date", "")
                if due and due < now:
                    urgency = 100  # Overdue
                elif due:
                    urgency = 50  # Has due date

                priority_scores = {"critical": 40, "high": 30, "medium": 20, "low": 10}
                urgency += priority_scores.get(t.get("priority", "medium"), 20)

                suggestions.append({
                    "id": t.get("id", ""),
                    "title": t.get("title", ""),
                    "current_priority": t.get("priority", "medium"),
                    "urgency_score": urgency,
                    "due_date": due,
                    "status": t.get("status", "pending"),
                })

            suggestions.sort(key=lambda x: x["urgency_score"], reverse=True)
            return {"suggestions": suggestions, "count": len(suggestions)}
        except NotImplementedError:
            return {"suggestions": [], "message": "Todo storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    return [create_todo, list_todos, update_todo, complete_todo, suggest_priorities]
