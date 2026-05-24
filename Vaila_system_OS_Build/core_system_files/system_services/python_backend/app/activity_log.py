from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


@dataclass
class ActivityEvent:
    id: str
    event_type: str
    summary: str
    created_at: str
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, event_type: str, summary: str, details: dict[str, Any] | None = None) -> "ActivityEvent":
        created_at = utc_now()
        raw_id = f"{created_at}|{event_type}|{summary}|{json.dumps(details or {}, sort_keys=True, default=str)}"
        return cls(
            id=f"event_{stable_hash(raw_id, 18)}",
            event_type=event_type,
            summary=summary,
            created_at=created_at,
            details=details or {},
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActivityEvent":
        return cls(
            id=data.get("id", ""),
            event_type=data.get("event_type", "unknown"),
            summary=data.get("summary", ""),
            created_at=data.get("created_at", ""),
            details=data.get("details", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ActivityLog:
    """Append-only activity log for Phase 2 review and debugging.

    This is not long-term memory. It is operational history: chats, imports,
    approvals, rejections, reloads, and review checkpoints.
    """

    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self.events: list[ActivityEvent] = []

    def load(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.events.clear()
        if not self.log_path.exists():
            return

        with self.log_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    self.events.append(ActivityEvent.from_dict(json.loads(line)))
                except json.JSONDecodeError as error:
                    print(f"Skipping invalid activity JSON in {self.log_path}, line {line_number}: {error}")

    def append(
        self,
        event_type: str,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        event = ActivityEvent.create(event_type=event_type, summary=summary, details=details or {})
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        self.events.append(event)
        return event

    def recent(self, limit: int = 50, event_type: str | None = None) -> list[ActivityEvent]:
        filtered = self.events
        if event_type:
            filtered = [event for event in filtered if event.event_type == event_type]
        return list(reversed(filtered[-limit:]))

    def counts_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return dict(sorted(counts.items()))
