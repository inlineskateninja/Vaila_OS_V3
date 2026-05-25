from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from System_Services.tool_intent_service import ToolIntent


@dataclass
class ApprovalRequest:
    approval_id: str
    created_at: str
    tool_id: str
    action: str
    risk_level: str
    user_prompt: str
    proposed_action_summary: str
    proposed_payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    approved_at: str = ""
    rejected_at: str = ""


class ApprovalService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.approval_log_dir = project_root / "System_Logging" / "Approval_Logs"
        self.approval_log_dir.mkdir(parents=True, exist_ok=True)
        self.approvals_path = self.approval_log_dir / "approvals.jsonl"
        self.decisions_path = self.approval_log_dir / "approval_decisions.jsonl"

    def create_approval_request(self, tool_intent: ToolIntent, proposed_action: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(proposed_action, str):
            proposed_action_summary = proposed_action
            proposed_payload: dict[str, Any] = {}
        else:
            proposed_action_summary = str(proposed_action.get("summary", "")).strip()
            proposed_payload = proposed_action.get("payload", {})
            if not isinstance(proposed_payload, dict):
                proposed_payload = {"value": proposed_payload}

        if not proposed_action_summary:
            proposed_action_summary = f"Prepare {tool_intent.tool_id}.{tool_intent.action} for user approval."

        approval = ApprovalRequest(
            approval_id=f"appr_{uuid4().hex}",
            created_at=self._now(),
            tool_id=tool_intent.tool_id,
            action=tool_intent.action,
            risk_level=tool_intent.risk_level,
            user_prompt=tool_intent.raw_text,
            proposed_action_summary=proposed_action_summary,
            proposed_payload=proposed_payload,
        )
        record = asdict(approval)
        self._append_jsonl(self.approvals_path, record)
        self._log_decision_event("approval_created", record)
        return record

    def approve_request(self, approval_id: str) -> dict[str, Any]:
        return self._resolve_request(approval_id=approval_id, status="approved")

    def reject_request(self, approval_id: str) -> dict[str, Any]:
        return self._resolve_request(approval_id=approval_id, status="rejected")

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        return [approval for approval in self._load_approvals() if approval.get("status") == "pending"]

    def _resolve_request(self, approval_id: str, status: str) -> dict[str, Any]:
        approvals = self._load_approvals()
        found = False
        resolved: dict[str, Any] = {}
        timestamp = self._now()

        for approval in approvals:
            if approval.get("approval_id") != approval_id:
                continue

            found = True
            if approval.get("status") != "pending":
                resolved = approval
                break

            approval["status"] = status
            if status == "approved":
                approval["approved_at"] = timestamp
                approval["rejected_at"] = ""
            else:
                approval["rejected_at"] = timestamp
                approval["approved_at"] = ""
            resolved = approval
            break

        if not found:
            return {"ok": False, "error": "approval_not_found", "approval_id": approval_id}

        self._write_all_approvals(approvals)
        self._log_decision_event(f"approval_{status}", resolved)
        return {"ok": True, "approval": resolved}

    def _load_approvals(self) -> list[dict[str, Any]]:
        if not self.approvals_path.exists():
            return []

        approvals: list[dict[str, Any]] = []
        for line in self.approvals_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                approvals.append(record)
        return approvals

    def _write_all_approvals(self, approvals: list[dict[str, Any]]) -> None:
        self.approval_log_dir.mkdir(parents=True, exist_ok=True)
        with self.approvals_path.open("w", encoding="utf-8") as f:
            for approval in approvals:
                f.write(json.dumps(approval, ensure_ascii=False) + "\n")

    def _log_decision_event(self, event_type: str, approval: dict[str, Any]) -> None:
        self._append_jsonl(
            self.decisions_path,
            {
                "event_type": event_type,
                "logged_at": self._now(),
                "approval_id": approval.get("approval_id"),
                "tool_id": approval.get("tool_id"),
                "action": approval.get("action"),
                "status": approval.get("status"),
            },
        )

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
