from pathlib import Path

from System_Services.envelope_service import EnvelopeService


def test_create_envelope():
    service = EnvelopeService(project_root=Path("."))
    envelope = service.create("Hello", source="test")
    assert envelope.user_text == "Hello"
    assert envelope.source == "test"
    assert envelope.request_id.startswith("req_")
