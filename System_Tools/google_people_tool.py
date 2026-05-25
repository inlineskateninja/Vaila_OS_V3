from __future__ import annotations

from typing import Any


class GooglePeopleTool:
    def health(self) -> dict[str, Any]:
        return {"ok": False, "status": "not_connected", "service_id": "google"}

    def supported_actions(self) -> list[str]:
        return ["search_contacts", "read_contact", "create_contact", "update_contact", "merge_contact_context"]

    def search_contacts(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def read_contact(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def create_contact(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def update_contact(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def merge_contact_context(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def _not_connected(self, tool_intent: Any, dry_run: bool) -> dict[str, Any]:
        status = "dry_run" if dry_run else "not_connected"
        return {
            "ok": dry_run,
            "status": status,
            "summary": "Google People is not connected yet. No Contacts API call was made.",
            "data": {"normalized_text": tool_intent.normalized_text},
        }
