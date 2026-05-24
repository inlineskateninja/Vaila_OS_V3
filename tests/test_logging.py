from pathlib import Path
from tempfile import TemporaryDirectory

from System_Services.logging_service import LoggingService


def test_logging_service_writes_without_crashing():
    with TemporaryDirectory() as temp:
        logger = LoggingService(project_root=Path(temp))
        logger.log_session_event({"event_type": "test_event"})
        logger.close()
        logs = list((Path(temp) / "System_Logging" / "Session_Logs").glob("*.jsonl"))
        assert logs
