from __future__ import annotations

from typing import Any, Callable

from app.context_loader import ContextLoader
from app.context_tools import SessionContext
from app.orchestration import OrchestrationPacket
from app.persona_continuity import PersonaContinuity, build_persona_continuity
from app.persona_selection import persona_selection_prompt_block
from app.prompt_budget import (
    DEFAULT_SECTION_MAX_CHARS,
    DEFAULT_USER_REQUEST_MAX_CHARS,
    compact_section_block,
    compact_text,
)
from app.prompt_interpreter import advisory_block
from app.schemas import MemoryRecord, PromptInterpretation, RequestEnvelope, RoutePlan, RoutingComparison
from app.task_planner import TaskPlan


class ContextPacketBuilder:
    """Builds audit and compact LLM context packets for chat responses."""

    def __init__(
        self,
        context_loader: ContextLoader,
        tool_registry_provider: Callable[[], list[dict[str, Any]]],
        service_registry_provider: Callable[[], list[dict[str, Any]]],
    ) -> None:
        self.context_loader = context_loader
        self.tool_registry_provider = tool_registry_provider
        self.service_registry_provider = service_registry_provider

    def build_context_packet(
        self,
        route_plan: RoutePlan,
        memories: list[MemoryRecord],
        response_route: Any | None = None,
        time_context: Any | None = None,
        session_context: SessionContext | None = None,
        request_envelope: RequestEnvelope | None = None,
        prompt_interpretation: PromptInterpretation | None = None,
        routing_comparison: RoutingComparison | None = None,
        persona_continuity: PersonaContinuity | None = None,
        task_plan: TaskPlan | None = None,
        orchestration_packet: OrchestrationPacket | None = None,
    ) -> str:
        memory_blocks = "\n".join(memory.to_prompt_block() for memory in memories) or "No relevant memory records were retrieved."
        memory_blocks, _ = compact_section_block(memory_blocks, 1800, "relevant memory")
        context_blocks = self.context_loader.build_context_blocks(route_plan)
        foundation_context, _ = compact_section_block(context_blocks["foundation_context"], 1600, "foundation context")
        persona_context, _ = compact_section_block(context_blocks["persona_context"], 3200, "persona context")
        task_instructions, _ = compact_section_block(context_blocks["task_instructions"], 1200, "task instructions")
        user_request_for_model = compact_text(route_plan.user_text, DEFAULT_USER_REQUEST_MAX_CHARS, "user request")
        response_instructions = response_route.instructions if response_route else "Format for text reading."
        context_tool_block = (
            session_context.to_prompt_block()
            if session_context
            else time_context.to_prompt_block()
            if time_context
            else "[Session Context Tools]\nNo request context tools were provided."
        )
        context_tool_block, _ = compact_section_block(context_tool_block, 1000, "session context tools")
        request_envelope_block = self._request_envelope_prompt_block(request_envelope)
        prompt_advisory_block = (
            advisory_block(prompt_interpretation, routing_comparison)
            if prompt_interpretation and routing_comparison
            else "[Prompt Interpretation Advisory]\nNo prompt interpretation metadata was provided."
        )
        prompt_advisory_block, _ = compact_section_block(prompt_advisory_block, DEFAULT_SECTION_MAX_CHARS, "prompt interpretation advisory")
        tool_registry_block = self._tool_registry_prompt_block(route_plan)
        persona_continuity = persona_continuity or build_persona_continuity(route_plan.persona)
        persona_continuity_block, _ = compact_section_block(persona_continuity.to_prompt_block(), 1000, "persona continuity")
        task_plan_block = self._task_plan_prompt_block(task_plan)
        orchestration_block = self._orchestration_prompt_block(orchestration_packet)
        selection_block = persona_selection_prompt_block(route_plan)
        return f"""
[Route]
Task type: {route_plan.task_type}
Persona: {route_plan.persona}
Context domain: {route_plan.context_domain}
Model tier: {route_plan.model_tier}
Model profile: {route_plan.model_profile}
Fallback profile: {route_plan.fallback_profile}
Preferred response type: {response_route.response_type if response_route else "text"}
Output channel: {response_route.output_channel if response_route else "text"}
TTS engine preference: {response_route.tts_engine if response_route else "kokoro"}
Future TTS fallback engine: {response_route.fallback_tts_engine if response_route else "chatterbox"}
Voice profile: {response_route.voice_profile_id if response_route else "proto_jane_default"}
Routing reasons:
{chr(10).join(f"- {reason}" for reason in route_plan.reasons)}
Context references:
{chr(10).join(f"- {reference}" for reference in route_plan.context_references) or "- None"}
File references:
{chr(10).join(f"- {reference}" for reference in route_plan.file_references) or "- None"}

{request_envelope_block}

{prompt_advisory_block}

{persona_continuity_block}

{orchestration_block}

{selection_block}

{task_plan_block}

{tool_registry_block}

{context_tool_block}

{foundation_context}

{persona_context}

[Relevant Memory]
{memory_blocks}

{task_instructions}

[User Request]
{user_request_for_model}

[Response Contract]
Answer as the active persona lens named in [Route].
If [Persona Selection] says the interface selection differs from a typed persona address, briefly correct the user before answering.
Use the installed persona library when the user asks who personas are or what influenced them.
Use recent memory for current-state questions and long-term memory for stable identity/project context.
Do not claim that memory has been updated directly. Memory changes become pending candidates that Malik must approve.
If the loaded context does not contain a detail, say so instead of inventing it.
{response_instructions}
Return only the final visible answer.
""".strip()

    def build_llm_context_packet(
        self,
        route_plan: RoutePlan,
        memories: list[MemoryRecord],
        response_route: Any | None = None,
        persona_continuity: PersonaContinuity | None = None,
        task_plan: TaskPlan | None = None,
        orchestration_packet: OrchestrationPacket | None = None,
    ) -> str:
        context_blocks = self.context_loader.build_context_blocks(route_plan)
        persona_context, _ = compact_section_block(context_blocks["persona_context"], 1800, "persona context")
        task_instructions, _ = compact_section_block(context_blocks["task_instructions"], 900, "task instructions")
        memory_blocks = "\n".join(memory.to_prompt_block() for memory in memories) or "No relevant memory records were retrieved."
        memory_blocks, _ = compact_section_block(memory_blocks, 1200, "relevant memory")
        user_request_for_model = compact_text(route_plan.user_text, DEFAULT_USER_REQUEST_MAX_CHARS, "user request")
        persona_continuity = persona_continuity or build_persona_continuity(route_plan.persona)
        response_instructions = response_route.instructions if response_route else "Format for text reading."
        task_plan_block = self._task_plan_prompt_block(task_plan)
        orchestration_block = self._orchestration_prompt_block(orchestration_packet)
        selection_block = persona_selection_prompt_block(route_plan)
        return f"""
[Routing Core]
Persona: {route_plan.persona}
Task type: {route_plan.task_type}
Context domain: {route_plan.context_domain}
Model profile: {route_plan.model_profile}
Response type: {response_route.response_type if response_route else "text"}
Voice profile: {response_route.voice_profile_id if response_route else "proto_jane_default"}

{persona_continuity.to_prompt_block()}

{orchestration_block}

{selection_block}

{task_plan_block}

[Context Pointers]
Context references:
{chr(10).join(f"- {reference}" for reference in route_plan.context_references[:8]) or "- None"}
File references:
{chr(10).join(f"- {reference}" for reference in route_plan.file_references[:6]) or "- None"}

{persona_context}

[Relevant Memory]
{memory_blocks}

{task_instructions}

[User Request]
{user_request_for_model}

[Response Contract]
Answer through {persona_continuity.display_name}'s active lens.
If [Persona Selection] says the interface selection differs from a typed persona address, briefly correct the user before answering.
Use available system/memory context, but do not invent missing details.
Do not claim memory was updated directly.
{response_instructions}
Return only the final visible answer.
""".strip()

    @staticmethod
    def _request_envelope_prompt_block(request_envelope: RequestEnvelope | None) -> str:
        if request_envelope is None:
            return "[Request Envelope]\nNo request envelope was provided."
        return (
            "[Request Envelope]\n"
            f"Request ID: {request_envelope.id}\n"
            f"Received UTC: {request_envelope.received_at}\n"
            f"Source: {request_envelope.source}\n"
            f"Response type: {request_envelope.response_type}\n"
            f"Persona source: {request_envelope.metadata.get('persona_source', 'detect_persona')}\n"
            f"Selected persona: {request_envelope.metadata.get('selected_persona', '') or 'None'}\n"
            f"Original request chars: {len(request_envelope.original_text)}\n"
            "Original request is preserved exactly in request_envelope.original_text and remains authoritative.\n"
            "Do not treat refined_prompt or compacted context as a replacement for what the user actually said."
        )

    def _tool_registry_prompt_block(self, route_plan: RoutePlan) -> str:
        if route_plan.task_type != "persona_tooling":
            return "[Available Tools Registry]\nLoaded only for tool/persona capability questions."
        tools = self.tool_registry_provider()
        services = self.service_registry_provider()
        tool_lines = [
            f"- {tool.get('name')}: {tool.get('description')} "
            f"(read_only={tool.get('read_only')}, approval_required={tool.get('approval_required')})"
            for tool in tools
        ]
        service_lines = [
            f"- {service.get('name')}: {service.get('purpose')} "
            f"(status={service.get('status')}, configured={service.get('configured')})"
            for service in services
        ]
        return (
            "[Available Tools Registry]\n"
            "Answer tool access questions from this registry. Do not invent installed tools.\n"
            "System tools:\n"
            + ("\n".join(tool_lines) if tool_lines else "- None")
            + "\nConnected services:\n"
            + ("\n".join(service_lines) if service_lines else "- None")
        )

    @staticmethod
    def _task_plan_prompt_block(task_plan: TaskPlan | None) -> str:
        if task_plan is None:
            return "[Task Intent Plan]\nNo task intent plan was provided."
        steps = "\n".join(
            f"- {step.step_id}: {step.kind}"
            + (f" via {step.tool_name}" if step.tool_name else "")
            + f" - {step.description}"
            for step in task_plan.steps
        ) or "- None"
        return (
            "[Task Intent Plan]\n"
            f"Mode: {task_plan.mode}\n"
            f"Requires synthesis: {task_plan.requires_synthesis}\n"
            f"Needs external research: {task_plan.needs_external_research}\n"
            f"Response goal: {task_plan.response_goal}\n"
            f"Requested outputs: {', '.join(task_plan.requested_outputs) or 'None'}\n"
            f"Requested operations: {', '.join(task_plan.requested_operations) or 'None'}\n"
            f"Context needs: {', '.join(task_plan.context_needs) or 'None'}\n"
            f"Tool hints: {', '.join(task_plan.tool_hints) or 'None'}\n"
            "Steps:\n"
            f"{steps}"
        )

    @staticmethod
    def _orchestration_prompt_block(orchestration_packet: OrchestrationPacket | None) -> str:
        if orchestration_packet is None:
            return "[Orchestration Packet]\nNo orchestration packet was provided."
        return orchestration_packet.to_prompt_block()
