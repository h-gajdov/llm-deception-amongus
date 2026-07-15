

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from ..logging import get_logger
from .ingest import find_experiment_dirs, iter_step_logs
from .records import StepLog

logger = get_logger()

                                                                                  
DEFAULT_TEST_SIZE = 0.2


def step_log_to_row(step: StepLog) -> dict[str, Any]:
    pass
    prompt = step.interaction.prompt
    response = step.interaction.response
    action = response.get("Action", "")
    identity = step.player.identity
    return {
        "game_index": step.game_index,
        "step": step.step,
        "model": step.player.model,
        "player_name": step.player.name,
        "identity": identity,
        "is_impostor": int(identity.lower() == "impostor"),
        "phase": prompt.get("Phase", ""),
        "location": step.player.location,
        "system_prompt": step.interaction.system_prompt,
        "memory": prompt.get("Memory", ""),
        "summarization": prompt.get("Summarization", ""),
        "all_info": prompt.get("All Info", ""),
        "condensed_memory": response.get("Condensed Memory", ""),
        "thinking": response.get("Thinking Process", ""),
        "action": action,
        "full_response": step.interaction.full_response,
        "is_speak": action.strip().upper().startswith("SPEAK"),
    }


def iter_rows(experiment_dirs: Iterable[Path]) -> Iterator[dict[str, Any]]:
    pass
    for directory in experiment_dirs:
        logs = directory / "agent-logs.json"
        if not logs.exists():
            logger.warning("Skipping {}: no agent-logs.json", directory)
            continue
        logger.info("Reading steps from {}", logs)
        for step in iter_step_logs(logs):
            yield step_log_to_row(step)


def build_hf_dataset(
    input_root: str | Path,
    output_dir: str | Path,
    *,
    test_size: float = DEFAULT_TEST_SIZE,
    seed: int = 0,
    write_parquet: bool = True,
) -> Path:
    pass
    try:
        from datasets import Dataset
    except ImportError as exc:                                             
        msg = "The 'datasets' library is required to build HF datasets."
        raise ImportError(msg) from exc

    dirs = find_experiment_dirs(input_root)
    if not dirs:
        msg = f"No experiment directories (agent-logs.json) found under {input_root}"
        raise ValueError(msg)

    rows = list(iter_rows(dirs))
    if not rows:
        msg = f"No decision records found under {input_root}"
        raise ValueError(msg)
    logger.info("Collected {} rows from {} experiment dir(s).", len(rows), len(dirs))

    dataset = Dataset.from_list(rows)
    split = dataset.train_test_split(test_size=test_size, seed=seed)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    split.save_to_disk(str(output_dir))
    if write_parquet:
        split["train"].to_parquet(str(output_dir / "train.parquet"))
        split["test"].to_parquet(str(output_dir / "test.parquet"))

    logger.info(
        "Saved dataset to {} (train={}, test={}).",
        output_dir,
        split["train"].num_rows,
        split["test"].num_rows,
    )
    return output_dir


__all__ = ["DEFAULT_TEST_SIZE", "build_hf_dataset", "iter_rows", "step_log_to_row"]
