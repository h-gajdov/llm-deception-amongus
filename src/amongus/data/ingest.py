

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..logging import get_logger
from .records import GameSummary, StepLog
from .schema_v2 import GAMES_FILE, TURNS_FILE, WORLD_STATES_FILE, GameRecord, TurnRecordModel

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


def find_v2_dirs(root: str | Path) -> list[Path]:
    pass
    root = Path(root)
    return sorted({p.parent for p in root.rglob(TURNS_FILE)})


def iter_turns(experiment_dir: str | Path) -> Iterator[TurnRecordModel]:
    pass
    path = Path(experiment_dir) / TURNS_FILE
    for line in _iter_jsonl(path):
        yield TurnRecordModel.model_validate(line)


def iter_games(experiment_dir: str | Path) -> Iterator[GameRecord]:
    pass
    path = Path(experiment_dir) / GAMES_FILE
    for line in _iter_jsonl(path):
        yield GameRecord.model_validate(line)


def iter_world_states(experiment_dir: str | Path) -> Iterator[dict[str, object]]:
    pass
    yield from _iter_jsonl(Path(experiment_dir) / WORLD_STATES_FILE)


def load_any(experiment_dir: str | Path) -> tuple[str, list[TurnRecordModel]]:
    pass
    directory = Path(experiment_dir)
    if (directory / TURNS_FILE).exists():
        return "2.0", list(iter_turns(directory))
    legacy = directory / "agent-logs.json"
    if legacy.exists():
        from .migrate import migrate_step_log

        return "1.0", [migrate_step_log(step) for step in iter_step_logs(legacy)]
    msg = f"No turns.jsonl or agent-logs.json under {directory}"
    raise FileNotFoundError(msg)


def _iter_jsonl(path: Path) -> Iterator[dict[str, object]]:
    pass
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield json.loads(stripped)


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
    "find_v2_dirs",
    "iter_game_summaries",
    "iter_games",
    "iter_json_objects",
    "iter_step_logs",
    "iter_turns",
    "iter_world_states",
    "load_any",
]
