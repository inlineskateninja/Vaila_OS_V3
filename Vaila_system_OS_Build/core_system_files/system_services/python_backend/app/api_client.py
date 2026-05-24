from __future__ import annotations

from pathlib import Path
from typing import Any

import requests


class VailaApiError(Exception):
    """Raised when the local Vaila API is unavailable or returns an error."""


class VailaApiClient:
    """Small HTTP client for the local Vaila FastAPI service."""

    def __init__(self, base_url: str = "http://127.0.0.1:8765", timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def reload(self) -> dict[str, Any]:
        return self._request("POST", "/reload")

    def resolve_models(self) -> dict[str, Any]:
        return self._request("POST", "/models/resolve")

    def models(self) -> dict[str, Any]:
        return self._request("GET", "/models")

    def commands(self) -> dict[str, Any]:
        return self._request("GET", "/commands")

    def response_types(self) -> dict[str, Any]:
        return self._request("GET", "/response-types")

    def tools(self) -> dict[str, Any]:
        return self._request("GET", "/tools")

    def integrations(self) -> dict[str, Any]:
        return self._request("GET", "/integrations")

    def integration_health(self, name: str) -> dict[str, Any]:
        return self._request("GET", f"/integrations/{name}/health")

    def context_tools(self) -> dict[str, Any]:
        return self._request("GET", "/context-tools")

    def recent_tool_result(self, tool_name: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if tool_name:
            params["tool_name"] = tool_name
        return self._request("GET", "/tools/recent", params=params)

    def personas(self) -> dict[str, Any]:
        return self._request("GET", "/personas")

    def model_evaluation(self) -> dict[str, Any]:
        return self._request("GET", "/models/evaluation")

    def chat(
        self,
        message: str,
        include_context: bool = False,
        response_type: str = "short_text",
        persona_id: str | None = None,
        device_id: str | None = None,
        device_type: str | None = None,
        location_available: bool = False,
        location_opt_in: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/chat",
            json={
                "message": message,
                "include_context": include_context,
                "response_type": response_type,
                "persona_id": persona_id,
                "device_id": device_id,
                "device_type": device_type,
                "location_available": location_available,
                "location_opt_in": location_opt_in,
            },
        )

    def import_document(
        self,
        path: str | Path,
        tags: list[str] | None = None,
        persona_scope: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/documents/import",
            json={
                "path": str(path),
                "tags": tags or [],
                "persona_scope": persona_scope or ["all"],
            },
        )

    def analyze_file(self, path: str | Path) -> dict[str, Any]:
        return self._request(
            "POST",
            "/files/analyze",
            json={"path": str(path)},
        )

    def list_candidates(self, status: str = "pending") -> dict[str, Any]:
        return self._request("GET", "/candidates", params={"status": status})

    def get_candidate(self, candidate_id: str) -> dict[str, Any]:
        return self._request("GET", f"/candidates/{candidate_id}")

    def approve_candidate(self, candidate_id: str) -> dict[str, Any]:
        return self._request("POST", f"/candidates/{candidate_id}/approve")

    def reject_candidate(self, candidate_id: str, note: str = "") -> dict[str, Any]:
        return self._request(
            "POST",
            f"/candidates/{candidate_id}/reject",
            json={"note": note},
        )


    def recent_activity(self, limit: int = 50, event_type: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        return self._request("GET", "/activity", params=params)

    def project_review(self, limit: int = 50) -> dict[str, Any]:
        return self._request("GET", "/project/review", params={"limit": limit})

    def search_memory(
        self,
        query: str,
        persona: str = "proto_jane",
        tags: list[str] | None = None,
        limit: int = 8,
        category: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/memory/search",
            json={
                "query": query,
                "persona": persona,
                "tags": tags or [],
                "limit": limit,
                "category": category,
            },
        )

    def propose_memories_from_chat(self, limit: int = 20) -> dict[str, Any]:
        return self._request("POST", "/memory/propose-from-chat", params={"limit": limit})

    def delete_memory_proposal(self, topic: str, limit: int = 20) -> dict[str, Any]:
        return self._request("POST", "/memory/delete-proposal", json={"topic": topic, "limit": limit})

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        timeout = kwargs.pop("timeout", self.timeout)

        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as error:
            raise VailaApiError(
                f"Could not reach Vaila API at {url}. Start the service with: python -m app.run_service\n{error}"
            ) from error

        try:
            data = response.json()
        except ValueError as error:
            raise VailaApiError(
                f"Vaila API returned non-JSON response from {url}. Status: {response.status_code}. Body: {response.text}"
            ) from error

        if response.status_code >= 400:
            detail = data.get("detail", data)
            raise VailaApiError(f"Vaila API error {response.status_code} from {url}: {detail}")

        return data
