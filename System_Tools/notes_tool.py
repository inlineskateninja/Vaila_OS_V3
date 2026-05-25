from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class NotesTool:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.notes_path = project_root / "data" / "assistant_notes.jsonl"

    def health(self) -> dict[str, Any]:
        return {"ok": True, "status": "local_ready", "service_id": "local_assistant"}

    def supported_actions(self) -> list[str]:
        return ["create_note", "search_notes", "summarize_notes", "update_note", "delete_note", "tag_note"]

    def create_note(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        text = self._note_text(tool_intent.normalized_text)
        record = {
            "note_id": f"note_{uuid4().hex}",
            "created_at": self._now(),
            "text": text,
            "source": tool_intent.source,
        }
        if dry_run:
            return {"ok": True, "status": "dry_run", "summary": f"Would create note: {text}", "data": record}

        self._append(record)
        return {"ok": True, "status": "completed", "summary": "Note created locally.", "data": record}

    def search_notes(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        query = tool_intent.normalized_text
        notes = self._read_notes()
        matches = [note for note in notes if query in note.get("text", "").lower()]
        return {"ok": True, "status": "dry_run" if dry_run else "completed", "summary": "Local notes searched.", "data": {"matches": matches}}

    def summarize_notes(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        notes = self._read_notes()
        return {"ok": True, "status": "dry_run" if dry_run else "completed", "summary": f"{len(notes)} local note(s) available.", "data": {"count": len(notes)}}

    def update_note(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Note update")

    def delete_note(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Note deletion")

    def tag_note(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Note tagging")

    def _note_text(self, normalized_text: str) -> str:
        for prefix in ["take a note", "create note", "write note", "save note", "note that"]:
            if normalized_text.startswith(prefix):
                return normalized_text[len(prefix):].strip() or normalized_text
        return normalized_text

    def _append(self, record: dict[str, Any]) -> None:
        self.notes_path.parent.mkdir(parents=True, exist_ok=True)
        with self.notes_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_notes(self) -> list[dict[str, Any]]:
        if not self.notes_path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.notes_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)
        return records

    def _placeholder(self, tool_intent: Any, dry_run: bool, label: str) -> dict[str, Any]:
        return {
            "ok": dry_run,
            "status": "dry_run" if dry_run else "not_implemented",
            "summary": f"{label} is not implemented yet.",
            "data": {"normalized_text": tool_intent.normalized_text},
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
