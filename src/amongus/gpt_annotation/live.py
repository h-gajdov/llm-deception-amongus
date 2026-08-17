from __future__ import annotations

import json
import time
from typing import Any

from ..logging import get_logger

logger = get_logger()


RATE_LIMIT_INITIAL_BACKOFF_S = 5.0
RATE_LIMIT_MAX_BACKOFF_S = 60.0


TRANSIENT_MAX_RETRIES = 5
TRANSIENT_MAX_BACKOFF_S = 60.0


def call_live(
    client: Any,
    *,
    model: str,
    system_prompt: str,
    user_message: str,
    response_format: dict[str, object],
    max_tokens: int,
) -> tuple[dict[str, Any] | None, str | None, str | None, dict[str, Any] | None]:
    import openai

    rate_limit_backoff = RATE_LIMIT_INITIAL_BACKOFF_S
    transient_attempts = 0
    while True:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format=response_format,
                temperature=0,
                max_tokens=max_tokens,
            )
        except openai.RateLimitError as exc:
            wait_s = _retry_after_seconds(exc) or rate_limit_backoff
            logger.info(
                "Rate limited -- waiting {:.0f}s before retrying (limit is expected to clear).",
                wait_s,
            )
            time.sleep(wait_s)
            rate_limit_backoff = min(rate_limit_backoff * 2, RATE_LIMIT_MAX_BACKOFF_S)
            continue
        except (openai.APIConnectionError, openai.InternalServerError) as exc:
            transient_attempts += 1
            if transient_attempts > TRANSIENT_MAX_RETRIES:
                msg = f"{type(exc).__name__} after {TRANSIENT_MAX_RETRIES} retries: {exc}"
                return None, "api_error", msg, None
            wait_s = min(2.0**transient_attempts, TRANSIENT_MAX_BACKOFF_S)
            logger.warning(
                "Transient API error ({}); retrying in {:.0f}s ({}/{}).",
                exc,
                wait_s,
                transient_attempts,
                TRANSIENT_MAX_RETRIES,
            )
            time.sleep(wait_s)
            continue
        except openai.APIStatusError as exc:
            return None, "api_error", f"HTTP {exc.status_code}: {exc.message}", None
        else:
            break

    choices = response.choices
    if not choices:
        return None, "parse_error", "No choices in response.", None
    content = choices[0].message.content or ""
    meta = {
        "model": response.model,
        "usage": response.usage.model_dump() if response.usage else None,
    }
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        return None, "parse_error", f"Invalid JSON in model content: {exc}", meta
    return parsed, None, None, meta


def _retry_after_seconds(exc: Any) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


__all__ = [
    "RATE_LIMIT_INITIAL_BACKOFF_S",
    "RATE_LIMIT_MAX_BACKOFF_S",
    "TRANSIENT_MAX_RETRIES",
    "call_live",
]
