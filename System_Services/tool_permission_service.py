from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from System_Services.tool_intent_service import ToolIntent


class ToolPermissionService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.registry_dir = project_root / "Tools_Registry"
        self.permission_registry = self._load_json(self.registry_dir / "assistant_tool_permissions.json")
        self.tool_registry = self._load_json(self.registry_dir / "assistant_tools.json")
        self._permission_rules = self._build_permission_rules()
        self._tool_rules = self._build_tool_rules()

    def get_risk_level(self, tool_id: str, action: str) -> str:
        tool = self._tool_rules.get(tool_id, {})
        risk_levels = tool.get("risk_levels", {})
        if isinstance(risk_levels, dict):
            return str(risk_levels.get(action, "unknown"))
        return "unknown"

    def requires_approval(self, tool_id: str, action: str) -> bool:
        tool = self._tool_rules.get(tool_id, {})
        approval_actions = tool.get("approval_required_actions", [])
        if isinstance(approval_actions, list) and action in approval_actions:
            return True

        permission_rule = self._permission_rules.get(tool_id, {})
        write_like = action.startswith(("create_", "update_", "delete_", "move_", "send_", "archive_", "label_"))
        requires_write_approval = bool(permission_rule.get("requires_user_approval_for_writes"))
        return write_like and requires_write_approval

    def can_execute_without_approval(self, tool_intent: ToolIntent) -> bool:
        if tool_intent.tool_id == "general_chat":
            return True
        if tool_intent.needs_clarification:
            return False
        return not self.requires_approval(tool_intent.tool_id, tool_intent.action)

    def explain_permission(self, tool_intent: ToolIntent) -> dict[str, Any]:
        tool_id = tool_intent.tool_id
        action = tool_intent.action
        permission_rule = self._permission_rules.get(tool_id, {})
        risk_level = self.get_risk_level(tool_id, action)
        approval_required = self.requires_approval(tool_id, action)
        can_execute = self.can_execute_without_approval(tool_intent)

        if tool_intent.needs_clarification:
            reason = "clarification_required_before_approval_or_execution"
        elif approval_required:
            reason = "approval_required_by_assistant_tool_policy"
        elif tool_id == "general_chat":
            reason = "no_tool_execution_requested"
        else:
            reason = "allowed_without_approval_by_current_policy"

        return {
            "tool_id": tool_id,
            "action": action,
            "risk_level": risk_level,
            "approval_required": approval_required,
            "can_execute_without_approval": can_execute,
            "auth_required": bool(permission_rule.get("auth_required", False)),
            "external_service": bool(permission_rule.get("external_service", False)),
            "default_policy": self.permission_registry.get("default_policy", ""),
            "reason": reason,
        }

    def _build_permission_rules(self) -> dict[str, dict[str, Any]]:
        rules = self.permission_registry.get("rules", []) if isinstance(self.permission_registry, dict) else []
        return {
            rule["tool_id"]: rule
            for rule in rules
            if isinstance(rule, dict) and isinstance(rule.get("tool_id"), str)
        }

    def _build_tool_rules(self) -> dict[str, dict[str, Any]]:
        tools = self.tool_registry.get("tools", []) if isinstance(self.tool_registry, dict) else []
        return {
            tool["tool_id"]: tool
            for tool in tools
            if isinstance(tool, dict) and isinstance(tool.get("tool_id"), str)
        }

    def _load_json(self, path: Path) -> Any:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
