

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T", bound=BaseModel)

                                                                               
                                                                          
SCHEMA_VERSION = "2.0"

VisibilityMode = Literal["full_room", "limited", "noisy", "imperfect_identification"]

                                                                             
                                                                              
                                                                  
_VISIBILITY_PRESETS: dict[str, dict[str, Any]] = {
    "full_room": {},
                                                                                
                                                         
    "limited": {
        "movement_visible_in_destination_room": False,
        "task_witness_probability": 0.0,
        "cameras_enabled": False,
    },
                                                                  
    "noisy": {
        "kill_witness_probability": 0.8,
        "vent_witness_probability": 0.7,
        "movement_witness_probability": 0.7,
        "task_witness_probability": 0.6,
    },
                                                                    
    "imperfect_identification": {
        "kill_identification_probability": 0.5,
        "vent_identification_probability": 0.5,
        "camera_shows_identity": False,
    },
}


class VisibilityConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

    mode: VisibilityMode = "full_room"

                                                                     
    kill_witness_probability: float = Field(default=1.0, ge=0.0, le=1.0)
    vent_witness_probability: float = Field(default=1.0, ge=0.0, le=1.0)
    movement_witness_probability: float = Field(default=1.0, ge=0.0, le=1.0)
    task_witness_probability: float = Field(default=1.0, ge=0.0, le=1.0)

                                                                            
                                                                           
    kill_identification_probability: float = Field(default=1.0, ge=0.0, le=1.0)
    vent_identification_probability: float = Field(default=1.0, ge=0.0, le=1.0)

    movement_visible_in_source_room: bool = True
    movement_visible_in_destination_room: bool = True

    cameras_enabled: bool = True
                                                                                
                                                                 
    camera_rooms: list[str] = Field(
        default_factory=lambda: ["Cafeteria", "Admin", "Upper Engine", "Electrical"]
    )
    camera_shows_identity: bool = True

                                                                              
                                                                               
    ghosts_observe: bool = False

    reveal_role_on_ejection: bool = False
    reveal_votes: bool = True
                                                                               
                                                                     
    body_report_reveals_killer: bool = False

    @model_validator(mode="before")
    @classmethod
    def _apply_preset(cls, data: Any) -> Any:
        pass
        if not isinstance(data, dict):
            return data
        preset = _VISIBILITY_PRESETS.get(str(data.get("mode", "full_room")), {})
        return {**preset, **data}


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
                                                                              
                                                                               
                                                           
    initial_kill_cooldown: int = Field(default=3, ge=0)
    max_timesteps: int = Field(default=50, ge=1)

    map_name: Literal["skeld"] = "skeld"
    meeting_order: Literal["seating", "random", "reporter_first"] = "seating"
    role_assignment: Literal["random", "fixed"] = "random"
    fixed_impostor_indices: list[int] = Field(default_factory=list)
                                                                              
                                                                              
                                                       
    count_dead_crewmate_tasks: bool = False

    visibility: VisibilityConfig = Field(default_factory=VisibilityConfig)

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

    @model_validator(mode="after")
    def _check_fixed_roles(self) -> GameConfig:
        pass
        if self.role_assignment != "fixed":
            return self
        indices = self.fixed_impostor_indices
        if len(indices) != self.num_impostors:
            msg = (
                f"role_assignment='fixed' needs {self.num_impostors} "
                f"fixed_impostor_indices, got {len(indices)}."
            )
            raise ValueError(msg)
        if any(not 1 <= i <= self.num_players for i in indices):
            msg = f"fixed_impostor_indices must be 1-based indices in 1..{self.num_players}."
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


class OpenAIConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=1)
    request_timeout_s: float = Field(default=120.0, gt=0.0)
    max_retries: int = Field(default=3, ge=0)


                                                                       
                                                                               
                                                                      
BACKENDS = ("ollama", "openai", "scripted", "heuristic")


class AgentConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

    impostor_backend: str = "ollama"
    crewmate_backend: str = "ollama"
    impostor_llm_choices: list[str] = Field(default_factory=lambda: ["qwen3:8b"])
    crewmate_llm_choices: list[str] = Field(default_factory=lambda: ["qwen3:8b"])
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)

                                                                                
                                                                           
                                                                       
    prompt_template: str = "v2"
                                                                              
                                                                          
                                                          
    role_prompt_mode: Literal["separate", "inline"] = "separate"
    personality_mode: Literal["none", "sampled"] = "none"
    personalities: list[str] = Field(default_factory=list)
    impostor_strategy_prompt: str | None = None
    crewmate_strategy_prompt: str | None = None
    language_style: str | None = None
                                                                              
                                                                            
    max_parse_retries: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def _check_personalities(self) -> AgentConfig:
        pass
        if self.personality_mode == "sampled" and not self.personalities:
            msg = "personality_mode='sampled' requires a non-empty 'personalities' list."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_backends(self) -> AgentConfig:
        pass
        for backend in (self.impostor_backend, self.crewmate_backend):
            if backend not in BACKENDS:
                msg = f"Unknown backend {backend!r}; expected one of {BACKENDS}."
                raise ValueError(msg)
        return self


class GenerationConfig(BaseModel):
    pass

    model_config = ConfigDict(extra="forbid")

    experiment_name: str = "qwen3_8b_selfplay"
    num_games: int = Field(default=10, ge=1)
    seed: int = 0
    output_dir: Path = Path("expt-logs")
    log_level: str = "INFO"
    write_compact_logs: bool = True
                                                                              
                                                                               
                                                      
    write_legacy_logs: bool = True
                                                                       
    write_world_states: bool = True
                                                             
    annotate: bool = True
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
    "BACKENDS",
    "SCHEMA_VERSION",
    "AgentConfig",
    "GameConfig",
    "GenerationConfig",
    "OllamaConfig",
    "OpenAIConfig",
    "VisibilityConfig",
    "VisibilityMode",
    "load_config",
]
