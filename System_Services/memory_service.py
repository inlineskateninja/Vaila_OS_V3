from __future__ import annotations

from pathlib import Path
from typing import Any

from System_Services.envelope_service import PromptEnvelope
from System_Services.logging_service import LoggingService


class MemoryService:
    """
    Phase 1 memory behavior:

    - Do not automatically write durable memories.
    - Log memory candidates for user review.
    - Later, connect this to OpenBrain or another memory backend.
    """

    def __init__(self, project_root: Path, logger: LoggingService) -> None:
        self.project_root = project_root
        self.logger = logger

    def capture_memory_candidate(self, envelope: PromptEnvelope, route: dict[str, Any]) -> None:
        text = envelope.user_text.lower()

        should_review = any(
            marker in text
            for marker in [
                "remember",
                "save this",
                "note that",
                "from now on",
                "going forward",
                "memory",
            ]
        )

        if not should_review:
            return

        self.logger.log_session_event(
            {
                "event_type": "memory_candidate_detected",
                "request_id": envelope.request_id,
                "source": envelope.source,
                "text": envelope.user_text,
                "route": route,
                "status": "needs_user_review",
            }
        )
