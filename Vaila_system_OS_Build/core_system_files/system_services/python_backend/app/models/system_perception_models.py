from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


FileCategory = Literal[
    "core_entrypoint",
    "router",
    "service",
    "model_schema",
    "persona_manifest",
    "persona_policy",
    "memory_file",
    "config_file",
    "test_file",
    "documentation",
    "script",
    "unknown",
]


class FileInventoryItem(BaseModel):
    path: str
    name: str
    extension: str
    size_bytes: int
    modified_time: str
    category: FileCategory
    metadata: dict[str, Any] = Field(default_factory=dict)


class DirectoryScanConfig(BaseModel):
    project_root: str
    allowed_roots: list[str] = Field(default_factory=list)
    ignored_folders: list[str] = Field(default_factory=list)
    ignored_extensions: list[str] = Field(default_factory=list)
    max_file_size_bytes: int = 512_000
    max_scan_depth: int = 8
    read_small_python_files: bool = True


class DirectoryScanResult(BaseModel):
    ok: bool
    scanned_at: str
    project_root: str
    config: DirectoryScanConfig
    files: list[FileInventoryItem] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    counts_by_category: dict[str, int] = Field(default_factory=dict)
    report_path: str | None = None


class SystemIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    path: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ArchitectureSnapshot(BaseModel):
    ok: bool
    generated_at: str
    project_root: str
    present_expected: list[str] = Field(default_factory=list)
    missing_expected: list[str] = Field(default_factory=list)
    useful_unexpected: list[str] = Field(default_factory=list)
    issues: list[SystemIssue] = Field(default_factory=list)
    counts_by_category: dict[str, int] = Field(default_factory=dict)


class CapabilityMap(BaseModel):
    can_scan_files: bool = False
    can_save_snapshots: bool = False
    can_load_latest_snapshot: bool = False
    has_router_layer: bool = False
    has_service_layer: bool = False
    has_persona_files: bool = False
    has_memory_files: bool = False
    has_config_files: bool = False
    has_tests: bool = False
    detected_import_issues: bool = False
    detected_missing_architecture: bool = False


class SystemPerceptionSummary(BaseModel):
    ok: bool
    generated_at: str
    project_root: str
    file_count: int
    counts_by_category: dict[str, int] = Field(default_factory=dict)
    capability_map: CapabilityMap
    issues: list[SystemIssue] = Field(default_factory=list)
    snapshot_paths: dict[str, str] = Field(default_factory=dict)


class CapabilityChange(BaseModel):
    name: str
    previous: Any = None
    current: Any = None


class SystemChangeReport(BaseModel):
    status: Literal["baseline_created", "changes_detected", "no_changes", "comparison_failed"]
    previous_scan_time: str = ""
    current_scan_time: str = ""
    summary_counts: dict[str, int] = Field(default_factory=dict)
    added_files: list[str] = Field(default_factory=list)
    removed_files: list[str] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list)
    unchanged_files_count: int = 0
    added_services: list[str] = Field(default_factory=list)
    removed_services: list[str] = Field(default_factory=list)
    added_routers: list[str] = Field(default_factory=list)
    removed_routers: list[str] = Field(default_factory=list)
    added_personas: list[str] = Field(default_factory=list)
    removed_personas: list[str] = Field(default_factory=list)
    capability_changes: list[CapabilityChange] = Field(default_factory=list)
    new_issues: list[SystemIssue] = Field(default_factory=list)
    resolved_issues: list[SystemIssue] = Field(default_factory=list)
    persistent_issues: list[SystemIssue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_posix_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
