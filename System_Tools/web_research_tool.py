from __future__ import annotations

from pathlib import Path
from typing import Any

from System_Services.web_search_service import WebSearchService


class WebResearchTool:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.web_search = WebSearchService(project_root=project_root)

    def health(self) -> dict[str, Any]:
        return {"ok": self.web_search.enabled, "status": "ready" if self.web_search.enabled else "disabled", "service_id": "web"}

    def supported_actions(self) -> list[str]:
        return ["search_web", "open_page", "summarize_page", "compare_sources", "extract_citations"]

    def search_web(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {
                "ok": True,
                "status": "dry_run",
                "summary": "Would search the web for additional context.",
                "data": {"query": tool_intent.normalized_text},
            }

        result = self.web_search.search(tool_intent.normalized_text)
        return {
            "ok": bool(result.get("ok")),
            "status": str(result.get("status", "unknown")),
            "summary": result.get("summary") or result.get("error") or "Web search did not return usable results.",
            "data": {
                "query": result.get("query", tool_intent.normalized_text),
                "results": result.get("results", []),
            },
            "error": result.get("error", ""),
        }

    def open_page(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def summarize_page(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def compare_sources(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def extract_citations(self, tool_intent: Any, dry_run: bool = False) -> dict[str, Any]:
        return self._not_connected(tool_intent, dry_run)

    def _not_connected(self, tool_intent: Any, dry_run: bool) -> dict[str, Any]:
        status = "dry_run" if dry_run else "not_connected"
        return {
            "ok": dry_run,
            "status": status,
            "summary": "Web research is not connected in this local execution layer yet. No network call was made.",
            "data": {"normalized_text": tool_intent.normalized_text},
        }
