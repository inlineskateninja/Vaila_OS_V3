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


def test_openbrain_local_mode_writes_and_reads_memory_candidates(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENBRAIN_ENABLED", "true")
    monkeypatch.setenv("OPENBRAIN_MODE", "local")
    monkeypatch.setenv("OPENBRAIN_LOCAL_STORE_PATH", str(tmp_path / "openbrain_candidates.jsonl"))

    service = OpenBrainService(Path("."))
    result = service.write_memory_candidate({"text": "remember this local fact"})
    search = service.search_memory("local fact")
    recent = service.get_recent_memories()

    assert result["ok"] is True
    assert result["stored"] is True
    assert result["mode"] == "local"
    assert search["count"] == 1
    assert search["memories"][0]["payload"]["text"] == "remember this local fact"
    assert recent["count"] == 1
