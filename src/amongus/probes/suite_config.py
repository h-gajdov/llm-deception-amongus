from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


LabelSource = Literal["auto", "grounded", "holistic", "impostor"]


class DatasetSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roots: list[Path] = Field(default_factory=lambda: [Path("expt-logs")])

    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

    max_rows: int | None = Field(default=None, ge=1)

    speak_only: bool = False


class ProbeSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[Path] = Field(default_factory=list)
    discover: list[Path] = Field(default_factory=lambda: [Path("data/probes")])

    exclude: list[str] = Field(default_factory=list)


class BaselineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seeds: int = Field(default=5, ge=1)
    seed: int = 0


class ChartConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True

    metric: Literal["auroc", "accuracy", "f1"] = "auroc"
    dpi: int = Field(default=150, ge=50)


class EvalSuiteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    probes: ProbeSelection = Field(default_factory=ProbeSelection)
    datasets: DatasetSelection = Field(default_factory=DatasetSelection)
    output_dir: Path = Path("data/probes/eval_suite")

    label_source: LabelSource = "auto"

    holistic_threshold: int = Field(default=7, ge=1, le=10)

    text_mode: Literal["response", "full"] = "response"

    apply_chat_template: bool = False

    device: str = "auto"
    batch_size: int = Field(default=16, ge=1)
    baseline: BaselineConfig = Field(default_factory=BaselineConfig)
    chart: ChartConfig = Field(default_factory=ChartConfig)

    cache_rows: bool = True

    reuse: bool = True


__all__ = [
    "BaselineConfig",
    "ChartConfig",
    "DatasetSelection",
    "EvalSuiteConfig",
    "LabelSource",
    "ProbeSelection",
]
