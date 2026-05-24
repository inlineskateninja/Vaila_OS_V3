from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from app.models.system_perception_models import (
    ArchitectureSnapshot,
    DirectoryScanResult,
    SystemIssue,
    as_posix_relative,
    utc_timestamp,
)


EXPECTED_PATHS = [
    "core_system_files/app.py",
    "core_system_files/system_services/python_backend/app/routers",
    "core_system_files/system_services/python_backend/app/services",
    "core_system_files/system_services/python_backend/app/models",
    "core_system_files/system_state/self_model",
    "core_system_files/system_state/scan_reports",
]

EXPECTED_SUPPORT_DIRS = [
    ["personas", "persona_files", "vaila_system_os/persona_files"],
    ["memory", "system_wide_memory", "vaila_system_os/system_wide_memory"],
]

SUSPICIOUS_PARTS = {"bridge_old", "deprecated", "legacy", "archive_old"}
DUPLICATE_BRIDGE_NAMES = {"bridge.py", "service_bridge.py", "router_bridge.py"}


class SystemManifestService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()

    def build_snapshot(self, scan: DirectoryScanResult) -> ArchitectureSnapshot:
        present_expected: list[str] = []
        missing_expected: list[str] = []
        issues: list[SystemIssue] = []

        for expected in EXPECTED_PATHS:
            path = self.project_root / expected
            if path.exists():
                present_expected.append(expected)
            else:
                missing_expected.append(expected)
                issues.append(
                    SystemIssue(
                        code="missing_expected_path",
                        severity="warning",
                        message=f"Expected architecture path is missing: {expected}",
                        path=expected,
                    )
                )

        for group in EXPECTED_SUPPORT_DIRS:
            existing = [name for name in group if (self.project_root / name).exists()]
            if existing:
                present_expected.extend(existing[:1])
            else:
                canonical = group[0]
                missing_expected.append(canonical)
                issues.append(
                    SystemIssue(
                        code="missing_support_directory",
                        severity="warning",
                        message=f"Expected support directory is missing. Accepted names: {', '.join(group)}",
                        path=canonical,
                    )
                )

        useful_unexpected = self._useful_unexpected(scan)
        issues.extend(self._empty_important_directories())
        issues.extend(self._suspicious_paths(scan))
        issues.extend(self._duplicate_bridge_files(scan))
        issues.extend(self._deprecated_imports(scan))

        return ArchitectureSnapshot(
            ok=True,
            generated_at=utc_timestamp(),
            project_root=str(self.project_root),
            present_expected=sorted(set(present_expected)),
            missing_expected=sorted(set(missing_expected)),
            useful_unexpected=useful_unexpected,
            issues=issues,
            counts_by_category=scan.counts_by_category,
        )

    def _useful_unexpected(self, scan: DirectoryScanResult) -> list[str]:
        expected_prefixes = tuple(EXPECTED_PATHS)
        useful_categories = {"service", "router", "model_schema", "test_file", "config_file"}
        useful = [
            item.path
            for item in scan.files
            if item.category in useful_categories and not item.path.startswith(expected_prefixes)
        ]
        return useful[:100]

    def _empty_important_directories(self) -> list[SystemIssue]:
        issues: list[SystemIssue] = []
        for relative in EXPECTED_PATHS:
            path = self.project_root / relative
            if path.exists() and path.is_dir() and not any(path.iterdir()):
                issues.append(
                    SystemIssue(
                        code="empty_important_directory",
                        severity="info",
                        message=f"Important architecture directory is empty: {relative}",
                        path=relative,
                    )
                )
        return issues

    def _suspicious_paths(self, scan: DirectoryScanResult) -> list[SystemIssue]:
        issues: list[SystemIssue] = []
        for item in scan.files:
            parts = set(Path(item.path.lower()).parts)
            if parts.intersection(SUSPICIOUS_PARTS):
                issues.append(
                    SystemIssue(
                        code="suspicious_path",
                        severity="warning",
                        message="Path contains a deprecated or suspicious folder marker.",
                        path=item.path,
                    )
                )
        return issues

    def _duplicate_bridge_files(self, scan: DirectoryScanResult) -> list[SystemIssue]:
        by_name: dict[str, list[str]] = defaultdict(list)
        for item in scan.files:
            if item.name.lower() in DUPLICATE_BRIDGE_NAMES:
                by_name[item.name.lower()].append(item.path)

        issues: list[SystemIssue] = []
        for name, paths in by_name.items():
            if len(paths) > 1:
                issues.append(
                    SystemIssue(
                        code="duplicate_bridge_files",
                        severity="warning",
                        message=f"Duplicate bridge file name found: {name}",
                        details={"paths": paths},
                    )
                )
        return issues

    def _deprecated_imports(self, scan: DirectoryScanResult) -> list[SystemIssue]:
        return [
            SystemIssue(
                code="deprecated_import_reference",
                severity="warning",
                message="Python file references a deprecated app import path.",
                path=item.path,
            )
            for item in scan.files
            if item.metadata.get("has_deprecated_import")
        ]

    def latest_snapshot_path(self) -> Path:
        return self.project_root / "core_system_files" / "system_state" / "self_model" / "architecture_snapshot.json"

    def load_latest_snapshot(self) -> dict[str, Any] | None:
        path = self.latest_snapshot_path()
        if not path.exists():
            return None
        import json

        return json.loads(path.read_text(encoding="utf-8"))
