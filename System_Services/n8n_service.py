from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

from System_Services.connected_service_manager import env_flag


class N8NService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        load_dotenv(project_root / ".env")

        self.enabled = env_flag("N8N_ENABLED", default=False)
        self.base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")
        self.webhook_base_url = os.getenv("N8N_WEBHOOK_BASE_URL", "http://localhost:5678/webhook").rstrip("/")
        self.api_key = os.getenv("N8N_API_KEY", "")
        self.webhook_secret = os.getenv("N8N_WEBHOOK_SECRET", "")
        self.timeout_seconds = int(os.getenv("N8N_TIMEOUT_SECONDS", "60"))

    def is_configured(self) -> bool:
        return self.enabled and bool(self.webhook_base_url)

    def status(self) -> dict[str, Any]:
        return {
            "service_id": "n8n",
            "enabled": self.enabled,
            "configured": self.is_configured(),
            "base_url": self.base_url,
            "webhook_base_url": self.webhook_base_url,
            "api_key_configured": bool(self.api_key),
            "webhook_secret_configured": bool(self.webhook_secret),
            "timeout_seconds": self.timeout_seconds,
            "mode": "webhook",
        }

    def call_webhook(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {
                "ok": False,
                "service_id": "n8n",
                "error": "n8n is disabled.",
                "status": self.status(),
            }

        if not self.is_configured():
            return {
                "ok": False,
                "service_id": "n8n",
                "error": "n8n is enabled but missing N8N_WEBHOOK_BASE_URL.",
                "status": self.status(),
            }

        url = self._webhook_url(path)
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return {
                "ok": False,
                "service_id": "n8n",
                "url": url,
                "error": str(exc),
            }

        return {
            "ok": True,
            "service_id": "n8n",
            "url": url,
            "status_code": response.status_code,
            "response": self._safe_response_body(response),
        }

    def call_workflow_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.call_webhook(tool_name, payload)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-N8N-API-Key"] = self.api_key
        if self.webhook_secret:
            headers["X-Vaila-Webhook-Secret"] = self.webhook_secret
        return headers

    def _webhook_url(self, path: str) -> str:
        clean_path = path.strip().lstrip("/")
        return urljoin(f"{self.webhook_base_url}/", clean_path)

    @staticmethod
    def _safe_response_body(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:2000]
