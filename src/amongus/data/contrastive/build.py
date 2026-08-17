from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from ...logging import get_logger
from .config import ContrastiveConfig
from .repeng import build_repeng, load_statements_csv
from .schema import ContrastiveExample, Source
from .truthfulqa import build_dqa, build_tqa, load_truthfulqa_rows

logger = get_logger()


DEFAULT_TEST_SIZE = 0.2


def build_examples(config: ContrastiveConfig) -> list[ContrastiveExample]:
    rng = random.Random(config.seed)
    examples: list[ContrastiveExample] = []
    needs_tqa = Source.TQA in config.sources
    needs_dqa = Source.DQA in config.sources

    if needs_tqa or needs_dqa:
        rows = load_truthfulqa_rows(config)
        logger.info("Loaded {} TruthfulQA rows.", len(rows))
        if needs_tqa:
            examples += build_tqa(rows, rng, config.max_incorrect_per_question)
        if needs_dqa:
            examples += build_dqa(
                rows,
                rng,
                config.honest_system,
                config.dishonest_system,
                config.max_incorrect_per_question,
            )

    if Source.REPENG in config.sources:
        examples += _build_repeng_source(config)

    if not examples:
        msg = "No contrastive examples were produced; check sources/config."
        raise ValueError(msg)
    _log_composition(examples)
    return examples


def _build_repeng_source(config: ContrastiveConfig) -> list[ContrastiveExample]:
    if config.repeng_statements_path is None:
        msg = (
            "RepEng requested but 'repeng_statements_path' is not set. Provide a "
            "CSV of true/false statements (e.g. RepEng's facts_true_false.csv)."
        )
        raise ValueError(msg)
    statements = load_statements_csv(
        config.repeng_statements_path,
        config.repeng_statement_column,
        config.repeng_label_column,
    )
    return build_repeng(statements, config.repeng_honest_system, config.repeng_untruthful_system)


def build_contrastive_dataset(config: ContrastiveConfig) -> Path:
    try:
        from datasets import Dataset
    except ImportError as exc:
        msg = "The 'datasets' library is required to build contrastive datasets."
        raise ImportError(msg) from exc

    examples = build_examples(config)
    dataset = Dataset.from_list([e.to_row() for e in examples])
    split = dataset.train_test_split(test_size=config.test_size, seed=config.seed)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    split.save_to_disk(str(output_dir))
    if config.write_parquet:
        split["train"].to_parquet(str(output_dir / "train.parquet"))
        split["test"].to_parquet(str(output_dir / "test.parquet"))

    logger.info(
        "Saved contrastive dataset to {} (train={}, test={}).",
        output_dir,
        split["train"].num_rows,
        split["test"].num_rows,
    )
    return output_dir


def _log_composition(examples: list[ContrastiveExample]) -> None:
    by_source: Counter[str] = Counter(e.source.value for e in examples)
    by_label: Counter[str] = Counter(e.label_name for e in examples)
    logger.info("Built {} contrastive examples.", len(examples))
    logger.info("  by source: {}", dict(by_source))
    logger.info("  by label:  {}", dict(by_label))


__all__ = ["DEFAULT_TEST_SIZE", "build_contrastive_dataset", "build_examples"]
