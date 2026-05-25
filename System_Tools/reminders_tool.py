from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class RemindersTool:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.reminders_path = project_root / "data" / "assistant_reminders.jsonl"

    def health(self) -> dict[str, Any]:
        return {"ok": True, "status": "local_ready", "service_id": "local_assistant"}

    def supported_actions(self) -> list[str]:
        return ["list_reminders", "create_reminder", "update_reminder", "complete_reminder", "delete_reminder"]

    def list_reminders(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        reminders = self._read_reminders()
        return {
            "ok": True,
            "status": "dry_run" if dry_run else "completed",
            "summary": f"{len(reminders)} local reminder(s) available.",
            "data": {"reminders": reminders},
        }

    def create_reminder(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        record = {
            "reminder_id": f"rem_{uuid4().hex}",
            "created_at": self._now(),
            "text": tool_intent.normalized_text,
            "date_terms": tool_intent.entities.get("date_terms", []),
            "status": "pending",
            "source": tool_intent.source,
        }
        if dry_run:
            return {"ok": True, "status": "dry_run", "summary": "Would create local reminder.", "data": record}

        self._append(record)
        return {"ok": True, "status": "completed", "summary": "Reminder created locally.", "data": record}

    def update_reminder(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Reminder update")

    def complete_reminder(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Reminder completion")

    def delete_reminder(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._placeholder(tool_intent, dry_run, "Reminder deletion")

    def _append(self, record: dict[str, Any]) -> None:
        self.reminders_path.parent.mkdir(parents=True, exist_ok=True)
        with self.reminders_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_reminders(self) -> list[dict[str, Any]]:
        if not self.reminders_path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.reminders_path.read_text(encoding="utf-8").splitlines():
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
