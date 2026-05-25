from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.system_change_service import SystemChangeService
from app.services.system_health_service import SystemHealthService
from app.services.system_recommendation_service import SystemRecommendationService
from app.services.system_repair_packet_service import SystemRepairPacketService


FORBIDDEN_LANGUAGE = [
    "i feel",
    "i became aware",
    "i discovered myself",
    "my consciousness noticed",
    "i evolved",
]


class SystemSelfQueryService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.health = SystemHealthService(project_root=project_root)
        self.project_root = self.health.project_root
        self.changes = SystemChangeService(self.project_root)
        self.recommendations = SystemRecommendationService(self.project_root)
        self.repair_packets = SystemRepairPacketService(self.project_root)

    def handle_self_query(self, prompt: str) -> dict[str, Any]:
        focus = self.extract_focus(prompt)
        try:
            if self.should_run_new_scan(prompt) or self.health.load_latest_snapshot() is None:
                summary = self.health.run_scan()
                action = "new_scan"
            else:
                summary = self._summary_from_latest()
                action = "latest_snapshot"

            data = summary.model_dump() if hasattr(summary, "model_dump") else summary
            response = self.format_self_query_response(data, focus, action=action)
            return {
                "ok": True,
                "action": action,
                "focus": focus,
                "data": data,
                "response": response,
            }
        except Exception as exc:
            return {
                "ok": False,
                "action": "failed",
                "focus": focus,
                "error": str(exc),
                "response": "I could not complete the system perception query. No files were modified.",
            }

    def should_run_new_scan(self, prompt: str) -> bool:
        text = prompt.lower()
        if self.extract_focus(prompt) == "changes":
            return any(phrase in text for phrase in ["rescan", "scan now", "run a new scan", "inspect now"])
        return any(phrase in text for phrase in ["scan", "rescan", "inspect now", "scan now", "inspect your system", "inspect your files"])

    def extract_focus(self, prompt: str) -> str:
        text = prompt.lower()
        if any(
            phrase in text
            for phrase in [
                "create a codex task",
                "create a repair packet",
                "package the next repair",
                "prepare the next codex step",
                "turn recommendations into codex tasks",
                "generate repair packets",
                "repair packet for the highest priority issue",
                "top repair packet",
                "safe codex task",
            ]
        ):
            return "repair_packets"
        if any(
            phrase in text
            for phrase in [
                "what should i fix next",
                "what should be fixed next",
                "what should codex work on next",
                "recommend next steps",
                "repair plan",
                "development plan",
                "highest priority issues",
                "what looks risky",
                "what should be repaired before adding features",
                "what is blocking progress",
                "what needs user approval",
            ]
        ):
            return "recommendations"
        if any(term in text for term in ["service", "services"]):
            return "services"
        if any(term in text for term in ["router", "routers", "routing"]):
            return "routers"
        if any(term in text for term in ["persona", "personas"]):
            return "personas"
        if "memory" in text:
            return "memory"
        if "config" in text:
            return "config"
        if "test" in text:
            return "tests"
        if any(term in text for term in ["capability", "capabilities", "capability map"]):
            return "capabilities"
        if any(term in text for term in ["issue", "issues", "broken", "suspicious"]):
            return "issues"
        if any(term in text for term in ["changed", "changes", "added files", "removed files", "modified files", "new issues", "resolved issues", "capability changes"]):
            return "changes"
        if any(term in text for term in ["architecture", "summary", "self model", "self-model", "system perception", "system"]):
            return "overview"
        return "unknown"

    def format_self_query_response(self, result: dict[str, Any], focus: str, action: str = "latest_snapshot") -> str:
        prefix = "I ran a new scan." if action == "new_scan" else "The latest self-model reports:"
        counts = result.get("counts_by_category", {})
        capabilities = result.get("capability_map", {})
        issues = result.get("issues", [])

        if focus == "services":
            return self._sanitize(f"{prefix} The architecture currently contains {counts.get('service', 0)} service files.")
        if focus == "routers":
            return self._sanitize(f"{prefix} The architecture currently contains {counts.get('router', 0)} router files.")
        if focus == "personas":
            total = counts.get("persona_manifest", 0) + counts.get("persona_policy", 0)
            return self._sanitize(f"{prefix} The scan found {total} persona-related files.")
        if focus == "memory":
            return self._sanitize(f"{prefix} The scan found {counts.get('memory_file', 0)} memory-related files.")
        if focus == "config":
            return self._sanitize(f"{prefix} The scan found {counts.get('config_file', 0)} config files.")
        if focus == "tests":
            return self._sanitize(f"{prefix} The scan found {counts.get('test_file', 0)} test files.")
        if focus == "capabilities":
            enabled = [name for name, value in capabilities.items() if value is True]
            disabled = [name for name, value in capabilities.items() if value is False]
            return self._sanitize(
                f"{prefix} Enabled capability flags: {', '.join(enabled) or 'none'}. "
                f"Inactive or false flags: {', '.join(disabled) or 'none'}."
            )
        if focus == "issues":
            if not issues:
                return self._sanitize(f"{prefix} No unresolved issues are currently reported.")
            issue_lines = "; ".join(f"{item.get('code')}: {item.get('message')}" for item in issues[:5])
            return self._sanitize(f"{prefix} Unresolved issues: {issue_lines}.")
        if focus == "changes":
            return self._sanitize(self._format_changes())
        if focus == "recommendations":
            return self._sanitize(self._format_recommendations())
        if focus == "repair_packets":
            return self._sanitize(self._format_repair_packets())

        return self._sanitize(
            f"{prefix} Current scan counts: "
            f"{counts.get('service', 0)} service files, "
            f"{counts.get('router', 0)} routers, "
            f"{counts.get('persona_manifest', 0) + counts.get('persona_policy', 0)} persona-related files, "
            f"{counts.get('config_file', 0)} config files, "
            f"{counts.get('test_file', 0)} test files, and "
            f"{len(issues)} unresolved issues."
        )

    def _summary_from_latest(self) -> dict[str, Any]:
        snapshot = self.health.load_latest_snapshot()
        capabilities = self.health.load_latest_capabilities() or {}
        issues_payload = self.health.load_latest_issues() or {"issues": []}
        if snapshot is None:
            return self.health.run_scan().model_dump()
        return {
            "ok": True,
            "generated_at": snapshot.get("generated_at", ""),
            "project_root": snapshot.get("project_root", str(self.project_root)),
            "file_count": sum(snapshot.get("counts_by_category", {}).values()),
            "counts_by_category": snapshot.get("counts_by_category", {}),
            "capability_map": capabilities,
            "issues": issues_payload.get("issues", []),
        }

    def _format_changes(self) -> str:
        report = self.changes.load_latest_change_report()
        if report is None:
            return "No previous scan exists yet. The latest scan is now the baseline for future comparisons."
        return self.changes.format_change_summary(report).strip()

    def _format_recommendations(self) -> str:
        plan = self.recommendations.load_latest_recommendation_plan()
        if plan is None:
            plan_model = self.recommendations.generate_recommendations()
            self.recommendations.save_recommendation_plan(plan_model)
            plan = plan_model.model_dump()

        if plan.get("status") == "no_data":
            return "No scan data exists yet. Run a system scan first, then generate recommendations."

        counts = plan.get("summary_counts", {})
        top = plan.get("top_recommendation") or {}
        response = (
            "The recommendation plan found "
            f"{counts.get('critical', 0)} critical, "
            f"{counts.get('high', 0)} high-priority, "
            f"{counts.get('medium', 0)} medium-priority, and "
            f"{counts.get('low', 0)} low-priority recommendations."
        )
        if top:
            response += (
                f" The top recommendation is: {top.get('title')}. "
                f"This appears {top.get('severity')} because {top.get('reason')} "
                "This requires user approval before changes are made."
            )
        return response

    def _format_repair_packets(self) -> str:
        batch = self.repair_packets.create_repair_packets(mode="top", limit=1)
        if batch.status == "no_data":
            return batch.notes[0] if batch.notes else "No recommendation plan exists yet. Generate recommendations first, then create repair packets."
        payload = batch.model_dump()
        return self.repair_packets.format_batch_summary(payload)

    def _sanitize(self, text: str) -> str:
        lowered = text.lower()
        if any(phrase in lowered for phrase in FORBIDDEN_LANGUAGE):
            return "The system perception response was blocked because it contained disallowed self-awareness language."
        return text
