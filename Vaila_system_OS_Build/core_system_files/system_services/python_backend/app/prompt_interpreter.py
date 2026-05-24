from __future__ import annotations

import json
import re
from typing import Any

from app.llm_client import LLMClientError, LMStudioClient
from app.model_registry import ModelRegistry
from app.router import PERSONA_ALIASES, TASK_CONFIGS, normalize_persona_override, route_user_input
from app.schemas import PromptInterpretation, RequestEnvelope, RoutePlan, RoutingComparison
from app.prompt_budget import DEFAULT_INTERPRETER_PROMPT_MAX_CHARS, compact_text

INTERPRETER_PROFILE = "prompt_interpreter"
SCHEMA_VERSION = "prompt_interpretation.v1"
ALLOWED_TASK_TYPES = sorted(TASK_CONFIGS.keys())
ALLOWED_PERSONAS = sorted(set(PERSONA_ALIASES.values()) | {"council"})
REQUIRED_KEYS = {
    "schema_version",
    "task_type",
    "persona",
    "model_profile",
    "fallback_profile",
    "confidence",
    "intent_summary",
    "refined_prompt",
    "requested_operations",
    "context_needs",
    "tool_hints",
    "response_goal",
    "memory_queries",
    "memory_tags",
    "reasons",
    "warnings",
}


class PromptInterpretationError(ValueError):
    pass


class PromptInterpreter:
    """Advisory model layer for interpreting a request before final routing.

    This class deliberately returns advice only. The deterministic router remains
    the final authority until logged comparisons prove the model layer helps.
    """

    def __init__(
        self,
        llm_client: LMStudioClient,
        model_registry: ModelRegistry,
        profile_name: str = INTERPRETER_PROFILE,
    ) -> None:
        self.llm_client = llm_client
        self.model_registry = model_registry
        self.profile_name = profile_name

    def interpret(self, envelope: RequestEnvelope) -> PromptInterpretation:
        profile = self.model_registry.get_profile_or_none(self.profile_name)
        if profile is None:
            return deterministic_interpretation(
                envelope,
                source="deterministic_fallback",
                warning=(
                    f"Interpreter profile '{self.profile_name}' is unavailable or has no resolved model. "
                    "Deterministic routing metadata was used as prompt interpretation."
                ),
            )

        messages = self._build_messages(envelope, profile)
        try:
            raw_text = self.llm_client.chat(
                model=profile["model"],
                messages=messages,
                temperature=profile.get("temperature", 0.0),
                max_tokens=profile.get("max_tokens", 550),
                timeout=profile.get("timeout_seconds", 75),
                extra=profile.get("extra"),
            )
            parsed = parse_interpretation_json(raw_text, self.model_registry.list_profile_names())
            parsed.source = "local_model"
            parsed.ok = True
            parsed.interpreter_profile = profile.get("profile_name", self.profile_name)
            parsed.interpreter_model = profile.get("model", "")
            parsed.raw_text = raw_text
            return parsed
        except (LLMClientError, PromptInterpretationError, json.JSONDecodeError, TypeError, ValueError) as error:
            fallback = deterministic_interpretation(
                envelope,
                source="deterministic_fallback",
                warning=f"Model prompt interpreter failed; deterministic routing metadata was used instead: {error}",
            )
            fallback.interpreter_profile = profile.get("profile_name", self.profile_name)
            fallback.interpreter_model = profile.get("model", "")
            fallback.error = str(error)
            return fallback

    def _build_messages(self, envelope: RequestEnvelope, profile: dict[str, Any]) -> list[dict[str, str]]:
        profile_names = self.model_registry.list_profile_names()
        schema = {
            "schema_version": SCHEMA_VERSION,
            "task_type": ALLOWED_TASK_TYPES,
            "persona": ALLOWED_PERSONAS,
            "model_profile": profile_names,
            "fallback_profile": profile_names,
            "confidence": "number from 0.0 to 1.0",
            "intent_summary": "short neutral summary of the user's intent",
            "refined_prompt": "optional clarified prompt as metadata only, never a replacement",
            "requested_operations": [
                "answer_question",
                "use_tool",
                "analyze_file",
                "retrieve_memory",
                "retrieve_system_context",
                "web_research",
                "critique_or_feedback",
                "synthesize",
                "create_artifact",
                "explain_system",
            ],
            "context_needs": [
                "persona",
                "memory",
                "time",
                "files",
                "tools",
                "system_registry",
                "project_context",
                "user_context",
                "web",
            ],
            "tool_hints": "array of likely tools or agents, such as file_analyze, memory_search, web_search, system_registry",
            "response_goal": "what the final user-visible answer should accomplish",
            "memory_queries": "array of 0 to 5 memory search strings",
            "memory_tags": "array of 0 to 8 lowercase tags",
            "reasons": "array of 1 to 6 short routing reasons",
            "warnings": "array of warnings, empty if none",
        }
        system = (
            "You are Vaila's prompt interpretation layer, not the response writer. "
            "Return one JSON object only. Do not answer the user. Do not rewrite the original prompt. "
            "Any refined_prompt must be treated as advisory metadata only. "
            "If the request envelope includes a selected persona, treat that persona as authoritative. "
            "Use the exact keys and allowed enum values from the schema."
        )
        original_for_model = compact_text(
            envelope.original_text,
            DEFAULT_INTERPRETER_PROMPT_MAX_CHARS,
            "interpreter view of original prompt",
        )
        user = (
            "Interpret this original user prompt for routing advice.\n\n"
            f"Request ID: {envelope.id}\n"
            f"Persona source: {envelope.metadata.get('persona_source', 'detect_persona')}\n"
            f"Selected persona: {normalize_persona_override(envelope.metadata.get('selected_persona')) or 'none'}\n"
            f"Original prompt chars: {len(envelope.original_text)}\n"
            "Full original prompt is preserved exactly in the request envelope log. "
            "The text below is the model-context view and may be compacted only when necessary.\n\n"
            "Original prompt view:\n"
            f"{original_for_model}\n\n"
            "Strict JSON schema and allowed values:\n"
            f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
            "Return only valid JSON."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_interpretation_json(raw_text: str, allowed_model_profiles: list[str]) -> PromptInterpretation:
    data = json.loads(_extract_json_object(raw_text))
    if not isinstance(data, dict):
        raise PromptInterpretationError("Prompt interpreter returned JSON that was not an object.")

    missing = sorted(REQUIRED_KEYS - set(data.keys()))
    if missing:
        raise PromptInterpretationError(f"Prompt interpreter JSON missing required keys: {', '.join(missing)}")

    schema_version = _require_string(data, "schema_version")
    if schema_version != SCHEMA_VERSION:
        raise PromptInterpretationError(f"Unsupported interpretation schema_version: {schema_version}")

    task_type = _require_enum(data, "task_type", ALLOWED_TASK_TYPES)
    persona = _require_enum(data, "persona", ALLOWED_PERSONAS)
    model_profile = _require_enum(data, "model_profile", allowed_model_profiles)
    fallback_profile = _require_enum(data, "fallback_profile", allowed_model_profiles)
    confidence = _require_confidence(data)

    return PromptInterpretation(
        schema_version=schema_version,
        advised_task_type=task_type,
        advised_persona=persona,
        advised_model_profile=model_profile,
        advised_fallback_profile=fallback_profile,
        confidence=confidence,
        intent_summary=_require_string(data, "intent_summary"),
        refined_prompt=_require_string(data, "refined_prompt", allow_empty=True),
        requested_operations=_require_string_list(data, "requested_operations", max_items=10),
        context_needs=_require_string_list(data, "context_needs", max_items=10),
        tool_hints=_require_string_list(data, "tool_hints", max_items=8),
        response_goal=_require_string(data, "response_goal", allow_empty=True),
        memory_queries=_require_string_list(data, "memory_queries", max_items=5),
        memory_tags=_require_string_list(data, "memory_tags", max_items=8),
        reasons=_require_string_list(data, "reasons", min_items=1, max_items=6),
        warnings=_require_string_list(data, "warnings", max_items=8),
    )


def deterministic_interpretation(
    envelope: RequestEnvelope,
    *,
    source: str = "deterministic_fallback",
    warning: str = "",
) -> PromptInterpretation:
    route = route_user_input(
        envelope.original_text,
        persona_override=envelope.metadata.get("selected_persona"),
    )
    requested_operations, context_needs, tool_hints, response_goal = deterministic_intent_needs(envelope.original_text, route)
    return PromptInterpretation(
        ok=True,
        source=source,
        interpreter_profile=INTERPRETER_PROFILE,
        advised_task_type=route.task_type,
        advised_persona=route.persona,
        advised_model_profile=route.model_profile,
        advised_fallback_profile=route.fallback_profile,
        confidence=0.72,
        intent_summary=f"Deterministic route: {route.task_type} for {route.persona}.",
        refined_prompt=envelope.normalized_text,
        requested_operations=requested_operations,
        context_needs=context_needs,
        tool_hints=tool_hints,
        response_goal=response_goal,
        memory_queries=route.memory_queries[:5],
        memory_tags=route.memory_tags[:8],
        reasons=[*route.reasons[:5], "Prompt interpretation used deterministic fallback metadata."],
        warnings=[warning] if warning else [],
    )


def compare_interpretation_to_route(
    interpretation: PromptInterpretation,
    route_plan: RoutePlan,
) -> RoutingComparison:
    if not interpretation.ok:
        return RoutingComparison(
            status="interpreter_unavailable",
            deterministic_task_type=route_plan.task_type,
            deterministic_persona=route_plan.persona,
            deterministic_model_profile=route_plan.model_profile,
        )

    disagreements: list[str] = []
    task_match = interpretation.advised_task_type == route_plan.task_type
    persona_match = interpretation.advised_persona == route_plan.persona
    profile_match = interpretation.advised_model_profile == route_plan.model_profile

    if not task_match:
        disagreements.append(
            f"task_type: deterministic={route_plan.task_type}, advised={interpretation.advised_task_type}"
        )
    if not persona_match:
        disagreements.append(
            f"persona: deterministic={route_plan.persona}, advised={interpretation.advised_persona}"
        )
    if not profile_match:
        disagreements.append(
            f"model_profile: deterministic={route_plan.model_profile}, advised={interpretation.advised_model_profile}"
        )

    return RoutingComparison(
        status="compared",
        deterministic_task_type=route_plan.task_type,
        deterministic_persona=route_plan.persona,
        deterministic_model_profile=route_plan.model_profile,
        advised_task_type=interpretation.advised_task_type,
        advised_persona=interpretation.advised_persona,
        advised_model_profile=interpretation.advised_model_profile,
        task_type_match=task_match,
        persona_match=persona_match,
        model_profile_match=profile_match,
        has_disagreement=bool(disagreements),
        disagreements=disagreements,
    )


def advisory_block(interpretation: PromptInterpretation, comparison: RoutingComparison) -> str:
    if not interpretation.ok:
        return (
            "[Prompt Interpretation Advisory]\n"
            "Status: unavailable\n"
            f"Reason: {interpretation.error}\n"
            "Final route source: deterministic router."
        )

    warnings = "\n".join(f"- {warning}" for warning in interpretation.warnings) or "- None"
    reasons = "\n".join(f"- {reason}" for reason in interpretation.reasons) or "- None"
    disagreements = "\n".join(f"- {item}" for item in comparison.disagreements) or "- None"
    memory_queries = "\n".join(f"- {query}" for query in interpretation.memory_queries) or "- None"
    requested_operations = "\n".join(f"- {item}" for item in interpretation.requested_operations) or "- None"
    context_needs = "\n".join(f"- {item}" for item in interpretation.context_needs) or "- None"
    tool_hints = "\n".join(f"- {item}" for item in interpretation.tool_hints) or "- None"
    return (
        "[Prompt Interpretation Advisory]\n"
        "This block is metadata only. The original [User Request] remains authoritative.\n"
        f"Interpreter source: {interpretation.source}\n"
        f"Advised task type: {interpretation.advised_task_type}\n"
        f"Advised persona: {interpretation.advised_persona}\n"
        f"Advised model profile: {interpretation.advised_model_profile}\n"
        f"Confidence: {interpretation.confidence}\n"
        f"Intent summary: {interpretation.intent_summary}\n"
        f"Refined prompt metadata: {interpretation.refined_prompt}\n"
        f"Response goal: {interpretation.response_goal}\n"
        "Requested operations:\n"
        f"{requested_operations}\n"
        "Context needs:\n"
        f"{context_needs}\n"
        "Tool hints:\n"
        f"{tool_hints}\n"
        "Advisory memory queries:\n"
        f"{memory_queries}\n"
        "Advisory reasons:\n"
        f"{reasons}\n"
        "Warnings:\n"
        f"{warnings}\n"
        f"Comparison status: {comparison.status}\n"
        "Disagreements with deterministic route:\n"
        f"{disagreements}"
    )


def deterministic_intent_needs(user_text: str, route: RoutePlan) -> tuple[list[str], list[str], list[str], str]:
    text = user_text.lower()
    operations = ["answer_question"]
    context_needs = ["persona"]
    tool_hints: list[str] = []

    if route.task_type in {"file_analysis", "document_import"} or any(item in text for item in [".md", ".txt", ".json", ".yaml", ".yml", ".py", ".log", "file", "document"]):
        context_needs.append("files")
        operations.append("analyze_file" if route.task_type == "file_analysis" else "use_tool")
        tool_hints.append("file_analyze" if route.task_type == "file_analysis" else "document_import")
    if route.task_type in {"persona_tooling", "technical_project"} or any(item in text for item in ["system", "router", "tool", "model", "memory", "gui", "tts", "stt", "n8n", "openbrain"]):
        context_needs.extend(["system_registry", "project_context"])
        operations.append("retrieve_system_context")
        tool_hints.append("system_registry")
    if route.memory_queries:
        context_needs.append("memory")
        operations.append("retrieve_memory")
        tool_hints.append("memory_search")
    if any(item in text for item in ["internet", "web", "online", "latest", "current price", "today's", "news", "look up", "search the web"]):
        context_needs.append("web")
        operations.append("web_research")
        tool_hints.append("web_search")
    if any(item in text for item in ["suggest", "recommend", "improve", "critique", "feedback", "evaluate", "assess", "risk", "risks"]):
        operations.extend(["critique_or_feedback", "synthesize"])
    if any(item in text for item in ["draft", "write", "create", "turn this into", "outline", "plan"]):
        operations.append("create_artifact")
    if any(item in text for item in ["this session", "today", "yesterday", "last week", "next month", "tomorrow"]):
        context_needs.append("time")
    if route.context_domain in {"goals", "projects", "tasks", "reminders", "events", "routines", "habits"}:
        context_needs.append("user_context")
    if route.task_type in {"persona_tooling", "persona_relationship"}:
        operations.append("explain_system")

    response_goal = _response_goal_for(route.task_type, operations)
    return _unique(operations), _unique(context_needs), _unique(tool_hints), response_goal


def _response_goal_for(task_type: str, operations: list[str]) -> str:
    if "critique_or_feedback" in operations:
        return "Use gathered context to give grounded feedback and useful next steps."
    if "web_research" in operations:
        return "Answer with current external information after retrieval or clearly note that web retrieval is needed."
    if task_type == "file_analysis":
        return "Use file context as evidence, then answer the full user request."
    if task_type in {"persona_tooling", "persona_relationship"}:
        return "Explain system/persona information from known registries and persona files."
    return "Answer the user's request using the minimum necessary context."


def _extract_json_object(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise PromptInterpretationError("Prompt interpreter returned no JSON object.")
    return match.group(0)


def _require_string(data: dict[str, Any], key: str, allow_empty: bool = False) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise PromptInterpretationError(f"'{key}' must be a string.")
    value = value.strip()
    if not allow_empty and not value:
        raise PromptInterpretationError(f"'{key}' cannot be empty.")
    return value


def _require_enum(data: dict[str, Any], key: str, allowed: list[str]) -> str:
    value = _require_string(data, key)
    if value not in allowed:
        raise PromptInterpretationError(f"'{key}' must be one of {allowed}; got {value!r}.")
    return value


def _require_confidence(data: dict[str, Any]) -> float:
    value = data.get("confidence")
    if not isinstance(value, (int, float)):
        raise PromptInterpretationError("'confidence' must be a number from 0.0 to 1.0.")
    value = float(value)
    if value < 0.0 or value > 1.0:
        raise PromptInterpretationError("'confidence' must be between 0.0 and 1.0.")
    return round(value, 3)


def _require_string_list(
    data: dict[str, Any],
    key: str,
    *,
    min_items: int = 0,
    max_items: int = 8,
) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        raise PromptInterpretationError(f"'{key}' must be an array of strings.")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PromptInterpretationError(f"'{key}' must contain strings only.")
        item = item.strip()
        if item:
            cleaned.append(item)
    if len(cleaned) < min_items:
        raise PromptInterpretationError(f"'{key}' must contain at least {min_items} item(s).")
    if len(cleaned) > max_items:
        raise PromptInterpretationError(f"'{key}' must contain no more than {max_items} item(s).")
    return cleaned


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
