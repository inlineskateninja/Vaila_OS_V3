from __future__ import annotations

from pathlib import Path
from typing import Any

from System_Services.envelope_service import PromptEnvelope


class PromptInterpreter:
    """
    Phase 1 stub.

    This should eventually run conditionally or asynchronously only when the regex router is uncertain.
    Do not put this on the critical path for every normal message.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def interpret(self, envelope: PromptEnvelope, route: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "stub",
            "note": "PromptInterpreter reserved for low-confidence routing only.",
            "original_task_type": route.get("task_type"),
            "original_persona": route.get("persona"),
        }
