from pathlib import Path

from System_Services.envelope_service import EnvelopeService
from System_Services.router_service import RouterService


def test_router_detects_persona_and_task():
    envelope = EnvelopeService(Path(".")).create("Vecht, analyze the file E:\\test.txt")
    route = RouterService(Path(".")).route(envelope)

    assert route["persona"] == "vecht"
    assert route["task_type"] == "file_analysis"
    assert route["confidence"] >= 2
