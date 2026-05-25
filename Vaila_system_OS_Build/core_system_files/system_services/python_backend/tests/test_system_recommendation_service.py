from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.system_recommendation_service import SystemRecommendationService


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def seed_state(
    root: Path,
    snapshot: dict | None = None,
    capabilities: dict | None = None,
    issues: list[dict] | None = None,
    change_report: dict | None = None,
) -> None:
    state = root / "core_system_files" / "system_state" / "self_model"
    if snapshot is not None:
        write_json(state / "architecture_snapshot.json", snapshot)
        write_json(state / "file_inventory.json", {"files": [], "counts_by_category": {}, "scanned_at": "2026-01-01T00:00:00Z"})
    if capabilities is not None:
        write_json(state / "capability_map.json", capabilities)
    if issues is not None:
        write_json(state / "unresolved_issues.json", {"issues": issues})
    if change_report is not None:
        write_json(state / "change_report.json", change_report)


def test_creates_no_data_plan_when_no_scan_data_exists(tmp_path: Path):
    plan = SystemRecommendationService(tmp_path).generate_recommendations()

    assert plan.status == "no_data"
    assert plan.summary_counts["total"] == 0


def test_generates_recommendation_from_missing_expected_file(tmp_path: Path):
    seed_state(
        tmp_path,
        snapshot={"missing_expected": ["core_system_files/app.py"], "issues": [], "counts_by_category": {}},
        capabilities={},
        issues=[],
    )

    plan = SystemRecommendationService(tmp_path).generate_recommendations()

    assert plan.status == "created"
    assert plan.recommendations[0].category == "missing_expected_file"
    assert plan.recommendations[0].priority == "critical"


def test_generates_recommendation_from_broken_import_issue(tmp_path: Path):
    seed_state(
        tmp_path,
        snapshot={"missing_expected": [], "issues": [], "counts_by_category": {}},
        capabilities={},
        issues=[{"code": "deprecated_import_reference", "severity": "warning", "message": "Bad import", "path": "app/core.py", "details": {}}],
    )

    plan = SystemRecommendationService(tmp_path).generate_recommendations()

    assert any(item.category == "broken_import" for item in plan.recommendations)
    assert any(item.priority == "critical" for item in plan.recommendations)


def test_prioritizes_critical_before_high_medium_low(tmp_path: Path):
    service = SystemRecommendationService(tmp_path)
    low = service._rec("Low", "cleanup", "low", "informational", "cleanup", ["x"], "Document cleanup.")
    high = service._rec("High", "missing_tests", "high", "risky", "tests missing", ["x"], "Add tests.")
    critical = service._rec("Critical", "broken_import", "critical", "blocking", "import broken", ["x"], "Fix import.")
    medium = service._rec("Medium", "documentation", "medium", "inconvenient", "docs missing", ["x"], "Add docs.")

    ordered = service.prioritize_recommendations([low, high, critical, medium])

    assert [item.priority for item in ordered] == ["critical", "high", "medium", "low"]


def test_duplicate_architecture_is_not_marked_safe_for_codex(tmp_path: Path):
    seed_state(
        tmp_path,
        snapshot={"missing_expected": [], "issues": [], "counts_by_category": {}},
        capabilities={},
        issues=[{"code": "duplicate_bridge_files", "severity": "warning", "message": "Duplicate bridge", "path": None, "details": {"paths": ["a.py", "b.py"]}}],
    )

    plan = SystemRecommendationService(tmp_path).generate_recommendations()
    duplicate = next(item for item in plan.recommendations if item.category == "duplicate_architecture")

    assert duplicate.safe_to_delegate_to_codex is False


def test_all_recommendations_require_user_approval(tmp_path: Path):
    seed_state(
        tmp_path,
        snapshot={"missing_expected": ["core_system_files/app.py"], "issues": [], "counts_by_category": {}},
        capabilities={"has_tests": False},
        issues=[],
    )

    plan = SystemRecommendationService(tmp_path).generate_recommendations()

    assert plan.recommendations
    assert all(item.requires_user_approval for item in plan.recommendations)


def test_saves_recommendation_plan_and_summary(tmp_path: Path):
    seed_state(
        tmp_path,
        snapshot={"missing_expected": ["core_system_files/app.py"], "issues": [], "counts_by_category": {}},
        capabilities={},
        issues=[],
    )
    service = SystemRecommendationService(tmp_path)
    plan = service.generate_recommendations()

    service.save_recommendation_plan(plan)

    state = tmp_path / "core_system_files" / "system_state" / "self_model"
    assert (state / "recommendation_plan.json").exists()
    assert (state / "last_recommendation_plan.md").exists()
    assert list((tmp_path / "core_system_files" / "system_state" / "scan_reports").glob("recommendations_*.json"))
