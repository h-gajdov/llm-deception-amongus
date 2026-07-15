

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ...logging import get_logger
from .schema import (
    LABEL_DISHONEST,
    LABEL_HONEST,
    LABEL_NAMES,
    Axis,
    ContrastiveExample,
    Source,
)

logger = get_logger()


def build_repeng(
    statements: Iterable[str],
    honest_system: str,
    untruthful_system: str,
) -> list[ContrastiveExample]:
    pass
    examples: list[ContrastiveExample] = []
    for i, raw in enumerate(statements):
        statement = raw.strip()
        if not statement:
            continue
        examples.append(
            ContrastiveExample(
                id=f"repeng-{i}-honest",
                source=Source.REPENG,
                axis=Axis.DECEPTION,
                system_prompt=honest_system,
                question="",
                answer=statement,
                label=LABEL_HONEST,
                label_name=LABEL_NAMES[LABEL_HONEST],
            )
        )
        examples.append(
            ContrastiveExample(
                id=f"repeng-{i}-dishonest",
                source=Source.REPENG,
                axis=Axis.DECEPTION,
                system_prompt=untruthful_system,
                question="",
                answer=statement,
                label=LABEL_DISHONEST,
                label_name=LABEL_NAMES[LABEL_DISHONEST],
            )
        )
    return examples


def load_statements_csv(
    path: str | Path,
    statement_column: str = "statement",
    label_column: str = "label",
    *,
    true_only: bool = True,
) -> list[str]:
    pass
    try:
        import pandas as pd
    except ImportError as exc:                                             
        msg = "pandas is required to read RepEng statement CSVs."
        raise ImportError(msg) from exc

    frame = pd.read_csv(path)
    if statement_column not in frame.columns:
        msg = f"Column {statement_column!r} not found in {path} (have {list(frame.columns)})"
        raise KeyError(msg)
    if true_only and label_column in frame.columns:
        frame = frame[frame[label_column] == 1]
    statements = [str(s) for s in frame[statement_column].tolist()]
    logger.info("Loaded {} statements from {}", len(statements), path)
    return statements


__all__ = ["build_repeng", "load_statements_csv"]
