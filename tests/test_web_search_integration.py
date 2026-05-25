from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from System_Services.envelope_service import EnvelopeService
from System_Services.logging_service import LoggingService
from System_Services.orchestration_service import OrchestrationService
from System_Services.tool_execution_service import ToolExecutionService
from System_Services.tool_intent_service import ToolIntentService
from System_Services.web_search_service import WebSearchService


class FakeResponse:
    text = """
    <html>
      <body>
        <a class="result__a" href="https://example.com/a">Example Result</a>
        <a class="result__snippet">A useful search snippet.</a>
      </body>
    </html>
    """

    def raise_for_status(self) -> None:
        return None


class FakeLLM:
    base_url = "fake"
    model = "fake"
    _resolved_model = "fake"

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def execute_with_fallback(self, messages: list[dict[str, str]]) -> str:
        self.messages = messages
        return "Answered with web evidence."


def prepared_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[1]
    root = tmp_path / "vaila"
    root.mkdir()
    shutil.copytree(source_root / "Tools_Registry", root / "Tools_Registry")
    return root


def test_web_search_service_parses_results(monkeypatch: Any, tmp_path: Path) -> None:
    def fake_get(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse()

    monkeypatch.setattr("System_Services.web_search_service.requests.get", fake_get)
    service = WebSearchService(project_root=prepared_root(tmp_path))

    result = service.search("example query")

    assert result["ok"] is True
    assert result["results"][0]["title"] == "Example Result"
    assert result["results"][0]["url"] == "https://example.com/a"
    assert "useful search snippet" in result["summary"]


def test_web_research_tool_executes_search_with_mocked_network(monkeypatch: Any, tmp_path: Path) -> None:
    def fake_get(*args: Any, **kwargs: Any) -> FakeResponse:
        return FakeResponse()

    root = prepared_root(tmp_path)
    monkeypatch.setattr("System_Services.web_search_service.requests.get", fake_get)
    intent = ToolIntentService(root).detect_intent("Research current Vaila sources.")

    result = ToolExecutionService(root).execute_intent(intent)

    assert result.ok is True
    assert result.tool_id == "web_research"
    assert result.status == "completed"
    assert result.data["results"][0]["title"] == "Example Result"


def test_normal_chat_can_receive_web_context(monkeypatch: Any, tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    envelope = EnvelopeService(root).create("Can you verify this with current sources?")
    route = {
        "request_id": envelope.request_id,
        "persona": "proto_jane",
        "task_type": "general_chat",
        "confidence": 1,
        "reasons": ["test route"],
        "needs_prompt_interpreter": False,
        "prompt_interpreter_allowed": False,
        "tool_intent": {},
    }
    logger = LoggingService(project_root=root)
    orchestrator = OrchestrationService(project_root=root, logger=logger)
    fake_llm = FakeLLM()
    orchestrator.llm = fake_llm

    def fake_search(query: str, limit: int | None = None) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "completed",
            "query": query,
            "results": [{"title": "Current Source", "url": "https://example.com", "snippet": "Fresh context."}],
            "summary": "Web search results for `test`:\n1. Current Source\n   URL: https://example.com\n   Snippet: Fresh context.",
        }

    monkeypatch.setattr(orchestrator.web_search, "search", fake_search)

    response = orchestrator.handle(envelope, route)
    logger.close()

    assert response.visible_text == "Answered with web evidence."
    user_message = fake_llm.messages[-1]["content"]
    assert "[Web Research Evidence]" in user_message
    assert "https://example.com" in user_message
