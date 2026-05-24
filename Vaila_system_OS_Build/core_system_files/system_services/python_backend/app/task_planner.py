from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.schemas import PromptInterpretation, RoutePlan
from app.tooling import ToolCall


SYNTHESIS_CUES = [
    "suggest", "recommend", "improve", "improvements", "what should", "next step", "next steps",
    "fix", "revise", "rewrite", "edit", "clean up", "make better", "critique", "evaluate",
    "assess", "action item", "action items", "plan", "turn this into", "draft", "create",
    "compare", "explain what to do", "give me options", "risks", "issues", "problems",
]

ANALYSIS_ONLY_CUES = [
    "analyze", "analyse", "inspect", "review", "scan", "summarize", "summarise", "read",
]


@dataclass
class TaskStep:
    step_id: str
    kind: str
    description: str
    tool_name: str = ""
    status: str = "planned"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskPlan:
    mode: str
    requires_synthesis: bool
    requested_outputs: list[str] = field(default_factory=list)
    requested_operations: list[str] = field(default_factory=list)
    context_needs: list[str] = field(default_factory=list)
    tool_hints: list[str] = field(default_factory=list)
    response_goal: str = ""
    needs_external_research: bool = False
    steps: list[TaskStep] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "requires_synthesis": self.requires_synthesis,
            "requested_outputs": self.requested_outputs,
            "requested_operations": self.requested_operations,
            "context_needs": self.context_needs,
            "tool_hints": self.tool_hints,
            "response_goal": self.response_goal,
            "needs_external_research": self.needs_external_research,
            "steps": [step.to_dict() for step in self.steps],
            "reasons": self.reasons,
        }


def build_task_plan(
    user_text: str,
    route_plan: RoutePlan,
    tool_call: ToolCall | None = None,
    prompt_interpretation: PromptInterpretation | None = None,
) -> TaskPlan:
    normalized = re.sub(r"\s+", " ", user_text.lower()).strip()
    requested_outputs = detect_requested_outputs(normalized, prompt_interpretation)
    requested_operations = detect_requested_operations(normalized, route_plan, prompt_interpretation)
    context_needs = detect_context_needs(normalized, route_plan, tool_call, prompt_interpretation)
    tool_hints = detect_tool_hints(normalized, tool_call, prompt_interpretation)
    response_goal = (
        prompt_interpretation.response_goal
        if prompt_interpretation and prompt_interpretation.response_goal
        else default_response_goal(route_plan.task_type, requested_operations)
    )
    needs_external_research = "web" in context_needs or "web_research" in requested_operations
    requires_synthesis = bool(requested_outputs) or "synthesize" in requested_operations or "critique_or_feedback" in requested_operations
    steps: list[TaskStep] = []
    reasons: list[str] = []

    if context_needs:
        steps.append(
            TaskStep(
                step_id="step_1",
                kind="context",
                description="Gather required context before final response: " + ", ".join(context_needs),
            )
        )
        reasons.append("Context needs identified: " + ", ".join(context_needs) + ".")

    if tool_call:
        steps.append(
            TaskStep(
                step_id=f"step_{len(steps) + 1}",
                kind="tool",
                tool_name=tool_call.tool_name,
                description=f"Run {tool_call.tool_name} to gather source information.",
            )
        )
        reasons.append(f"Tool call detected: {tool_call.tool_name}.")

    if needs_external_research:
        steps.append(
            TaskStep(
                step_id=f"step_{len(steps) + 1}",
                kind="external_research",
                tool_name="web_search",
                description="External/current information is needed before a fully grounded answer.",
            )
        )
        reasons.append("Prompt appears to need current or internet-backed information.")

    if requires_synthesis:
        steps.append(
            TaskStep(
                step_id=f"step_{len(steps) + 1}",
                kind="synthesis",
                description="Use gathered tool results and the active persona lens to produce the requested final answer.",
            )
        )
        reasons.append("User asked for interpretation or follow-up output beyond raw tool results.")

    if not steps:
        steps.append(
            TaskStep(
                step_id="step_1",
                kind="response",
                description="Respond directly from route, memory, and context.",
            )
        )
        reasons.append("No tool step was required.")

    if not requires_synthesis and tool_call:
        reasons.append("Tool result can serve as the final response.")

    mode = determine_mode(tool_call=tool_call, requires_synthesis=requires_synthesis, context_needs=context_needs, needs_external_research=needs_external_research)
    return TaskPlan(
        mode=mode,
        requires_synthesis=requires_synthesis,
        requested_outputs=requested_outputs,
        requested_operations=requested_operations,
        context_needs=context_needs,
        tool_hints=tool_hints,
        response_goal=response_goal,
        needs_external_research=needs_external_research,
        steps=steps,
        reasons=reasons,
    )


def determine_mode(
    tool_call: ToolCall | None,
    requires_synthesis: bool,
    context_needs: list[str],
    needs_external_research: bool,
) -> str:
    if needs_external_research:
        return "research_then_respond"
    if tool_call and requires_synthesis:
        return "tool_then_synthesize"
    if tool_call:
        return "tool_only"
    if requires_synthesis:
        return "context_then_synthesize"
    if context_needs:
        return "context_then_response"
    return "direct_response"


def detect_requested_operations(
    normalized_text: str,
    route_plan: RoutePlan,
    prompt_interpretation: PromptInterpretation | None = None,
) -> list[str]:
    operations = ["answer_question"]
    if prompt_interpretation and prompt_interpretation.requested_operations:
        operations.extend(prompt_interpretation.requested_operations)
    if route_plan.task_type == "file_analysis" or any(item in normalized_text for item in [".md", ".txt", ".json", ".yaml", ".yml", ".py", ".log"]):
        operations.append("analyze_file")
    if route_plan.task_type in {"document_import", "file_analysis"}:
        operations.append("use_tool")
    if route_plan.memory_queries:
        operations.append("retrieve_memory")
    if route_plan.task_type in {"technical_project", "persona_tooling", "persona_relationship"}:
        operations.append("retrieve_system_context")
    if any(item in normalized_text for item in SYNTHESIS_CUES):
        operations.append("synthesize")
    if any(item in normalized_text for item in ["suggest", "recommend", "improve", "critique", "feedback", "evaluate", "assess", "risk", "risks"]):
        operations.append("critique_or_feedback")
    if any(item in normalized_text for item in ["internet", "web", "online", "latest", "look up", "news", "search the web"]):
        operations.append("web_research")
    if any(item in normalized_text for item in ["draft", "write", "create", "turn this into", "outline"]):
        operations.append("create_artifact")
    return _unique(operations)


def detect_context_needs(
    normalized_text: str,
    route_plan: RoutePlan,
    tool_call: ToolCall | None = None,
    prompt_interpretation: PromptInterpretation | None = None,
) -> list[str]:
    needs = ["persona"]
    if prompt_interpretation and prompt_interpretation.context_needs:
        needs.extend(prompt_interpretation.context_needs)
    if route_plan.memory_queries:
        needs.append("memory")
    if route_plan.context_domain in {"goals", "projects", "tasks", "reminders", "events", "routines", "habits"}:
        needs.append("user_context")
    if route_plan.task_type in {"technical_project", "persona_tooling", "persona_relationship"}:
        needs.extend(["system_registry", "project_context"])
    if route_plan.task_type in {"file_analysis", "document_import"} or tool_call or route_plan.file_references:
        needs.append("files")
    if any(item in normalized_text for item in ["today", "yesterday", "tomorrow", "last week", "next month", "this session"]):
        needs.append("time")
    if any(item in normalized_text for item in ["internet", "web", "online", "latest", "look up", "news", "search the web"]):
        needs.append("web")
    return _unique(needs)


def detect_tool_hints(
    normalized_text: str,
    tool_call: ToolCall | None = None,
    prompt_interpretation: PromptInterpretation | None = None,
) -> list[str]:
    hints: list[str] = []
    if prompt_interpretation and prompt_interpretation.tool_hints:
        hints.extend(prompt_interpretation.tool_hints)
    if tool_call:
        hints.append(tool_call.tool_name)
    if "memory" in normalized_text:
        hints.append("memory_search")
    if any(item in normalized_text for item in ["internet", "web", "online", "latest", "look up", "news", "search the web"]):
        hints.append("web_search")
    if any(item in normalized_text for item in ["system", "router", "tool", "model", "persona"]):
        hints.append("system_registry")
    return _unique(hints)


def default_response_goal(task_type: str, requested_operations: list[str]) -> str:
    if "web_research" in requested_operations:
        return "Gather current external information before producing the final answer."
    if "critique_or_feedback" in requested_operations:
        return "Give grounded feedback and practical improvements."
    if task_type == "file_analysis":
        return "Use file analysis as evidence for the requested answer."
    if task_type == "persona_tooling":
        return "Explain available and needed system tools from registry context."
    return "Answer the user's request with the needed context and persona lens."


def detect_requested_outputs(
    normalized_text: str,
    prompt_interpretation: PromptInterpretation | None = None,
) -> list[str]:
    outputs: list[str] = []
    if any(cue in normalized_text for cue in SYNTHESIS_CUES):
        outputs.append("synthesis")
    if any(cue in normalized_text for cue in ["suggest", "recommend", "improve", "improvements", "fix", "revise", "rewrite", "edit", "make better"]):
        outputs.append("improvements")
    if any(cue in normalized_text for cue in ["next step", "next steps", "action item", "action items", "plan", "what should"]):
        outputs.append("next_actions")
    if any(cue in normalized_text for cue in ["risk", "risks", "issue", "issues", "problems", "critique", "evaluate", "assess"]):
        outputs.append("critique")
    if any(cue in normalized_text for cue in ["draft", "create", "turn this into", "rewrite"]):
        outputs.append("artifact")

    if prompt_interpretation and prompt_interpretation.ok:
        text = " ".join(
            [
                prompt_interpretation.intent_summary,
                prompt_interpretation.refined_prompt,
                " ".join(prompt_interpretation.reasons),
            ]
        ).lower()
        if any(cue in text for cue in SYNTHESIS_CUES):
            outputs.append("interpreter_synthesis")

    return _unique(outputs)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
