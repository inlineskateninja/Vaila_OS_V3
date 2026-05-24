from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class PromptEnvelope:
    request_id: str
    user_text: str
    source: str
    created_utc: str
    project_root: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EnvelopeService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def create(self, user_text: str, source: str = "unknown") -> PromptEnvelope:
        return PromptEnvelope(
            request_id=f"req_{uuid4().hex[:16]}",
            user_text=user_text,
            source=source,
            created_utc=datetime.now(timezone.utc).isoformat(),
            project_root=str(self.project_root),
            metadata={},
        )
