from __future__ import annotations

from pathlib import Path
from typing import Any

from System_Services.envelope_service import PromptEnvelope
from System_Services.logging_service import LoggingService
from System_Services.openbrain_service import OpenBrainService


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
        self.openbrain = OpenBrainService(project_root=project_root)

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

        candidate = {
            "event_type": "memory_candidate_detected",
            "request_id": envelope.request_id,
            "source": envelope.source,
            "text": envelope.user_text,
            "route": route,
            "status": "needs_user_review",
        }

        self.logger.log_session_event(candidate)
        self._forward_to_openbrain(candidate)

    def _forward_to_openbrain(self, candidate: dict[str, Any]) -> None:
        if not self.openbrain.enabled:
            return

        try:
            result = self.openbrain.write_memory_candidate(candidate)
        except Exception as exc:
            result = {
                "ok": False,
                "service_id": "openbrain",
                "error": str(exc),
            }

        if not result.get("ok"):
            self.logger.log_error(
                {
                    "event_type": "openbrain_memory_forward_failed",
                    "request_id": candidate.get("request_id"),
                    "error": result.get("error", "unknown OpenBrain forwarding failure"),
                    "service_id": "openbrain",
                }
            )
