from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


VALID_CATEGORIES = {
    "core_entrypoint",
    "router",
    "service",
    "model_schema",
    "persona_manifest",
    "persona_policy",
    "memory_file",
    "config_file",
    "test_file",
    "documentation",
    "script",
    "unknown",
}


class SystemLLMClassificationService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1").rstrip("/")
        self.timeout_seconds = float(os.getenv("VAILA_PERCEPTION_LLM_TIMEOUT_SECONDS", "75"))
        self.batch_size = int(os.getenv("VAILA_PERCEPTION_LLM_BATCH_SIZE", "10"))
        self.model = os.getenv("VAILA_PERCEPTION_LLM_MODEL", "").strip()

    def classify_files(self, files: list[dict[str, Any]]) -> dict[str, Any]:
        if not files:
            return {"ok": True, "classifications": {}, "model": "", "error": ""}

        model = self.model or self._resolve_model()
        if not model:
            return {"ok": False, "classifications": {}, "model": "", "error": "No local LLM model is available."}

        classifications: dict[str, dict[str, Any]] = {}
        for index in range(0, len(files), self.batch_size):
            batch = files[index : index + self.batch_size]
            batch_result = self._classify_batch(model=model, batch=batch)
            if not batch_result["ok"]:
                retry_result = self._classify_individually(model=model, batch=batch)
                classifications.update(retry_result["classifications"])
                if not retry_result["ok"]:
                    return {
                        "ok": False,
                        "classifications": classifications,
                        "model": model,
                        "error": retry_result["error"],
                    }
                continue
            classifications.update(batch_result["classifications"])

        return {"ok": True, "classifications": classifications, "model": model, "error": ""}

    def _resolve_model(self) -> str:
        try:
            response = requests.get(f"{self.base_url}/models", timeout=min(self.timeout_seconds, 5))
            response.raise_for_status()
            available = [item.get("id", "") for item in response.json().get("data", []) if item.get("id")]
        except requests.RequestException:
            return ""

        candidates = self._model_candidates()
        for candidate in candidates:
            for model_id in available:
                if self._is_reasoning_or_embedding_model(model_id):
                    continue
                if model_id.lower() == candidate.lower():
                    return model_id
        for candidate in candidates:
            compact = candidate.lower().replace("-", "").replace("_", "").replace(".", "")
            for model_id in available:
                if self._is_reasoning_or_embedding_model(model_id):
                    continue
                model_compact = model_id.lower().replace("-", "").replace("_", "").replace(".", "")
                if compact and compact in model_compact:
                    return model_id
        for model_id in available:
            if not self._is_reasoning_or_embedding_model(model_id):
                return model_id
        return ""

    @staticmethod
    def _is_reasoning_or_embedding_model(model_id: str) -> bool:
        value = model_id.lower()
        blocked = ["thinking", "reasoning", "deepseek-r1", "r1-distill", "embedding", "embed"]
        return any(marker in value for marker in blocked)

    def _model_candidates(self) -> list[str]:
        profiles_path = self.project_root / "core_system_files" / "system_services" / "runtime_services" / "model_profiles.json"
        if not profiles_path.exists():
            return ["qwen3-4b", "phi-4-mini", "qwen3-8b", "gemma-3-4b"]
        try:
            data = json.loads(profiles_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ["qwen3-4b", "phi-4-mini", "qwen3-8b", "gemma-3-4b"]

        profiles = data.get("profiles", {})
        candidates: list[str] = ["qwen3-1.7b", "phi-4-mini", "gemma-3-4b", "qwen3-4b"]
        for profile_name in ["prompt_interpreter", "instruct_clean", "router_small"]:
            candidates.extend(profiles.get(profile_name, {}).get("model_candidates", []))
        return candidates or ["qwen3-4b", "phi-4-mini", "qwen3-8b", "gemma-3-4b"]

    def _classify_batch(self, model: str, batch: list[dict[str, Any]]) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You classify Vaila OS project files for operational self-modeling. "
                    "Do not think step by step. "
                    "Return strict JSON only in this shape: "
                    '{"classifications":[{"path":"same path from input","category":"one allowed category","confidence":"low|medium|high","reason":"short reason"}]}. '
                    "Do not include prose. "
                    "Allowed categories: "
                    + ", ".join(sorted(VALID_CATEGORIES))
                    + ". Use the path, filename, extension, and deterministic_category evidence. "
                    "Do not infer secrets or read file contents."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"files": batch}, ensure_ascii=True),
            },
        ]
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 2000,
            "stream": False,
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(self._extract_json_payload(content))
        except requests.HTTPError as exc:
            body = exc.response.text[:1000] if exc.response is not None else ""
            return {"ok": False, "classifications": {}, "error": f"Model {model}: {exc}. {body}"}
        except (KeyError, IndexError, TypeError, ValueError, requests.RequestException) as exc:
            return {"ok": False, "classifications": {}, "error": f"Model {model}: {exc}"}

        classifications: dict[str, dict[str, Any]] = {}
        raw_items = parsed.get("classifications", []) if isinstance(parsed, dict) else parsed
        if not isinstance(raw_items, list):
            raw_items = []

        input_paths = [item.get("path", "") for item in batch]
        for index, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", ""))
            if not path and index < len(input_paths):
                path = str(input_paths[index])
            category = str(item.get("category") or item.get("deterministic_category") or "unknown")
            if path and category in VALID_CATEGORIES:
                classifications[path] = {
                    "category": category,
                    "confidence": item.get("confidence", ""),
                    "reason": str(item.get("reason", ""))[:500],
                }
        return {"ok": True, "classifications": classifications, "error": ""}

    def _classify_individually(self, model: str, batch: list[dict[str, Any]]) -> dict[str, Any]:
        classifications: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        for item in batch:
            result = self._classify_batch(model=model, batch=[item])
            if result["ok"]:
                classifications.update(result["classifications"])
            else:
                errors.append(f"{item.get('path', '')}: {result['error']}")
        return {
            "ok": not errors,
            "classifications": classifications,
            "error": "; ".join(errors[:5]),
        }

    @staticmethod
    def _extract_json_payload(content: str) -> str:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            return text
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start : end + 1]
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            return text[start : end + 1]
        return text
