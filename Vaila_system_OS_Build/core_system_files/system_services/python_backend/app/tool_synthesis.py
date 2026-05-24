from __future__ import annotations

import time
from typing import Any

from app.llm_client import LLMClientError, LMStudioClient
from app.model_evaluator import ModelEvaluator
from app.model_registry import ModelRegistry
from app.persona_continuity import PersonaContinuity
from app.persona_selection import persona_selection_prompt_block
from app.prompt_budget import DEFAULT_LLM_CONTEXT_PACKET_MAX_CHARS, fit_context_packet
from app.schemas import RoutePlan
from app.task_planner import TaskPlan


class ToolSynthesizer:
    """Turns raw tool output into persona-aware user responses."""

    def __init__(
        self,
        llm_client: LMStudioClient,
        model_registry: ModelRegistry,
        model_evaluator: ModelEvaluator,
    ) -> None:
        self.llm_client = llm_client
        self.model_registry = model_registry
        self.model_evaluator = model_evaluator

    def synthesize_tool_response(
        self,
        user_text: str,
        route_plan: RoutePlan,
        analysis: dict[str, Any],
        task_plan: TaskPlan,
        response_route: Any,
        persona_continuity: PersonaContinuity,
        result: dict[str, Any],
    ) -> str:
        packet = self._build_tool_synthesis_packet(
            user_text=user_text,
            route_plan=route_plan,
            analysis=analysis,
            task_plan=task_plan,
            response_route=response_route,
            persona_continuity=persona_continuity,
        )
        packet, budget = fit_context_packet(packet, DEFAULT_LLM_CONTEXT_PACKET_MAX_CHARS)
        result["tool_synthesis_prompt_budget"] = budget.to_dict()
        profile_names = self.model_evaluator.choose_profile_order(route_plan.model_profile, route_plan.fallback_profile)
        errors: list[str] = []
        messages = self._build_chat_messages(packet)
        for profile_name in profile_names:
            model_profile = self.model_registry.get_profile_or_none(profile_name)
            if model_profile is None:
                errors.append(f"Profile unavailable: {profile_name}")
                result["attempts"].append({"profile": profile_name, "model": None, "ok": False, "error": "Profile unavailable or no resolved model."})
                continue
            start_time = time.perf_counter()
            try:
                response_text = self.llm_client.chat(
                    model=model_profile["model"],
                    messages=messages,
                    temperature=model_profile.get("temperature", 0.55),
                    max_tokens=model_profile.get("max_tokens", 1200),
                    timeout=model_profile.get("timeout_seconds", 120),
                    extra=model_profile.get("extra"),
                )
                elapsed = round(time.perf_counter() - start_time, 3)
                result["attempts"].append({"profile": model_profile.get("profile_name", profile_name), "model": model_profile.get("model"), "ok": True, "elapsed_seconds": elapsed, "error": ""})
                self.model_evaluator.log_attempt(
                    model_profile.get("profile_name", profile_name),
                    model_profile.get("model"),
                    route_plan.task_type,
                    route_plan.persona,
                    True,
                    elapsed,
                    "",
                )
                result.update(
                    {
                        "selected_profile": model_profile.get("profile_name", profile_name),
                        "model": model_profile.get("model"),
                        "elapsed_seconds": elapsed,
                    }
                )
                return response_text
            except LLMClientError as error:
                elapsed = round(time.perf_counter() - start_time, 3)
                error_text = str(error)
                errors.append(f"{profile_name}: {error_text}")
                result["attempts"].append({"profile": model_profile.get("profile_name", profile_name), "model": model_profile.get("model"), "ok": False, "elapsed_seconds": elapsed, "error": error_text})
                self.model_evaluator.log_attempt(
                    model_profile.get("profile_name", profile_name),
                    model_profile.get("model"),
                    route_plan.task_type,
                    route_plan.persona,
                    False,
                    elapsed,
                    error_text,
                )
        result["tool_synthesis_note"] = "Local synthesis fallback used. " + " | ".join(errors)
        result.update({"selected_profile": "local_synthesis", "model": "local_rule_based", "elapsed_seconds": 0})
        return self._local_tool_synthesis_response(analysis, task_plan, route_plan.persona)

    def _build_tool_synthesis_packet(
        self,
        user_text: str,
        route_plan: RoutePlan,
        analysis: dict[str, Any],
        task_plan: TaskPlan,
        response_route: Any,
        persona_continuity: PersonaContinuity,
    ) -> str:
        key_lines = "\n".join(f"- {line}" for line in analysis.get("key_lines", [])[:8]) or "- None"
        action_items = "\n".join(f"- {item}" for item in analysis.get("action_items", [])[:8]) or "- None"
        warnings = "\n".join(f"- {item}" for item in analysis.get("warnings", [])[:8]) or "- None"
        requested_outputs = ", ".join(task_plan.requested_outputs) or "final synthesis"
        return f"""
[Tool Workflow Synthesis]
Persona: {route_plan.persona}
Context domain: {route_plan.context_domain}
Requested outputs: {requested_outputs}
Response type: {response_route.response_type}

{persona_continuity.to_prompt_block()}

{persona_selection_prompt_block(route_plan)}

[Original User Request]
{user_text}

[Task Plan]
{chr(10).join(f"- {step.kind}: {step.description}" for step in task_plan.steps)}

[File Analysis Result]
File: {analysis.get("path")}
Type: {analysis.get("file_type")}
Lines: {analysis.get("line_count")}
Words: {analysis.get("word_count")}
Summary:
{analysis.get("summary", "")}

Key lines:
{key_lines}

Action items:
{action_items}

Warnings:
{warnings}

[Response Contract]
Do not stop at reporting the raw tool result.
If [Persona Selection] says the interface selection differs from a typed persona address, briefly correct the user before answering.
Use the file analysis as evidence, then satisfy the user's requested outputs.
If suggesting improvements, make them specific and grounded in the analysis.
Preserve the active persona lens.
{response_route.instructions}
Return only the final visible answer.
""".strip()

    def _local_tool_synthesis_response(self, analysis: dict[str, Any], task_plan: TaskPlan, persona: str) -> str:
        lines = [
            "File analysis complete, with follow-up synthesis.",
            "",
            f"File: {analysis.get('path')}",
            f"Type: {analysis.get('file_type')}",
            f"Lines: {analysis.get('line_count')}",
            f"Words: {analysis.get('word_count')}",
            "",
        ]
        lines.extend(file_analysis_persona_lens(analysis, persona))
        lines.extend(["", "Summary:", analysis.get("summary", "")])
        key_lines = analysis.get("key_lines", [])[:5]
        action_items = analysis.get("action_items", [])[:5]
        if key_lines:
            lines.extend(["", "What stands out:"])
            lines.extend(f"- {line}" for line in key_lines)
        if "improvements" in task_plan.requested_outputs or "synthesis" in task_plan.requested_outputs:
            lines.extend(
                [
                    "",
                    "Suggested improvements:",
                    "- Clarify the main purpose of the file at the top so a reader can quickly understand what it is for.",
                    "- Group related points under headings; the analyzer found limited structure to lean on.",
                    "- Turn any unresolved items into explicit next steps with owner, date, and desired outcome.",
                    "- Preserve concrete names, dates, and quotes where accuracy matters, but separate them from interpretation.",
                ]
            )
        if "critique" in task_plan.requested_outputs:
            lines.extend(["", "Risks / issues to check:"])
            warnings = analysis.get("warnings", [])[:5]
            if warnings:
                lines.extend(f"- {warning}" for warning in warnings)
            else:
                lines.extend(
                    [
                        "- The file may need a clearer distinction between observed facts, interpretation, and desired outcome.",
                        "- Any claim that depends on dates, names, or quotes should stay attached to the exact source wording.",
                        "- If this is meant to support a decision, add the missing decision point so the reader knows what action should follow.",
                    ]
                )
        if "artifact" in task_plan.requested_outputs:
            lines.extend(
                [
                    "",
                    "Draftable structure:",
                    "- Purpose: state what this file is meant to accomplish.",
                    "- Evidence: list the strongest concrete points from the file.",
                    "- Interpretation: explain what those points suggest without overstating them.",
                    "- Request or next move: close with the specific action you want taken.",
                ]
            )
        if "next_actions" in task_plan.requested_outputs or action_items:
            lines.extend(["", "Next actions:"])
            if action_items:
                lines.extend(f"- {item}" for item in action_items)
            else:
                lines.append("- Decide what outcome you want from this file: summary, revision, escalation, planning, or memory capture.")
        return "\n".join(lines)

    @staticmethod
    def _build_chat_messages(context_packet: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are the response generation layer for Vaila Persona Core. The user message contains a structured context packet. "
                    "Use the compact LLM packet's persona continuity, relevant memory, task instructions, and user request before giving a generic answer. "
                    "Return a visible final answer only. Do not claim memory was written directly."
                ),
            },
            {"role": "user", "content": context_packet},
        ]


def format_file_analysis_response(
    analysis: dict[str, Any],
    prefix: str = "File analysis complete",
    persona: str = "proto_jane",
    response_route: Any | None = None,
) -> str:
    if not analysis:
        return "No file analysis details were available."

    def section(title: str, items: list[str]) -> list[str]:
        lines = [f"{title}:"]
        if items:
            lines.extend(f"- {item}" for item in items[:10])
        else:
            lines.append("- None")
        return lines

    lines = [
        prefix + ".",
        "",
        f"File: {analysis.get('path')}",
        f"Type: {analysis.get('file_type')}",
        f"Lines: {analysis.get('line_count')}",
        f"Words: {analysis.get('word_count')}",
    ]
    if response_route:
        lines.extend(
            [
                f"Response type: {response_route.response_type}",
                f"TTS engine preference: {response_route.tts_engine}",
                f"Future fallback engine: {response_route.fallback_tts_engine}",
            ]
        )
    lines.append("")
    lines.extend(file_analysis_persona_lens(analysis, persona))
    lines.extend(
        [
            "",
            "Tool summary:",
            analysis.get("summary", ""),
            "",
        ]
    )
    lines.extend(section("Headings / structure", analysis.get("headings", [])))
    lines.append("")
    lines.extend(section("Key lines", analysis.get("key_lines", [])))
    lines.append("")
    lines.extend(section("Action items", analysis.get("action_items", [])))
    lines.append("")
    lines.extend(section("Warnings", analysis.get("warnings", [])))
    return "\n".join(lines)


def file_analysis_persona_lens(analysis: dict[str, Any], persona: str) -> list[str]:
    summary = analysis.get("summary", "")
    key_lines = analysis.get("key_lines", [])
    action_items = analysis.get("action_items", [])

    if persona == "vecht":
        return [
            "Vecht lens:",
            "This reads as an evidence-and-process document. The useful move is to separate what is alleged, what was reported, what response was promised, and what remains unresolved.",
            "Priority: preserve timeline, names, dates, exact claims, promised follow-up, and gaps in response.",
            "Next practical move: turn this into a clean chronology and unresolved-issues list before any escalation or meeting.",
        ]

    if persona == "serren":
        return [
            "Serren lens:",
            "This appears emotionally heavy because it centers on being mischaracterized, not believed, and left without reliable follow-up.",
            "Priority: keep the summary grounded while naming the human impact clearly.",
            "Next supportive move: identify what you need from the record before rereading it, so the document does not pull you back through the whole experience at full force.",
        ]

    if persona == "riven":
        return [
            "Riven lens:",
            "This should be checked for claim clarity, evidence quality, timeline continuity, and places where wording could be misread.",
            "Priority: distinguish direct knowledge, reported statements, inference, and unresolved follow-up.",
        ]

    if persona == "maelith":
        return [
            "Maelith lens:",
            "The document carries a pattern of rupture, testimony, and unanswered repair.",
            "Priority: keep the emotional truth intact while preserving the factual spine.",
        ]

    if key_lines or action_items or summary:
        return [
            "Proto Jane lens:",
            "This is a read-only file analysis. I am separating the tool's extracted signals from any memory-writing or follow-up action.",
        ]

    return [
        "Proto Jane lens:",
        "No strong interpretive signal was available beyond the file metadata.",
    ]
