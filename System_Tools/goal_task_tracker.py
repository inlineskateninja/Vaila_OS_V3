from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GoalTaskTracker:
    """
    Gives Vaila a structured working memory for active projects, unfinished tasks,
    blocked items, and user priorities.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.state_file = project_root / "data" / "goal_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            # Seed default state
            default_state = {
                "active_project": "Vaila OS V3 Installation",
                "priorities": ["Complete core tool implementations", "Maintain persona alignment", "Verify API endpoints"],
                "goals": []
            }
            self.save_state(default_state)
            return default_state

        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return {"active_project": "Vaila OS V3", "priorities": [], "goals": []}

    def save_state(self, state: dict[str, Any]) -> bool:
        try:
            self.state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception:
            return False

    def set_active_project(self, name: str) -> bool:
        state = self.load_state()
        state["active_project"] = name
        return self.save_state(state)

    def add_goal(self, title: str, description: str = "", status: str = "todo", priority: str = "medium") -> dict[str, Any]:
        state = self.load_state()
        goal = {
            "id": f"g_{len(state['goals']) + 1}",
            "title": title,
            "description": description,
            "status": status,  # todo, in_progress, blocked, done
            "priority": priority,  # high, medium, low
            "blockers": [],
            "subtasks": [],
            "linked_files": []
        }
        state["goals"].append(goal)
        self.save_state(state)
        return goal

    def add_subtask(self, goal_id: str, title: str, status: str = "todo") -> bool:
        state = self.load_state()
        for goal in state["goals"]:
            if goal.get("id") == goal_id:
                sub = {
                    "id": f"{goal_id}_s{len(goal.get('subtasks', [])) + 1}",
                    "title": title,
                    "status": status
                }
                goal.setdefault("subtasks", []).append(sub)
                return self.save_state(state)
        return False

    def update_subtask_status(self, goal_id: str, subtask_id: str, status: str) -> bool:
        state = self.load_state()
        for goal in state["goals"]:
            if goal.get("id") == goal_id:
                for sub in goal.get("subtasks", []):
                    if sub.get("id") == subtask_id:
                        sub["status"] = status
                        return self.save_state(state)
        return False

    def add_blocker(self, goal_id: str, blocker: str) -> bool:
        state = self.load_state()
        for goal in state["goals"]:
            if goal.get("id") == goal_id:
                goal.setdefault("blockers", []).append(blocker)
                goal["status"] = "blocked"
                return self.save_state(state)
        return False

    def remove_blocker(self, goal_id: str, blocker: str) -> bool:
        state = self.load_state()
        for goal in state["goals"]:
            if goal.get("id") == goal_id:
                if blocker in goal.get("blockers", []):
                    goal["blockers"].remove(blocker)
                    if not goal["blockers"] and goal["status"] == "blocked":
                        goal["status"] = "in_progress"
                    return self.save_state(state)
        return False

    def update_goal_status(self, goal_id: str, status: str) -> bool:
        state = self.load_state()
        for goal in state["goals"]:
            if goal.get("id") == goal_id:
                goal["status"] = status
                return self.save_state(state)
        return False

    def link_file_to_goal(self, goal_id: str, file_path: str) -> bool:
        state = self.load_state()
        for goal in state["goals"]:
            if goal.get("id") == goal_id:
                goal.setdefault("linked_files", []).append(file_path)
                return self.save_state(state)
        return False

    def render_kanban_board(self) -> str:
        state = self.load_state()
        project = state.get("active_project", "Vaila OS V3")
        priorities = state.get("priorities", [])

        # Categorize goals by status
        columns = {"todo": [], "in_progress": [], "blocked": [], "done": []}
        for goal in state.get("goals", []):
            status = goal.get("status", "todo")
            if status in columns:
                columns[status].append(goal)

        lines = [
            f"# 📋 Kanban Task Board: {project}",
            "",
            "## 🎯 Active Project Priorities",
        ]
        for p in priorities:
            lines.append(f"- **[PRIORITY]** {p}")

        lines.append("")
        lines.append("## 🗂️ Task Columns")

        status_titles = {
            "todo": "⏳ TO DO",
            "in_progress": "⚡ IN PROGRESS",
            "blocked": "🛑 BLOCKED",
            "done": "✅ COMPLETED"
        }

        for col, col_goals in columns.items():
            lines.append(f"### {status_titles[col]} ({len(col_goals)})")
            if not col_goals:
                lines.append("_No tasks in this column._")
                lines.append("")
                continue

            for goal in col_goals:
                prio_badge = f"[`{goal['priority'].upper()}`]"
                lines.append(f"#### {goal['title']} {prio_badge}")
                lines.append(f"- **ID**: `{goal['id']}`")
                if goal.get("description"):
                    lines.append(f"- **Description**: {goal['description']}")
                
                # Render Blockers
                if goal.get("blockers"):
                    lines.append(f"- **🚨 Blockers**: {', '.join(goal['blockers'])}")
                
                # Render Subtasks
                subtasks = goal.get("subtasks", [])
                if subtasks:
                    lines.append("- **Subtasks**:")
                    for sub in subtasks:
                        marker = "[x]" if sub["status"] == "done" else "[ ]"
                        lines.append(f"  - `{marker}` {sub['title']} (ID: `{sub['id']}`)")

                # Render Linked Files
                files = goal.get("linked_files", [])
                if files:
                    lines.append(f"- **🔗 Linked Attachments**: {', '.join(files)}")
                lines.append("")

        return "\n".join(lines)
