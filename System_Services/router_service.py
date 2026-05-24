from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from System_Services.envelope_service import PromptEnvelope


class RouterService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

        self.persona_patterns = {
            "proto_jane": r"\b(proto jane|jane)\b",
            "serren": r"\bserren\b",
            "maelith": r"\bmaelith\b",
            "vecht": r"\bvecht\b",
            "riven": r"\briven\b",
        }

        self.task_patterns = {
            "file_analysis": r"\b(analyze|summarize|read|inspect)\b.*\b(file|document|txt|md|json|py)\b",
            "self_assessment": r"\b(self[- ]?assessment|scan your own|analyze your own|os directory|system directory)\b",
            "log_summary": r"\b(log|logs|error logs|failure logs|session logs)\b.*\b(summary|summarize|review|analyze)\b",
            "technical_project": r"\b(code|python|pycharm|script|service|api|router|gateway|function|class)\b",
            "memory_task": r"\b(memory|remember|saved memories|import into memory|candidate memory)\b",
            "general_chat": r".*",
        }

    def route(self, envelope: PromptEnvelope) -> dict[str, Any]:
        text = envelope.user_text.strip()
        text_lower = text.lower()

        persona = "proto_jane"
        persona_reason = "default persona"

        for candidate, pattern in self.persona_patterns.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                persona = candidate
                persona_reason = f"addressed persona detected: {candidate}"
                break

        task_type = "general_chat"
        task_reason = "default route"
        confidence = 1

        for candidate, pattern in self.task_patterns.items():
            if candidate == "general_chat":
                continue

            if re.search(pattern, text_lower, re.IGNORECASE):
                task_type = candidate
                task_reason = f"matched task pattern: {candidate}"
                confidence = 3
                break

        if task_type == "general_chat":
            confidence = 1

        return {
            "request_id": envelope.request_id,
            "persona": persona,
            "task_type": task_type,
            "confidence": confidence,
            "reasons": [persona_reason, task_reason],
            "needs_prompt_interpreter": confidence < 2,
        }
