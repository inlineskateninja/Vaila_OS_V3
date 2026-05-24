import json
from pathlib import Path
from tempfile import TemporaryDirectory

from System_Services.envelope_service import EnvelopeService
from System_Services.logging_service import LoggingService
from System_Services.memory_service import MemoryService


class FailingOpenBrain:
    enabled = True

    def write_memory_candidate(self, payload):
        raise RuntimeError("forward failed")


def test_memory_service_logs_locally_when_openbrain_disabled(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_ENABLED", "false")

    with TemporaryDirectory() as temp:
        root = Path(temp)
        logger = LoggingService(root)
        envelope = EnvelopeService(root).create("remember this local-only memory", source="test")

        MemoryService(root, logger).capture_memory_candidate(envelope, {"task_type": "memory_task"})
        logger.close()

        logs = list((root / "System_Logging" / "Session_Logs").glob("*.jsonl"))
        assert logs
        assert "memory_candidate_detected" in logs[0].read_text(encoding="utf-8")


def test_memory_service_succeeds_if_openbrain_forwarding_fails(monkeypatch):
    monkeypatch.setenv("OPENBRAIN_ENABLED", "true")
    monkeypatch.setenv("OPENBRAIN_MODE", "local")

    with TemporaryDirectory() as temp:
        root = Path(temp)
        logger = LoggingService(root)
        envelope = EnvelopeService(root).create("remember this even if forwarding fails", source="test")
        service = MemoryService(root, logger)
        service.openbrain = FailingOpenBrain()

        service.capture_memory_candidate(envelope, {"task_type": "memory_task"})
        logger.close()

        session_logs = list((root / "System_Logging" / "Session_Logs").glob("*.jsonl"))
        error_logs = list((root / "System_Logging" / "Error_Logs").glob("*.jsonl"))

        assert session_logs
        assert "memory_candidate_detected" in session_logs[0].read_text(encoding="utf-8")
        assert error_logs

        error_event = json.loads(error_logs[0].read_text(encoding="utf-8").splitlines()[0])
        assert error_event["event_type"] == "openbrain_memory_forward_failed"
        assert "forward failed" in error_event["error"]
