

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T", bound=BaseModel)


class GameConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

    num_players: int = Field(default=7, ge=3, le=15)
    num_impostors: int = Field(default=2, ge=1)
    num_common_tasks: int = Field(default=1, ge=0)
    num_short_tasks: int = Field(default=1, ge=0)
    num_long_tasks: int = Field(default=1, ge=0)
    discussion_rounds: int = Field(default=3, ge=1)
    max_num_buttons: int = Field(default=2, ge=0)
    kill_cooldown: int = Field(default=3, ge=0)
    max_timesteps: int = Field(default=50, ge=1)

    @model_validator(mode="after")
    def _check_impostor_ratio(self) -> GameConfig:
        pass
        if self.num_impostors * 2 >= self.num_players:
            msg = (
                f"num_impostors ({self.num_impostors}) must be < half of "
                f"num_players ({self.num_players}); impostors win at parity."
            )
            raise ValueError(msg)
        return self


class OllamaConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

    model: str = "qwen3:8b"
    host: str = "http://localhost:11434"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    num_ctx: int = Field(default=8192, ge=512)
    max_tokens: int = Field(default=1024, ge=1)
                                                                              
                                                                              
                                                                          
                                                                               
                                                                        
                                                                                
    think: bool = False
    request_timeout_s: float = Field(default=180.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0)


class AgentConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

    impostor_backend: str = "ollama"
    crewmate_backend: str = "ollama"
    impostor_llm_choices: list[str] = Field(default_factory=lambda: ["qwen3:8b"])
    crewmate_llm_choices: list[str] = Field(default_factory=lambda: ["qwen3:8b"])
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)


class GenerationConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

    experiment_name: str = "qwen3_8b_selfplay"
    num_games: int = Field(default=10, ge=1)
    seed: int = 0
    output_dir: Path = Path("expt-logs")
    log_level: str = "INFO"
    write_compact_logs: bool = True
    game: GameConfig = Field(default_factory=GameConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)

    def experiment_dirname(self) -> str:
        pass
        return f"{self.experiment_name}_{self.num_games}_games"


def load_config(path: str | Path, model: type[T] = GenerationConfig) -> T:                            
    pass
    path = Path(path)
    if not path.exists():
        msg = f"Config file not found: {path}"
        raise FileNotFoundError(msg)
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return model.model_validate(raw)


__all__ = [
    "AgentConfig",
    "GameConfig",
    "GenerationConfig",
    "OllamaConfig",
    "load_config",
]
