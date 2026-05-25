from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class SafetyBoundaryAuditor:
    """
    Reviews tool permissions against System_Dogma, flags dangerous write paths,
    destructive actions, and unclear approval boundaries.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.dogma_dir = project_root / "System_Dogma"
        self.tools_dir = project_root / "System_Tools"
        self.permissions_file = project_root / "Tools_Registry" / "tool_permissions.json"

    def audit_boundaries(self) -> dict[str, Any]:
        violations = []
        alerts = []
        metrics = {
            "audited_tools_count": 0,
            "permissions_checked": False,
            "dogma_loaded": False,
            "safety_status": "SECURE"
        }

        # 1. Load Dogma rules
        dogma_rules = []
        safety_path = self.dogma_dir / "safety_boundaries.md"
        if safety_path.exists():
            content = safety_path.read_text(encoding="utf-8")
            # Extract bullet points
            dogma_rules = re.findall(r"-\s*([^\n\r]+)", content)
            metrics["dogma_loaded"] = True

        # 2. Load Permissions
        permissions = {}
        if self.permissions_file.exists():
            try:
                permissions = json.loads(self.permissions_file.read_text(encoding="utf-8"))
                metrics["permissions_checked"] = True
            except Exception:
                pass

        # 3. Check for elevated system permissions in registry
        rules = permissions.get("rules", [])
        for r in rules:
            if isinstance(r, dict):
                t_id = r.get("tool_id", "")
                if r.get("can_write_core_files") is True:
                    if t_id not in {"user_profile_tool", "patch_proposal_reviewer"}:
                        violations.append(f"Dogma Violation: Tool '{t_id}' is allowed 'can_write_core_files: true' which directly violates the write confinement policy.")

        # 4. Scan tool modules source code for security patterns
        for p in self.tools_dir.glob("*.py"):
            if p.stem == "__init__":
                continue
            
            metrics["audited_tools_count"] += 1
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            # Destructive file deletions
            for idx, line in enumerate(lines):
                # Check for os.remove or shutil.rmtree
                if "os.remove(" in line or "os.unlink(" in line or "shutil.rmtree(" in line:
                    # Is it protected/reviewed?
                    if "patch_proposal_reviewer" not in p.name and "memory_review_console" not in p.name:
                        violations.append(f"Unsanctioned file deletion in 'System_Tools/{p.name}' line {idx+1}: `{line.strip()}`.")

                # Check for raw subprocess commands execution
                if "subprocess." in line or "os.system(" in line:
                    alerts.append(f"Subprocess call detected in 'System_Tools/{p.name}' line {idx+1}: `{line.strip()}`. Subprocesses must be isolated to sandbox directories.")

                # Check for exposed API Keys or hardcoded secrets
                if re.search(r"(api_key|secret|password|token)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]", line, re.IGNORECASE):
                    violations.append(f"Dogma Violation: Hardcoded credential or token detected in 'System_Tools/{p.name}' line {idx+1}.")

        is_secure = len(violations) == 0
        metrics["safety_status"] = "SECURE" if is_secure else "VULNERABLE"

        return {
            "ok": True,
            "is_secure": is_secure,
            "metrics": metrics,
            "dogma_rules_compiled": dogma_rules,
            "violations": violations,
            "warnings_and_alerts": alerts
        }

    def render_safety_report(self) -> str:
        res = self.audit_boundaries()
        metrics = res["metrics"]
        status = metrics["safety_status"]
        icon = "🟢" if status == "SECURE" else "🔴"

        report = [
            f"# Vaila OS Safety Boundary & Dogma Audit Report {icon}",
            f"Safety Status: **{status}**",
            "",
            "## Dogma Integrity Verification",
            f"- Loaded Dogma rules: {'YES' if metrics['dogma_loaded'] else 'NO (using defaults)'}",
            f"- Registry Permissions verified: {'YES' if metrics['permissions_checked'] else 'NO'}",
            f"- Audited system tool python files: {metrics['audited_tools_count']}",
            ""
        ]

        if res["violations"]:
            report.append("## ❌ Safety Boundary Violations")
            for viol in res["violations"]:
                report.append(f"- **[VIOLATION]** {viol}")
            report.append("")
        else:
            report.append("## ✅ Safety Boundary Violations")
            report.append("No active dogma or sandbox isolation violations found. Write confinement rules are intact.")
            report.append("")

        if res["warnings_and_alerts"]:
            report.append("## ⚠️ Sandboxed Execution Warnings")
            for alert in res["warnings_and_alerts"]:
                report.append(f"- **[WARNING]** {alert}")
        else:
            report.append("## ✅ Subshell Confinement Verification")
            report.append("No unsafe subprocess triggers or raw shell command executions detected.")

        return "\n".join(report)
