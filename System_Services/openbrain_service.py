from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from System_Services.connected_service_manager import env_flag


class OpenBrainService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        load_dotenv(project_root / ".env")

        self.enabled = env_flag("OPENBRAIN_ENABLED", default=False)
        self.mode = os.getenv("OPENBRAIN_MODE", "disabled").strip().lower() or "disabled"
        self.base_url = os.getenv("OPENBRAIN_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("OPENBRAIN_API_KEY", "")
        self.timeout_seconds = int(os.getenv("OPENBRAIN_TIMEOUT_SECONDS", "60"))

    def is_configured(self) -> bool:
        if not self.enabled:
            return False
        if self.mode == "local":
            return True
        if self.mode in {"http", "mcp"}:
            return bool(self.base_url)
        return False

    def status(self) -> dict[str, Any]:
        return {
            "service_id": "openbrain",
            "enabled": self.enabled,
            "configured": self.is_configured(),
            "mode": self.mode,
            "base_url": self.base_url,
            "api_key_configured": bool(self.api_key),
            "timeout_seconds": self.timeout_seconds,
        }

    def write_memory_candidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        disabled = self._disabled_or_misconfigured()
        if disabled:
            return disabled

        if self.mode == "local":
            return {
                "ok": True,
                "service_id": "openbrain",
                "mode": "local",
                "stored": False,
                "note": "Local placeholder mode accepted the candidate without durable storage.",
            }

        return self._post("/memory/candidates", payload)

    def search_memory(self, query: str, limit: int = 5) -> dict[str, Any]:
        disabled = self._disabled_or_misconfigured()
        if disabled:
            return disabled

        if self.mode == "local":
            return {
                "ok": True,
                "service_id": "openbrain",
                "mode": "local",
                "query": query,
                "memories": [],
                "note": "Local placeholder mode has no durable memory index.",
            }

        return self._get("/memory/search", params={"query": query, "limit": limit})

    def get_recent_memories(self, limit: int = 10) -> dict[str, Any]:
        disabled = self._disabled_or_misconfigured()
        if disabled:
            return disabled

        if self.mode == "local":
            return {
                "ok": True,
                "service_id": "openbrain",
                "mode": "local",
                "memories": [],
                "note": "Local placeholder mode has no durable memory index.",
            }

        return self._get("/memory/recent", params={"limit": limit})

    def _disabled_or_misconfigured(self) -> dict[str, Any] | None:
        if not self.enabled:
            return {
                "ok": False,
                "service_id": "openbrain",
                "enabled": False,
                "error": "OpenBrain is disabled.",
            }

        if not self.is_configured():
            return {
                "ok": False,
                "service_id": "openbrain",
                "enabled": True,
                "error": f"OpenBrain mode '{self.mode}' is not configured.",
                "status": self.status(),
            }

        return None

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(
                f"{self.base_url}{path}",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return {"ok": False, "service_id": "openbrain", "error": str(exc)}

        return {"ok": True, "service_id": "openbrain", "response": self._safe_response_body(response)}

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.get(
                f"{self.base_url}{path}",
                params=params,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return {"ok": False, "service_id": "openbrain", "error": str(exc)}

        return {"ok": True, "service_id": "openbrain", "response": self._safe_response_body(response)}

    @staticmethod
    def _safe_response_body(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:2000]
