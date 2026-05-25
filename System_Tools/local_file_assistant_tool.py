from __future__ import annotations

from pathlib import Path
from typing import Any


class LocalFileAssistantTool:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def health(self) -> dict[str, Any]:
        return {"ok": True, "status": "local_ready", "service_id": "local_files"}

    def supported_actions(self) -> list[str]:
        return ["search_files", "read_file", "summarize_file", "create_file", "rename_file", "move_file", "delete_file"]

    def search_files(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        query = tool_intent.normalized_text
        matches = []
        if not dry_run:
            for path in self.project_root.rglob("*"):
                if path.is_file() and query in path.name.lower():
                    matches.append(str(path))
                    if len(matches) >= 25:
                        break
        return {
            "ok": True,
            "status": "dry_run" if dry_run else "completed",
            "summary": "Local file search prepared." if dry_run else f"Found {len(matches)} local file match(es).",
            "data": {"query": query, "matches": matches},
        }

    def read_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Local file reading")

    def summarize_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Local file summarization")

    def create_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Local file creation")

    def rename_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Local file rename")

    def move_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Local file move")

    def delete_file(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Local file deletion")

    def _placeholder(self, tool_intent: Any, dry_run: bool, label: str) -> dict[str, Any]:
        return {
            "ok": dry_run,
            "status": "dry_run" if dry_run else "not_implemented",
            "summary": f"{label} is not implemented in the execution layer yet.",
            "data": {"normalized_text": tool_intent.normalized_text},
        }
