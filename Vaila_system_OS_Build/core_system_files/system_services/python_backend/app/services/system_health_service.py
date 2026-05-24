from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.system_perception_models import (
    ArchitectureSnapshot,
    CapabilityMap,
    DirectoryScanResult,
    SystemIssue,
    SystemPerceptionSummary,
    utc_timestamp,
)
from app.services.system_introspection_service import SystemIntrospectionService
from app.services.system_manifest_service import SystemManifestService
from app.services.system_change_service import SystemChangeService


class SystemHealthService:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.introspection = SystemIntrospectionService(project_root=project_root)
        self.project_root = self.introspection.project_root
        self.manifest = SystemManifestService(self.project_root)
        self.change_service = SystemChangeService(self.project_root)
        self.self_model_dir = self.project_root / "core_system_files" / "system_state" / "self_model"
        self.scan_reports_dir = self.project_root / "core_system_files" / "system_state" / "scan_reports"

    def run_scan(self) -> SystemPerceptionSummary:
        previous_snapshot = self._load_comparison_snapshot()
        scan = self.introspection.scan(save_report=True)
        snapshot = self.manifest.build_snapshot(scan)
        capability_map = self.build_capability_map(scan, snapshot)
        current_snapshot = self._comparison_snapshot(scan, snapshot, capability_map)
        change_report = self.change_service.compare_snapshots(previous_snapshot, current_snapshot)
        self.save_latest(scan, snapshot, capability_map)
        self.change_service.save_change_report(change_report)
        return self.build_summary(scan, snapshot, capability_map)

    def build_capability_map(
        self,
        scan: DirectoryScanResult,
        snapshot: ArchitectureSnapshot,
    ) -> CapabilityMap:
        categories = scan.counts_by_category
        issue_codes = {issue.code for issue in snapshot.issues}
        self_model_path = self.self_model_dir / "architecture_snapshot.json"

        return CapabilityMap(
            can_scan_files=scan.ok,
            can_save_snapshots=self.self_model_dir.exists() or self._can_create(self.self_model_dir),
            can_load_latest_snapshot=self_model_path.exists(),
            has_router_layer=categories.get("router", 0) > 0,
            has_service_layer=categories.get("service", 0) > 0,
            has_persona_files=categories.get("persona_manifest", 0) > 0 or categories.get("persona_policy", 0) > 0,
            has_memory_files=categories.get("memory_file", 0) > 0,
            has_config_files=categories.get("config_file", 0) > 0,
            has_tests=categories.get("test_file", 0) > 0,
            detected_import_issues="deprecated_import_reference" in issue_codes,
            detected_missing_architecture=bool(snapshot.missing_expected),
        )

    def save_latest(
        self,
        scan: DirectoryScanResult,
        snapshot: ArchitectureSnapshot,
        capability_map: CapabilityMap,
    ) -> dict[str, str]:
        self.self_model_dir.mkdir(parents=True, exist_ok=True)
        self.scan_reports_dir.mkdir(parents=True, exist_ok=True)

        issues = [issue.model_dump() for issue in snapshot.issues]
        paths = {
            "architecture_snapshot": self.self_model_dir / "architecture_snapshot.json",
            "file_inventory": self.self_model_dir / "file_inventory.json",
            "capability_map": self.self_model_dir / "capability_map.json",
            "unresolved_issues": self.self_model_dir / "unresolved_issues.json",
            "last_scan_summary": self.self_model_dir / "last_scan_summary.md",
        }

        self._write_json(paths["architecture_snapshot"], snapshot.model_dump())
        self._write_json(paths["file_inventory"], scan.model_dump())
        self._write_json(paths["capability_map"], capability_map.model_dump())
        self._write_json(paths["unresolved_issues"], {"issues": issues})
        paths["last_scan_summary"].write_text(self._summary_markdown(scan, snapshot, capability_map), encoding="utf-8")

        return {key: str(path) for key, path in paths.items()}

    def build_summary(
        self,
        scan: DirectoryScanResult,
        snapshot: ArchitectureSnapshot,
        capability_map: CapabilityMap,
    ) -> SystemPerceptionSummary:
        return SystemPerceptionSummary(
            ok=True,
            generated_at=utc_timestamp(),
            project_root=str(self.project_root),
            file_count=len(scan.files),
            counts_by_category=scan.counts_by_category,
            capability_map=capability_map,
            issues=snapshot.issues,
            snapshot_paths={
                "architecture_snapshot": str(self.self_model_dir / "architecture_snapshot.json"),
                "file_inventory": str(self.self_model_dir / "file_inventory.json"),
                "capability_map": str(self.self_model_dir / "capability_map.json"),
                "unresolved_issues": str(self.self_model_dir / "unresolved_issues.json"),
                "last_scan_summary": str(self.self_model_dir / "last_scan_summary.md"),
                "scan_reports": str(self.scan_reports_dir),
            },
        )

    def load_latest_snapshot(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "architecture_snapshot.json")

    def load_latest_capabilities(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "capability_map.json")

    def load_latest_issues(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "unresolved_issues.json")

    def load_latest_change_report(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "change_report.json")

    def load_latest_change_summary_text(self) -> str | None:
        path = self.self_model_dir / "last_change_summary.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def load_latest_summary_text(self) -> str | None:
        path = self.self_model_dir / "last_scan_summary.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def _summary_markdown(
        self,
        scan: DirectoryScanResult,
        snapshot: ArchitectureSnapshot,
        capability_map: CapabilityMap,
    ) -> str:
        lines = [
            "# Vaila System Perception Summary",
            "",
            f"- Generated: {snapshot.generated_at}",
            f"- Project root: {self.project_root}",
            f"- Files scanned: {len(scan.files)}",
            f"- Issues detected: {len(snapshot.issues)}",
            "",
            "## Capability Map",
        ]
        for key, value in capability_map.model_dump().items():
            lines.append(f"- {key}: {value}")

        lines.extend(["", "## File Categories"])
        for category, count in sorted(scan.counts_by_category.items()):
            lines.append(f"- {category}: {count}")

        lines.extend(["", "## Issues"])
        if snapshot.issues:
            for issue in snapshot.issues:
                path = f" ({issue.path})" if issue.path else ""
                lines.append(f"- [{issue.severity}] {issue.code}: {issue.message}{path}")
        else:
            lines.append("- No unresolved issues detected.")

        return "\n".join(lines) + "\n"

    def _can_create(self, path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except OSError:
            return False

    def _load_comparison_snapshot(self) -> dict[str, Any] | None:
        return self._load_json(self.self_model_dir / "file_inventory.json")

    def _comparison_snapshot(
        self,
        scan: DirectoryScanResult,
        snapshot: ArchitectureSnapshot,
        capability_map: CapabilityMap,
    ) -> dict[str, Any]:
        payload = scan.model_dump()
        payload["capability_map"] = capability_map.model_dump()
        payload["issues"] = [issue.model_dump() for issue in snapshot.issues]
        return payload

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
