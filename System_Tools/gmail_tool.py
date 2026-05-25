from __future__ import annotations

from typing import Any


class GmailTool:
    def health(self) -> dict[str, Any]:
        return {"ok": False, "status": "not_connected", "service_id": "google"}

    def supported_actions(self) -> list[str]:
        return ["search_email", "summarize_thread", "draft_reply", "send_email", "label_email", "archive_email"]

    def search_email(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def summarize_thread(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def draft_reply(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def send_email(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def label_email(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def archive_email(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def _not_connected(self, tool_intent: Any, dry_run: bool) -> dict[str, Any]:
        status = "dry_run" if dry_run else "not_connected"
        return {
            "ok": dry_run,
            "status": status,
            "summary": "Gmail is not connected yet. No Gmail API call was made.",
            "data": {"normalized_text": tool_intent.normalized_text},
        }
