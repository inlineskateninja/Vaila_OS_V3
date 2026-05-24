from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


class ConnectedServiceManager:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.registry_dir = project_root / "Connected_Services_Registry"
        load_dotenv(project_root / ".env")

    def load_registry(self) -> dict[str, dict[str, Any]]:
        services: dict[str, dict[str, Any]] = {}
        if not self.registry_dir.exists():
            return services

        for path in sorted(self.registry_dir.glob("*_registry.json")):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                services[path.stem] = {
                    "service_id": path.stem.replace("_registry", ""),
                    "registry_file": str(path),
                    "registry_error": str(exc),
                }
                continue

            service_id = item.get("service_id", path.stem.replace("_registry", ""))
            item["registry_file"] = str(path)
            services[service_id] = item

        return services

    def service_statuses(self) -> dict[str, dict[str, Any]]:
        return {
            service_id: self.service_status(service_id, registry)
            for service_id, registry in self.load_registry().items()
        }

    def service_status(
        self,
        service_id: str,
        registry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        registry = registry or self.load_registry().get(service_id, {})
        enabled_env = registry.get("enabled_env")
        enabled = env_flag(enabled_env) if enabled_env else bool(registry.get("enabled", False))

        return {
            "service_id": service_id,
            "enabled": enabled,
            "enabled_env": enabled_env,
            "adapter": registry.get("adapter"),
            "phase": registry.get("phase"),
            "required_for_boot": bool(registry.get("required_for_boot", False)),
            "status": registry.get("status", "unknown"),
            "configured": self._is_known_service_configured(service_id, enabled),
            "missing_env": self._missing_env(service_id, enabled),
            "notes": registry.get("notes", ""),
        }

    def is_enabled(self, service_id: str) -> bool:
        status = self.service_status(service_id)
        return bool(status.get("enabled"))

    def _is_known_service_configured(self, service_id: str, enabled: bool) -> bool:
        if not enabled:
            return False
        return not self._missing_env(service_id, enabled)

    def _missing_env(self, service_id: str, enabled: bool) -> list[str]:
        if not enabled:
            return []

        if service_id == "n8n":
            return [name for name in ["N8N_WEBHOOK_BASE_URL"] if not os.getenv(name, "").strip()]

        if service_id == "openbrain":
            mode = os.getenv("OPENBRAIN_MODE", "disabled").strip().lower()
            if mode in {"disabled", "local"}:
                return []
            return [name for name in ["OPENBRAIN_BASE_URL"] if not os.getenv(name, "").strip()]

        return []
