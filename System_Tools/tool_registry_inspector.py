from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ToolRegistryInspector:
    """
    Audits available tools, routes, permissions, missing registrations,
    duplicate capabilities, and unsafe permission drift.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.registry_dir = project_root / "Tools_Registry"
        self.tools_dir = project_root / "System_Tools"

    def run_audit(self) -> dict[str, Any]:
        available_path = self.registry_dir / "available_tools.json"
        permissions_path = self.registry_dir / "tool_permissions.json"
        routes_path = self.registry_dir / "tool_routes.json"
        assistant_tools_path = self.registry_dir / "assistant_tools.json"
        assistant_intents_path = self.registry_dir / "assistant_tool_intents.json"
        assistant_examples_path = self.registry_dir / "assistant_tool_examples.json"
        assistant_permissions_path = self.registry_dir / "assistant_tool_permissions.json"
        assistant_routes_path = self.registry_dir / "assistant_tool_routes.json"

        # Load registries
        available_data = self._load_json(available_path)
        permissions_data = self._load_json(permissions_path)
        routes_data = self._load_json(routes_path)
        assistant_tools_data = self._load_json(assistant_tools_path)
        assistant_intents_data = self._load_json(assistant_intents_path)
        assistant_examples_data = self._load_json(assistant_examples_path)
        assistant_permissions_data = self._load_json(assistant_permissions_path)
        assistant_routes_data = self._load_json(assistant_routes_path)

        issues: list[str] = []
        warnings: list[str] = []
        metrics: dict[str, Any] = {}

        # Scan actual Python files in System_Tools. Assistant placeholders are
        # audited through assistant registries, not internal system-tool routes.
        assistant_module_stems = self._assistant_module_stems()
        py_tools = [
            p.stem
            for p in self.tools_dir.glob("*.py")
            if p.stem != "__init__" and p.stem not in assistant_module_stems
        ]

        # 1. Audits available tools
        tools_list = available_data.get("tools", []) if isinstance(available_data, dict) else []
        registered_tool_ids = [t.get("tool_id") for t in tools_list if isinstance(t, dict)]
        registered_modules = []
        for t in tools_list:
            if isinstance(t, dict) and "module" in t:
                mod = t["module"]
                if mod.startswith("System_Tools."):
                    registered_modules.append(mod.split(".", 1)[1])
                else:
                    registered_modules.append(mod)

        # Detect missing registrations
        for py_tool in py_tools:
            if py_tool not in registered_modules:
                issues.append(f"Missing registration: Tool module 'System_Tools.{py_tool}' exists but is not registered in available_tools.json.")

        # Detect registered tools without backing python files
        for t in tools_list:
            if isinstance(t, dict):
                mod = t.get("module", "")
                tool_id = t.get("tool_id", "")
                stem = mod.split(".", 1)[1] if "." in mod else mod
                if not (self.tools_dir / f"{stem}.py").exists():
                    issues.append(f"Dead registration: Registered tool '{tool_id}' references non-existent file 'System_Tools/{stem}.py'.")

        # 2. Audits routes
        routes = routes_data.get("routes", {}) if isinstance(routes_data, dict) else {}
        for r_name, t_id in routes.items():
            if t_id not in registered_tool_ids:
                issues.append(f"Routing mismatch: Route '{r_name}' maps to unregistered tool ID '{t_id}'.")

        # 3. Audits duplicate capabilities
        seen_ids = set()
        duplicates = []
        for t_id in registered_tool_ids:
            if t_id in seen_ids:
                duplicates.append(t_id)
            seen_ids.add(t_id)
        if duplicates:
            issues.append(f"Duplicate capability: Tool ID(s) {list(set(duplicates))} are registered multiple times.")

        # 4. Audits permission drift
        rules = permissions_data.get("rules", []) if isinstance(permissions_data, dict) else []
        policy = permissions_data.get("default_policy", "deny_destructive_actions")
        
        permission_map = {r.get("tool_id"): r for r in rules if isinstance(r, dict)}
        for t_id in registered_tool_ids:
            if t_id not in permission_map:
                warnings.append(f"Missing permissions rule: Registered tool '{t_id}' has no explicit rule in tool_permissions.json. Will fallback to default policy: '{policy}'.")
            else:
                rule = permission_map[t_id]
                # Flag potential unsafe permission drift
                if rule.get("can_write_core_files") is True:
                    if t_id not in {"user_profile_tool", "patch_proposal_reviewer"}:
                        warnings.append(f"Unsafe permission drift: Tool '{t_id}' has write permission 'can_write_core_files' enabled.")

        assistant_audit = self._audit_assistant_tool_registries(
            assistant_tools_data=assistant_tools_data,
            assistant_intents_data=assistant_intents_data,
            assistant_examples_data=assistant_examples_data,
            assistant_permissions_data=assistant_permissions_data,
            assistant_routes_data=assistant_routes_data,
        )
        issues.extend(assistant_audit["issues"])
        warnings.extend(assistant_audit["warnings"])

        # Structure audit results
        is_clean = len(issues) == 0
        metrics = {
            "total_python_files": len(py_tools),
            "total_registered_tools": len(registered_tool_ids),
            "total_configured_routes": len(routes),
            "total_permission_rules": len(rules),
            "assistant_tool_count": assistant_audit["metrics"]["assistant_tool_count"],
            "assistant_route_count": assistant_audit["metrics"]["assistant_route_count"],
            "assistant_permission_rule_count": assistant_audit["metrics"]["assistant_permission_rule_count"],
            "assistant_intent_count": assistant_audit["metrics"]["assistant_intent_count"],
            "assistant_example_count": assistant_audit["metrics"]["assistant_example_count"],
            "status": "PASS" if is_clean else "FAIL"
        }

        return {
            "ok": True,
            "is_clean": is_clean,
            "metrics": metrics,
            "issues": issues,
            "warnings": warnings
        }

    def _audit_assistant_tool_registries(
        self,
        assistant_tools_data: Any,
        assistant_intents_data: Any,
        assistant_examples_data: Any,
        assistant_permissions_data: Any,
        assistant_routes_data: Any,
    ) -> dict[str, Any]:
        issues: list[str] = []
        warnings: list[str] = []

        tools = assistant_tools_data.get("tools", []) if isinstance(assistant_tools_data, dict) else []
        intents = assistant_intents_data.get("intents", {}) if isinstance(assistant_intents_data, dict) else {}
        examples = assistant_examples_data.get("examples", []) if isinstance(assistant_examples_data, dict) else []
        rules = assistant_permissions_data.get("rules", []) if isinstance(assistant_permissions_data, dict) else []
        routes = assistant_routes_data.get("routes", {}) if isinstance(assistant_routes_data, dict) else {}

        required_tool_fields = {
            "tool_id",
            "display_name",
            "service_id",
            "enabled",
            "module",
            "description",
            "actions",
            "risk_levels",
            "approval_required_actions",
            "voice_enabled",
            "text_enabled",
            "example_prompts",
        }

        assistant_tool_ids: list[str] = []
        for tool in tools:
            if not isinstance(tool, dict):
                issues.append("Assistant registry contains a non-object tool entry.")
                continue

            tool_id = tool.get("tool_id")
            if not isinstance(tool_id, str) or not tool_id:
                issues.append("Assistant registry contains a tool without a valid tool_id.")
                continue

            assistant_tool_ids.append(tool_id)
            missing_fields = sorted(required_tool_fields - set(tool.keys()))
            if missing_fields:
                issues.append(f"Assistant tool '{tool_id}' is missing required field(s): {missing_fields}.")

            actions = tool.get("actions", [])
            risk_levels = tool.get("risk_levels", {})
            approval_actions = tool.get("approval_required_actions", [])

            if not isinstance(actions, list) or not actions:
                issues.append(f"Assistant tool '{tool_id}' must define at least one action.")
                actions = []

            if not isinstance(risk_levels, dict):
                issues.append(f"Assistant tool '{tool_id}' risk_levels must be an object.")
                risk_levels = {}

            missing_risk_actions = [action for action in actions if action not in risk_levels]
            if missing_risk_actions:
                issues.append(f"Assistant tool '{tool_id}' is missing risk levels for action(s): {missing_risk_actions}.")

            unknown_approval_actions = [action for action in approval_actions if action not in actions]
            if unknown_approval_actions:
                issues.append(
                    f"Assistant tool '{tool_id}' approval_required_actions references unknown action(s): {unknown_approval_actions}."
                )

        duplicate_ids = self._duplicates(assistant_tool_ids)
        if duplicate_ids:
            issues.append(f"Duplicate assistant tool ID(s): {duplicate_ids}.")

        assistant_tool_id_set = set(assistant_tool_ids)

        for route_name, tool_id in routes.items():
            if tool_id not in assistant_tool_id_set:
                issues.append(f"Assistant route '{route_name}' maps to unregistered assistant tool ID '{tool_id}'.")

        permission_tool_ids = {
            rule.get("tool_id")
            for rule in rules
            if isinstance(rule, dict) and isinstance(rule.get("tool_id"), str)
        }
        for tool_id in assistant_tool_ids:
            if tool_id not in permission_tool_ids:
                warnings.append(f"Assistant tool '{tool_id}' has no explicit permissions rule.")

        for tool_id in sorted(permission_tool_ids - assistant_tool_id_set):
            issues.append(f"Assistant permissions rule references unregistered assistant tool ID '{tool_id}'.")

        for intent_name, intent in intents.items():
            if not isinstance(intent, dict):
                issues.append(f"Assistant intent '{intent_name}' must be an object.")
                continue
            tool_id = intent.get("tool_id")
            if tool_id not in assistant_tool_id_set:
                issues.append(f"Assistant intent '{intent_name}' maps to unregistered assistant tool ID '{tool_id}'.")

        for example in examples:
            if not isinstance(example, dict):
                issues.append("Assistant examples registry contains a non-object example entry.")
                continue
            tool_id = example.get("tool_id")
            if tool_id not in assistant_tool_id_set:
                issues.append(f"Assistant example maps to unregistered assistant tool ID '{tool_id}'.")

        return {
            "metrics": {
                "assistant_tool_count": len(assistant_tool_ids),
                "assistant_route_count": len(routes),
                "assistant_permission_rule_count": len(rules),
                "assistant_intent_count": len(intents),
                "assistant_example_count": len(examples),
            },
            "issues": issues,
            "warnings": warnings,
        }

    def render_report(self) -> str:
        res = self.run_audit()
        metrics = res["metrics"]
        issues = res["issues"]
        warnings = res["warnings"]

        report = [
            "# Vaila OS Tool Registry Audit Report",
            f"Status: **{metrics['status']}**",
            "",
            "## Summary Metrics",
            f"- Python files in System_Tools: {metrics['total_python_files']}",
            f"- Registered tools in available_tools.json: {metrics['total_registered_tools']}",
            f"- Configured routes in tool_routes.json: {metrics['total_configured_routes']}",
            f"- Explicit permission rules: {metrics['total_permission_rules']}",
            f"- Assistant tools in assistant_tools.json: {metrics['assistant_tool_count']}",
            f"- Assistant routes in assistant_tool_routes.json: {metrics['assistant_route_count']}",
            f"- Assistant permission rules: {metrics['assistant_permission_rule_count']}",
            f"- Assistant intents: {metrics['assistant_intent_count']}",
            f"- Assistant examples: {metrics['assistant_example_count']}",
            ""
        ]

        if issues:
            report.append("## ❌ Critical Registry Issues")
            for iss in issues:
                report.append(f"- {iss}")
            report.append("")
        else:
            report.append("## ✅ Critical Registry Issues")
            report.append("No critical registration, route mapping, or duplication issues detected.")
            report.append("")

        if warnings:
            report.append("## ⚠️ Warnings & Permission Drifts")
            for warn in warnings:
                report.append(f"- {warn}")
        else:
            report.append("## ✅ Permissions Verification")
            report.append("No unsafe permission drift or missing rule warnings detected.")

        return "\n".join(report)

    def _load_json(self, path: Path) -> Any:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _duplicates(self, values: list[str]) -> list[str]:
        seen = set()
        duplicates = set()
        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        return sorted(duplicates)

    def _assistant_module_stems(self) -> set[str]:
        return {
            "google_calendar_tool",
            "google_drive_tool",
            "gmail_tool",
            "google_tasks_tool",
            "google_people_tool",
            "notes_tool",
            "reminders_tool",
            "web_research_tool",
            "local_file_assistant_tool",
            "calculator_tool",
        }
