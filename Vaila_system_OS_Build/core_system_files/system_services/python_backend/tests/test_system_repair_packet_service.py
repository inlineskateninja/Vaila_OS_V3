from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.system_repair_packet_service import SystemRepairPacketService


def recommendation(
    rec_id: str = "rec_top",
    priority: str = "critical",
    safe: bool = True,
    title: str = "Fix perception router registration",
) -> dict:
    return {
        "id": rec_id,
        "title": title,
        "category": "missing_router",
        "priority": priority,
        "severity": "blocking" if priority == "critical" else "risky",
        "reason": "The route exists but may not be registered.",
        "evidence": ["route missing"],
        "suggested_action": "Register the perception router with the active app.",
        "affected_files": ["app/service.py"],
        "blocked_by": [],
        "safe_to_delegate_to_codex": safe,
        "requires_user_approval": True,
    }


def write_plan(root: Path, recommendations: list[dict]) -> None:
    path = root / "core_system_files" / "system_state" / "self_model" / "recommendation_plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "created",
        "created_at": "2026-01-01T00:00:00Z",
        "source_files": {},
        "summary_counts": {"critical": 1, "high": 0, "medium": 0, "low": 0, "total": len(recommendations)},
        "top_recommendation": recommendations[0] if recommendations else {},
        "recommendations": recommendations,
        "notes": [],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_creates_no_data_response_when_no_recommendation_plan_exists(tmp_path: Path):
    batch = SystemRepairPacketService(tmp_path).create_repair_packets()

    assert batch.status == "no_data"
    assert not batch.packets


def test_creates_one_top_repair_packet_from_top_recommendation(tmp_path: Path):
    write_plan(tmp_path, [recommendation()])

    batch = SystemRepairPacketService(tmp_path).create_repair_packets(mode="top", limit=1)

    assert batch.status == "created"
    assert len(batch.packets) == 1
    assert batch.packets[0].title == "Fix perception router registration"


def test_creates_safe_repair_packets_only_when_mode_is_safe(tmp_path: Path):
    write_plan(tmp_path, [recommendation("safe", safe=True), recommendation("unsafe", safe=False, title="Review duplicate bridge")])

    batch = SystemRepairPacketService(tmp_path).create_repair_packets(mode="safe", limit=10)

    assert len(batch.packets) == 1
    assert batch.packets[0].safe_to_delegate_to_codex is True


def test_respects_packet_limit(tmp_path: Path):
    write_plan(tmp_path, [recommendation("a"), recommendation("b", priority="high", title="Add tests")])

    batch = SystemRepairPacketService(tmp_path).create_repair_packets(mode="all", limit=1)

    assert len(batch.packets) == 1


def test_every_packet_requires_user_approval(tmp_path: Path):
    write_plan(tmp_path, [recommendation()])

    batch = SystemRepairPacketService(tmp_path).create_repair_packets()

    assert batch.packets[0].requires_user_approval is True


def test_destructive_recommendations_are_not_marked_safe_for_codex(tmp_path: Path):
    write_plan(tmp_path, [recommendation(safe=False, title="Review duplicate architecture")])

    batch = SystemRepairPacketService(tmp_path).create_repair_packets()

    assert batch.packets[0].safe_to_delegate_to_codex is False


def test_saves_json_markdown_and_updates_index(tmp_path: Path):
    write_plan(tmp_path, [recommendation()])
    service = SystemRepairPacketService(tmp_path)

    batch = service.create_repair_packets()
    metadata = batch.packet_metadata[0]

    assert Path(metadata["json_path"]).exists()
    assert Path(metadata["markdown_path"]).exists()
    assert (tmp_path / "core_system_files" / "system_state" / "self_model" / "repair_packet_index.json").exists()


def test_generated_codex_prompt_contains_required_sections(tmp_path: Path):
    write_plan(tmp_path, [recommendation()])

    packet = SystemRepairPacketService(tmp_path).create_repair_packets().packets[0]
    prompt = packet.codex_prompt.lower()

    assert "goal:" in prompt
    assert "context:" in prompt
    assert "allowed actions:" in prompt
    assert "forbidden actions:" in prompt
    assert "tests to add or update:" in prompt
    assert "acceptance criteria:" in prompt
