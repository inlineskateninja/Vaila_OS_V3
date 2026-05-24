from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

from app.paths import find_project_root

DEFAULT_REGISTRY_PATH = (
    find_project_root(__file__)
    / "vaila_system_os"
    / "core_system_files"
    / "connected_services_registry"
    / "services.json"
)


@dataclass
class ServiceIntegration:
    name: str
    kind: str
    status: str = "planned"
    base_url_env: str = ""
    auth_header: str = ""
    auth_token_env: str = ""
    webhook_path_env: str = ""
    purpose: str = ""
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceIntegration":
        return cls(
            name=str(data.get("name", "")),
            kind=str(data.get("kind", "")),
            status=str(data.get("status", "planned")),
            base_url_env=str(data.get("base_url_env", "")),
            auth_header=str(data.get("auth_header", "")),
            auth_token_env=str(data.get("auth_token_env", "")),
            webhook_path_env=str(data.get("webhook_path_env", "")),
            purpose=str(data.get("purpose", "")),
            notes=[str(item) for item in data.get("notes", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["configured"] = bool(self.base_url())
        data["base_url"] = self.base_url()
        data["auth_configured"] = bool(self.auth_token())
        if self.webhook_path_env:
            data["webhook_path_configured"] = bool(os.getenv(self.webhook_path_env, "").strip())
        return data

    def base_url(self) -> str:
        return os.getenv(self.base_url_env, "").strip().rstrip("/") if self.base_url_env else ""

    def auth_token(self) -> str:
        return os.getenv(self.auth_token_env, "").strip() if self.auth_token_env else ""

    def headers(self) -> dict[str, str]:
        token = self.auth_token()
        if not token or not self.auth_header:
            return {}
        return {self.auth_header: token}


class ServiceIntegrationRegistry:
    def __init__(self, path: str | Path = DEFAULT_REGISTRY_PATH) -> None:
        self.path = Path(path)
        self.integrations: dict[str, ServiceIntegration] = {}

    def load(self) -> None:
        self.integrations.clear()
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for item in data.get("services", []):
            integration = ServiceIntegration.from_dict(item)
            if integration.name:
                self.integrations[integration.name] = integration

    def list(self) -> list[dict[str, Any]]:
        if not self.integrations:
            self.load()
        return [integration.to_dict() for integration in self.integrations.values()]

    def get(self, name: str) -> ServiceIntegration | None:
        if not self.integrations:
            self.load()
        return self.integrations.get(name)

    def health(self, name: str, timeout: int = 10) -> dict[str, Any]:
        integration = self.get(name)
        if integration is None:
            return {"ok": False, "name": name, "status": "unknown", "error": f"Unknown integration: {name}"}
        base_url = integration.base_url()
        if not base_url:
            return {
                "ok": False,
                "name": integration.name,
                "status": integration.status,
                "configured": False,
                "error": f"{integration.base_url_env} is not set.",
            }
        try:
            response = requests.get(base_url, headers=integration.headers(), timeout=timeout)
            return {
                "ok": response.status_code < 500,
                "name": integration.name,
                "status": integration.status,
                "configured": True,
                "status_code": response.status_code,
            }
        except requests.RequestException as error:
            return {
                "ok": False,
                "name": integration.name,
                "status": integration.status,
                "configured": True,
                "error": str(error),
            }

    def n8n_webhook_url(self, workflow_name: str = "default") -> str:
        integration = self.get("n8n")
        if integration is None:
            return ""
        base_url = integration.base_url()
        if not base_url:
            return ""
        path_env = integration.webhook_path_env or "VAILA_N8N_WEBHOOK_PATH"
        path = os.getenv(path_env, "").strip().lstrip("/")
        if not path:
            return ""
        return f"{base_url}/{path}"

    def post_n8n_webhook(self, payload: dict[str, Any], workflow_name: str = "default", timeout: int = 30) -> dict[str, Any]:
        integration = self.get("n8n")
        if integration is None:
            return {"ok": False, "error": "n8n integration is not registered."}
        url = self.n8n_webhook_url(workflow_name)
        if not url:
            return {"ok": False, "error": "n8n webhook URL is not configured."}
        try:
            response = requests.post(url, json=payload, headers=integration.headers(), timeout=timeout)
            return {
                "ok": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "response": _safe_response_body(response),
            }
        except requests.RequestException as error:
            return {"ok": False, "error": str(error)}


def _safe_response_body(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:2000]
