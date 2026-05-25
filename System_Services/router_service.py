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
            "tool_registry_inspection": r"\b(registry inspector|audit registry|verify registrations)\b",
            "system_dependency_doctor": r"\b(dependency doctor|package health|startup readiness|python paths)\b",
            "memory_review_console": r"\b(memory console|review candidates|durable memory reviewer|approve memory)\b",
            "memory_backend_adapter": r"\b(memory backend|memory adapter|pgvector adapter|qdrant adapter)\b",
            "self_model_diff": r"\b(model diff|compare reports|assess blind spots|model drift analysis)\b",
            "capability_map": r"\b(capability map|architecture map|mermaid graph|live map)\b",
            "behavior_regression": r"\b(regression tester|behavior check|verify routing benchmarks)\b",
            "patch_proposal_review": r"\b(patch proposal|review patches|apply proposal|sandbox patch)\b",
            "goal_task_tracking": r"\b(goal state|kanban board|task checklist|active projects)\b",
            "n8n_librarian": r"\b(n8n librarian|workflow librarian|automation catalog)\b",
            "artifact_indexing": r"\b(artifact indexer|index artifacts|search past work)\b",
            "safety_boundary_auditing": r"\b(safety boundary|audit dogma|destructive command check)\b",
            "persona_drift_monitoring": r"\b(drift monitor|linguistic alignment|tone verification)\b",
            "user_context_routing": r"\b(context router|profile telemetry|loaded modules list)\b",
            "self_evolution_planning": r"\b(evolution planner|action proposals|ranked roadmaps)\b",
            "technical_project": r"\b(code|python|pycharm|script|service|api|router|gateway|function|class)\b",
            "memory_task": r"\b(memory|remember|saved memories|import into memory|candidate memory)\b",
            "n8n_workflows": r"\b(n8n|workflow|workflows|automation|trigger|node|nodes)\b",
            "general_chat": r".*",
        }

    def route(self, envelope: PromptEnvelope) -> dict[str, Any]:
        text = envelope.user_text.strip()
        text_lower = text.lower()

        persona = "proto_jane"
        persona_reason = "default persona"
        selected_persona = envelope.metadata.get("selected_persona")

        if selected_persona in self.persona_patterns:
            persona = selected_persona
            persona_reason = f"persona selected by interface: {selected_persona}"
        else:
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

        prompt_interpreter_enabled = bool(envelope.metadata.get("prompt_interpreter_enabled"))
        if envelope.source in {"stt", "stt_voice", "voice_stt"}:
            prompt_interpreter_enabled = True

        return {
            "request_id": envelope.request_id,
            "persona": persona,
            "task_type": task_type,
            "confidence": confidence,
            "reasons": [persona_reason, task_reason],
            "needs_prompt_interpreter": prompt_interpreter_enabled and confidence < 2,
            "prompt_interpreter_allowed": prompt_interpreter_enabled,
        }
