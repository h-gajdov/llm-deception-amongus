from __future__ import annotations

import os
import time

import httpx

from ...config import OpenAIConfig
from ...logging import get_logger
from .base import LLMResponse

logger = get_logger()


class OpenAIError(RuntimeError):
    pass


class OpenAIClient:
    def __init__(self, config: OpenAIConfig) -> None:
        self.config = config
        self.model = config.model
        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            msg = (
                f"OpenAI backend requires the {config.api_key_env} environment "
                "variable to be set with your API key."
            )
            raise OpenAIError(msg)
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.request_timeout_s,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def chat(self, system: str, user: str) -> LLMResponse:
        payload = self._build_payload(system, user)
        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return self._post_chat(payload)
            except (httpx.HTTPError, OpenAIError) as exc:
                last_exc = exc
                wait = 2.0 * (attempt + 1)
                logger.warning(
                    "OpenAI chat failed (attempt {}/{}): {}. Retrying in {:.1f}s.",
                    attempt + 1,
                    self.config.max_retries + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)
        msg = f"OpenAI chat failed after {self.config.max_retries + 1} attempts: {last_exc}"
        raise OpenAIError(msg)

    def _build_payload(self, system: str, user: str) -> dict[str, object]:
        return {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "max_tokens": self.config.max_tokens,
        }

    def _post_chat(self, payload: dict[str, object]) -> LLMResponse:
        response = self._client.post("/chat/completions", json=payload)
        if response.status_code >= 400:
            raise OpenAIError(f"HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise OpenAIError(f"No choices in response: {str(data)[:200]}")
        content = choices[0].get("message", {}).get("content", "")
        return LLMResponse(content=str(content).strip())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenAIClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = ["OpenAIClient", "OpenAIError"]
