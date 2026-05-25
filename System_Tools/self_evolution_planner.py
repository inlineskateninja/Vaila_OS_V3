from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from System_Tools.tool_registry_inspector import ToolRegistryInspector
from System_Tools.system_dependency_doctor import SystemDependencyDoctor
from System_Tools.safety_boundary_auditor import SafetyBoundaryAuditor
from System_Tools.self_model_diff_tool import SelfModelDiffTool


class SelfEvolutionPlanner:
    """
    Converts self-assessment findings into ranked improvement proposals:
    bug fix, test gap, architecture upgrade, tool addition, or documentation update.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.registry_inspector = ToolRegistryInspector(project_root)
        self.dependency_doctor = SystemDependencyDoctor(project_root)
        self.safety_auditor = SafetyBoundaryAuditor(project_root)
        self.model_diff = SelfModelDiffTool(project_root)

    def formulate_plan(self) -> dict[str, Any]:
        # Gather diagnostics
        registry_res = self.registry_inspector.run_audit()
        dep_res = self.dependency_doctor.run_diagnostics()
        safety_res = self.safety_auditor.audit_boundaries()
        diff_res = self.model_diff.calculate_diffs()

        proposals = []

        # 1. Check Critical Registry Issues
        if not registry_res.get("is_clean", True):
            for issue in registry_res.get("issues", []):
                proposals.append({
                    "priority": 1,
                    "category": "bug_fix",
                    "title": "Fix Tool Registry Configuration",
                    "issue": issue,
                    "remedy": "Update available_tools.json or tool_routes.json to map correct files and routes."
                })

        # 2. Check Safety Violations
        if not safety_res.get("is_secure", True):
            for viol in safety_res.get("violations", []):
                proposals.append({
                    "priority": 1,
                    "category": "safety_boundary",
                    "title": "Mitigate Safety Confinement Violation",
                    "issue": viol,
                    "remedy": "Refactor the flagged tool to operate in Sandbox directories and follow System_Dogma rules."
                })

        # 3. Check Dependency Readiness
        if not dep_res.get("readiness", True):
            req_health = dep_res.get("requirements_health", {})
            for pkg, stat in req_health.get("status", {}).items():
                if not stat.get("importable"):
                    proposals.append({
                        "priority": 2,
                        "category": "test_gap",
                        "title": f"Install Missing Dependency: {pkg}",
                        "issue": f"Package {pkg} is required but failed to import: {stat.get('error')}",
                        "remedy": f"Run `pip install {pkg}` inside the workspace virtual environment."
                    })

        # 4. Check Registry Warnings & Drift
        for warn in registry_res.get("warnings", []):
            proposals.append({
                "priority": 3,
                "category": "architecture_upgrade",
                "title": "Rectify Tool Permission Drift",
                "issue": warn,
                "remedy": "Review permission parameters in Tools_Registry/tool_permissions.json."
            })

        # 5. Check Persistent Blind Spots
        blind_spots = diff_res.get("comparison", {}).get("blind_spots", [])
        for bs in blind_spots:
            proposals.append({
                "priority": 3,
                "category": "documentation_update",
                "title": "Address Self-Model Blind Spot",
                "issue": bs,
                "remedy": "Generate explicit self-assessment notes or refactor missing directory items."
            })

        # Default proposal if system is perfectly green to remain functional!
        if not proposals:
            proposals.append({
                "priority": 4,
                "category": "architecture_upgrade",
                "title": "Upgrade Memory Vectors Backend",
                "issue": "System is currently perfectly healthy. Local JSONL is stable.",
                "remedy": "Switch MEMORY_BACKEND_ADAPTER to 'qdrant' or 'pgvector' in .env for advanced semantic vector query speeds."
            })

        # Sort by priority ascending (1 = highest)
        proposals.sort(key=lambda x: x["priority"])

        return {
            "ok": True,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "health_level": "OPTIMIZED" if len(proposals) <= 1 and proposals[0]["priority"] == 4 else "ATTENTION_REQUIRED",
            "proposals_count": len(proposals),
            "proposals": proposals
        }

    def render_evolution_report(self) -> str:
        plan = self.formulate_plan()
        
        lines = [
            "# Vaila OS Self-Evolution & Ranked Roadmaps",
            f"Compiled UTC: {plan['timestamp']}",
            f"System Health Category: **{plan['health_level']}**",
            "",
            "The **SelfEvolutionPlanner** merges system-wide logs, tool registry diagnostics, dependencies, and boundary audits into prioritized optimization tickets.",
            "",
            "## Ranked System Action Proposals",
        ]

        priority_labels = {
            1: "🔥 PRIORITY 1: CRITICAL REPAIR",
            2: "⚡ PRIORITY 2: PACKAGE / BOOT READY",
            3: "🟡 PRIORITY 3: SYSTEM DRIFT MONITORING",
            4: "🟢 PRIORITY 4: STRUCTURAL ENHANCEMENTS"
        }

        for idx, prop in enumerate(plan["proposals"]):
            lines.append(f"### {idx+1}. {prop['title']}")
            lines.append(f"- **Rank**: {priority_labels[prop['priority']]}")
            lines.append(f"- **Proposed Category**: `{prop['category'].upper()}`")
            lines.append(f"- **Diagnosed Issue**: {prop['issue']}")
            lines.append(f"- **Prescribed Remedy**: *{prop['remedy']}*")
            lines.append("")

        return "\n".join(lines)

    def export_evolution_plan(self) -> str:
        report = self.render_evolution_report()
        export_dir = self.project_root / "Sandbox" / "Self_Assessment_Exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        stamp = time.strftime("self_evolution_%Y%m%d_%H%M%S.md")
        dest = export_dir / stamp
        dest.write_text(report, encoding="utf-8")
        return f"Self-Evolution plan generated and exported to sandbox: Sandbox/Self_Assessment_Exports/{stamp}"
