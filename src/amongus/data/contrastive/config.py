

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .prompts import (
    DISHONEST_SYSTEM,
    HONEST_SYSTEM,
    REPENG_HONEST_SYSTEM,
    REPENG_UNTRUTHFUL_SYSTEM,
)
from .schema import Source


class ContrastiveConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

    sources: list[Source] = Field(default_factory=lambda: [Source.TQA, Source.DQA])
    output_dir: Path = Path("data/processed/contrastive")
    test_size: float = Field(default=0.2, gt=0.0, lt=1.0)
    seed: int = 0
    write_parquet: bool = True

                                                                          
    truthfulqa_name: str = "truthfulqa/truthful_qa"
    truthfulqa_config: str = "generation"
    truthfulqa_split: str = "validation"
    max_incorrect_per_question: int = Field(default=1, ge=1)

                                                                                      
    repeng_statements_path: Path | None = None
    repeng_statement_column: str = "statement"
    repeng_label_column: str = "label"

                                                                              
    honest_system: str = HONEST_SYSTEM
    dishonest_system: str = DISHONEST_SYSTEM
    repeng_honest_system: str = REPENG_HONEST_SYSTEM
    repeng_untruthful_system: str = REPENG_UNTRUTHFUL_SYSTEM


__all__ = ["ContrastiveConfig"]
