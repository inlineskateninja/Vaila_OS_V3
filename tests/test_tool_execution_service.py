from __future__ import annotations

import shutil
from pathlib import Path

from System_Services.tool_execution_service import ToolExecutionService
from System_Services.tool_intent_service import ToolIntentService


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def prepared_root(tmp_path: Path) -> Path:
    root = tmp_path / "vaila"
    root.mkdir()
    shutil.copytree(project_root() / "Tools_Registry", root / "Tools_Registry")
    return root


def detect(text: str, source: str = "text"):
    return ToolIntentService(project_root()).detect_intent(text, source=source)


def test_intent_can_flow_into_dry_run_execution(tmp_path: Path) -> None:
    service = ToolExecutionService(project_root=prepared_root(tmp_path))
    intent = detect("Find the latest roadmap document in Google Drive.")

    result = service.dry_run_intent(intent)

    assert result.ok is True
    assert result.tool_id == "google_drive"
    assert result.action == "search_files"
    assert result.status == "dry_run"
    assert result.audit_id.startswith("audit_")


def test_external_tool_fails_gracefully_when_not_connected_after_approval(tmp_path: Path) -> None:
    service = ToolExecutionService(project_root=prepared_root(tmp_path))
    intent = detect("Schedule a project meeting tomorrow at 2 PM.")

    result = service.execute_intent(intent, approved=True)

    assert result.ok is False
    assert result.tool_id == "google_calendar"
    assert result.status == "not_connected"
    assert "not connected yet" in result.summary


def test_approval_required_before_calendar_execution(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    service = ToolExecutionService(project_root=root)
    intent = detect("Schedule a project meeting tomorrow at 2 PM.")

    result = service.execute_intent(intent)

    assert result.ok is False
    assert result.status == "approval_required"
    assert result.requires_approval is True
    assert result.approval_id.startswith("appr_")
    assert (root / "System_Logging" / "Approval_Logs" / "approvals.jsonl").exists()


def test_calculator_executes_locally(tmp_path: Path) -> None:
    service = ToolExecutionService(project_root=prepared_root(tmp_path))
    intent = detect("What is 22 percent of 180?")

    result = service.execute_intent(intent)

    assert result.ok is True
    assert result.tool_id == "calculator"
    assert result.status == "completed"
    assert result.data["result"] == 39.6


def test_notes_create_locally(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    service = ToolExecutionService(project_root=root)
    intent = detect("Take a note that execution placeholders are ready.")

    result = service.execute_intent(intent)

    assert result.ok is True
    assert result.tool_id == "notes"
    assert result.status == "completed"
    assert (root / "data" / "assistant_notes.jsonl").exists()


def test_reminder_create_requires_approval_then_can_write_locally(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    service = ToolExecutionService(project_root=root)
    intent = detect("Remind me tomorrow to test execution.")

    blocked = service.execute_intent(intent)
    approved = service.execute_intent(intent, approved=True)

    assert blocked.status == "approval_required"
    assert approved.ok is True
    assert approved.status == "completed"
    assert (root / "data" / "assistant_reminders.jsonl").exists()
