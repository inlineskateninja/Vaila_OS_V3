from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core import VailaCore
from app.router import route_user_input
from app.service import app
from app.services.system_health_service import SystemHealthService
from app.services.system_self_query_service import SystemSelfQueryService


FORBIDDEN_LANGUAGE = [
    "i feel",
    "i became aware",
    "i discovered myself",
    "my consciousness noticed",
    "i evolved",
]


def write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(tmp_path: Path) -> Path:
    write(tmp_path / "core_system_files" / "app.py", "print('start')\n")
    write(tmp_path / "core_system_files" / "system_services" / "python_backend" / "app" / "routers" / "system_router.py")
    write(tmp_path / "core_system_files" / "system_services" / "python_backend" / "app" / "services" / "system_service.py")
    write(tmp_path / "core_system_files" / "system_services" / "python_backend" / "app" / "models" / "system_models.py")
    write(tmp_path / "personas" / "Proto_Jane" / "manifest.json", "{}")
    write(tmp_path / "memory" / "notes.jsonl", "{}\n")
    write(tmp_path / "config" / "app_config.json", "{}")
    write(tmp_path / "tests" / "test_system.py", "def test_ok():\n    assert True\n")
    return tmp_path


def test_prompt_classification_routes_system_self_query():
    assert route_user_input("scan your system").task_type == "system_self_query"
    assert route_user_input("inspect your files").task_type == "system_self_query"
    assert route_user_input("what changed since the last scan").task_type == "system_self_query"
    assert route_user_input("what services do you have").task_type == "system_self_query"
    assert route_user_input("what personas are present").task_type == "system_self_query"
    assert route_user_input("how should I plan tomorrow?").task_type != "system_self_query"


def test_self_query_loads_latest_snapshot_when_available(tmp_path: Path):
    project = make_project(tmp_path)
    SystemHealthService(project).run_scan()
    service = SystemSelfQueryService(project)

    result = service.handle_self_query("what services do you currently have?")

    assert result["ok"] is True
    assert result["action"] == "latest_snapshot"
    assert result["focus"] == "services"
    assert "service files" in result["response"]


def test_self_query_runs_scan_when_prompt_requests_scan(tmp_path: Path):
    project = make_project(tmp_path)
    service = SystemSelfQueryService(project)

    result = service.handle_self_query("Vaila, scan your system.")

    assert result["ok"] is True
    assert result["action"] == "new_scan"


def test_change_query_uses_latest_report_without_new_scan(tmp_path: Path):
    project = make_project(tmp_path)
    service = SystemSelfQueryService(project)
    service.health.run_scan()

    result = service.handle_self_query("what changed since the last scan")

    assert result["ok"] is True
    assert result["action"] == "latest_snapshot"
    assert result["focus"] == "changes"


def test_self_query_extracts_focus_values(tmp_path: Path):
    service = SystemSelfQueryService(make_project(tmp_path))

    assert service.extract_focus("what services do you have") == "services"
    assert service.extract_focus("what routers are installed") == "routers"
    assert service.extract_focus("what personas are present") == "personas"
    assert service.extract_focus("show unresolved issues") == "issues"
    assert service.extract_focus("show capability map") == "capabilities"
    assert service.extract_focus("what changed since the last scan") == "changes"


def test_self_query_returns_safe_fallback_when_scan_fails(tmp_path: Path):
    service = SystemSelfQueryService(make_project(tmp_path))
    service.health.run_scan = lambda: (_ for _ in ()).throw(RuntimeError("scan failed"))

    result = service.handle_self_query("scan your system")

    assert result["ok"] is False
    assert "could not complete" in result["response"].lower()


def test_chat_route_returns_perception_based_answer():
    client = TestClient(app)

    response = client.post("/chat", json={"message": "What services do you currently have?"})

    assert response.status_code == 200
    body = response.json()
    text = body["response"].lower()
    assert body["route_plan"]["task_type"] == "system_self_query"
    assert "service files" in text
    assert all(phrase not in text for phrase in FORBIDDEN_LANGUAGE)


def test_chat_route_change_query_uses_change_report():
    client = TestClient(app)
    client.get("/system-core/perception/scan")

    response = client.post("/chat", json={"message": "What changed since the last scan?"})

    assert response.status_code == 200
    body = response.json()
    text = body["response"].lower()
    assert body["route_plan"]["task_type"] == "system_self_query"
    assert body["system_self_query"]["focus"] == "changes"
    assert "comparison" in text or "baseline" in text or "no changes" in text
    assert all(phrase not in text for phrase in FORBIDDEN_LANGUAGE)


def test_core_chat_system_self_query_includes_architecture_facts():
    core = VailaCore()

    result = core.chat("Give me a summary of your current architecture.")

    text = result["response"].lower()
    assert result["route_plan"]["task_type"] == "system_self_query"
    assert "service files" in text
    assert "routers" in text
    assert all(phrase not in text for phrase in FORBIDDEN_LANGUAGE)
