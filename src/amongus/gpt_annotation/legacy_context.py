from __future__ import annotations

from pathlib import Path
from typing import Any

from ..data.ingest import iter_json_objects
from ..data.records import StepLog


LEGACY_LOG_CANDIDATES: tuple[str, ...] = ("agent-logs-compact.json", "agent-logs.json")


def find_legacy_log(dataset_dir: Path) -> Path:
    for name in LEGACY_LOG_CANDIDATES:
        path = dataset_dir / name
        if path.exists():
            return path
    msg = (
        f"Neither {' nor '.join(LEGACY_LOG_CANDIDATES)} found under {dataset_dir}; "
        "the holistic rating mode reads v1 agent-logs."
    )
    raise FileNotFoundError(msg)


def load_legacy_rows(log_path: Path) -> list[dict[str, Any]]:
    text = log_path.read_text(encoding="utf-8")
    return list(iter_json_objects(text))


def row_id(raw: dict[str, Any], index: int) -> str:
    return f"{raw.get('game_index')}#{raw.get('step')}#{index}"


def build_row_context(raw: dict[str, Any]) -> dict[str, Any]:
    step = StepLog.model_validate(raw)
    response = step.interaction.response
    return {
        "game_id": step.game_index,
        "step": step.step,
        "timestamp": step.timestamp,
        "player_name": step.player.name,
        "role": step.player.identity,
        "personality": step.player.personality,
        "game_info": step.interaction.prompt.get("All Info", ""),
        "memory": response.get("Condensed Memory", ""),
        "action": response.get("Action", ""),
        "thought": response.get("Thinking Process", ""),
    }


__all__ = [
    "LEGACY_LOG_CANDIDATES",
    "build_row_context",
    "find_legacy_log",
    "load_legacy_rows",
    "row_id",
]
