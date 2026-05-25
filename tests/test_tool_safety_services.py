from __future__ import annotations

from pathlib import Path

from System_Services.approval_service import ApprovalService
from System_Services.tool_intent_service import ToolIntent, ToolIntentService
from System_Services.tool_permission_service import ToolPermissionService


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_permission_service_explains_calendar_create() -> None:
    intent = ToolIntentService(project_root()).detect_intent("Schedule a meeting tomorrow at 2 PM.")
    service = ToolPermissionService(project_root())

    assert service.get_risk_level(intent.tool_id, intent.action) == "high"
    assert service.requires_approval(intent.tool_id, intent.action) is True
    assert service.can_execute_without_approval(intent) is False

    explanation = service.explain_permission(intent)
    assert explanation["approval_required"] is True
    assert explanation["can_execute_without_approval"] is False
    assert explanation["reason"] == "approval_required_by_assistant_tool_policy"


def test_permission_service_allows_calculator_without_approval() -> None:
    intent = ToolIntentService(project_root()).detect_intent("What is 12 percent of 50?")
    service = ToolPermissionService(project_root())

    assert intent.tool_id == "calculator"
    assert service.get_risk_level(intent.tool_id, intent.action) == "low"
    assert service.requires_approval(intent.tool_id, intent.action) is False
    assert service.can_execute_without_approval(intent) is True


def test_approval_service_create_approve_reject_flow(tmp_path: Path) -> None:
    intent = ToolIntent(
        intent_id="email_management",
        tool_id="gmail",
        service_id="google",
        action="draft_reply",
        confidence=0.95,
        risk_level="medium",
        approval_required=False,
        source="text",
        raw_text="Draft an email to Malik.",
        normalized_text="draft an email to malik",
    )
    service = ApprovalService(project_root=tmp_path)

    created = service.create_approval_request(
        intent,
        {
            "summary": "Draft an email for review.",
            "payload": {"to": "Malik", "body": "Ready for review."},
        },
    )

    assert created["approval_id"].startswith("appr_")
    assert created["status"] == "pending"
    assert service.list_pending_approvals()[0]["approval_id"] == created["approval_id"]

    approved = service.approve_request(created["approval_id"])
    assert approved["ok"] is True
    assert approved["approval"]["status"] == "approved"
    assert approved["approval"]["approved_at"]
    assert service.list_pending_approvals() == []

    rejected_missing = service.reject_request("appr_missing")
    assert rejected_missing == {
        "ok": False,
        "error": "approval_not_found",
        "approval_id": "appr_missing",
    }


def test_approval_service_reject_pending_request(tmp_path: Path) -> None:
    intent = ToolIntentService(project_root()).detect_intent("Remind me tomorrow to test approvals.")
    service = ApprovalService(project_root=tmp_path)
    created = service.create_approval_request(intent, "Prepare reminder for approval.")

    rejected = service.reject_request(created["approval_id"])

    assert rejected["ok"] is True
    assert rejected["approval"]["status"] == "rejected"
    assert rejected["approval"]["rejected_at"]
