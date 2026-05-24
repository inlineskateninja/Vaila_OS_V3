from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.schemas import MemoryRecord, PromptInterpretation, RequestEnvelope, RoutePlan, RoutingComparison
from app.task_planner import TaskPlan


@dataclass
class OrchestrationPacket:
    schema_version: str
    request_id: str
    persona: str
    persona_display_name: str
    task_type: str
    context_domain: str
    model_profile: str
    fallback_profile: str
    response_type: str
    output_channel: str
    requested_operations: list[str] = field(default_factory=list)
    context_needs: list[str] = field(default_factory=list)
    tool_hints: list[str] = field(default_factory=list)
    response_goal: str = ""
    needs_external_research: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    memory_record_ids: list[str] = field(default_factory=list)
    context_references: list[str] = field(default_factory=list)
    file_references: list[str] = field(default_factory=list)
    route_reasons: list[str] = field(default_factory=list)
    interpreter_source: str = ""
    interpreter_confidence: float = 0.0
    routing_disagreements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_block(self) -> str:
        return (
            "[Orchestration Packet]\n"
            f"Request ID: {self.request_id}\n"
            f"Persona: {self.persona_display_name} ({self.persona})\n"
            f"Task type: {self.task_type}\n"
            f"Context domain: {self.context_domain}\n"
            f"Model profile: {self.model_profile}\n"
            f"Fallback profile: {self.fallback_profile}\n"
            f"Response type: {self.response_type}\n"
            f"Output channel: {self.output_channel}\n"
            f"Response goal: {self.response_goal}\n"
            f"Needs external research: {self.needs_external_research}\n"
            f"Requested operations: {', '.join(self.requested_operations) or 'None'}\n"
            f"Context needs: {', '.join(self.context_needs) or 'None'}\n"
            f"Tool hints: {', '.join(self.tool_hints) or 'None'}\n"
            f"Tool calls: {', '.join(call.get('tool_name', '') for call in self.tool_calls) or 'None'}\n"
            f"Memory records: {', '.join(self.memory_record_ids) or 'None'}\n"
            f"Context references: {', '.join(self.context_references[:8]) or 'None'}\n"
            f"File references: {', '.join(self.file_references[:6]) or 'None'}"
        )


def build_orchestration_packet(
    *,
    request_envelope: RequestEnvelope,
    route_plan: RoutePlan,
    prompt_interpretation: PromptInterpretation,
    routing_comparison: RoutingComparison,
    task_plan: TaskPlan,
    response_route: Any,
    persona_continuity: Any,
    memories: list[MemoryRecord] | None = None,
    tool_calls: list[Any] | None = None,
) -> OrchestrationPacket:
    tool_call_dicts = [
        call.to_dict() if hasattr(call, "to_dict") else dict(call)
        for call in (tool_calls or [])
    ]
    warnings = [*prompt_interpretation.warnings]
    if task_plan.needs_external_research:
        warnings.append("External/current information may be needed before a fully grounded answer.")
    return OrchestrationPacket(
        schema_version="orchestration_packet.v1",
        request_id=request_envelope.id,
        persona=route_plan.persona,
        persona_display_name=persona_continuity.display_name,
        task_type=route_plan.task_type,
        context_domain=route_plan.context_domain,
        model_profile=route_plan.model_profile,
        fallback_profile=route_plan.fallback_profile,
        response_type=response_route.response_type,
        output_channel=response_route.output_channel,
        requested_operations=task_plan.requested_operations,
        context_needs=task_plan.context_needs,
        tool_hints=task_plan.tool_hints,
        response_goal=task_plan.response_goal,
        needs_external_research=task_plan.needs_external_research,
        tool_calls=tool_call_dicts,
        memory_record_ids=[memory.id for memory in memories or []],
        context_references=route_plan.context_references,
        file_references=route_plan.file_references,
        route_reasons=route_plan.reasons,
        interpreter_source=prompt_interpretation.source,
        interpreter_confidence=prompt_interpretation.confidence,
        routing_disagreements=routing_comparison.disagreements,
        warnings=warnings,
    )
