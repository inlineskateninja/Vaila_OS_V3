from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LoggingService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.session_log_dir = project_root / "System_Logging" / "Session_Logs"
        self.error_log_dir = project_root / "System_Logging" / "Error_Logs"
        self.router_log_dir = project_root / "System_Logging" / "Router_Orchestration_Logs"

        for folder in [self.session_log_dir, self.error_log_dir, self.router_log_dir]:
            folder.mkdir(parents=True, exist_ok=True)

    def log_session_event(self, event: dict[str, Any]) -> None:
        self._submit_jsonl(self.session_log_dir / self._daily_filename("session"), event)

    def log_error(self, event: dict[str, Any]) -> None:
        self._submit_jsonl(self.error_log_dir / self._daily_filename("error"), event)

    def log_router_event(self, event: dict[str, Any]) -> None:
        self._submit_jsonl(self.router_log_dir / self._daily_filename("router"), event)

    def _submit_jsonl(self, path: Path, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("logged_utc", datetime.now(timezone.utc).isoformat())
        self.executor.submit(self._write_jsonl, path, payload)

    @staticmethod
    def _write_jsonl(path: Path, event: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    @staticmethod
    def _daily_filename(prefix: str) -> str:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"{prefix}_{date}.jsonl"

    def close(self) -> None:
        self.executor.shutdown(wait=True)
