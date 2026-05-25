from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services.system_health_service import SystemHealthService
from app.services.system_recommendation_service import SystemRecommendationService
from app.services.system_repair_packet_service import SystemRepairPacketService

router = APIRouter(prefix="/system-core/perception", tags=["system perception"])


def _service() -> SystemHealthService:
    return SystemHealthService()


def _recommendation_service() -> SystemRecommendationService:
    return SystemRecommendationService(_service().project_root)


def _repair_packet_service() -> SystemRepairPacketService:
    return SystemRepairPacketService(_service().project_root)


@router.get("/scan")
def scan() -> dict[str, Any]:
    summary = _service().run_scan()
    return summary.model_dump()


@router.get("/latest")
def latest() -> dict[str, Any]:
    service = _service()
    snapshot = service.load_latest_snapshot()
    if snapshot is None:
        return service.run_scan().model_dump()
    return snapshot


@router.get("/capabilities")
def capabilities() -> dict[str, Any]:
    service = _service()
    capability_map = service.load_latest_capabilities()
    if capability_map is None:
        return service.run_scan().capability_map.model_dump()
    return capability_map


@router.get("/issues")
def issues() -> dict[str, Any]:
    service = _service()
    unresolved = service.load_latest_issues()
    if unresolved is None:
        return {"issues": [issue.model_dump() for issue in service.run_scan().issues]}
    return unresolved


@router.get("/summary")
def summary() -> dict[str, str]:
    service = _service()
    text = service.load_latest_summary_text()
    if text is None:
        service.run_scan()
        text = service.load_latest_summary_text() or ""
    return {"summary": text}


@router.get("/changes")
def changes() -> dict[str, Any]:
    service = _service()
    report = service.load_latest_change_report()
    if report is None:
        service.run_scan()
        report = service.load_latest_change_report() or {}
    return report


@router.get("/changes/summary")
def changes_summary() -> dict[str, str]:
    service = _service()
    text = service.load_latest_change_summary_text()
    if text is None:
        service.run_scan()
        text = service.load_latest_change_summary_text() or ""
    return {"summary": text}


@router.get("/recommendations")
def recommendations() -> dict[str, Any]:
    service = _recommendation_service()
    plan = service.load_latest_recommendation_plan()
    if plan is None:
        plan_model = service.generate_recommendations()
        service.save_recommendation_plan(plan_model)
        return plan_model.model_dump()
    return plan


@router.get("/recommendations/generate")
def generate_recommendations() -> dict[str, Any]:
    service = _recommendation_service()
    plan = service.generate_recommendations()
    service.save_recommendation_plan(plan)
    return plan.model_dump()


@router.get("/recommendations/summary")
def recommendations_summary() -> dict[str, str]:
    service = _recommendation_service()
    text = service.load_latest_recommendation_summary()
    if text is None:
        plan = service.generate_recommendations()
        service.save_recommendation_plan(plan)
        text = service.load_latest_recommendation_summary() or ""
    return {"summary": text}


@router.get("/repair-packets")
def repair_packets() -> dict[str, Any]:
    return _repair_packet_service().load_repair_packet_index()


@router.get("/repair-packets/generate")
def generate_repair_packets(mode: str = "top", limit: int = 1) -> dict[str, Any]:
    batch = _repair_packet_service().create_repair_packets(mode=mode, limit=limit)
    return batch.model_dump()


@router.get("/repair-packets/latest")
def latest_repair_packet() -> dict[str, Any]:
    packet = _repair_packet_service().load_latest_packet()
    return packet or {"packet": None}


@router.get("/repair-packets/summary")
def repair_packet_summary() -> dict[str, str]:
    service = _repair_packet_service()
    latest = service.load_latest_packet()
    if latest is None:
        return {"summary": "No repair packets have been generated yet."}
    return {"summary": service.format_repair_packet_summary(latest)}
