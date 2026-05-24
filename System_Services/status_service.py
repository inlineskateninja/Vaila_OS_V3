from __future__ import annotations

from datetime import datetime


class StatusService:
    def info(self, message: str) -> None:
        print(f"[{self._stamp()}] {message}")

    def route(self, route: dict) -> None:
        task = route.get("task_type", "unknown")
        persona = route.get("persona", "unknown")
        confidence = route.get("confidence", "?")
        print(f"[{self._stamp()}] Route: task={task} persona={persona} confidence={confidence}")

    @staticmethod
    def _stamp() -> str:
        return datetime.now().strftime("%H:%M:%S")
