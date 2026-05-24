from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.system_change_service import SystemChangeService


def file_item(path: str, size: int = 10, modified: str = "2026-01-01T00:00:00Z", category: str = "script") -> dict:
    return {
        "path": path,
        "name": Path(path).name,
        "extension": Path(path).suffix,
        "size_bytes": size,
        "modified_time": modified,
        "category": category,
        "metadata": {},
    }


def snapshot(files: list[dict], capabilities: dict | None = None, issues: list[dict] | None = None, scan_time: str = "2026-01-01T00:00:00Z") -> dict:
    return {
        "scanned_at": scan_time,
        "files": files,
        "capability_map": capabilities or {},
        "issues": issues or [],
    }


def test_baseline_report_is_created_when_no_previous_snapshot(tmp_path: Path):
    service = SystemChangeService(tmp_path)

    report = service.compare_snapshots(None, snapshot([file_item("core_system_files/app.py")]))

    assert report.status == "baseline_created"
    assert report.summary_counts["added_files"] == 0


def test_added_files_are_detected(tmp_path: Path):
    service = SystemChangeService(tmp_path)
    previous = snapshot([file_item("core_system_files/app.py")])
    current = snapshot([file_item("core_system_files/app.py"), file_item("core_system_files/new.py")])

    report = service.compare_snapshots(previous, current)

    assert report.status == "changes_detected"
    assert report.added_files == ["core_system_files/new.py"]


def test_removed_files_are_detected(tmp_path: Path):
    service = SystemChangeService(tmp_path)
    previous = snapshot([file_item("core_system_files/app.py"), file_item("core_system_files/old.py")])
    current = snapshot([file_item("core_system_files/app.py")])

    report = service.compare_snapshots(previous, current)

    assert report.removed_files == ["core_system_files/old.py"]


def test_modified_files_are_detected_by_timestamp_or_size(tmp_path: Path):
    service = SystemChangeService(tmp_path)
    previous = snapshot([file_item("core_system_files/app.py", size=10, modified="2026-01-01T00:00:00Z")])
    current = snapshot([file_item("core_system_files/app.py", size=12, modified="2026-01-01T00:00:01Z")])

    report = service.compare_snapshots(previous, current)

    assert report.modified_files == ["core_system_files/app.py"]


def test_capability_changes_are_detected(tmp_path: Path):
    service = SystemChangeService(tmp_path)
    previous = snapshot([], capabilities={"has_tests": False})
    current = snapshot([], capabilities={"has_tests": True})

    report = service.compare_snapshots(previous, current)

    assert len(report.capability_changes) == 1
    assert report.capability_changes[0].name == "has_tests"


def test_new_and_resolved_issues_are_detected(tmp_path: Path):
    service = SystemChangeService(tmp_path)
    old_issue = {"code": "old_issue", "severity": "warning", "message": "Old issue", "path": "old.py", "details": {}}
    new_issue = {"code": "new_issue", "severity": "warning", "message": "New issue", "path": "new.py", "details": {}}
    previous = snapshot([], issues=[old_issue])
    current = snapshot([], issues=[new_issue])

    report = service.compare_snapshots(previous, current)

    assert report.new_issues[0].code == "new_issue"
    assert report.resolved_issues[0].code == "old_issue"


def test_no_changes_returns_no_changes_status(tmp_path: Path):
    service = SystemChangeService(tmp_path)
    previous = snapshot([file_item("core_system_files/app.py")], capabilities={"has_tests": True})
    current = snapshot([file_item("core_system_files/app.py")], capabilities={"has_tests": True})

    report = service.compare_snapshots(previous, current)

    assert report.status == "no_changes"
    assert report.summary_counts["modified_files"] == 0


def test_change_report_is_saved(tmp_path: Path):
    service = SystemChangeService(tmp_path)
    report = service.compare_snapshots(None, snapshot([file_item("core_system_files/app.py")]))

    service.save_change_report(report)

    assert (tmp_path / "core_system_files" / "system_state" / "self_model" / "change_report.json").exists()
    assert (tmp_path / "core_system_files" / "system_state" / "self_model" / "last_change_summary.md").exists()
    assert list((tmp_path / "core_system_files" / "system_state" / "scan_reports").glob("change_*.json"))
