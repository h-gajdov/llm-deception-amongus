from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Pooling = Literal["last", "mean", "last_n"]


class QuantizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    load_in_4bit: bool = False
    load_in_8bit: bool = False
    bnb_4bit_quant_type: Literal["nf4", "fp4"] = "nf4"
    bnb_4bit_use_double_quant: bool = True
    bnb_4bit_compute_dtype: str = "float16"

    @property
    def enabled(self) -> bool:
        return self.load_in_4bit or self.load_in_8bit


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    device: str = "auto"
    dtype: str = "auto"
    quantization: QuantizationConfig = Field(default_factory=QuantizationConfig)


class ProbeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    epochs: int = Field(default=150, ge=1)
    lr: float = Field(default=1e-3, gt=0.0)
    weight_decay: float = Field(default=1e-3, ge=0.0)
    batch_size: int = Field(default=64, ge=1)
    standardize: bool = True
    log_every: int = Field(default=10, ge=1)


class WandbConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    project: str = "amongus-probes"
    entity: str | None = None
    run_name: str | None = None
    mode: Literal["online", "offline", "disabled"] = "online"


class MlflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    tracking_uri: str | None = None
    experiment: str = "amongus-probes"
    run_name: str | None = None


class TrackingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wandb: WandbConfig = Field(default_factory=WandbConfig)
    mlflow: MlflowConfig = Field(default_factory=MlflowConfig)


class ProbeTrainConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_dir: Path = Path("data/processed/contrastive")
    output_dir: Path = Path("data/probes")

    model: ModelConfig = Field(default_factory=ModelConfig)

    layers: list[int] | None = None

    pooling: Pooling = "last"
    pooling_tokens: int = Field(default=20, ge=1)
    max_length: int = 512
    extraction_batch_size: int = Field(default=16, ge=1)
    use_chat_template: bool = True

    probe: ProbeConfig = Field(default_factory=ProbeConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)

    debug_tokens: int = Field(default=0, ge=0)

    limit: int | None = Field(default=None, ge=1)
    seed: int = 0

    @property
    def tokens_per_example(self) -> int:
        return self.pooling_tokens if self.pooling == "last_n" else 1

    @model_validator(mode="after")
    def _check_pooling_tokens(self) -> ProbeTrainConfig:
        if self.pooling != "last_n" and "pooling_tokens" in self.model_fields_set:
            msg = f"pooling_tokens only applies to pooling='last_n' (got {self.pooling!r})."
            raise ValueError(msg)
        return self


__all__ = [
    "MlflowConfig",
    "ModelConfig",
    "Pooling",
    "ProbeConfig",
    "ProbeTrainConfig",
    "QuantizationConfig",
    "TrackingConfig",
    "WandbConfig",
]
