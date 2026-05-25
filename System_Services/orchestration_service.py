from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from System_Services.envelope_service import PromptEnvelope
from System_Services.llm_gateway import LLMGateway
from System_Services.logging_service import LoggingService
from System_Services.memory_service import MemoryService
from System_Services.prompt_interpreter import PromptInterpreter
from System_Services.tool_execution_service import ToolExecutionService, ToolResult
from System_Services.tool_intent_service import ToolIntent
from System_Services.tool_permission_service import ToolPermissionService
from System_Tools.file_analyzer import FileAnalyzer
from System_Tools.log_summarizer import LogSummarizer
from System_Tools.self_assessment import SelfAssessmentTool
from System_Services.n8n_service import N8NService
from System_Tools.n8n_workflow_manager import N8NWorkflowManager
from System_Tools.user_profile_tool import UserProfileTool

# Import new advanced system tools
from System_Tools.tool_registry_inspector import ToolRegistryInspector
from System_Tools.system_dependency_doctor import SystemDependencyDoctor
from System_Tools.memory_review_console import MemoryReviewConsole
from System_Tools.memory_backend_adapter import MemoryBackendAdapterFactory
from System_Tools.self_model_diff_tool import SelfModelDiffTool
from System_Tools.capability_map_generator import CapabilityMapGenerator
from System_Tools.behavior_regression_tester import BehaviorRegressionTester
from System_Tools.patch_proposal_reviewer import PatchProposalReviewer
from System_Tools.goal_task_tracker import GoalTaskTracker
from System_Tools.n8n_workflow_librarian import N8NWorkflowLibrarian
from System_Tools.artifact_indexer import ArtifactIndexer
from System_Tools.safety_boundary_auditor import SafetyBoundaryAuditor
from System_Tools.persona_drift_monitor import PersonaDriftMonitor
from System_Tools.user_context_router import UserContextRouter
from System_Tools.self_evolution_planner import SelfEvolutionPlanner


@dataclass
class OrchestrationResponse:
    visible_text: str
    meta: dict[str, Any] = field(default_factory=dict)


class OrchestrationService:
    PERSONA_CONTEXT_MAX_CHARS = 2200
    TOOL_CONTEXT_MAX_CHARS = 3000

    def __init__(self, project_root: Path, logger: LoggingService) -> None:
        self.project_root = project_root
        self.logger = logger
        self.llm = LLMGateway(project_root=project_root)
        self.memory = MemoryService(project_root=project_root, logger=logger)
        self.prompt_interpreter = PromptInterpreter(project_root=project_root)
        self.tool_permissions = ToolPermissionService(project_root=project_root)
        self.tool_execution = ToolExecutionService(project_root=project_root)
        self.file_analyzer = FileAnalyzer(project_root=project_root)
        self.log_summarizer = LogSummarizer(project_root=project_root)
        self.self_assessment = SelfAssessmentTool(project_root=project_root)
        self.n8n = N8NService(project_root=project_root)
        self.n8n_manager = N8NWorkflowManager(project_root=project_root)
        self.user_profile = UserProfileTool(project_root=project_root)
        
        # Initialize new advanced system tools
        self.registry_inspector = ToolRegistryInspector(project_root=project_root)
        self.dependency_doctor = SystemDependencyDoctor(project_root=project_root)
        self.memory_review_console = MemoryReviewConsole(project_root=project_root)
        self.memory_adapter = MemoryBackendAdapterFactory.get_adapter(project_root=project_root)
        self.model_diff_tool = SelfModelDiffTool(project_root=project_root)
        self.capability_map_generator = CapabilityMapGenerator(project_root=project_root)
        self.behavior_regression_tester = BehaviorRegressionTester(project_root=project_root)
        self.patch_proposal_reviewer = PatchProposalReviewer(project_root=project_root)
        self.goal_task_tracker = GoalTaskTracker(project_root=project_root)
        self.n8n_workflow_librarian = N8NWorkflowLibrarian(project_root=project_root)
        self.artifact_indexer = ArtifactIndexer(project_root=project_root)
        self.safety_boundary_auditor = SafetyBoundaryAuditor(project_root=project_root)
        self.persona_drift_monitor = PersonaDriftMonitor(project_root=project_root)
        self.user_context_router = UserContextRouter(project_root=project_root)
        self.self_evolution_planner = SelfEvolutionPlanner(project_root=project_root)

        self.chat_histories: dict[str, list[dict[str, str]]] = {}

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        if session_id not in self.chat_histories:
            self.chat_histories[session_id] = []
        return self.chat_histories[session_id]

    def clear_history(self, session_id: str) -> None:
        if session_id in self.chat_histories:
            self.chat_histories[session_id].clear()

    def handle(self, envelope: PromptEnvelope, route: dict[str, Any]) -> OrchestrationResponse:
        tool_context = ""
        llm_error = ""
        audit_queued = False

        task_type = route.get("task_type")

        if task_type == "assistant_tool":
            response = self._handle_assistant_tool(envelope=envelope, route=route)
            self.logger.run_background(self.memory.capture_memory_candidate, envelope, deepcopy(route))
            return response

        if task_type == "assistant_tool_candidate":
            response = self._handle_assistant_tool_candidate(envelope=envelope, route=route)
            self.logger.run_background(self.memory.capture_memory_candidate, envelope, deepcopy(route))
            return response

        if task_type == "file_analysis":
            file_path = self._extract_windows_path(envelope.user_text)
            if file_path:
                analysis = self.file_analyzer.analyze_file(file_path)
                tool_context = f"File analysis result:\n{analysis}"
            else:
                tool_context = "No file path detected. Ask the user for a file path only if needed."

        elif task_type == "log_summary":
            tool_context = self.log_summarizer.summarize_recent_logs()

        elif task_type == "n8n_workflows":
            tool_context = self._handle_n8n_workflows(envelope, route)

        elif task_type == "tool_registry_inspection":
            tool_context = self.registry_inspector.render_report()

        elif task_type == "system_dependency_doctor":
            tool_context = self.dependency_doctor.render_report()

        elif task_type == "memory_review_console":
            tool_context = f"Active memory candidates for review:\n{json.dumps(self.memory_review_console.list_reviewable_candidates(), indent=2)}"

        elif task_type == "memory_backend_adapter":
            tool_context = f"Active memories using {self.memory_adapter.__class__.__name__}:\n{json.dumps(self.memory_adapter.read_memories(), indent=2)}"

        elif task_type == "self_model_diff":
            tool_context = self.model_diff_tool.render_diff_report()

        elif task_type == "capability_map":
            tool_context = self.capability_map_generator.render_mermaid_flowchart()

        elif task_type == "behavior_regression":
            tool_context = self.behavior_regression_tester.render_regression_report()

        elif task_type == "patch_proposal_review":
            tool_context = f"Available patches in sandbox:\n{json.dumps(self.patch_proposal_reviewer.list_patches(), indent=2)}"

        elif task_type == "goal_task_tracking":
            tool_context = self.goal_task_tracker.render_kanban_board()

        elif task_type == "n8n_librarian":
            tool_context = f"n8n Librarian catalog:\n{json.dumps(self.n8n_workflow_librarian.list_library_workflows(), indent=2)}"

        elif task_type == "artifact_indexing":
            tool_context = f"Artifact Index catalog:\n{json.dumps(self.artifact_indexer.load_index()[:10], indent=2)}"

        elif task_type == "safety_boundary_auditing":
            tool_context = self.safety_boundary_auditor.render_safety_report()

        elif task_type == "persona_drift_monitoring":
            tool_context = self.persona_drift_monitor.render_drift_report()

        elif task_type == "user_context_routing":
            tool_context = self.user_context_router.render_analysis_report()

        elif task_type == "self_evolution_planning":
            tool_context = self.self_evolution_planner.render_evolution_report()
            # Also auto-export to sandbox on evolution queries
            self.self_evolution_planner.export_evolution_plan()

        elif task_type == "self_assessment":
            tool_context = self.self_assessment.run_self_assessment()
            self.logger.run_background(self.memory.capture_memory_candidate, envelope, deepcopy(route))
            return OrchestrationResponse(
                visible_text=tool_context,
                meta={
                    "request_id": envelope.request_id,
                    "route": route,
                    "used_tool_context": True,
                    "prompt_interpreter": "not_needed",
                    "memory_candidate_capture": "background_queued",
                    "llm": {
                        "base_url": self.llm.base_url,
                        "model": self.llm._resolved_model or self.llm.model or "(auto)",
                        "error": "",
                    },
                },
            )

        # Dynamically match active user profile modules
        profile_res = self.user_profile.route_context(envelope.user_text)
        user_profile_context = profile_res.get("context_block", "")

        # Log User Context telemetry
        self.user_context_router.log_routing_event(
            prompt=envelope.user_text,
            loaded_modules=profile_res.get("loaded_modules", []),
            matched_keywords=profile_res.get("matched_keywords", {}),
            context_size_chars=len(user_profile_context)
        )

        persona_context = self._load_persona_context(route.get("persona", "proto_jane"))

        # Retrieve session-specific chat history
        session_id = envelope.metadata.get("session_id", "default")
        history = self.get_history(session_id)

        messages = [
            {
                "role": "system",
                "content": self._build_system_prompt(
                    persona_context=persona_context, route=route, user_profile_context=user_profile_context
                ),
            }
        ]
        # Append conversation history
        messages.extend(history)
        # Append current user prompt
        messages.append({
            "role": "user",
            "content": self._build_user_content(envelope=envelope, tool_context=tool_context),
        })

        try:
            llm_text = self.llm.execute_with_fallback(messages=messages)
            visible_text = llm_text.strip() if llm_text.strip() else self._fallback_response(route, tool_context)
            
            # Save successful turns to history
            if not llm_error and visible_text:
                history.append({"role": "user", "content": envelope.user_text})
                history.append({"role": "assistant", "content": visible_text})
                if len(history) > 20:
                    history[:] = history[-20:]
        except Exception as exc:
            llm_error = str(exc)
            self.logger.log_error(
                {
                    "event_type": "llm_gateway_error",
                    "request_id": envelope.request_id,
                    "error": llm_error,
                    "gateway": self.llm.diagnostics(),
                }
            )
            visible_text = self._fallback_response(route, tool_context, llm_error)

        if route.get("needs_prompt_interpreter"):
            audit_queued = True
            self.logger.run_background(self._audit_prompt_interpretation, envelope, deepcopy(route))

        self.logger.run_background(self.memory.capture_memory_candidate, envelope, deepcopy(route))

        return OrchestrationResponse(
            visible_text=visible_text,
            meta={
                "request_id": envelope.request_id,
                "route": route,
                "used_tool_context": bool(tool_context),
                "prompt_interpreter": "background_audit_queued" if audit_queued else "not_needed",
                "memory_candidate_capture": "background_queued",
                "user_profile_routing": {
                    "loaded_modules": profile_res.get("loaded_modules", []),
                    "matched_keywords": profile_res.get("matched_keywords", {})
                },
                "llm": {
                    "base_url": self.llm.base_url,
                    "model": self.llm._resolved_model or self.llm.model or "(auto)",
                    "error": llm_error,
                },
            },
        )

    def _handle_assistant_tool(self, envelope: PromptEnvelope, route: dict[str, Any]) -> OrchestrationResponse:
        tool_intent = self._route_tool_intent(route, envelope)
        permission = self.tool_permissions.explain_permission(tool_intent)
        approved = bool(envelope.metadata.get("tool_approved") or envelope.metadata.get("approved_tool_execution"))

        result = self.tool_execution.execute_intent(tool_intent, approved=approved)
        visible_text = self._format_tool_response(
            result=result,
            route=route,
            permission=permission,
        )

        return OrchestrationResponse(
            visible_text=visible_text,
            meta={
                "request_id": envelope.request_id,
                "route": route,
                "used_tool_context": True,
                "assistant_tool": {
                    "intent": self._tool_intent_to_dict(tool_intent),
                    "permission": permission,
                    "result": result.to_dict(),
                },
                "memory_candidate_capture": "background_queued",
                "prompt_interpreter": "not_needed",
            },
        )

    def _handle_assistant_tool_candidate(self, envelope: PromptEnvelope, route: dict[str, Any]) -> OrchestrationResponse:
        tool_intent = self._route_tool_intent(route, envelope)
        question = tool_intent.clarification_question or (
            f"I might use {tool_intent.tool_id}.{tool_intent.action}, but I need one more detail before I touch tools. "
            "What exactly would you like me to do?"
        )
        persona = route.get("persona", "proto_jane")
        visible_text = f"{self._persona_prefix(persona)}{question}"

        return OrchestrationResponse(
            visible_text=visible_text,
            meta={
                "request_id": envelope.request_id,
                "route": route,
                "used_tool_context": False,
                "assistant_tool_candidate": {
                    "intent": self._tool_intent_to_dict(tool_intent),
                    "executed": False,
                },
                "memory_candidate_capture": "background_queued",
                "prompt_interpreter": "clarification_requested",
            },
        )

    def _route_tool_intent(self, route: dict[str, Any], envelope: PromptEnvelope) -> ToolIntent:
        data = route.get("tool_intent")
        if not isinstance(data, dict) or not data:
            from System_Services.tool_intent_service import ToolIntentService

            return ToolIntentService(project_root=self.project_root).detect_intent(envelope.user_text, source=envelope.source)

        return ToolIntent(
            intent_id=str(data.get("intent_id", "general_chat")),
            tool_id=str(data.get("tool_id", "general_chat")),
            service_id=str(data.get("service_id", "assistant")),
            action=str(data.get("action", "chat")),
            confidence=float(data.get("confidence", 0.0)),
            risk_level=str(data.get("risk_level", "unknown")),
            approval_required=bool(data.get("approval_required", False)),
            source=str(data.get("source", envelope.source)),
            raw_text=str(data.get("raw_text", envelope.user_text)),
            normalized_text=str(data.get("normalized_text", "")),
            entities=data.get("entities", {}) if isinstance(data.get("entities", {}), dict) else {},
            matched_patterns=data.get("matched_patterns", []) if isinstance(data.get("matched_patterns", []), list) else [],
            needs_clarification=bool(data.get("needs_clarification", False)),
            clarification_question=str(data.get("clarification_question", "")),
        )

    def _format_tool_response(
        self,
        result: ToolResult,
        route: dict[str, Any],
        permission: dict[str, Any],
    ) -> str:
        persona = route.get("persona", "proto_jane")
        prefix = self._persona_prefix(persona)

        if result.status == "approval_required":
            return (
                f"{prefix}I can use the {result.tool_id} tool for `{result.action}`, but this action needs approval first.\n\n"
                f"Risk: {permission.get('risk_level', result.status)}\n"
                f"Approval ID: {result.approval_id}\n"
                f"Summary: {result.summary}\n\n"
                "No tool action has been executed."
            )

        if result.status == "not_connected":
            return (
                f"{prefix}The `{result.tool_id}` tool exists and routed correctly, but the service is not connected yet.\n\n"
                f"{result.summary}"
            )

        if result.ok:
            return f"{prefix}{result.summary}"

        return f"{prefix}{result.summary or 'The tool could not complete.'}"

    def _persona_prefix(self, persona: str) -> str:
        if persona == "vecht":
            return "Action check: "
        if persona == "maelith":
            return "Constraint check: "
        if persona == "serren":
            return "I can feel the shape of that request. "
        if persona == "riven":
            return "System reflection: "
        return ""

    def _tool_intent_to_dict(self, tool_intent: ToolIntent) -> dict[str, Any]:
        return {
            "intent_id": tool_intent.intent_id,
            "tool_id": tool_intent.tool_id,
            "service_id": tool_intent.service_id,
            "action": tool_intent.action,
            "confidence": tool_intent.confidence,
            "risk_level": tool_intent.risk_level,
            "approval_required": tool_intent.approval_required,
            "source": tool_intent.source,
            "raw_text": tool_intent.raw_text,
            "normalized_text": tool_intent.normalized_text,
            "entities": tool_intent.entities,
            "matched_patterns": tool_intent.matched_patterns,
            "needs_clarification": tool_intent.needs_clarification,
            "clarification_question": tool_intent.clarification_question,
        }

    def _audit_prompt_interpretation(self, envelope: PromptEnvelope, route: dict[str, Any]) -> None:
        interpreted = self.prompt_interpreter.interpret(envelope=envelope, route=route)
        self.logger.log_router_event(
            {
                "event_type": "prompt_interpreter_audit",
                "request_id": envelope.request_id,
                "route": route,
                "prompt_interpreter": interpreted,
            }
        )

    def _build_system_prompt(self, persona_context: str, route: dict[str, Any], user_profile_context: str = "") -> str:
        profile_section = f"\nUser Profile Context:\n{user_profile_context}\n" if user_profile_context else ""
        return f"""
You are Vaila OS V3, a local assistant system for Malik.
{profile_section}
Current route:
{route}

Persona context:
{persona_context}

Response rules:
- Be clear, direct, and useful.
- Preserve the selected persona's lens when a persona is selected.
- Do not pretend to have modified files unless a tool actually did so.
- Proposed self-modifications must be exported to Sandbox, not applied directly.
- Keep Phase 1 focused on stable routing, services, tools, logging, and memory candidates.
""".strip()

    def _build_user_content(self, envelope: PromptEnvelope, tool_context: str) -> str:
        if not tool_context:
            return f"""
[User Request]
{envelope.user_text}
""".strip()

        tool_context = self._clip_text(tool_context, self.TOOL_CONTEXT_MAX_CHARS)
        return f"""
[User Request]
{envelope.user_text}

[Evidence Block]
{tool_context}
""".strip()

    def _load_persona_context(self, persona: str) -> str:
        folder_map = {
            "proto_jane": "Proto_Jane",
            "serren": "Serren",
            "maelith": "Maelith",
            "vecht": "Vecht",
            "riven": "Riven",
        }

        folder_name = folder_map.get(persona, "Proto_Jane")
        persona_dir = self.project_root / "Persona_Files" / folder_name

        if not persona_dir.exists():
            return f"No persona folder found for {persona}. Use default Vaila voice."

        priority_files = [
            "persona_primer.md",
            "identity.md",
            "function.md",
            "behavior_rules.md",
            "response_patterns.md",
        ]
        paths = [persona_dir / name for name in priority_files if (persona_dir / name).exists()]
        paths.extend(path for path in sorted(persona_dir.glob("*.md")) if path not in paths)

        chunks: list[str] = []
        remaining = self.PERSONA_CONTEXT_MAX_CHARS
        for path in paths:
            if remaining <= 0:
                break

            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                chunk = f"# {path.name}\n{self._clip_text(text, remaining)}"
                chunks.append(chunk)
                remaining -= len(chunk)
            except Exception:
                continue

        if not chunks:
            return f"Persona folder exists for {persona}, but no markdown context files were loaded."

        return "\n\n".join(chunks)

    def _clip_text(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n[Context clipped for local model window.]"

    def _extract_windows_path(self, text: str) -> str | None:
        match = re.search(r"[A-Za-z]:\\[^\n\r\"']+", text)
        if match:
            return match.group(0).strip()
        return None

    def _fallback_response(self, route: dict[str, Any], tool_context: str, llm_error: str = "") -> str:
        task_type = route.get("task_type", "general_chat")
        persona = route.get("persona", "proto_jane")
        error_text = f"\n\nGateway detail:\n{llm_error}" if llm_error else ""

        if tool_context:
            return (
                f"[Fallback response]\n"
                f"Persona: {persona}\n"
                f"Task: {task_type}\n\n"
                f"The tool layer returned context, but the LLM response failed."
                f"{error_text}\n\n"
                f"{tool_context[:4000]}"
            )

        return (
            f"[Fallback response]\n"
            f"Persona: {persona}\n"
            f"Task: {task_type}\n\n"
            f"The core routing path is alive, but the LLM gateway did not return a usable response."
            f"{error_text}"
        )

    def _handle_n8n_workflows(self, envelope: PromptEnvelope, route: dict[str, Any]) -> str:
        text = envelope.user_text.lower()
        
        if "list" in text or "show" in text:
            res = self.n8n.list_workflows()
            if not res.get("ok"):
                return f"Failed to list n8n workflows: {res.get('error')}"
            
            w_list = res.get("workflows", [])
            if not w_list:
                return "No workflows found in local n8n instance."
            
            lines = ["Active n8n Workflows:"]
            for w in w_list:
                status = "ACTIVE" if w.get("active") else "INACTIVE"
                lines.append(f"- [{w.get('id')}] {w.get('name')} ({status})")
            return "\n".join(lines)
            
        elif "create" in text or "deploy" in text or "new" in text:
            name = "Vaila Auto Workflow"
            path = "vaila_trigger"
            action_url = "http://localhost:8765/chat"
            
            quotes = re.findall(r'"([^"]*)"', envelope.user_text)
            if len(quotes) >= 1:
                name = quotes[0]
            if len(quotes) >= 2:
                path = quotes[1]
                
            nodes, connections = self.n8n_manager.compile_webhook_trigger_workflow(
                name=name,
                webhook_path=path,
                action_url=action_url,
                secret_token=self.n8n.webhook_secret
            )
            
            res = self.n8n.create_workflow(name=name, nodes=nodes, connections=connections)
            if not res.get("ok"):
                return f"Failed to create workflow '{name}': {res.get('error')}"
                
            w = res.get("workflow", {})
            return f"Successfully created n8n workflow:\n- ID: {w.get('id')}\n- Name: {w.get('name')}\n- Trigger URL: {self.n8n.webhook_base_url}/{path}\n\nRemember to activate the workflow to make it functional!"
            
        elif "activate" in text or "enable" in text:
            words = envelope.user_text.split()
            w_id = ""
            for w in words:
                if w.isdigit() or len(w) > 4:
                    w_id = w
                    break
            
            if not w_id:
                return "Please specify a workflow ID to activate."
                
            res = self.n8n.toggle_workflow(w_id, True)
            if not res.get("ok"):
                return f"Failed to activate workflow '{w_id}': {res.get('error')}"
            return f"Workflow '{w_id}' has been successfully activated!"
            
        elif "deactivate" in text or "disable" in text:
            words = envelope.user_text.split()
            w_id = ""
            for w in words:
                if w.isdigit() or len(w) > 4:
                    w_id = w
                    break
            
            if not w_id:
                return "Please specify a workflow ID to deactivate."
                
            res = self.n8n.toggle_workflow(w_id, False)
            if not res.get("ok"):
                return f"Failed to deactivate workflow '{w_id}': {res.get('error')}"
            return f"Workflow '{w_id}' has been successfully deactivated!"
            
        elif "delete" in text or "remove" in text:
            words = envelope.user_text.split()
            w_id = ""
            for w in words:
                if w.isdigit() or len(w) > 4:
                    w_id = w
                    break
            
            if not w_id:
                return "Please specify a workflow ID to delete."
                
            res = self.n8n.delete_workflow(w_id)
            if not res.get("ok"):
                return f"Failed to delete workflow '{w_id}': {res.get('error')}"
            return f"Workflow '{w_id}' has been successfully deleted!"

        return "Unrecognized n8n directive. Supported actions: list, create, activate <id>, deactivate <id>, delete <id>."
