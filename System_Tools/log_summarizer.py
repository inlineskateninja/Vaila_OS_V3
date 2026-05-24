from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LogSummarizer:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.log_root = project_root / "System_Logging"

    def summarize_recent_logs(self, max_files: int = 5, max_lines_per_file: int = 20) -> str:
        if not self.log_root.exists():
            return "No System_Logging folder found."

        log_files = sorted(
            self.log_root.glob("**/*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:max_files]

        if not log_files:
            return "No JSONL logs found yet."

        chunks: list[str] = []
        for path in log_files:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            recent = lines[-max_lines_per_file:]

            chunks.append(f"\n## {path.relative_to(self.project_root)}")
            chunks.append(f"Lines scanned: {len(recent)}")

            for line in recent:
                try:
                    item: dict[str, Any] = json.loads(line)
                    event_type = item.get("event_type", "unknown_event")
                    request_id = item.get("request_id", "no_request_id")
                    chunks.append(f"- {event_type} | {request_id}")
                except json.JSONDecodeError:
                    chunks.append("- malformed log line")

        return "\n".join(chunks)
