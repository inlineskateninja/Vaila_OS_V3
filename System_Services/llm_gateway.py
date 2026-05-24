from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


class LLMGatewayError(RuntimeError):
    """Raised when the local LLM gateway cannot produce usable text."""


class LLMGateway:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        load_dotenv(project_root / ".env")

        self.base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1").rstrip("/")
        self.model = os.getenv("LMSTUDIO_MODEL", "auto").strip() or "auto"
        self.timeout_seconds = int(os.getenv("LMSTUDIO_TIMEOUT_SECONDS", "120"))
        self._resolved_model: str | None = None

    def available_models(self) -> list[str]:
        url = f"{self.base_url}/models"
        response = requests.get(url, timeout=min(self.timeout_seconds, 10))
        response.raise_for_status()

        data = response.json()
        models = data.get("data", [])
        return [item.get("id", "") for item in models if item.get("id")]

    def resolve_model(self, refresh: bool = False) -> str:
        if self.model not in {"auto", "local-model"}:
            return self.model

        if self._resolved_model and not refresh:
            return self._resolved_model

        models = self.available_models()
        chat_models = [model for model in models if "embedding" not in model.lower()]
        if not chat_models:
            raise LLMGatewayError("No chat-capable models were reported by the local LLM server.")

        self._resolved_model = chat_models[0]
        return self._resolved_model

    def diagnostics(self) -> dict[str, Any]:
        try:
            models = self.available_models()
        except Exception as exc:
            return {
                "base_url": self.base_url,
                "configured_model": self.model,
                "resolved_model": self._resolved_model,
                "server_reachable": False,
                "error": str(exc),
            }

        return {
            "base_url": self.base_url,
            "configured_model": self.model,
            "resolved_model": self._resolved_model,
            "server_reachable": True,
            "available_models": models,
        }

    def execute_with_fallback(self, messages: list[dict[str, str]], temperature: float = 0.4) -> str:
        return self.chat(messages=messages, temperature=temperature)

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.4) -> str:
        url = f"{self.base_url}/chat/completions"
        model = self.resolve_model()

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text[:1000] if "response" in locals() else ""
            raise LLMGatewayError(f"LLM gateway rejected model '{model}': {exc}. {detail}") from exc
        except requests.RequestException as exc:
            raise LLMGatewayError(f"LLM gateway request failed for model '{model}': {exc}") from exc

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise LLMGatewayError(f"LLM gateway returned no choices for model '{model}'.")

        message = choices[0].get("message", {})
        content = self._extract_content(message)

        if not content:
            raise LLMGatewayError(f"LLM gateway returned empty visible content for model '{model}'.")

        return content

    def _extract_content(self, message: dict[str, Any]) -> str:
        content = message.get("content", "")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "\n".join(parts)

        return ""
