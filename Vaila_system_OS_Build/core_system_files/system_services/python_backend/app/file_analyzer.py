from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.document_importer import KEY_SIGNAL_WORDS, SUPPORTED_EXTENSIONS, normalize_space


@dataclass
class FileAnalysis:
    path: str
    title: str
    file_type: str
    sha256: str
    size_bytes: int
    char_count: int
    line_count: int
    word_count: int
    summary: str
    headings: list[str] = field(default_factory=list)
    key_lines: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    structural_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FileAnalyzer:
    """Read-only file analysis for Phase 2 tools.

    This intentionally does not create memory candidates. Import remains the
    explicit memory-writing path; analysis is for inspection and review.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def analyze(self, path: str | Path) -> FileAnalysis:
        source_path = Path(path).expanduser()
        if not source_path.is_absolute():
            source_path = (self.project_root / source_path).resolve()

        if not source_path.exists():
            raise FileNotFoundError(f"File not found: {source_path}")
        if not source_path.is_file():
            raise ValueError(f"Path is not a file: {source_path}")

        file_type = source_path.suffix.lower()
        if file_type not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {file_type}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        raw = source_path.read_text(encoding="utf-8", errors="replace")
        normalized = raw.replace("\r\n", "\n")
        warnings: list[str] = []
        structural_notes = self._structural_notes(source_path, file_type, normalized, warnings)

        return FileAnalysis(
            path=self._display_path(source_path),
            title=source_path.name,
            file_type=file_type,
            sha256=hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest(),
            size_bytes=source_path.stat().st_size,
            char_count=len(normalized),
            line_count=len(normalized.splitlines()),
            word_count=len(re.findall(r"\b[\w'-]+\b", normalized)),
            summary=self._summarize(normalized),
            headings=self._headings(normalized, file_type),
            key_lines=self._key_lines(normalized),
            action_items=self._action_items(normalized),
            structural_notes=structural_notes,
            warnings=warnings,
        )

    def _summarize(self, text: str, max_sentences: int = 5, max_chars: int = 1000) -> str:
        cleaned = normalize_space(text)
        if len(cleaned) <= max_chars:
            return cleaned

        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        selected: list[str] = []
        char_count = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if char_count + len(sentence) > max_chars:
                break
            selected.append(sentence)
            char_count += len(sentence)
            if len(selected) >= max_sentences:
                break
        if selected:
            return " ".join(selected)
        return cleaned[:max_chars].rsplit(" ", 1)[0].strip()

    def _headings(self, text: str, file_type: str) -> list[str]:
        if file_type == ".py":
            headings = []
            try:
                tree = ast.parse(text)
            except SyntaxError:
                return []
            for node in tree.body:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    headings.append(node.name)
            return headings[:20]

        headings = []
        for line in text.splitlines():
            match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
            if match:
                headings.append(match.group(1).strip())
        return headings[:20]

    def _key_lines(self, text: str) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()
        for raw_line in text.splitlines():
            line = normalize_space(raw_line.strip(" -\t"))
            if len(line) < 20 or len(line) > 260:
                continue
            lower = line.lower()
            if any(word in lower for word in KEY_SIGNAL_WORDS):
                if line not in seen:
                    lines.append(line)
                    seen.add(line)
            if len(lines) >= 15:
                break
        return lines

    def _action_items(self, text: str) -> list[str]:
        items: list[str] = []
        patterns = ("todo", "fixme", "next step", "next steps", "follow up", "action item")
        for raw_line in text.splitlines():
            line = normalize_space(raw_line.strip(" -\t"))
            if len(line) < 5 or len(line) > 240:
                continue
            if any(pattern in line.lower() for pattern in patterns):
                items.append(line)
            if len(items) >= 12:
                break
        return items

    def _structural_notes(
        self,
        path: Path,
        file_type: str,
        text: str,
        warnings: list[str],
    ) -> list[str]:
        if file_type == ".py":
            return self._python_notes(text, warnings)
        if file_type == ".json":
            return self._json_notes(text, warnings)
        if file_type in {".yaml", ".yml"}:
            return ["YAML file detected. Parsed validation is not enabled yet; analysis is text-based."]
        if file_type == ".log":
            return self._log_notes(text)
        return self._text_notes(path, text)

    def _python_notes(self, text: str, warnings: list[str]) -> list[str]:
        try:
            tree = ast.parse(text)
        except SyntaxError as error:
            warnings.append(f"Python syntax issue: line {error.lineno}: {error.msg}")
            return ["Python file could not be parsed."]

        classes = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
        functions = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
        imports = sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
        return [
            f"Python structure: {classes} class(es), {functions} function(s), {imports} import statement(s)."
        ]

    def _json_notes(self, text: str, warnings: list[str]) -> list[str]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            warnings.append(f"JSON parse issue: line {error.lineno}: {error.msg}")
            return ["JSON file could not be parsed; analysis is text-based."]
        if isinstance(parsed, dict):
            return [f"JSON object with {len(parsed)} top-level key(s): {', '.join(list(parsed.keys())[:12])}"]
        if isinstance(parsed, list):
            return [f"JSON array with {len(parsed)} item(s)."]
        return [f"JSON scalar value: {type(parsed).__name__}."]

    def _log_notes(self, text: str) -> list[str]:
        error_count = len(re.findall(r"\b(error|exception|traceback|failed)\b", text, flags=re.IGNORECASE))
        warning_count = len(re.findall(r"\b(warn|warning)\b", text, flags=re.IGNORECASE))
        return [f"Log signals: {error_count} error-like term(s), {warning_count} warning-like term(s)."]

    def _text_notes(self, path: Path, text: str) -> list[str]:
        paragraph_count = len([block for block in re.split(r"\n\s*\n", text) if block.strip()])
        return [f"Text structure: {paragraph_count} paragraph/block(s) in {path.name}."]

    def _display_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.project_root))
        except ValueError:
            return str(path)
