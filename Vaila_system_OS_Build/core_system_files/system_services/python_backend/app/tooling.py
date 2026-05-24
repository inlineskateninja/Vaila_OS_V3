from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.activity_log import utc_now
from app.document_importer import SUPPORTED_EXTENSIONS


@dataclass
class ToolSpec:
    name: str
    description: str
    inputs: dict[str, str] = field(default_factory=dict)
    approval_required: bool = False
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    source: str = "chat"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResultRecord:
    id: str
    tool_name: str
    created_at: str
    arguments: dict[str, Any]
    ok: bool
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @classmethod
    def create(
        cls,
        tool_name: str,
        arguments: dict[str, Any],
        ok: bool,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> "ToolResultRecord":
        created_at = utc_now()
        raw = json.dumps(
            {
                "created_at": created_at,
                "tool_name": tool_name,
                "arguments": arguments,
                "ok": ok,
                "error": error,
            },
            sort_keys=True,
            default=str,
        )
        return cls(
            id=f"tool_result_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:18]}",
            tool_name=tool_name,
            created_at=created_at,
            arguments=arguments,
            ok=ok,
            result=result or {},
            error=error,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolResultRecord":
        return cls(
            id=data.get("id", ""),
            tool_name=data.get("tool_name", ""),
            created_at=data.get("created_at", ""),
            arguments=data.get("arguments", {}),
            ok=bool(data.get("ok", False)),
            result=data.get("result", {}),
            error=data.get("error", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolResultStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.records: list[ToolResultRecord] = []

    def load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records.clear()
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.records.append(ToolResultRecord.from_dict(json.loads(line)))
                except json.JSONDecodeError:
                    continue

    def append(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        ok: bool,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> ToolResultRecord:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = ToolResultRecord.create(
            tool_name=tool_name,
            arguments=arguments,
            ok=ok,
            result=result or {},
            error=error,
        )
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        self.records.append(record)
        return record

    def latest(self, tool_name: str | None = None) -> ToolResultRecord | None:
        for record in reversed(self.records):
            if tool_name is None or record.tool_name == tool_name:
                return record
        return None


def phase2_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="file_analyze",
            description="Read-only analysis of supported local files without creating memory candidates.",
            inputs={"path": "Path to a supported file."},
            approval_required=False,
            read_only=True,
        ),
        ToolSpec(
            name="document_import",
            description="Import a supported file into the memory-candidate approval queue.",
            inputs={"path": "Path to a supported file.", "tags": "Optional tags.", "persona_scope": "Optional persona scope."},
            approval_required=True,
            read_only=False,
        ),
        ToolSpec(
            name="memory_search",
            description="Search approved local memory records with recency-aware scoring.",
            inputs={"query": "Search phrase.", "persona": "Persona scope.", "tags": "Optional tags."},
            approval_required=False,
            read_only=True,
        ),
        ToolSpec(
            name="memory_delete_proposal",
            description="Produce a safe proposal for matching memories without deleting anything.",
            inputs={"topic": "Topic to find matching memories."},
            approval_required=True,
            read_only=True,
        ),
        ToolSpec(
            name="project_review",
            description="Generate a deterministic Phase 2 project status review.",
            inputs={"limit": "Recent activity count."},
            approval_required=False,
            read_only=True,
        ),
    ]


def detect_chat_tool_call(user_text: str) -> ToolCall | None:
    text = user_text.strip()
    normalized = re.sub(r"\s+", " ", text.lower())

    if _mentions_recent_file_analysis(normalized):
        if any(word in normalized for word in ["reanalyze", "re-analyze", "again", "rerun", "run it"]):
            return ToolCall("file_analyze", {"use_recent": True})
        return ToolCall("file_analysis_recent", {})

    if _mentions_file_analysis(normalized):
        path = _extract_supported_path(text)
        if path:
            return ToolCall("file_analyze", {"path": path})
        return ToolCall("file_analyze", {"missing_path": True})

    return None


def _mentions_file_analysis(normalized: str) -> bool:
    file_words = ["file", "document", "readme", ".md", ".txt", ".json", ".yaml", ".yml", ".py", ".log"]
    analysis_words = ["analyze", "analyse", "inspect", "review", "scan", "summarize", "summarise"]
    tool_words = ["file analyzer", "file analysis", "analysis tool"]
    return (
        any(word in normalized for word in analysis_words)
        and any(word in normalized for word in file_words)
    ) or any(word in normalized for word in tool_words)


def _mentions_recent_file_analysis(normalized: str) -> bool:
    recent_words = ["last", "recent", "recently", "previous", "previously", "just"]
    analysis_words = ["analyzed", "analysed", "analysis", "file analyzer", "file analysis"]
    return any(word in normalized for word in recent_words) and any(word in normalized for word in analysis_words)


def _extract_supported_path(text: str) -> str | None:
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", text)
    unquoted = re.findall(r"(?<!\w)([^\s,;:]+?\.(?:md|txt|json|ya?ml|py|log))\b", text, flags=re.IGNORECASE)
    candidates = [*quoted, *unquoted]

    for candidate in candidates:
        cleaned = candidate.strip().strip(".,;:")
        suffix = Path(cleaned).suffix.lower()
        if suffix in SUPPORTED_EXTENSIONS:
            return cleaned
    return None
