from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from System_Services.envelope_service import PromptEnvelope


class PromptInterpreter:
    """Deterministic advisory classifier for low-confidence voice routing audits."""

    PERSONA_PATTERNS = {
        "proto_jane": r"\b(proto jane|jane)\b",
        "serren": r"\bserren\b",
        "maelith": r"\bmaelith\b",
        "vecht": r"\bvecht\b",
        "riven": r"\briven\b",
    }

    TASK_PATTERNS = {
        "file_analysis": r"\b(analyze|summarize|read|inspect)\b.*\b(file|document|txt|md|json|py)\b",
        "self_assessment": r"\b(self[- ]?assessment|scan your own|analyze your own|os directory|system directory)\b",
        "log_summary": r"\b(log|logs|error logs|failure logs|session logs)\b.*\b(summary|summarize|review|analyze)\b",
        "technical_project": r"\b(code|python|pycharm|script|service|api|router|gateway|function|class)\b",
        "memory_task": r"\b(memory|remember|saved memories|import into memory|candidate memory)\b",
    }

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def interpret(self, envelope: PromptEnvelope, route: dict[str, Any]) -> dict[str, Any]:
        text = envelope.user_text.strip().lower()
        persona = self._match_persona(text) or route.get("persona", "proto_jane")
        task_type = self._match_task(text) or route.get("task_type", "general_chat")
        confidence = 3 if task_type != "general_chat" or persona != route.get("persona") else 1

        return {
            "status": "interpreted",
            "mode": "deterministic_advisory",
            "advisory_task_type": task_type,
            "advisory_persona": persona,
            "confidence": confidence,
            "signals": self._signals(text),
            "route_disagreement": {
                "task_type": task_type != route.get("task_type"),
                "persona": persona != route.get("persona"),
            },
            "original_task_type": route.get("task_type"),
            "original_persona": route.get("persona"),
        }

    def _match_persona(self, text: str) -> str | None:
        for persona, pattern in self.PERSONA_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return persona
        return None

    def _match_task(self, text: str) -> str | None:
        for task_type, pattern in self.TASK_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return task_type
        return None

    def _signals(self, text: str) -> dict[str, bool]:
        return {
            "mentions_file": bool(re.search(r"\b(file|document|txt|md|json|py)\b", text)),
            "mentions_logs": bool(re.search(r"\b(log|logs|error logs|session logs)\b", text)),
            "mentions_memory": bool(re.search(r"\b(memory|remember|saved memories)\b", text)),
            "mentions_code": bool(re.search(r"\b(code|python|script|service|api|router|function|class)\b", text)),
            "addresses_persona": self._match_persona(text) is not None,
        }
