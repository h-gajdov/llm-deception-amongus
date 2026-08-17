from __future__ import annotations

import time

import httpx

from ...config import OllamaConfig
from ...logging import get_logger
from .base import LLMResponse

logger = get_logger()


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config: OllamaConfig) -> None:
        self.config = config
        self.model = config.model
        self._client = httpx.Client(
            base_url=config.host.rstrip("/"),
            timeout=config.request_timeout_s,
        )

    def chat(self, system: str, user: str) -> LLMResponse:
        payload = self._build_payload(system, user)
        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return self._post_chat(payload)
            except (httpx.HTTPError, OllamaError) as exc:
                last_exc = exc
                wait = 1.5 * (attempt + 1)
                logger.warning(
                    "Ollama chat failed (attempt {}/{}): {}. Retrying in {:.1f}s.",
                    attempt + 1,
                    self.config.max_retries + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)
        msg = f"Ollama chat failed after {self.config.max_retries + 1} attempts: {last_exc}"
        raise OllamaError(msg)

    def _build_payload(self, system: str, user: str) -> dict[str, object]:
        return {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": self.config.think,
            "options": {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "num_ctx": self.config.num_ctx,
                "num_predict": self.config.max_tokens,
            },
        }

    def _post_chat(self, payload: dict[str, object]) -> LLMResponse:
        response = self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})
        return LLMResponse(
            content=str(message.get("content", "")).strip(),
            thinking=str(message.get("thinking", "") or "").strip(),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = ["OllamaClient", "OllamaError"]
