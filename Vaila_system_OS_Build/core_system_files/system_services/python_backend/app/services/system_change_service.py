from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.system_perception_models import (
    CapabilityChange,
    SystemChangeReport,
    SystemIssue,
    utc_timestamp,
)


class SystemChangeService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.self_model_dir = self.project_root / "core_system_files" / "system_state" / "self_model"
        self.scan_reports_dir = self.project_root / "core_system_files" / "system_state" / "scan_reports"

    def load_previous_snapshot(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "file_inventory.json")

    def load_latest_snapshot(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "file_inventory.json")

    def load_latest_change_report(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "change_report.json")

    def load_latest_change_summary(self) -> str | None:
        path = self.self_model_dir / "last_change_summary.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def compare_snapshots(self, previous: dict[str, Any] | None, current: dict[str, Any]) -> SystemChangeReport:
        if previous is None:
            return self._baseline_report(current)

        previous_files = self._files_by_path(previous)
        current_files = self._files_by_path(current)
        previous_paths = set(previous_files)
        current_paths = set(current_files)

        added_files = sorted(current_paths - previous_paths)
        removed_files = sorted(previous_paths - current_paths)
        common_paths = sorted(previous_paths & current_paths)
        modified_files = [
            path
            for path in common_paths
            if self._file_changed(previous_files[path], current_files[path])
        ]
        unchanged_files_count = len(common_paths) - len(modified_files)

        capability_changes = self._capability_changes(previous, current)
        new_issues, resolved_issues, persistent_issues = self._issue_changes(previous, current)

        summary_counts = {
            "added_files": len(added_files),
            "removed_files": len(removed_files),
            "modified_files": len(modified_files),
            "new_issues": len(new_issues),
            "resolved_issues": len(resolved_issues),
            "capability_changes": len(capability_changes),
        }
        status = "changes_detected" if any(summary_counts.values()) else "no_changes"

        return SystemChangeReport(
            status=status,
            previous_scan_time=previous.get("scanned_at", previous.get("generated_at", "")),
            current_scan_time=current.get("scanned_at", current.get("generated_at", utc_timestamp())),
            summary_counts=summary_counts,
            added_files=added_files,
            removed_files=removed_files,
            modified_files=modified_files,
            unchanged_files_count=unchanged_files_count,
            added_services=self._category_paths(added_files, current_files, "service"),
            removed_services=self._category_paths(removed_files, previous_files, "service"),
            added_routers=self._category_paths(added_files, current_files, "router"),
            removed_routers=self._category_paths(removed_files, previous_files, "router"),
            added_personas=self._persona_paths(added_files, current_files),
            removed_personas=self._persona_paths(removed_files, previous_files),
            capability_changes=capability_changes,
            new_issues=new_issues,
            resolved_issues=resolved_issues,
            persistent_issues=persistent_issues,
            notes=[],
        )

    def save_change_report(self, report: SystemChangeReport | dict[str, Any]) -> None:
        if isinstance(report, dict):
            report = SystemChangeReport(**report)

        self.self_model_dir.mkdir(parents=True, exist_ok=True)
        self.scan_reports_dir.mkdir(parents=True, exist_ok=True)

        payload = report.model_dump()
        self._write_json(self.self_model_dir / "change_report.json", payload)
        (self.self_model_dir / "last_change_summary.md").write_text(self.format_change_summary(payload), encoding="utf-8")

        from datetime import UTC, datetime

        stamp = datetime.now(UTC).strftime("%Y_%m_%d_%H%M%S_%f")
        self._write_json(self.scan_reports_dir / f"change_{stamp}.json", payload)

    def format_change_summary(self, report: dict[str, Any] | SystemChangeReport) -> str:
        if isinstance(report, SystemChangeReport):
            report = report.model_dump()

        status = report.get("status", "comparison_failed")
        counts = report.get("summary_counts", {})
        if status == "baseline_created":
            return "A baseline scan was created. Future scans can be compared against this snapshot.\n"
        if status == "no_changes":
            return "No changes were detected between the latest scan and the previous scan.\n"
        if status == "comparison_failed":
            return "The system could not compare the latest scan against the previous scan.\n"

        return (
            "The latest comparison found "
            f"{counts.get('added_files', 0)} added files, "
            f"{counts.get('modified_files', 0)} modified files, "
            f"{counts.get('removed_files', 0)} removed files, "
            f"{counts.get('new_issues', 0)} new issues, "
            f"{counts.get('resolved_issues', 0)} resolved issues, and "
            f"{counts.get('capability_changes', 0)} capability changes.\n"
        )

    def _baseline_report(self, current: dict[str, Any]) -> SystemChangeReport:
        return SystemChangeReport(
            status="baseline_created",
            previous_scan_time="",
            current_scan_time=current.get("scanned_at", current.get("generated_at", utc_timestamp())),
            summary_counts={
                "added_files": 0,
                "removed_files": 0,
                "modified_files": 0,
                "new_issues": 0,
                "resolved_issues": 0,
                "capability_changes": 0,
            },
            unchanged_files_count=len(current.get("files", [])),
            notes=["No previous scan existed. The current scan is the baseline for future comparisons."],
        )

    def _files_by_path(self, snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {item["path"]: item for item in snapshot.get("files", []) if item.get("path")}

    @staticmethod
    def _file_changed(previous: dict[str, Any], current: dict[str, Any]) -> bool:
        return (
            previous.get("modified_time") != current.get("modified_time")
            or previous.get("size_bytes") != current.get("size_bytes")
        )

    def _capability_changes(self, previous: dict[str, Any], current: dict[str, Any]) -> list[CapabilityChange]:
        previous_capabilities = previous.get("capability_map", {})
        current_capabilities = current.get("capability_map", {})
        keys = sorted(set(previous_capabilities) | set(current_capabilities))
        return [
            CapabilityChange(name=key, previous=previous_capabilities.get(key), current=current_capabilities.get(key))
            for key in keys
            if previous_capabilities.get(key) != current_capabilities.get(key)
        ]

    def _issue_changes(
        self,
        previous: dict[str, Any],
        current: dict[str, Any],
    ) -> tuple[list[SystemIssue], list[SystemIssue], list[SystemIssue]]:
        previous_issues = {self._issue_key(item): item for item in previous.get("issues", [])}
        current_issues = {self._issue_key(item): item for item in current.get("issues", [])}

        new_keys = sorted(set(current_issues) - set(previous_issues))
        resolved_keys = sorted(set(previous_issues) - set(current_issues))
        persistent_keys = sorted(set(current_issues) & set(previous_issues))
        return (
            [SystemIssue(**current_issues[key]) for key in new_keys],
            [SystemIssue(**previous_issues[key]) for key in resolved_keys],
            [SystemIssue(**current_issues[key]) for key in persistent_keys],
        )

    @staticmethod
    def _issue_key(issue: dict[str, Any]) -> str:
        return "|".join([issue.get("code", ""), issue.get("path", ""), issue.get("message", "")])

    @staticmethod
    def _category_paths(paths: list[str], files: dict[str, dict[str, Any]], category: str) -> list[str]:
        return [path for path in paths if files.get(path, {}).get("category") == category]

    @staticmethod
    def _persona_paths(paths: list[str], files: dict[str, dict[str, Any]]) -> list[str]:
        return [
            path
            for path in paths
            if files.get(path, {}).get("category") in {"persona_manifest", "persona_policy"}
        ]

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
