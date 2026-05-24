import requests
from typing import Any


class LLMClientError(Exception):
    pass


class LMStudioClient:
    def __init__(self, base_url: str = "http://localhost:1234/v1", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def list_models(self) -> list[str]:
        url = f"{self.base_url}/models"

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
        except requests.RequestException as error:
            raise LLMClientError(f"Could not reach LM Studio at {url}: {error}") from error

        data = response.json()
        models = data.get("data", [])

        return [model.get("id", "") for model in models if model.get("id")]

    def chat(
            self,
            model: str,
            messages: list[dict[str, str]],
            temperature: float = 0.7,
            max_tokens: int = 1200,
            stream: bool = False,
            timeout: int | None = None,
            extra: dict[str, Any] | None = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        if extra:
            payload.update(extra)

        request_timeout = timeout or self.timeout

        try:
            response = requests.post(url, json=payload, timeout=request_timeout)
            response.raise_for_status()
        except requests.RequestException as error:
            response_body = ""

            if error.response is not None:
                response_body = error.response.text

            raise LLMClientError(
                "LM Studio chat request failed.\n"
                f"URL: {url}\n"
                f"Model: {model}\n"
                f"Timeout: {request_timeout}\n"
                f"Status/Error: {error}\n"
                f"Response body: {response_body}"
            ) from error

        data = response.json()
        return self._extract_chat_text(data)

    def _extract_chat_text(self, data: dict[str, Any]) -> str:
        choices = data.get("choices", [])

        if not choices:
            raise LLMClientError(f"LM Studio returned no choices. Raw response: {data}")

        message = choices[0].get("message", {})

        content = message.get("content")

        if isinstance(content, str) and content.strip():
            return content.strip()

        # Some reasoning models may return reasoning/internal fields separately.
        # We do not use reasoning_content as the final visible answer by default.
        reasoning_content = message.get("reasoning_content")

        if isinstance(reasoning_content, str) and reasoning_content.strip():
            raise LLMClientError(
                "Model returned reasoning content but no visible response content. "
                "Use a different model profile, increase max_tokens, or adjust the prompt."
            )

        raise LLMClientError(f"Could not extract visible text from LM Studio response: {data}")