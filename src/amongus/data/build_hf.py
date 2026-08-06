

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from ..logging import get_logger
from .ingest import find_experiment_dirs, find_v2_dirs, iter_step_logs, iter_turns
from .records import StepLog
from .schema_v2 import TurnRecordModel
from .splits import SplitAssignment, build_splits, load_splits, write_splits

logger = get_logger()

                                                                                  
DEFAULT_TEST_SIZE = 0.2

                                                                               
                                                                              
                                                                        
_BINARY_LABEL = {"truthful": 0, "deceptive": 1}


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


                                                                               
                    
                                                                               
def turn_to_row(turn: TurnRecordModel, split: str) -> dict[str, Any]:
    pass
    sections = turn.model_input.sections or {}
    status = turn.deception_status()
    speech = turn.model_output.speech or ""
    probe_text = turn.probe_text()
    role_span = turn.probe_regions.get("role_private_context")
    claims = [c for c in (turn.annotations.get("claims") or []) if isinstance(c, dict)]
    return {
        "game_id": turn.game_id,
        "turn_id": turn.turn_id,
        "step": turn.step,
        "timestep": turn.timestep,
        "phase": turn.phase,
        "split": split,
                                                                             
        "player_name": turn.actor.player_id,
        "identity": turn.actor.role,
        "is_impostor": int(turn.actor.role.lower() == "impostor"),
        "model": turn.actor.model,
        "personality": turn.actor.personality or "",
                                      
        "is_speak": bool(speech),
        "speech": speech,
        "utterance_deception_status": status,
        "utterance_truth_status": str(turn.annotations.get("utterance_truth_status", "")),
        "intent_evidence": str(turn.annotations.get("intent_evidence", "none")),
        "deception_label": _BINARY_LABEL.get(status),
        "deception_types": ",".join(
            sorted({str(c["deception_type"]) for c in claims if c.get("deception_type")})
        ),
        "num_claims": len(claims),
        "num_resolved_claims": sum(1 for c in claims if c.get("resolution") == "resolved"),
                             
        "system_prompt": turn.model_input.system_prompt,
        "user_prompt": turn.model_input.user_prompt,
        "role_private_context": str(sections.get("role_private_context", "")),
        "observation_context": "\n\n".join(
            str(sections.get(name, "")) for name in ("witnessed", "heard", "public_state")
        ),
        "memory_context": str(sections.get("memory_context", "")),
        "action_list": str(sections.get("action_list", "")),
        "generated_rationale": turn.model_output.generated_rationale,
                                                                                
                                                                        
        "generated_action": str((turn.model_output.action or {}).get("rendered", "")),
        "requested_action": str(
            (turn.model_output.requested_action or {}).get("rendered", "")
            or turn.model_output.requested_action_text
        ),
        "requested_action_valid": bool(turn.model_output.requested_action_valid),
        "execution_source": turn.model_output.execution_source,
        "fallback_reason": turn.model_output.fallback_reason or "",
        "probe_text": probe_text,
        "probe_text_no_role": _excise(probe_text, role_span),
        "probe_regions": json.dumps(turn.probe_regions),
                     
        "parse_status": turn.model_output.parse_status,
        "action_valid": bool(turn.evaluation.get("action_valid", True)),
        "validation_warnings": ",".join(
            str(w) for w in (turn.annotations.get("validation_warnings") or [])
        ),
    }


def _excise(text: str, span: list[int] | None) -> str:
    pass
    if not span or len(span) != 2:
        return text
    start, end = span
    if not 0 <= start <= end <= len(text):
        return text
    return text[:start] + text[end:]


def build_v2_dataset(
    input_root: str | Path,
    output_dir: str | Path,
    *,
    strategy: str = "random",
    seed: int = 0,
    speak_only: bool = False,
    labelled_only: bool = False,
    write_parquet: bool = True,
) -> Path:
    pass
    try:
        from datasets import Dataset, DatasetDict
    except ImportError as exc:                                             
        msg = "The 'datasets' library is required to build HF datasets."
        raise ImportError(msg) from exc

    dirs = find_v2_dirs(input_root)
    if not dirs:
        msg = f"No schema 2.0 experiment directories (turns.jsonl) found under {input_root}"
        raise ValueError(msg)

    rows: list[dict[str, Any]] = []
    assignments: dict[str, dict[str, object]] = {}
    for directory in dirs:
        assignment = _assignment_for(directory, strategy, seed)
        assignments[str(directory)] = assignment.to_dict()
        for turn in iter_turns(directory):
            split = assignment.assignment.get(turn.game_id, "train")
            row = turn_to_row(turn, split)
            if speak_only and not row["is_speak"]:
                continue
            if labelled_only and row["deception_label"] is None:
                continue
            rows.append(row)

    if not rows:
        msg = f"No rows survived filtering under {input_root}"
        raise ValueError(msg)

    by_split: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_split.setdefault(str(row["split"]), []).append(row)
    dataset = DatasetDict({name: Dataset.from_list(part) for name, part in by_split.items()})

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    dataset.save_to_disk(str(output))
    if write_parquet:
        for name, part in dataset.items():
            part.to_parquet(str(output / f"{name}.parquet"))
    (output / "split-assignments.json").write_text(
        json.dumps(assignments, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(
        "Saved schema 2.0 dataset to {} ({}).",
        output,
        {name: part.num_rows for name, part in dataset.items()},
    )
    return output


def _assignment_for(directory: Path, strategy: str, seed: int) -> SplitAssignment:
    pass
    existing = load_splits(directory)
    if existing is not None and existing.strategy == strategy and existing.seed == seed:
        return existing
    assignment = build_splits(directory, strategy=strategy, seed=seed)                          
    write_splits(directory, assignment)
    return assignment


__all__ = [
    "DEFAULT_TEST_SIZE",
    "build_hf_dataset",
    "build_v2_dataset",
    "iter_rows",
    "step_log_to_row",
    "turn_to_row",
]
