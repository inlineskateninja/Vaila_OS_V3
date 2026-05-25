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

        # Load registries
        available_data = self._load_json(available_path)
        permissions_data = self._load_json(permissions_path)
        routes_data = self._load_json(routes_path)

        issues: list[str] = []
        warnings: list[str] = []
        metrics: dict[str, Any] = {}

        # Scan actual Python files in System_Tools
        py_tools = [p.stem for p in self.tools_dir.glob("*.py") if p.stem != "__init__"]

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

        # Structure audit results
        is_clean = len(issues) == 0
        metrics = {
            "total_python_files": len(py_tools),
            "total_registered_tools": len(registered_tool_ids),
            "total_configured_routes": len(routes),
            "total_permission_rules": len(rules),
            "status": "PASS" if is_clean else "FAIL"
        }

        return {
            "ok": True,
            "is_clean": is_clean,
            "metrics": metrics,
            "issues": issues,
            "warnings": warnings
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
