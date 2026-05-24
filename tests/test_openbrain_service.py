from pathlib import Path

from System_Services.openbrain_service import OpenBrainService


def test_openbrain_service_reports_disabled(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_ENABLED", "false")

    service = OpenBrainService(Path("."))

    assert service.is_configured() is False
    assert service.status()["enabled"] is False
    assert service.write_memory_candidate({"text": "hello"})["enabled"] is False


def test_openbrain_status_does_not_expose_secret(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_ENABLED", "true")
    monkeypatch.setenv("OPENBRAIN_MODE", "local")
    monkeypatch.setenv("OPENBRAIN_API_KEY", "openbrain-secret")

    status = OpenBrainService(Path(".")).status()

    assert status["api_key_configured"] is True
    assert "openbrain-secret" not in str(status)


def test_openbrain_local_placeholder_does_not_store_durable_memory(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_ENABLED", "true")
    monkeypatch.setenv("OPENBRAIN_MODE", "local")

    result = OpenBrainService(Path(".")).write_memory_candidate({"text": "remember this"})

    assert result["ok"] is True
    assert result["stored"] is False
    assert result["mode"] == "local"
