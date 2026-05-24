from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.system_perception_models import DirectoryScanConfig
from app.routers.system_perception_router import router as system_perception_router
from app.services.system_health_service import SystemHealthService
from app.services.system_introspection_service import SystemIntrospectionService
from app.services.system_manifest_service import SystemManifestService


def write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(tmp_path: Path) -> Path:
    write(tmp_path / "core_system_files" / "app.py", "print('start')\n")
    write(tmp_path / "core_system_files" / "system_services" / "python_backend" / "app" / "routers" / "chat_router.py")
    write(tmp_path / "core_system_files" / "system_services" / "python_backend" / "app" / "services" / "chat_service.py")
    write(tmp_path / "core_system_files" / "system_services" / "python_backend" / "app" / "models" / "chat_models.py")
    write(tmp_path / "personas" / "Proto_Jane" / "manifest.json", "{}")
    write(tmp_path / "memory" / "notes.jsonl", "{}\n")
    write(tmp_path / "config" / "app_config.json", "{}")
    write(tmp_path / "tests" / "test_chat.py", "def test_ok():\n    assert True\n")
    return tmp_path


def scan_config(project_root: Path) -> DirectoryScanConfig:
    return DirectoryScanConfig(
        project_root=str(project_root),
        allowed_roots=["core_system_files", "personas", "memory", "config", "tests"],
        ignored_folders=[".git", ".venv", "venv", "__pycache__", "node_modules", "models"],
        ignored_extensions=[".zip", ".pyc", ".wav", ".gguf"],
        max_file_size_bytes=128_000,
        max_scan_depth=12,
    )


def test_scanner_ignores_forbidden_folders(tmp_path: Path):
    project = make_project(tmp_path)
    write(project / "core_system_files" / "__pycache__" / "bad.py", "x = 1")
    write(project / "core_system_files" / "models" / "model.gguf", "binary")
    write(project / ".git" / "config", "secret-ish")

    result = SystemIntrospectionService(project).scan(config=scan_config(project), save_report=False)
    paths = {item.path for item in result.files}

    assert "core_system_files/__pycache__/bad.py" not in paths
    assert "core_system_files/models/model.gguf" not in paths
    assert ".git/config" not in paths


def test_scanner_classifies_routers_correctly(tmp_path: Path):
    project = make_project(tmp_path)

    result = SystemIntrospectionService(project).scan(config=scan_config(project), save_report=False)
    item = next(file for file in result.files if file.name == "chat_router.py")

    assert item.category == "router"


def test_scanner_classifies_services_correctly(tmp_path: Path):
    project = make_project(tmp_path)

    result = SystemIntrospectionService(project).scan(config=scan_config(project), save_report=False)
    item = next(file for file in result.files if file.name == "chat_service.py")

    assert item.category == "service"


def test_scanner_saves_snapshot_json(tmp_path: Path):
    project = make_project(tmp_path)
    service = SystemHealthService(project)

    summary = service.run_scan()

    assert summary.snapshot_paths["architecture_snapshot"]
    assert (project / "core_system_files" / "system_state" / "self_model" / "architecture_snapshot.json").exists()
    assert (project / "core_system_files" / "system_state" / "self_model" / "file_inventory.json").exists()
    assert list((project / "core_system_files" / "system_state" / "scan_reports").glob("scan_*.json"))


def test_latest_snapshot_can_be_loaded(tmp_path: Path):
    project = make_project(tmp_path)
    service = SystemHealthService(project)
    service.run_scan()

    latest = service.load_latest_snapshot()

    assert latest is not None
    assert latest["project_root"] == str(project.resolve())


def test_capability_map_is_generated(tmp_path: Path):
    project = make_project(tmp_path)
    service = SystemHealthService(project)
    summary = service.run_scan()

    assert summary.capability_map.can_scan_files is True
    assert summary.capability_map.has_router_layer is True
    assert summary.capability_map.has_service_layer is True
    assert summary.capability_map.has_persona_files is True
    assert summary.capability_map.has_memory_files is True
    assert summary.capability_map.has_config_files is True
    assert summary.capability_map.has_tests is True


def test_missing_expected_files_produce_issues(tmp_path: Path):
    project = tmp_path
    write(project / "core_system_files" / "system_services" / "python_backend" / "app" / "services" / "only_service.py")
    result = SystemIntrospectionService(project).scan(config=scan_config(project), save_report=False)
    snapshot = SystemManifestService(project).build_snapshot(result)

    codes = {issue.code for issue in snapshot.issues}

    assert "missing_expected_path" in codes


def test_fastapi_routes_respond_successfully():
    test_app = FastAPI()
    test_app.include_router(system_perception_router)
    client = TestClient(test_app)

    scan_response = client.get("/system-core/perception/scan")
    latest_response = client.get("/system-core/perception/latest")
    capabilities_response = client.get("/system-core/perception/capabilities")
    issues_response = client.get("/system-core/perception/issues")
    summary_response = client.get("/system-core/perception/summary")
    changes_response = client.get("/system-core/perception/changes")
    changes_summary_response = client.get("/system-core/perception/changes/summary")

    assert scan_response.status_code == 200
    assert latest_response.status_code == 200
    assert capabilities_response.status_code == 200
    assert issues_response.status_code == 200
    assert summary_response.status_code == 200
    assert changes_response.status_code == 200
    assert changes_summary_response.status_code == 200
