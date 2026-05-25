from __future__ import annotations

import html
import os
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests
from dotenv import load_dotenv


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        class_name = attrs_dict.get("class", "")

        if tag == "a" and "result__a" in class_name:
            self._current = {"title": "", "url": self._clean_url(attrs_dict.get("href", "")), "snippet": ""}
            self._capture_title = True
            return

        if self._current is not None and tag in {"a", "div"} and "result__snippet" in class_name:
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            self._capture_title = False
            return

        if self._capture_snippet and tag in {"a", "div"}:
            self._capture_snippet = False
            if self._current and self._current.get("title") and self._current.get("url"):
                self.results.append(self._current)
                self._current = None

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return

        text = html.unescape(data).strip()
        if not text:
            return

        if self._capture_title:
            self._current["title"] = f"{self._current['title']} {text}".strip()
        elif self._capture_snippet:
            self._current["snippet"] = f"{self._current['snippet']} {text}".strip()

    def _clean_url(self, url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.path == "/l/":
            uddg = parse_qs(parsed.query).get("uddg", [""])[0]
            if uddg:
                return unquote(uddg)
        return url


class WebSearchService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        load_dotenv(project_root / ".env")
        self.enabled = os.getenv("VAILA_WEB_SEARCH_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        self.timeout_seconds = int(os.getenv("VAILA_WEB_SEARCH_TIMEOUT_SECONDS", "10"))
        self.max_results = int(os.getenv("VAILA_WEB_SEARCH_MAX_RESULTS", "5"))
        self.search_url = os.getenv("VAILA_WEB_SEARCH_URL", "https://duckduckgo.com/html/").strip()

    def should_search(self, text: str, route: dict[str, Any] | None = None) -> bool:
        if not self.enabled:
            return False

        if route and route.get("task_type") in {"assistant_tool", "assistant_tool_candidate"}:
            tool_intent = route.get("tool_intent", {})
            return isinstance(tool_intent, dict) and tool_intent.get("tool_id") == "web_research"

        normalized = self._normalize(text)
        triggers = [
            "latest",
            "current",
            "recent",
            "today",
            "news",
            "source",
            "sources",
            "citation",
            "citations",
            "look up",
            "search the web",
            "research",
            "find official docs",
            "verify",
            "up to date",
        ]
        return any(trigger in normalized for trigger in triggers)

    def search(self, query: str, limit: int | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "status": "disabled", "query": query, "results": [], "error": "web_search_disabled"}

        max_results = limit or self.max_results
        params = {"q": query}
        headers = {
            "User-Agent": "VailaOS/0.1 local assistant research",
        }

        try:
            response = requests.get(self.search_url, params=params, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            return {
                "ok": False,
                "status": "unavailable",
                "query": query,
                "results": [],
                "error": str(exc),
            }

        parser = _DuckDuckGoHTMLParser()
        parser.feed(response.text)

        results = [
            WebSearchResult(
                title=self._clean_text(item.get("title", "")),
                url=item.get("url", ""),
                snippet=self._clean_text(item.get("snippet", "")),
            )
            for item in parser.results
            if item.get("title") and item.get("url")
        ][:max_results]

        return {
            "ok": True,
            "status": "completed",
            "query": query,
            "results": [result.to_dict() for result in results],
            "summary": self.format_results(query=query, results=results),
        }

    def format_results(self, query: str, results: list[WebSearchResult] | list[dict[str, str]]) -> str:
        if not results:
            return f"Web search completed for `{query}`, but returned no usable results."

        lines = [f"Web search results for `{query}`:"]
        for index, result in enumerate(results, start=1):
            if isinstance(result, WebSearchResult):
                item = result.to_dict()
            else:
                item = result
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            snippet = item.get("snippet", "").strip()
            lines.append(f"{index}. {title}\n   URL: {url}\n   Snippet: {snippet}")
        return "\n".join(lines)

    def _normalize(self, text: str) -> str:
        lowered = text.lower().strip()
        lowered = re.sub(r"[^\w\s]", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    def _clean_text(self, text: str) -> str:
        cleaned = html.unescape(text)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()
