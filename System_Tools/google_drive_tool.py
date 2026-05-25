from __future__ import annotations

from typing import Any


class GoogleDriveTool:
    def health(self) -> dict[str, Any]:
        return {"ok": False, "status": "not_connected", "service_id": "google"}

    def supported_actions(self) -> list[str]:
        return ["search_files", "read_file", "summarize_file", "create_folder", "move_file", "share_file"]

    def search_files(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def read_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def summarize_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def create_folder(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def move_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def share_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def _not_connected(self, tool_intent: Any, dry_run: bool) -> dict[str, Any]:
        status = "dry_run" if dry_run else "not_connected"
        return {
            "ok": dry_run,
            "status": status,
            "summary": "Google Drive is not connected yet. No Drive API call was made.",
            "data": {"normalized_text": tool_intent.normalized_text},
        }
