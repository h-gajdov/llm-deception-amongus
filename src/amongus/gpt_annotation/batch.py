from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from ..logging import get_logger

logger = get_logger()

MODEL_ENV_VAR = "OPENAI_ANNOTATION_MODEL"
DEFAULT_MODEL = "gpt-4o-mini"
API_KEY_ENV = "OPENAI_API_KEY"
BATCH_ENDPOINT = "/v1/chat/completions"
COMPLETION_WINDOW = "24h"
DEFAULT_MAX_OUTPUT_TOKENS = 4096


DEFAULT_BATCH_SIZE = 300


TERMINAL_STATUSES = frozenset({"completed", "failed", "expired", "cancelled"})


class AnnotationClientError(RuntimeError):
    pass


def resolve_model(explicit: str | None) -> str:
    if explicit:
        return explicit
    return os.environ.get(MODEL_ENV_VAR) or DEFAULT_MODEL


def get_client() -> Any:
    try:
        import openai
    except ImportError as exc:
        msg = (
            "The 'openai' package is required for GPT annotation "
            "(install with `uv sync --extra annotate` or `pip install openai`)."
        )
        raise AnnotationClientError(msg) from exc
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        msg = f"GPT annotation requires the {API_KEY_ENV} environment variable to be set."
        raise AnnotationClientError(msg)
    return openai.OpenAI(api_key=api_key)


def build_batch_request(
    custom_id: str,
    system_prompt: str,
    user_message: str,
    model: str,
    response_format: dict[str, object],
    max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
) -> dict[str, object]:
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": BATCH_ENDPOINT,
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "response_format": response_format,
            "temperature": 0,
            "max_tokens": max_tokens,
        },
    }


def write_batch_input(path: Path, requests: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for request in requests:
            handle.write(json.dumps(request, ensure_ascii=False))
            handle.write("\n")


def submit_batch(client: Any, input_path: Path) -> Any:
    with input_path.open("rb") as handle:
        uploaded = client.files.create(file=handle, purpose="batch")
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint=BATCH_ENDPOINT,
        completion_window=COMPLETION_WINDOW,
    )
    logger.info("Submitted batch {} from {}", batch.id, input_path)
    return batch


def retrieve_batch(client: Any, batch_id: str) -> Any:
    return client.batches.retrieve(batch_id)


def describe_batch_errors(batch: Any) -> str:
    errors = getattr(batch, "errors", None)
    data = getattr(errors, "data", None) if errors else None
    if not data:
        return f"Batch {batch.id} ended with status '{batch.status}' (no error detail available)."
    codes = sorted({getattr(e, "code", None) or "unknown" for e in data})
    first = data[0]
    first_message = getattr(first, "message", None) or str(first)
    return (
        f"Batch {batch.id} ended with status '{batch.status}': {len(data)} error(s), "
        f"codes={codes}. First: {first_message}"
    )


def request_counts_dict(batch: Any) -> dict[str, int] | None:
    counts = getattr(batch, "request_counts", None)
    if counts is None:
        return None
    return {
        "completed": getattr(counts, "completed", 0),
        "failed": getattr(counts, "failed", 0),
        "total": getattr(counts, "total", 0),
    }


def submit_and_maybe_wait(
    client: Any,
    input_path: Path,
    *,
    wait: bool,
    poll_interval_s: float,
    poll_timeout_s: float | None,
    checkpoint: Callable[[Any], None],
) -> Any:
    batch = submit_batch(client, input_path)
    if wait:
        checkpoint(batch)
        batch = poll_batch(
            client, batch.id, poll_interval_s=poll_interval_s, timeout_s=poll_timeout_s
        )
    return batch


def poll_batch(
    client: Any, batch_id: str, *, poll_interval_s: float, timeout_s: float | None = None
) -> Any:
    start = time.monotonic()
    while True:
        batch = retrieve_batch(client, batch_id)
        if batch.status in TERMINAL_STATUSES:
            return batch
        if timeout_s is not None and time.monotonic() - start >= timeout_s:
            return batch
        counts = getattr(batch, "request_counts", None)
        logger.info(
            "Batch {} status={} ({}/{} completed) -- waiting {:.0f}s",
            batch_id,
            batch.status,
            getattr(counts, "completed", "?"),
            getattr(counts, "total", "?"),
            poll_interval_s,
        )
        time.sleep(poll_interval_s)


def iter_batch_result_lines(client: Any, batch: Any) -> Iterator[dict[str, object]]:
    for file_id in (getattr(batch, "output_file_id", None), getattr(batch, "error_file_id", None)):
        if not file_id:
            continue
        content = client.files.content(file_id).text
        for line in content.splitlines():
            stripped = line.strip()
            if stripped:
                yield json.loads(stripped)


__all__ = [
    "API_KEY_ENV",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_MODEL",
    "MODEL_ENV_VAR",
    "TERMINAL_STATUSES",
    "AnnotationClientError",
    "build_batch_request",
    "describe_batch_errors",
    "get_client",
    "iter_batch_result_lines",
    "poll_batch",
    "request_counts_dict",
    "resolve_model",
    "retrieve_batch",
    "submit_and_maybe_wait",
    "submit_batch",
    "write_batch_input",
]
