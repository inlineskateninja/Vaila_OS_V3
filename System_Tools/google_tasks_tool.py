from __future__ import annotations

from typing import Any


class GoogleTasksTool:
    def health(self) -> dict[str, Any]:
        return {"ok": False, "status": "not_connected", "service_id": "google"}

    def supported_actions(self) -> list[str]:
        return ["list_tasks", "create_task", "update_task", "complete_task", "delete_task", "prioritize_tasks"]

    def list_tasks(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def create_task(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def update_task(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def complete_task(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def delete_task(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def prioritize_tasks(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def _not_connected(self, tool_intent: Any, dry_run: bool) -> dict[str, Any]:
        status = "dry_run" if dry_run else "not_connected"
        return {
            "ok": dry_run,
            "status": status,
            "summary": "Google Tasks is not connected yet. No Tasks API call was made.",
            "data": {"normalized_text": tool_intent.normalized_text},
        }
