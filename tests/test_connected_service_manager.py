from pathlib import Path
from tempfile import TemporaryDirectory

from System_Services.connected_service_manager import ConnectedServiceManager


def test_connected_service_manager_reports_disabled_services(monkeypatch):
    monkeypatch.setenv("N8N_ENABLED", "false")
    monkeypatch.setenv("OPENBRAIN_ENABLED", "false")

    manager = ConnectedServiceManager(Path("."))
    statuses = manager.service_statuses()

    assert statuses["n8n"]["enabled"] is False
    assert statuses["n8n"]["required_for_boot"] is False
    assert statuses["openbrain"]["enabled"] is False
    assert statuses["openbrain"]["required_for_boot"] is False


def test_connected_service_manager_boots_without_registry(monkeypatch):
    monkeypatch.setenv("N8N_ENABLED", "false")
    monkeypatch.setenv("OPENBRAIN_ENABLED", "false")

    with TemporaryDirectory() as temp:
        manager = ConnectedServiceManager(Path(temp))
        assert manager.service_statuses() == {}
