from __future__ import annotations

import os
from pathlib import Path


class FileAnalyzer:
    def __init__(self, project_root: Path, max_chars: int = 30000) -> None:
        self.project_root = project_root
        self.max_chars = max_chars

    def analyze_file(self, file_path: str) -> str:
        path = Path(file_path)

        if not path.exists():
            return f"File not found: {file_path}"

        if not path.is_file():
            return f"Path is not a file: {file_path}"

        stat = path.stat()
        suffix = path.suffix.lower()

        if suffix not in {".txt", ".md", ".json", ".py", ".yaml", ".yml", ".csv", ".log"}:
            return (
                f"Unsupported file type for Phase 1 text analysis: {suffix}\n"
                f"File: {path}\n"
                f"Size: {stat.st_size} bytes"
            )

        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        words = text.split()

        preview = text[: self.max_chars]
        truncated = len(text) > self.max_chars

        return (
            f"File: {path}\n"
            f"Type: {suffix}\n"
            f"Size: {stat.st_size} bytes\n"
            f"Lines: {len(lines)}\n"
            f"Words: {len(words)}\n"
            f"Truncated: {truncated}\n\n"
            f"Content preview:\n{preview}"
        )
