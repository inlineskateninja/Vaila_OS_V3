from __future__ import annotations

from typing import Any


class GoogleCalendarTool:
    def health(self) -> dict[str, Any]:
        return {"ok": False, "status": "not_connected", "service_id": "google"}

    def supported_actions(self) -> list[str]:
        return ["list_events", "search_events", "create_event", "update_event", "delete_event", "summarize_schedule"]

    def list_events(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def search_events(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def create_event(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def update_event(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def delete_event(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def summarize_schedule(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def _not_connected(self, tool_intent: Any, dry_run: bool) -> dict[str, Any]:
        status = "dry_run" if dry_run else "not_connected"
        return {
            "ok": dry_run,
            "status": status,
            "summary": "Google Calendar is not connected yet. No calendar API call was made.",
            "data": {"normalized_text": tool_intent.normalized_text},
        }
