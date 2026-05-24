from pathlib import Path

from System_Services.envelope_service import EnvelopeService
from System_Services.router_service import RouterService


def test_router_detects_persona_and_task():
    envelope = EnvelopeService(Path(".")).create("Vecht, analyze the file E:\\test.txt")
    route = RouterService(Path(".")).route(envelope)

    assert route["persona"] == "vecht"
    assert route["task_type"] == "file_analysis"
    assert route["confidence"] >= 2


def test_router_uses_interface_persona_without_prompt_interpreter():
    envelope = EnvelopeService(Path(".")).create(
        "What should I focus on next?",
        source="desktop_client",
        metadata={
            "selected_persona": "serren",
            "prompt_interpreter_enabled": False,
        },
    )
    route = RouterService(Path(".")).route(envelope)

    assert route["persona"] == "serren"
    assert route["needs_prompt_interpreter"] is False
    assert route["prompt_interpreter_allowed"] is False


def test_router_allows_prompt_interpreter_for_stt_layer():
    envelope = EnvelopeService(Path(".")).create("What should I focus on next?", source="stt_voice")
    route = RouterService(Path(".")).route(envelope)

    assert route["needs_prompt_interpreter"] is True
    assert route["prompt_interpreter_allowed"] is True
