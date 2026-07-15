

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..logging import get_logger
from .records import GameSummary, StepLog

logger = get_logger()

REFERENCE_REPO_ID = "7vik/amongus"


def iter_json_objects(text: str) -> Iterator[dict[str, object]]:
    pass
    decoder = json.JSONDecoder()
    idx, length = 0, len(text)
    while idx < length:
        while idx < length and text[idx].isspace():
            idx += 1
        if idx >= length:
            break
        obj, end = decoder.raw_decode(text, idx)
        yield obj
        idx = end


def iter_step_logs(agent_logs_path: str | Path) -> Iterator[StepLog]:
    pass
    text = Path(agent_logs_path).read_text(encoding="utf-8")
    for raw in iter_json_objects(text):
        yield StepLog.model_validate(raw)


def iter_game_summaries(summary_path: str | Path) -> Iterator[tuple[str, GameSummary]]:
    pass
    for line in Path(summary_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        for game_index, value in obj.items():
            yield game_index, GameSummary.model_validate(value)


def find_experiment_dirs(root: str | Path) -> list[Path]:
    pass
    root = Path(root)
    dirs = {p.parent for p in root.rglob("agent-logs.json")}
    return sorted(dirs)


def download_reference(
    dest: str | Path,
    *,
    repo_id: str = REFERENCE_REPO_ID,
    allow_patterns: list[str] | None = None,
) -> Path:
    pass
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:                                             
        msg = "huggingface_hub is required to download the reference dataset."
        raise ImportError(msg) from exc

    logger.info("Downloading dataset '{}' -> {}", repo_id, dest)
    path = snapshot_download(
        repo_id=repo_id,
        repo_type="dataset",
        local_dir=str(dest),
        allow_patterns=allow_patterns,
    )
    return Path(path)


__all__ = [
    "REFERENCE_REPO_ID",
    "download_reference",
    "find_experiment_dirs",
    "iter_game_summaries",
    "iter_json_objects",
    "iter_step_logs",
]
