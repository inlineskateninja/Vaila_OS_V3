from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services.system_health_service import SystemHealthService

router = APIRouter(prefix="/system-core/perception", tags=["system perception"])


def _service() -> SystemHealthService:
    return SystemHealthService()


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
