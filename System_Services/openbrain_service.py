from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests
from dotenv import load_dotenv

from System_Services.connected_service_manager import env_flag


class OpenBrainService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        load_dotenv(project_root / ".env")

        self.enabled = env_flag("OPENBRAIN_ENABLED", default=False)
        self.mode = os.getenv("OPENBRAIN_MODE", "disabled").strip().lower() or "disabled"
        self.base_url = os.getenv("OPENBRAIN_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("OPENBRAIN_API_KEY", "")
        self.timeout_seconds = int(os.getenv("OPENBRAIN_TIMEOUT_SECONDS", "60"))
        self.local_store_path = self._resolve_local_store_path(os.getenv("OPENBRAIN_LOCAL_STORE_PATH", ""))

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
            "local_store_path": str(self.local_store_path) if self.mode == "local" else "",
            "timeout_seconds": self.timeout_seconds,
        }

    def write_memory_candidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        disabled = self._disabled_or_misconfigured()
        if disabled:
            return disabled

        if self.mode == "local":
            return self._write_local_candidate(payload)

        return self._post("/memory/candidates", payload)

    def search_memory(self, query: str, limit: int = 5) -> dict[str, Any]:
        disabled = self._disabled_or_misconfigured()
        if disabled:
            return disabled

        if self.mode == "local":
            return self._search_local_memory(query=query, limit=limit)

        return self._get("/memory/search", params={"query": query, "limit": limit})

    def get_recent_memories(self, limit: int = 10) -> dict[str, Any]:
        disabled = self._disabled_or_misconfigured()
        if disabled:
            return disabled

        if self.mode == "local":
            return self._recent_local_memories(limit=limit)

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

    def _resolve_local_store_path(self, configured_path: str) -> Path:
        if configured_path.strip():
            path = Path(configured_path.strip())
            return path if path.is_absolute() else self.project_root / path
        return self.project_root / "data" / "openbrain_memory_candidates.jsonl"

    def _write_local_candidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {
                "ok": False,
                "service_id": "openbrain",
                "mode": "local",
                "error": "OpenBrain local memory candidates must be dictionaries.",
            }

        record = {
            "candidate_id": f"ob_{uuid4().hex}",
            "created_at": datetime.now(UTC).isoformat(),
            "service_id": "openbrain",
            "mode": "local",
            "status": "candidate_logged",
            "payload": payload,
        }
        try:
            self.local_store_path.parent.mkdir(parents=True, exist_ok=True)
            with self.local_store_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        except OSError as exc:
            return {
                "ok": False,
                "service_id": "openbrain",
                "mode": "local",
                "error": f"Could not write OpenBrain local candidate store: {exc}",
            }

        return {
            "ok": True,
            "service_id": "openbrain",
            "mode": "local",
            "stored": True,
            "candidate_id": record["candidate_id"],
            "status": record["status"],
        }

    def _search_local_memory(self, query: str, limit: int) -> dict[str, Any]:
        query_terms = [term for term in query.lower().split() if term]
        records = self._read_local_records()
        matches = []
        for record in reversed(records):
            searchable = json.dumps(record.get("payload", {}), sort_keys=True).lower()
            if not query_terms or all(term in searchable for term in query_terms):
                matches.append(record)
            if len(matches) >= max(1, limit):
                break
        return {
            "ok": True,
            "service_id": "openbrain",
            "mode": "local",
            "query": query,
            "memories": matches,
            "count": len(matches),
        }

    def _recent_local_memories(self, limit: int) -> dict[str, Any]:
        records = list(reversed(self._read_local_records()))[: max(1, limit)]
        return {
            "ok": True,
            "service_id": "openbrain",
            "mode": "local",
            "memories": records,
            "count": len(records),
        }

    def _read_local_records(self) -> list[dict[str, Any]]:
        if not self.local_store_path.exists():
            return []

        records: list[dict[str, Any]] = []
        for line in self.local_store_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return records

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
