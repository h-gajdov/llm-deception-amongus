

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProbeTrainConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

                                                                                  
    dataset_dir: Path = Path("data/processed/contrastive")
    output_dir: Path = Path("data/probes")

                                                                               
                                                
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    device: str = "auto"                           
    dtype: str = "auto"                                               

                                                                                
                                                              
    layers: list[int] | None = None
    pooling: Literal["last", "mean"] = "last"
    max_length: int = 512
    batch_size: int = Field(default=16, ge=1)
    use_chat_template: bool = True

                                                
    standardize: bool = True
    reg_c: float = Field(default=1.0, gt=0.0)
    max_iter: int = Field(default=1000, ge=1)

                                                                   
    limit: int | None = Field(default=None, ge=1)
    seed: int = 0


__all__ = ["ProbeTrainConfig"]
