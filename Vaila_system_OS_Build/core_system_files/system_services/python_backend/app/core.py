from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.activity_log import ActivityLog
from app.candidate_store import CandidateStore
from app.context_packet_builder import ContextPacketBuilder
from app.context_tools import DeviceContext, SessionContext, build_session_context, context_tool_specs
from app.context_loader import ContextLoader
from app.document_importer import DocumentImporter
from app.file_analyzer import FileAnalyzer
from app.llm_client import LLMClientError, LMStudioClient
from app.local_responses import build_local_response
from app.memory_commands import candidate_from_activity, command_list, extract_memory_candidates
from app.memory_store import MemoryStore
from app.model_evaluator import ModelEvaluator
from app.model_registry import ModelRegistry
from app.orchestration import OrchestrationPacket, build_orchestration_packet
from app.paths import find_project_root, get_vaila_paths
from app.persona_continuity import PersonaContinuity, build_persona_continuity
from app.persona_selection import persona_selection_notice, persona_selection_prompt_block
from app.persona_library import PersonaLibrary
from app.project_reviewer import ProjectReviewer
from app.response_routing import build_response_route, format_response_for_route, response_type_options
from app.router import route_user_input
from app.request_envelope import build_request_envelope
from app.service_integrations import ServiceIntegrationRegistry
from app.prompt_interpreter import PromptInterpreter, compare_interpretation_to_route
from app.prompt_budget import (
    DEFAULT_CONTEXT_PACKET_MAX_CHARS,
    DEFAULT_LLM_CONTEXT_PACKET_MAX_CHARS,
    fit_context_packet,
)
from app.schemas import MemoryCandidate, MemoryRecord, PromptInterpretation, RequestEnvelope, RoutePlan, RoutingComparison
from app.task_planner import TaskPlan, build_task_plan
from app.time_context import utc_now
from app.tool_synthesis import ToolSynthesizer, file_analysis_persona_lens, format_file_analysis_response
from app.tooling import ToolResultRecord, ToolResultStore, detect_chat_tool_call, phase2_tool_specs


PROJECT_ROOT = find_project_root(__file__)
DEFAULT_PATHS = get_vaila_paths(PROJECT_ROOT)
MEMORY_ROOT = DEFAULT_PATHS.memory_root
CANDIDATE_ROOT = DEFAULT_PATHS.candidate_root
ACTIVITY_LOG_PATH = DEFAULT_PATHS.activity_log_path
MODEL_EVAL_PATH = DEFAULT_PATHS.model_eval_path
MODEL_PROFILES_PATH = DEFAULT_PATHS.model_profiles_path
TOOL_RESULT_PATH = DEFAULT_PATHS.tool_result_path


class VailaCore:
    """Shared application core used by the CLI and the local API service."""

    def __init__(self, project_root: str | Path = PROJECT_ROOT) -> None:
        self.project_root = Path(project_root)
        self.paths = get_vaila_paths(self.project_root)
        self.memory_root = self.paths.memory_root
        self.candidate_root = self.paths.candidate_root
        self.model_profiles_path = self.paths.model_profiles_path
        self.activity_log_path = self.paths.activity_log_path
        self.model_eval_path = self.paths.model_eval_path
        self.tool_result_path = self.paths.tool_result_path

        self.memory_store = MemoryStore(self.memory_root)
        self.candidate_store = CandidateStore(self.candidate_root)
        self.activity_log = ActivityLog(self.activity_log_path)
        self.model_evaluator = ModelEvaluator(self.model_eval_path)
        self.tool_results = ToolResultStore(self.tool_result_path)
        self.service_integrations = ServiceIntegrationRegistry()
        self.model_registry = ModelRegistry(self.model_profiles_path)
        self.llm_client = LMStudioClient()
        self.prompt_interpreter = PromptInterpreter(self.llm_client, self.model_registry)
        self.document_importer = DocumentImporter(self.project_root, report_path=self.paths.import_report_path)
        self.file_analyzer = FileAnalyzer(self.project_root)
        self.persona_library = PersonaLibrary(self.project_root, personas_root=self.paths.persona_root)
        self.context_loader = ContextLoader(self.project_root, self.persona_library, foundation_root=self.paths.foundation_root)
        self.context_packet_builder = ContextPacketBuilder(
            self.context_loader,
            tool_registry_provider=self.tool_registry,
            service_registry_provider=self.service_registry,
        )
        self.tool_synthesizer = ToolSynthesizer(
            self.llm_client,
            self.model_registry,
            self.model_evaluator,
        )
        self.project_reviewer = ProjectReviewer(
            self.project_root,
            self.memory_store,
            self.candidate_store,
            self.activity_log,
        )
        self.last_model_resolution: dict[str, Any] = {
            "ok": False,
            "message": "Models have not been resolved yet.",
            "available_models": [],
        }

    def load_local_state(self) -> dict[str, Any]:
        self.memory_store.load()
        self.candidate_store.load()
        self.activity_log.load()
        self.model_evaluator.load()
        self.tool_results.load()
        self.service_integrations.load()
        self.persona_library.load()
        self.model_registry.load()
        return self.state_summary()

    def reload(self) -> dict[str, Any]:
        summary = self.load_local_state()
        self.activity_log.append("state_reloaded", "Local state reloaded", summary)
        return summary

    def state_summary(self) -> dict[str, Any]:
        return {
            "memory_records": len(self.memory_store.records),
            "memory_categories": self.memory_store.category_counts(),
            "memory_recency": self.memory_store.recency_counts(),
            "pending_candidates": len(self.candidate_store.list_candidates("pending")),
            "approved_candidates": len(self.candidate_store.list_candidates("approved")),
            "rejected_candidates": len(self.candidate_store.list_candidates("rejected")),
            "activity_events": len(self.activity_log.events),
            "tool_results": len(self.tool_results.records),
            "service_integrations": len(self.service_integrations.integrations),
            "personas": len(self.persona_library.list_personas()),
            "project_root": str(self.project_root),
        }

    def resolve_models(self) -> dict[str, Any]:
        try:
            available_models = self.llm_client.list_models()
            self.model_registry.resolve_available_models(available_models)
            profiles = self._model_profiles_as_dict()
            self.last_model_resolution = {
                "ok": True,
                "message": "Model profiles resolved.",
                "available_models": available_models,
                "profiles": profiles,
            }
            self.activity_log.append("models_resolved", f"Resolved {len(available_models)} available model(s)", {"available_models": available_models})
        except LLMClientError as error:
            self.last_model_resolution = {
                "ok": False,
                "message": str(error),
                "available_models": [],
                "profiles": self._model_profiles_as_dict(),
            }
            self.activity_log.append("models_resolution_failed", "Model resolution failed", {"error": str(error)})
        return self.last_model_resolution

    def _model_profiles_as_dict(self) -> dict[str, dict[str, Any]]:
        if self.model_registry.resolved_profiles:
            return self.model_registry.resolved_profiles
        profiles = self.model_registry.data.get("profiles", {}) if self.model_registry.data else {}
        return {
            profile_name: {
                "profile_name": profile_name,
                **profile,
                "is_available": bool(profile.get("model")),
            }
            for profile_name, profile in profiles.items()
        }

    def route(self, user_text: str, persona_override: str | None = None) -> RoutePlan:
        return route_user_input(user_text, persona_override=persona_override)

    def retrieve_memory(self, route_plan: RoutePlan, per_query_limit: int = 3) -> list[MemoryRecord]:
        retrieved: list[MemoryRecord] = []
        for query in route_plan.memory_queries:
            results = self.memory_store.search(
                query=query,
                persona=route_plan.persona,
                tags=route_plan.memory_tags,
                limit=per_query_limit,
                prefer_recent=True,
            )
            retrieved.extend(results)
        unique_records: dict[str, MemoryRecord] = {}
        for record in retrieved:
            unique_records[record.id] = record
        return list(unique_records.values())

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
        return self.context_packet_builder.build_context_packet(
            route_plan,
            memories,
            response_route=response_route,
            time_context=time_context,
            session_context=session_context,
            request_envelope=request_envelope,
            prompt_interpretation=prompt_interpretation,
            routing_comparison=routing_comparison,
            persona_continuity=persona_continuity,
            task_plan=task_plan,
            orchestration_packet=orchestration_packet,
        )

    def build_llm_context_packet(
        self,
        route_plan: RoutePlan,
        memories: list[MemoryRecord],
        response_route: Any | None = None,
        persona_continuity: PersonaContinuity | None = None,
        task_plan: TaskPlan | None = None,
        orchestration_packet: OrchestrationPacket | None = None,
    ) -> str:
        return self.context_packet_builder.build_llm_context_packet(
            route_plan,
            memories,
            response_route=response_route,
            persona_continuity=persona_continuity,
            task_plan=task_plan,
            orchestration_packet=orchestration_packet,
        )

    def _persona_selection_prompt_block(self, route_plan: RoutePlan) -> str:
        return persona_selection_prompt_block(route_plan)
    def chat(
        self,
        user_text: str,
        include_context: bool = False,
        response_type: str = "short_text",
        persona_id: str | None = None,
        device_id: str | None = None,
        device_type: str | None = None,
        location_available: bool = False,
        location_opt_in: bool = False,
    ) -> dict[str, Any]:
        device_context = DeviceContext.from_values(
            device_id=device_id,
            device_type=device_type,
            location_available=location_available,
            location_opt_in=location_opt_in,
        )
        request_envelope = build_request_envelope(
            user_text,
            response_type=response_type,
            device_context=device_context.to_dict(),
            metadata={
                "persona_source": "interface" if persona_id else "detect_persona",
                "selected_persona": persona_id or "",
            },
        )
        route_plan = self.route(request_envelope.original_text, persona_override=persona_id)
        prompt_interpretation = self.prompt_interpreter.interpret(request_envelope)
        routing_comparison = compare_interpretation_to_route(prompt_interpretation, route_plan)
        persona_continuity = build_persona_continuity(route_plan.persona)
        session_context = build_session_context(request_envelope.original_text, device_context=device_context)
        time_context = session_context.time_context
        response_route = build_response_route(response_type, route_plan.persona)
        tool_call = detect_chat_tool_call(request_envelope.original_text)
        task_plan = build_task_plan(
            request_envelope.original_text,
            route_plan,
            tool_call=tool_call,
            prompt_interpretation=prompt_interpretation,
        )
        if tool_call:
            orchestration_packet = build_orchestration_packet(
                request_envelope=request_envelope,
                route_plan=route_plan,
                prompt_interpretation=prompt_interpretation,
                routing_comparison=routing_comparison,
                task_plan=task_plan,
                response_route=response_route,
                persona_continuity=persona_continuity,
                memories=[],
                tool_calls=[tool_call],
            )
            return self._chat_with_tool(
                request_envelope.original_text,
                route_plan,
                tool_call,
                include_context=include_context,
                response_route=response_route,
                session_context=session_context,
                request_envelope=request_envelope,
                prompt_interpretation=prompt_interpretation,
                routing_comparison=routing_comparison,
                persona_continuity=persona_continuity,
                task_plan=task_plan,
                orchestration_packet=orchestration_packet,
            )

        memories = self.retrieve_memory(route_plan)
        orchestration_packet = build_orchestration_packet(
            request_envelope=request_envelope,
            route_plan=route_plan,
            prompt_interpretation=prompt_interpretation,
            routing_comparison=routing_comparison,
            task_plan=task_plan,
            response_route=response_route,
            persona_continuity=persona_continuity,
            memories=memories,
            tool_calls=[],
        )
        context_packet = self.build_context_packet(
            route_plan,
            memories,
            response_route=response_route,
            time_context=time_context,
            session_context=session_context,
            request_envelope=request_envelope,
            prompt_interpretation=prompt_interpretation,
            routing_comparison=routing_comparison,
            persona_continuity=persona_continuity,
            task_plan=task_plan,
            orchestration_packet=orchestration_packet,
        )
        llm_context_packet = self.build_llm_context_packet(
            route_plan,
            memories,
            response_route=response_route,
            persona_continuity=persona_continuity,
            task_plan=task_plan,
            orchestration_packet=orchestration_packet,
        )

        profile_names = self.model_evaluator.choose_profile_order(route_plan.model_profile, route_plan.fallback_profile)

        base_result: dict[str, Any] = {
            "ok": False,
            "request_envelope": request_envelope.to_dict(),
            "route_plan": asdict(route_plan),
            "prompt_interpretation": prompt_interpretation.to_dict(),
            "routing_comparison": routing_comparison.to_dict(),
            "persona_continuity": persona_continuity.to_dict(),
            "task_plan": task_plan.to_dict(),
            "orchestration_packet": orchestration_packet.to_dict(),
            "memories": [memory.to_dict() for memory in memories],
            "selected_profile": route_plan.model_profile,
            "model": None,
            "elapsed_seconds": None,
            "response": "",
            "error": "",
            "attempts": [],
            "response_route": response_route.to_dict(),
            "request_timestamp": time_context.request_utc,
            "request_local_timestamp": time_context.request_local,
            "time_context": time_context.to_dict(),
            "session_context": session_context.to_dict(),
            "context_tools": [result.to_dict() for result in session_context.tool_results],
            "memory_candidates_created": [],
            "memory_candidate_count": 0,
        }
        context_budget_chars = self._context_budget_for_profiles(profile_names)
        context_packet, audit_prompt_budget = fit_context_packet(context_packet, context_budget_chars)
        llm_context_packet, llm_prompt_budget = fit_context_packet(
            llm_context_packet,
            min(context_budget_chars, DEFAULT_LLM_CONTEXT_PACKET_MAX_CHARS),
        )
        base_result["prompt_budget"] = llm_prompt_budget.to_dict()
        base_result["context_audit_budget"] = audit_prompt_budget.to_dict()
        if include_context:
            base_result["context_packet"] = context_packet
            base_result["llm_context_packet"] = llm_context_packet

        deterministic_response = build_local_response(route_plan)
        if deterministic_response and route_plan.task_type in {"persona_tooling"}:
            deterministic_response = format_response_for_route(deterministic_response, response_route)
            base_result.update(
                {
                    "ok": True,
                    "model": "local_rule_based",
                    "selected_profile": "local_response",
                    "elapsed_seconds": 0,
                    "response": deterministic_response,
                    "error": "",
                }
            )
            return self._finalize_chat_result(base_result, user_text, route_plan)

        messages = self._build_chat_messages(llm_context_packet)
        errors: list[str] = []

        for profile_name in profile_names:
            model_profile = self.model_registry.get_profile_or_none(profile_name)
            if model_profile is None:
                errors.append(f"Profile unavailable: {profile_name}")
                base_result["attempts"].append({"profile": profile_name, "model": None, "ok": False, "error": "Profile unavailable or no resolved model."})
                self.model_evaluator.log_attempt(profile_name, None, route_plan.task_type, route_plan.persona, False, None, "Profile unavailable")
                continue
            start_time = time.perf_counter()
            try:
                response_text = self.llm_client.chat(
                    model=model_profile["model"],
                    messages=messages,
                    temperature=model_profile.get("temperature", 0.7),
                    max_tokens=model_profile.get("max_tokens", 1200),
                    timeout=model_profile.get("timeout_seconds", 120),
                    extra=model_profile.get("extra"),
                )
                elapsed = round(time.perf_counter() - start_time, 3)
                base_result["attempts"].append({"profile": model_profile.get("profile_name", profile_name), "model": model_profile.get("model"), "ok": True, "elapsed_seconds": elapsed, "error": ""})
                self.model_evaluator.log_attempt(model_profile.get("profile_name", profile_name), model_profile.get("model"), route_plan.task_type, route_plan.persona, True, elapsed, "")
                response_text = format_response_for_route(response_text, response_route)
                base_result.update({"ok": True, "model": model_profile.get("model"), "selected_profile": model_profile.get("profile_name", profile_name), "elapsed_seconds": elapsed, "response": response_text, "error": ""})
                return self._finalize_chat_result(base_result, user_text, route_plan)
            except LLMClientError as error:
                elapsed = round(time.perf_counter() - start_time, 3)
                error_text = str(error)
                errors.append(f"{profile_name}: {error_text}")
                base_result["attempts"].append({"profile": model_profile.get("profile_name", profile_name), "model": model_profile.get("model"), "ok": False, "elapsed_seconds": elapsed, "error": error_text})
                self.model_evaluator.log_attempt(model_profile.get("profile_name", profile_name), model_profile.get("model"), route_plan.task_type, route_plan.persona, False, elapsed, error_text)

        local_response = build_local_response(route_plan)
        if local_response:
            local_response = format_response_for_route(local_response, response_route)
            base_result.update({"ok": True, "model": "local_rule_based", "selected_profile": "local_response", "elapsed_seconds": 0, "response": local_response, "error": "Model fallback used local response. " + " | ".join(errors)})
            return self._finalize_chat_result(base_result, user_text, route_plan)

        base_result["error"] = " | ".join(errors) or f"No usable model profile available. Tried primary '{route_plan.model_profile}' and fallback '{route_plan.fallback_profile}'."
        return self._finalize_chat_result(base_result, user_text, route_plan)

    def _chat_with_tool(
        self,
        user_text: str,
        route_plan: RoutePlan,
        tool_call: Any,
        include_context: bool = False,
        response_route: Any | None = None,
        time_context: Any | None = None,
        session_context: SessionContext | None = None,
        request_envelope: RequestEnvelope | None = None,
        prompt_interpretation: PromptInterpretation | None = None,
        routing_comparison: RoutingComparison | None = None,
        persona_continuity: PersonaContinuity | None = None,
        task_plan: TaskPlan | None = None,
        orchestration_packet: OrchestrationPacket | None = None,
    ) -> dict[str, Any]:
        response_route = response_route or build_response_route("text", route_plan.persona)
        persona_continuity = persona_continuity or build_persona_continuity(route_plan.persona)
        task_plan = task_plan or build_task_plan(user_text, route_plan, tool_call=tool_call, prompt_interpretation=prompt_interpretation)
        session_context = session_context or build_session_context(user_text)
        time_context = time_context or session_context.time_context
        if orchestration_packet is None and request_envelope and prompt_interpretation and routing_comparison:
            orchestration_packet = build_orchestration_packet(
                request_envelope=request_envelope,
                route_plan=route_plan,
                prompt_interpretation=prompt_interpretation,
                routing_comparison=routing_comparison,
                task_plan=task_plan,
                response_route=response_route,
                persona_continuity=persona_continuity,
                memories=[],
                tool_calls=[tool_call],
            )
        result: dict[str, Any] = {
            "ok": False,
            "request_envelope": request_envelope.to_dict() if request_envelope else {},
            "route_plan": asdict(route_plan),
            "prompt_interpretation": prompt_interpretation.to_dict() if prompt_interpretation else {},
            "routing_comparison": routing_comparison.to_dict() if routing_comparison else {},
            "persona_continuity": persona_continuity.to_dict(),
            "task_plan": task_plan.to_dict(),
            "orchestration_packet": orchestration_packet.to_dict() if orchestration_packet else {},
            "memories": [],
            "selected_profile": "tool_dispatch",
            "model": "local_tool",
            "elapsed_seconds": 0,
            "response": "",
            "error": "",
            "attempts": [],
            "response_route": response_route.to_dict(),
            "request_timestamp": time_context.request_utc,
            "request_local_timestamp": time_context.request_local,
            "time_context": time_context.to_dict(),
            "session_context": session_context.to_dict(),
            "context_tools": [result.to_dict() for result in session_context.tool_results],
            "tool_calls": [tool_call.to_dict()],
            "tool_results": [],
            "memory_candidates_created": [],
            "memory_candidate_count": 0,
        }
        if include_context:
            result["context_packet"] = "Tool dispatch handled this request before LLM context generation. Request envelope and prompt interpretation metadata are logged in the result."

        try:
            if tool_call.tool_name == "file_analyze":
                if tool_call.arguments.get("missing_path"):
                    raise ValueError("Tell me which supported file to analyze, for example: analyze README.md")
                if tool_call.arguments.get("use_recent"):
                    latest = self.tool_results.latest("file_analyze")
                    if latest is None:
                        raise ValueError("No recent file analysis was found.")
                    path = latest.arguments.get("path")
                    if not path:
                        raise ValueError("The recent file analysis did not include a reusable path.")
                    tool_output = self.analyze_file(path, record_result=True)
                else:
                    tool_output = self.analyze_file(tool_call.arguments["path"], record_result=True)
                analysis = tool_output["analysis"]
                result["ok"] = True
                result["tool_results"] = [tool_output.get("tool_result", {})]
                if task_plan.requires_synthesis:
                    response_text = self._synthesize_tool_response(
                        user_text=user_text,
                        route_plan=route_plan,
                        analysis=analysis,
                        task_plan=task_plan,
                        response_route=response_route,
                        persona_continuity=persona_continuity,
                        result=result,
                    )
                else:
                    response_text = self._format_file_analysis_response(
                        analysis,
                        persona=route_plan.persona,
                        response_route=response_route,
                    )
                result["response"] = format_response_for_route(response_text, response_route)
            elif tool_call.tool_name == "file_analysis_recent":
                latest = self.tool_results.latest("file_analyze")
                if latest is None:
                    raise ValueError("No recent file analysis was found.")
                analysis = latest.result.get("analysis", {})
                result["ok"] = True
                result["tool_results"] = [latest.to_dict()]
                if task_plan.requires_synthesis:
                    result["response"] = self._synthesize_tool_response(
                        user_text=user_text,
                        route_plan=route_plan,
                        analysis=analysis,
                        task_plan=task_plan,
                        response_route=response_route,
                        persona_continuity=persona_continuity,
                        result=result,
                    )
                else:
                    result["response"] = self._format_file_analysis_response(
                        analysis,
                        prefix="Most recent file analysis",
                        persona=route_plan.persona,
                        response_route=response_route,
                    )
                result["response"] = format_response_for_route(result["response"], response_route)
            else:
                raise ValueError(f"Unknown tool call: {tool_call.tool_name}")
        except Exception as error:
            result["error"] = str(error)
            result["response"] = str(error)

        return self._finalize_chat_result(result, user_text, route_plan)

    def _finalize_chat_result(self, result: dict[str, Any], user_text: str, route_plan: RoutePlan) -> dict[str, Any]:
        notice = self._persona_selection_notice(route_plan)
        if notice and result.get("response"):
            response_text = str(result["response"]).lstrip()
            if not response_text.startswith(notice):
                result["persona_selection_notice"] = notice
                result["response"] = f"{notice}\n\n{response_text}"
        result["response_timestamp"] = utc_now()
        candidates = extract_memory_candidates(user_text, route_plan)
        added = self.candidate_store.add_many(candidates) if candidates else []
        result["memory_candidates_created"] = [candidate.to_dict() for candidate in added]
        result["memory_candidate_count"] = len(added)
        if candidates and not added:
            result["memory_candidate_note"] = "A matching chat memory candidate already exists."
        elif added:
            result["memory_candidate_note"] = "Pending memory candidate created. Review it before approval."
        self._log_chat_result(result)
        if added:
            self.activity_log.append("chat_memory_candidate_created", f"Created {len(added)} chat memory candidate(s)", {"candidate_ids": [candidate.id for candidate in added]})
        return result

    def _synthesize_tool_response(
        self,
        user_text: str,
        route_plan: RoutePlan,
        analysis: dict[str, Any],
        task_plan: TaskPlan,
        response_route: Any,
        persona_continuity: PersonaContinuity,
        result: dict[str, Any],
    ) -> str:
        return self.tool_synthesizer.synthesize_tool_response(
            user_text=user_text,
            route_plan=route_plan,
            analysis=analysis,
            task_plan=task_plan,
            response_route=response_route,
            persona_continuity=persona_continuity,
            result=result,
        )

    def _persona_selection_notice(self, route_plan: RoutePlan) -> str:
        return persona_selection_notice(route_plan)
    def _context_budget_for_profiles(self, profile_names: list[str]) -> int:
        budgets: list[int] = []
        for profile_name in profile_names:
            profile = self.model_registry.get_profile_or_none(profile_name)
            if profile is None:
                continue
            value = profile.get("max_input_chars")
            if isinstance(value, int) and value > 0:
                budgets.append(value)
        if not budgets:
            return DEFAULT_CONTEXT_PACKET_MAX_CHARS
        return max(2500, min(budgets))

    def _build_chat_messages(self, context_packet: str) -> list[dict[str, str]]:
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

    def _log_chat_result(self, result: dict[str, Any]) -> None:
        route = result.get("route_plan", {})
        event_type = "chat_completed" if result.get("ok") else "chat_failed"
        user_text = route.get("user_text", "")
        response_text = result.get("response", "") or ""
        self.activity_log.append(
            event_type=event_type,
            summary=user_text[:140] if user_text else "Chat request",
            details={
                "user_text": user_text,
                "request_envelope": result.get("request_envelope"),
                "prompt_interpretation": result.get("prompt_interpretation"),
                "routing_comparison": result.get("routing_comparison"),
                "task_type": route.get("task_type"),
                "persona": route.get("persona"),
                "selected_profile": result.get("selected_profile"),
                "model": result.get("model"),
                "ok": result.get("ok"),
                "elapsed_seconds": result.get("elapsed_seconds"),
                "request_timestamp": result.get("request_timestamp"),
                "response_timestamp": result.get("response_timestamp"),
                "time_context": result.get("time_context"),
                "context_tools": result.get("context_tools"),
                "response_route": result.get("response_route"),
                "persona_continuity": result.get("persona_continuity"),
                "prompt_budget": result.get("prompt_budget"),
                "context_audit_budget": result.get("context_audit_budget"),
                "memory_ids": [memory.get("id") for memory in result.get("memories", [])],
                "memory_candidate_count": result.get("memory_candidate_count", 0),
                "response_excerpt": response_text[:500],
                "error": result.get("error", ""),
            },
        )

    def import_document(self, path: str | Path, tags: list[str] | None = None, persona_scope: list[str] | None = None) -> dict[str, Any]:
        resolved_path = self.resolve_user_path(str(path))
        report, candidates = self.document_importer.import_document(resolved_path, tags=tags or [], persona_scope=persona_scope or ["all"])
        added = self.candidate_store.add_many(candidates)
        result = {"ok": True, "report": report.to_dict(), "added_count": len(added), "skipped_duplicate_count": len(candidates) - len(added), "added_candidate_ids": [candidate.id for candidate in added]}
        self.activity_log.append("document_imported", f"Imported {resolved_path.name} as memory candidates", {"path": str(resolved_path), "added_count": len(added), "skipped_duplicate_count": len(candidates) - len(added)})
        return result

    def analyze_file(self, path: str | Path, record_result: bool = True) -> dict[str, Any]:
        resolved_path = self.resolve_user_path(str(path))
        analysis = self.file_analyzer.analyze(resolved_path)
        result = {"ok": True, "analysis": analysis.to_dict()}
        tool_record: ToolResultRecord | None = None
        if record_result:
            tool_record = self.tool_results.append(
                tool_name="file_analyze",
                arguments={"path": str(resolved_path)},
                ok=True,
                result=result,
            )
            result["tool_result"] = tool_record.to_dict()
        self.activity_log.append(
            "file_analyzed",
            f"Analyzed {resolved_path.name}",
            {
                "path": str(resolved_path),
                "tool_result_id": tool_record.id if tool_record else "",
                "file_type": analysis.file_type,
                "line_count": analysis.line_count,
                "warning_count": len(analysis.warnings),
            },
        )
        return result

    def list_candidates(self, status: str = "pending") -> list[dict[str, Any]]:
        return [candidate.to_dict() for candidate in self.candidate_store.list_candidates(status)]

    def get_candidate(self, candidate_id: str) -> MemoryCandidate | None:
        return self.candidate_store.get(candidate_id)

    def approve_candidate(self, candidate_id: str) -> dict[str, Any]:
        candidate, target_path = self.candidate_store.approve(candidate_id, self.memory_store)
        result = {"ok": True, "candidate": candidate.to_dict(), "written_to": self._display_path(target_path), "memory_records": len(self.memory_store.records)}
        self.activity_log.append("candidate_approved", f"Approved memory candidate {candidate.id}", {"candidate_id": candidate.id, "written_to": result["written_to"], "category": candidate.category})
        return result

    def reject_candidate(self, candidate_id: str, note: str = "") -> dict[str, Any]:
        candidate = self.candidate_store.reject(candidate_id, note=note)
        result = {"ok": True, "candidate": candidate.to_dict()}
        self.activity_log.append("candidate_rejected", f"Rejected memory candidate {candidate.id}", {"candidate_id": candidate.id, "review_note": note})
        return result

    def search_memory(self, query: str, persona: str = "proto_jane", tags: list[str] | None = None, limit: int = 8, category: str | None = None) -> list[dict[str, Any]]:
        scored = self.memory_store.search_scored(query=query, persona=persona, tags=tags or [], limit=limit, category=category)
        return [{"score": score, "recency": self._memory_recency(record), **record.to_dict()} for score, record in scored]

    def list_personas(self) -> list[dict[str, Any]]:
        return [info.to_dict() for info in self.persona_library.list_personas()]

    def memory_commands(self) -> list[dict[str, Any]]:
        return command_list()

    def response_type_options(self) -> list[dict[str, str]]:
        return response_type_options()

    def tool_registry(self) -> list[dict[str, Any]]:
        return [tool.to_dict() for tool in [*context_tool_specs(), *phase2_tool_specs()]]

    def context_tool_registry(self) -> list[dict[str, Any]]:
        return [tool.to_dict() for tool in context_tool_specs()]

    def service_registry(self) -> list[dict[str, Any]]:
        return self.service_integrations.list()

    def service_health(self, name: str) -> dict[str, Any]:
        return self.service_integrations.health(name)

    def recent_tool_result(self, tool_name: str | None = None) -> dict[str, Any] | None:
        record = self.tool_results.latest(tool_name)
        return record.to_dict() if record else None

    def propose_memories_from_recent_chat(self, limit: int = 20) -> dict[str, Any]:
        events = self.activity_log.recent(limit=limit, event_type="chat_completed")
        candidates = []
        for event in events:
            candidate = candidate_from_activity(event.to_dict())
            if candidate:
                candidates.append(candidate)
        added = self.candidate_store.add_many(candidates)
        self.activity_log.append("chat_memory_review", f"Proposed {len(added)} memory candidate(s) from recent chat", {"candidate_ids": [candidate.id for candidate in added]})
        return {"ok": True, "created": [candidate.to_dict() for candidate in added], "created_count": len(added), "reviewed_events": len(events)}

    def delete_memory_proposal(self, topic: str, limit: int = 20) -> dict[str, Any]:
        matches = self.search_memory(topic, limit=limit)
        self.activity_log.append("memory_delete_proposal", f"Generated delete proposal for topic: {topic}", {"matches": [record.get("id") for record in matches]})
        return {"ok": True, "topic": topic, "matches": matches, "message": "No memories were deleted. Review these matches manually before destructive action."}

    def recent_activity(self, limit: int = 50, event_type: str | None = None) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.activity_log.recent(limit=limit, event_type=event_type)]

    def project_review(self, limit: int = 50) -> dict[str, Any]:
        review = self.project_reviewer.build_review(limit=limit)
        review["memory_categories"] = self.memory_store.category_counts()
        review["memory_recency"] = self.memory_store.recency_counts()
        review["model_evaluation"] = self.model_evaluator.summary()
        self.activity_log.append("project_review_generated", "Generated Phase 2 project review", {"pending_candidates": review["state"].get("pending_candidates"), "memory_records": review["state"].get("memory_records")})
        return review

    def model_evaluation(self) -> dict[str, Any]:
        return self.model_evaluator.summary()

    def _format_file_analysis_response(
        self,
        analysis: dict[str, Any],
        prefix: str = "File analysis complete",
        persona: str = "proto_jane",
        response_route: Any | None = None,
    ) -> str:
        return format_file_analysis_response(
            analysis,
            prefix=prefix,
            persona=persona,
            response_route=response_route,
        )

    def _file_analysis_persona_lens(self, analysis: dict[str, Any], persona: str) -> list[str]:
        return file_analysis_persona_lens(analysis, persona)
    @staticmethod
    def _memory_recency(record: MemoryRecord) -> str:
        from app.memory_store import recency_bucket
        return recency_bucket(record)

    def resolve_user_path(self, value: str) -> Path:
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            return candidate
        project_candidate = self.project_root / candidate
        if project_candidate.exists():
            return project_candidate
        return (Path.cwd() / candidate).resolve()

    def _display_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.project_root))
        except ValueError:
            return str(path)



