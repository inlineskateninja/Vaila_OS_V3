from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.system_perception_models import (
    SystemRecommendation,
    SystemRecommendationPlan,
    utc_timestamp,
)


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SEVERITY_ORDER = {"blocking": 0, "risky": 1, "inconvenient": 2, "informational": 3}


class SystemRecommendationService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.self_model_dir = self.project_root / "core_system_files" / "system_state" / "self_model"
        self.scan_reports_dir = self.project_root / "core_system_files" / "system_state" / "scan_reports"

    def load_latest_snapshot(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "architecture_snapshot.json")

    def load_latest_file_inventory(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "file_inventory.json")

    def load_latest_capability_map(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "capability_map.json")

    def load_latest_issues(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "unresolved_issues.json")

    def load_latest_change_report(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "change_report.json")

    def load_latest_recommendation_plan(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "recommendation_plan.json")

    def load_latest_recommendation_summary(self) -> str | None:
        path = self.self_model_dir / "last_recommendation_plan.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def generate_recommendations(self) -> SystemRecommendationPlan:
        snapshot = self.load_latest_snapshot()
        inventory = self.load_latest_file_inventory()
        capabilities = self.load_latest_capability_map()
        issues_payload = self.load_latest_issues()
        change_report = self.load_latest_change_report()

        source_files = self._source_files()
        if not snapshot or not inventory:
            return SystemRecommendationPlan(
                status="no_data",
                created_at=utc_timestamp(),
                source_files=source_files,
                summary_counts=self._summary_counts([]),
                notes=["No scan data exists yet. Run a system scan before generating recommendations."],
            )

        recommendations: list[SystemRecommendation] = []
        recommendations.extend(self._recommend_from_missing_expected(snapshot))
        recommendations.extend(self._recommend_from_capabilities(capabilities or {}))
        recommendations.extend(self._recommend_from_issues((issues_payload or {}).get("issues", []), source="current"))
        if change_report:
            recommendations.extend(self._recommend_from_change_report(change_report))

        recommendations = self.prioritize_recommendations(self._dedupe(recommendations))
        plan = SystemRecommendationPlan(
            status="created",
            created_at=utc_timestamp(),
            source_files=source_files,
            summary_counts=self._summary_counts(recommendations),
            top_recommendation=recommendations[0].model_dump() if recommendations else {},
            recommendations=recommendations,
            notes=[] if recommendations else ["No repair or development recommendations were generated from the latest scan data."],
        )
        return plan

    def prioritize_recommendations(self, recommendations: list[SystemRecommendation]) -> list[SystemRecommendation]:
        return sorted(
            recommendations,
            key=lambda item: (
                PRIORITY_ORDER[item.priority],
                SEVERITY_ORDER[item.severity],
                item.category,
                item.title,
            ),
        )

    def save_recommendation_plan(self, plan: SystemRecommendationPlan | dict[str, Any]) -> None:
        if isinstance(plan, dict):
            plan = SystemRecommendationPlan(**plan)

        self.self_model_dir.mkdir(parents=True, exist_ok=True)
        self.scan_reports_dir.mkdir(parents=True, exist_ok=True)
        payload = plan.model_dump()
        self._write_json(self.self_model_dir / "recommendation_plan.json", payload)
        (self.self_model_dir / "last_recommendation_plan.md").write_text(
            self.format_recommendation_summary(payload),
            encoding="utf-8",
        )

        from datetime import UTC, datetime

        stamp = datetime.now(UTC).strftime("%Y_%m_%d_%H%M%S_%f")
        self._write_json(self.scan_reports_dir / f"recommendations_{stamp}.json", payload)

    def format_recommendation_summary(self, plan: SystemRecommendationPlan | dict[str, Any]) -> str:
        if isinstance(plan, SystemRecommendationPlan):
            plan = plan.model_dump()

        if plan.get("status") == "no_data":
            return "No scan data exists yet. Run a system scan first, then generate recommendations.\n"
        if plan.get("status") == "failed":
            return "Recommendation planning failed. No source files were modified.\n"

        counts = plan.get("summary_counts", {})
        top = plan.get("top_recommendation") or {}
        lines = [
            "# Vaila Recommendation Plan",
            "",
            (
                "The recommendation plan found "
                f"{counts.get('critical', 0)} critical, "
                f"{counts.get('high', 0)} high-priority, "
                f"{counts.get('medium', 0)} medium-priority, and "
                f"{counts.get('low', 0)} low-priority recommendations."
            ),
        ]
        if top:
            lines.extend(
                [
                    "",
                    f"Top recommendation: {top.get('title')}",
                    f"Reason: {top.get('reason')}",
                    f"Suggested action: {top.get('suggested_action')}",
                    "This requires user approval before changes are made.",
                ]
            )
        return "\n".join(lines) + "\n"

    def _recommend_from_missing_expected(self, snapshot: dict[str, Any]) -> list[SystemRecommendation]:
        recommendations: list[SystemRecommendation] = []
        for path in snapshot.get("missing_expected", []):
            if path.endswith("app.py"):
                recommendations.append(
                    self._rec(
                        title="Restore missing core entrypoint",
                        category="missing_expected_file",
                        priority="critical",
                        severity="blocking",
                        reason="The architecture manifest expects a core entrypoint and the latest scan reports it missing.",
                        evidence=[f"missing_expected: {path}"],
                        suggested_action="Create or restore the expected entrypoint bridge after user approval.",
                        affected_files=[path],
                        safe=True,
                    )
                )
            elif "/routers" in path or path.endswith("routers"):
                recommendations.append(
                    self._rec(
                        title="Restore missing router layer",
                        category="missing_router",
                        priority="critical",
                        severity="blocking",
                        reason="A missing router directory can prevent API routes from being registered.",
                        evidence=[f"missing_expected: {path}"],
                        suggested_action="Create the expected router package or update the manifest if the route layer moved.",
                        affected_files=[path],
                        safe=True,
                    )
                )
            elif "/services" in path or path.endswith("services"):
                recommendations.append(
                    self._rec(
                        title="Restore missing service layer",
                        category="missing_service",
                        priority="critical",
                        severity="blocking",
                        reason="A missing service directory can prevent active routes from calling their implementation layer.",
                        evidence=[f"missing_expected: {path}"],
                        suggested_action="Create the expected service package or update the manifest if the service layer moved.",
                        affected_files=[path],
                        safe=True,
                    )
                )
            elif "/models" in path or path.endswith("models"):
                recommendations.append(
                    self._rec(
                        title="Restore missing model schema layer",
                        category="missing_model_schema",
                        priority="high",
                        severity="risky",
                        reason="Missing schema models reduce route validation and API clarity.",
                        evidence=[f"missing_expected: {path}"],
                        suggested_action="Create the expected model package or update the manifest if schemas moved.",
                        affected_files=[path],
                        safe=True,
                    )
                )
            else:
                recommendations.append(
                    self._rec(
                        title="Resolve missing expected architecture path",
                        category="missing_expected_file",
                        priority="medium",
                        severity="inconvenient",
                        reason="The expected architecture manifest and scan output disagree.",
                        evidence=[f"missing_expected: {path}"],
                        suggested_action="Review whether the path should be restored or the manifest should be updated.",
                        affected_files=[path],
                        safe=True,
                    )
                )
        return recommendations

    def _recommend_from_capabilities(self, capabilities: dict[str, Any]) -> list[SystemRecommendation]:
        recommendations: list[SystemRecommendation] = []
        if capabilities.get("can_scan_files") is False:
            recommendations.append(self._capability_gap("Repair file scanning", "can_scan_files", "critical", "blocking"))
        if capabilities.get("can_save_snapshots") is False:
            recommendations.append(self._capability_gap("Repair snapshot saving", "can_save_snapshots", "critical", "blocking"))
        if capabilities.get("has_router_layer") is False:
            recommendations.append(self._capability_gap("Add or register router layer", "has_router_layer", "critical", "blocking", "missing_router"))
        if capabilities.get("has_service_layer") is False:
            recommendations.append(self._capability_gap("Add or register service layer", "has_service_layer", "critical", "blocking", "missing_service"))
        if capabilities.get("has_tests") is False:
            recommendations.append(
                self._rec(
                    title="Add tests for active service layers",
                    category="missing_tests",
                    priority="high",
                    severity="risky",
                    reason="The capability map reports no tests for active system layers.",
                    evidence=["capability has_tests: false"],
                    suggested_action="Add deterministic tests for active routers, services, and scan behavior.",
                    safe=True,
                )
            )
        if capabilities.get("has_memory_files") is False:
            recommendations.append(self._capability_gap("Review memory support coverage", "has_memory_files", "high", "risky"))
        if capabilities.get("has_persona_files") is False:
            recommendations.append(self._capability_gap("Review persona file support", "has_persona_files", "high", "risky"))
        if capabilities.get("detected_import_issues") is True:
            recommendations.append(
                self._rec(
                    title="Clean up deprecated import references",
                    category="broken_import",
                    priority="critical",
                    severity="blocking",
                    reason="The capability map reports import issues in scanned files.",
                    evidence=["capability detected_import_issues: true"],
                    suggested_action="Replace deprecated imports with current app package paths after user approval.",
                    safe=True,
                )
            )
        return recommendations

    def _recommend_from_issues(self, issues: list[dict[str, Any]], source: str) -> list[SystemRecommendation]:
        recommendations: list[SystemRecommendation] = []
        for issue in issues:
            code = issue.get("code", "unknown")
            path = issue.get("path")
            if code == "deprecated_import_reference":
                recommendations.append(
                    self._rec(
                        title="Fix deprecated import reference",
                        category="broken_import",
                        priority="critical",
                        severity="blocking",
                        reason="A scanned Python file references a deprecated import path.",
                        evidence=[issue.get("message", ""), f"source: {source}"],
                        suggested_action="Update the import to the current package path and add a regression test.",
                        affected_files=[path] if path else [],
                        safe=True,
                    )
                )
            elif code == "empty_important_directory":
                recommendations.append(
                    self._rec(
                        title="Review empty required directory",
                        category="empty_required_directory",
                        priority="medium",
                        severity="inconvenient",
                        reason="An important architecture directory exists but contains no files.",
                        evidence=[issue.get("message", ""), f"source: {source}"],
                        suggested_action="Add the expected deterministic files or update the manifest if the directory is intentionally empty.",
                        affected_files=[path] if path else [],
                        safe=True,
                    )
                )
            elif code == "duplicate_bridge_files":
                recommendations.append(
                    self._rec(
                        title="Review duplicate bridge files",
                        category="duplicate_architecture",
                        priority="high",
                        severity="risky",
                        reason="Duplicate bridge files can confuse imports or launch paths.",
                        evidence=[issue.get("message", ""), f"source: {source}"],
                        suggested_action="Review duplicate bridge paths and choose one canonical bridge before deleting or moving anything.",
                        affected_files=issue.get("details", {}).get("paths", []),
                        safe=False,
                    )
                )
            else:
                recommendations.append(
                    self._rec(
                        title=f"Review issue: {code}",
                        category="new_issue" if source == "new_change" else "persistent_issue",
                        priority="medium",
                        severity="inconvenient",
                        reason=issue.get("message", "The scan reported an issue."),
                        evidence=[f"issue_code: {code}", f"source: {source}"],
                        suggested_action="Review the issue and decide whether it needs a targeted repair task.",
                        affected_files=[path] if path else [],
                        safe=True,
                    )
                )
        return recommendations

    def _recommend_from_change_report(self, change_report: dict[str, Any]) -> list[SystemRecommendation]:
        recommendations: list[SystemRecommendation] = []
        recommendations.extend(self._recommend_from_issues(change_report.get("new_issues", []), source="new_change"))
        recommendations.extend(self._recommend_from_issues(change_report.get("persistent_issues", []), source="persistent_change"))
        for change in change_report.get("capability_changes", []):
            if change.get("previous") is True and change.get("current") is False:
                recommendations.append(
                    self._rec(
                        title=f"Review capability regression: {change.get('name')}",
                        category="capability_gap",
                        priority="high",
                        severity="risky",
                        reason="The latest change report shows a capability changed to false.",
                        evidence=[f"{change.get('name')}: {change.get('previous')} -> {change.get('current')}"],
                        suggested_action="Inspect the related scan data and restore the capability if the regression is unintended.",
                        safe=True,
                    )
                )
        return recommendations

    def _capability_gap(
        self,
        title: str,
        capability: str,
        priority: str,
        severity: str,
        category: str = "capability_gap",
    ) -> SystemRecommendation:
        return self._rec(
            title=title,
            category=category,
            priority=priority,
            severity=severity,
            reason=f"The latest capability map reports {capability} as false.",
            evidence=[f"capability {capability}: false"],
            suggested_action="Review the latest scan output and add deterministic wiring or tests after user approval.",
            safe=True,
        )

    def _rec(
        self,
        title: str,
        category: str,
        priority: str,
        severity: str,
        reason: str,
        evidence: list[str],
        suggested_action: str,
        affected_files: list[str] | None = None,
        safe: bool = True,
    ) -> SystemRecommendation:
        rec_id = self._stable_id(category, title, affected_files or evidence)
        return SystemRecommendation(
            id=rec_id,
            title=title,
            category=category,
            priority=priority,
            severity=severity,
            reason=reason,
            evidence=[item for item in evidence if item],
            suggested_action=suggested_action,
            affected_files=affected_files or [],
            blocked_by=[],
            safe_to_delegate_to_codex=safe,
            requires_user_approval=True,
        )

    def _dedupe(self, recommendations: list[SystemRecommendation]) -> list[SystemRecommendation]:
        by_id: dict[str, SystemRecommendation] = {}
        for recommendation in recommendations:
            by_id.setdefault(recommendation.id, recommendation)
        return list(by_id.values())

    def _summary_counts(self, recommendations: list[SystemRecommendation]) -> dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": len(recommendations)}
        for recommendation in recommendations:
            counts[recommendation.priority] += 1
        return counts

    def _source_files(self) -> dict[str, str]:
        return {
            "architecture_snapshot": str(self.self_model_dir / "architecture_snapshot.json"),
            "capability_map": str(self.self_model_dir / "capability_map.json"),
            "issues": str(self.self_model_dir / "unresolved_issues.json"),
            "change_report": str(self.self_model_dir / "change_report.json"),
        }

    @staticmethod
    def _stable_id(category: str, title: str, values: list[str]) -> str:
        import hashlib

        raw = "|".join([category, title, *values])
        return "rec_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
