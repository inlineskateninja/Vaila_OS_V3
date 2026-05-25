import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class MemoryRecallEvent:
    id: str
    created_at: str
    request_id: str
    persona: str
    task_type: str
    query: str
    memory_ids: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    used_in_context: bool = True
    source: str = "chat"
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecallEvent":
        return cls(
            id=data.get("id", ""),
            created_at=data.get("created_at", ""),
            request_id=data.get("request_id", ""),
            persona=data.get("persona", ""),
            task_type=data.get("task_type", ""),
            query=data.get("query", ""),
            memory_ids=data.get("memory_ids", []),
            scores=data.get("scores", []),
            filters=data.get("filters", {}),
            used_in_context=data.get("used_in_context", True),
            source=data.get("source", "chat"),
            notes=data.get("notes", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryRecallLog:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.events: list[MemoryRecallEvent] = []

    def load(self) -> None:
        self.events.clear()
        if not self.file_path.exists():
            return

        with self.file_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    self.events.append(MemoryRecallEvent.from_dict(json.loads(line)))
                except json.JSONDecodeError as error:
                    print(f"Skipping invalid recall log line {line_number}: {error}")

    def append(self, event: MemoryRecallEvent) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not event.id:
            event.id = f"recall_{uuid.uuid4().hex[:16]}"
        if not event.created_at:
            event.created_at = datetime.now(timezone.utc).isoformat()

        with self.file_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

        self.events.append(event)

    def list_recent(self, limit: int = 50) -> list[MemoryRecallEvent]:
        return list(reversed(self.events))[:limit]

    def count(self) -> int:
        return len(self.events)
