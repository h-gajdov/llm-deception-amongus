from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any, cast

from .config import ContrastiveConfig
from .schema import (
    LABEL_DISHONEST,
    LABEL_HONEST,
    LABEL_NAMES,
    Axis,
    ContrastiveExample,
    Source,
)


def _correct_answer(row: dict[str, Any]) -> str:
    best = (row.get("best_answer") or "").strip()
    if best:
        return best
    correct = row.get("correct_answers") or []
    return correct[0].strip() if correct else ""


def _sample_incorrect(row: dict[str, Any], k: int, rng: random.Random) -> list[str]:
    incorrect = [a.strip() for a in (row.get("incorrect_answers") or []) if a.strip()]
    if not incorrect:
        return []
    return rng.sample(incorrect, min(k, len(incorrect)))


def build_examples(
    rows: Iterable[dict[str, Any]],
    *,
    source: Source,
    rng: random.Random,
    max_incorrect: int = 1,
    honest_system: str = "",
    dishonest_system: str = "",
) -> list[ContrastiveExample]:
    axis = Axis.LYING if source is Source.TQA else Axis.DECEPTION
    examples: list[ContrastiveExample] = []
    for i, row in enumerate(rows):
        question = (row.get("question") or "").strip()
        correct = _correct_answer(row)
        incorrect = _sample_incorrect(row, max_incorrect, rng)
        if not question or not correct or not incorrect:
            continue
        category = row.get("category")

        examples.append(
            ContrastiveExample(
                id=f"{source.value}-{i}-honest",
                source=source,
                axis=axis,
                system_prompt=honest_system,
                question=question,
                answer=correct,
                label=LABEL_HONEST,
                label_name=LABEL_NAMES[LABEL_HONEST],
                category=category,
            )
        )
        for j, answer in enumerate(incorrect):
            examples.append(
                ContrastiveExample(
                    id=f"{source.value}-{i}-dishonest{j}",
                    source=source,
                    axis=axis,
                    system_prompt=dishonest_system,
                    question=question,
                    answer=answer,
                    label=LABEL_DISHONEST,
                    label_name=LABEL_NAMES[LABEL_DISHONEST],
                    category=category,
                )
            )
    return examples


def build_tqa(
    rows: Iterable[dict[str, Any]], rng: random.Random, max_incorrect: int = 1
) -> list[ContrastiveExample]:
    return build_examples(rows, source=Source.TQA, rng=rng, max_incorrect=max_incorrect)


def build_dqa(
    rows: Iterable[dict[str, Any]],
    rng: random.Random,
    honest_system: str,
    dishonest_system: str,
    max_incorrect: int = 1,
) -> list[ContrastiveExample]:
    return build_examples(
        rows,
        source=Source.DQA,
        rng=rng,
        max_incorrect=max_incorrect,
        honest_system=honest_system,
        dishonest_system=dishonest_system,
    )


def load_truthfulqa_rows(config: ContrastiveConfig) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        msg = "The 'datasets' library is required to load TruthfulQA."
        raise ImportError(msg) from exc

    try:
        dataset = load_dataset(
            config.truthfulqa_name, config.truthfulqa_config, split=config.truthfulqa_split
        )
    except Exception as exc:
        msg = (
            f"Failed to load TruthfulQA ('{config.truthfulqa_name}', "
            f"'{config.truthfulqa_config}', split='{config.truthfulqa_split}'). "
            "If this persists, try truthfulqa_name='truthfulqa/truthful_qa'. "
            f"Underlying error: {exc}"
        )
        raise RuntimeError(msg) from exc
    return [cast("dict[str, Any]", row) for row in dataset]


__all__ = [
    "build_dqa",
    "build_examples",
    "build_tqa",
    "load_truthfulqa_rows",
]
