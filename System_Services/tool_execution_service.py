from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from System_Services.approval_service import ApprovalService
from System_Services.tool_intent_service import ToolIntent
from System_Services.tool_permission_service import ToolPermissionService
from System_Tools.calculator_tool import CalculatorTool
from System_Tools.gmail_tool import GmailTool
from System_Tools.google_calendar_tool import GoogleCalendarTool
from System_Tools.google_drive_tool import GoogleDriveTool
from System_Tools.google_people_tool import GooglePeopleTool
from System_Tools.google_tasks_tool import GoogleTasksTool
from System_Tools.local_file_assistant_tool import LocalFileAssistantTool
from System_Tools.notes_tool import NotesTool
from System_Tools.reminders_tool import RemindersTool
from System_Tools.web_research_tool import WebResearchTool


@dataclass
class ToolResult:
    ok: bool
    tool_id: str
    action: str
    status: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    approval_id: str = ""
    error: str = ""
    audit_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolExecutionService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.permission_service = ToolPermissionService(project_root=project_root)
        self.approval_service = ApprovalService(project_root=project_root)
        self.audit_dir = project_root / "System_Logging" / "Tool_Execution_Logs"
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        self.google_calendar = GoogleCalendarTool()
        self.google_drive = GoogleDriveTool()
        self.gmail = GmailTool()
        self.google_tasks = GoogleTasksTool()
        self.google_people = GooglePeopleTool()
        self.notes = NotesTool(project_root=project_root)
        self.reminders = RemindersTool(project_root=project_root)
        self.web_research = WebResearchTool(project_root=project_root)
        self.local_files = LocalFileAssistantTool(project_root=project_root)
        self.calculator = CalculatorTool()

        self.dispatch_table: dict[tuple[str, str], Callable[[ToolIntent, bool], dict[str, Any]]] = {}
        self._build_dispatch_table()

    def execute_intent(self, tool_intent: ToolIntent, approved: bool = False) -> ToolResult:
        audit_id = self._new_audit_id()

        if tool_intent.needs_clarification:
            return self._finalize(
                ToolResult(
                    ok=False,
                    tool_id=tool_intent.tool_id,
                    action=tool_intent.action,
                    status="needs_clarification",
                    summary=tool_intent.clarification_question,
                    data={"intent": self._intent_data(tool_intent)},
                    audit_id=audit_id,
                )
            )

        requires_approval = self.permission_service.requires_approval(tool_intent.tool_id, tool_intent.action)
        if requires_approval and not approved:
            approval = self.approval_service.create_approval_request(
                tool_intent,
                {
                    "summary": f"Approve {tool_intent.tool_id}.{tool_intent.action} before execution.",
                    "payload": {"intent": self._intent_data(tool_intent)},
                },
            )
            return self._finalize(
                ToolResult(
                    ok=False,
                    tool_id=tool_intent.tool_id,
                    action=tool_intent.action,
                    status="approval_required",
                    summary="Approval is required before this tool action can run.",
                    data={"intent": self._intent_data(tool_intent)},
                    requires_approval=True,
                    approval_id=approval["approval_id"],
                    audit_id=audit_id,
                )
            )

        return self._dispatch(tool_intent=tool_intent, dry_run=False, audit_id=audit_id)

    def dry_run_intent(self, tool_intent: ToolIntent) -> ToolResult:
        return self._dispatch(tool_intent=tool_intent, dry_run=True, audit_id=self._new_audit_id())

    def _dispatch(self, tool_intent: ToolIntent, dry_run: bool, audit_id: str) -> ToolResult:
        if tool_intent.tool_id == "general_chat":
            return self._finalize(
                ToolResult(
                    ok=True,
                    tool_id=tool_intent.tool_id,
                    action=tool_intent.action,
                    status="no_tool_intent",
                    summary="No tool execution is needed for general chat.",
                    data={"intent": self._intent_data(tool_intent)},
                    audit_id=audit_id,
                )
            )

        handler = self.dispatch_table.get((tool_intent.tool_id, tool_intent.action))
        if handler is None:
            return self._finalize(
                ToolResult(
                    ok=False,
                    tool_id=tool_intent.tool_id,
                    action=tool_intent.action,
                    status="unsupported_action",
                    summary=f"No handler registered for {tool_intent.tool_id}.{tool_intent.action}.",
                    data={"intent": self._intent_data(tool_intent)},
                    error="unsupported_action",
                    audit_id=audit_id,
                )
            )

        try:
            raw = handler(tool_intent, dry_run)
        except Exception as exc:
            return self._finalize(
                ToolResult(
                    ok=False,
                    tool_id=tool_intent.tool_id,
                    action=tool_intent.action,
                    status="error",
                    summary="Tool handler failed before completing.",
                    data={"intent": self._intent_data(tool_intent)},
                    error=str(exc),
                    audit_id=audit_id,
                )
            )

        return self._finalize(
            ToolResult(
                ok=bool(raw.get("ok", False)),
                tool_id=tool_intent.tool_id,
                action=tool_intent.action,
                status=str(raw.get("status", "unknown")),
                summary=str(raw.get("summary", "")),
                data=raw.get("data", {}) if isinstance(raw.get("data", {}), dict) else {"value": raw.get("data")},
                requires_approval=False,
                approval_id="",
                error=str(raw.get("error", "")),
                audit_id=audit_id,
            )
        )

    def _build_dispatch_table(self) -> None:
        tools = {
            "google_calendar": self.google_calendar,
            "google_drive": self.google_drive,
            "gmail": self.gmail,
            "google_tasks": self.google_tasks,
            "google_people": self.google_people,
            "notes": self.notes,
            "reminders": self.reminders,
            "web_research": self.web_research,
            "local_file_assistant": self.local_files,
            "calculator": self.calculator,
        }

        for tool_id, tool in tools.items():
            for action in tool.supported_actions():
                method = getattr(tool, action, None)
                if callable(method):
                    self.dispatch_table[(tool_id, action)] = method

    def _finalize(self, result: ToolResult) -> ToolResult:
        self._write_audit(result)
        return result

    def _write_audit(self, result: ToolResult) -> None:
        path = self.audit_dir / self._daily_filename()
        record = result.to_dict()
        record["logged_at"] = datetime.now(timezone.utc).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _intent_data(self, tool_intent: ToolIntent) -> dict[str, Any]:
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

    def _new_audit_id(self) -> str:
        return f"audit_{uuid4().hex}"

    def _daily_filename(self) -> str:
        return f"tool_execution_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
