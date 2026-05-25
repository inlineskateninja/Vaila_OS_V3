from __future__ import annotations

import shutil
from pathlib import Path

from System_Services.envelope_service import EnvelopeService
from System_Services.logging_service import LoggingService
from System_Services.orchestration_service import OrchestrationService
from System_Services.router_service import RouterService


def prepared_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[1]
    root = tmp_path / "vaila"
    root.mkdir()
    shutil.copytree(source_root / "Tools_Registry", root / "Tools_Registry")
    return root


def test_router_routes_calendar_read_as_assistant_tool(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    envelope = EnvelopeService(root).create("What's on my calendar today?")
    route = RouterService(root).route(envelope)

    assert route["task_type"] == "assistant_tool"
    assert route["confidence"] == 3
    assert route["tool_intent"]["tool_id"] == "google_calendar"
    assert route["tool_intent"]["action"] == "list_events"


def test_orchestrator_calendar_not_connected_response(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    envelope = EnvelopeService(root).create("What's on my calendar today?")
    route = RouterService(root).route(envelope)
    logger = LoggingService(root)
    orchestrator = OrchestrationService(project_root=root, logger=logger)

    response = orchestrator.handle(envelope, route)
    logger.close()

    assert "tool exists and routed correctly" in response.visible_text
    assert "not connected yet" in response.visible_text
    assert response.meta["assistant_tool"]["result"]["status"] == "not_connected"


def test_orchestrator_calculator_returns_local_result(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    envelope = EnvelopeService(root).create("What is 10 plus 5?")
    route = RouterService(root).route(envelope)
    logger = LoggingService(root)
    orchestrator = OrchestrationService(project_root=root, logger=logger)

    response = orchestrator.handle(envelope, route)
    logger.close()

    assert route["task_type"] == "assistant_tool"
    assert "10 + 5 = 15" in response.visible_text
    assert response.meta["assistant_tool"]["result"]["data"]["result"] == 15


def test_router_general_chat_still_general(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    envelope = EnvelopeService(root).create("How are you feeling about the system today?")
    route = RouterService(root).route(envelope)

    assert route["task_type"] == "general_chat"
    assert route["tool_intent"] == {}


def test_router_preserves_file_analysis_route(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    envelope = EnvelopeService(root).create("Analyze the file E:\\test.txt")
    route = RouterService(root).route(envelope)

    assert route["task_type"] == "file_analysis"
    assert route["tool_intent"] == {}
