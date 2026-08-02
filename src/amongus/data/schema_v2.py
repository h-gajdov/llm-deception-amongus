

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

                                                                     
TURNS_FILE = "turns.jsonl"
WORLD_STATES_FILE = "world-states.jsonl"
EVENTS_FILE = "events.jsonl"
GAMES_FILE = "games.jsonl"
METADATA_FILE = "dataset-metadata.json"


class ActorInfo(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    player_id: str
    player_index: int = 0
    role: str
    alive: bool = True
    model: str = "unknown"
    personality: str | None = None


class ModelInput(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    system_prompt: str = ""
    user_prompt: str = ""
    sections: dict[str, str] = Field(default_factory=dict)
    available_actions: list[str] = Field(default_factory=list)


class ModelOutput(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    raw: str = ""
    generated_rationale: str = ""
    generated_condensed_memory: str = ""
    action: dict[str, Any] = Field(default_factory=dict)
    requested_action: dict[str, Any] = Field(default_factory=dict)
    speech: str | None = None
    declared_speech: dict[str, Any] | None = None
    parse_status: str = "valid"
    attempts: list[dict[str, Any]] = Field(default_factory=list)


class TurnRecordModel(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    schema_version: str = "2.0"
    game_id: str
    turn_id: str
    step: int
    timestep: int = 0
    phase: str = ""
    timestamp: str = ""
    actor: ActorInfo
    world_state_before_ref: int = -1
    world_state_after_ref: int = -1
    private_state: dict[str, Any] = Field(default_factory=dict)
    model_input: ModelInput = Field(default_factory=ModelInput)
    model_output: ModelOutput = Field(default_factory=ModelOutput)
    annotations: dict[str, Any] = Field(default_factory=dict)
    evaluation: dict[str, Any] = Field(default_factory=dict)
    probe_regions: dict[str, list[int]] = Field(default_factory=dict)

    def is_speech(self) -> bool:
        pass
        return bool(self.model_output.speech)

    def deception_status(self) -> str:
        pass
        return str(self.annotations.get("utterance_deception_status", "not_applicable"))

    def probe_text(self) -> str:
        pass
        sep = "\n\n"
        return (
            f"{self.model_input.system_prompt}{sep}"
            f"{self.model_input.user_prompt}{sep}"
            f"{self.model_output.raw}"
        )


class GameRecord(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    schema_version: str = "2.0"
    game_id: str
    winner: int
    winner_reason: str
    seed: int | None = None
    num_turns: int = 0
    players: list[dict[str, Any]] = Field(default_factory=list)
    game_config: dict[str, Any] = Field(default_factory=dict)
    generation_config: dict[str, Any] = Field(default_factory=dict)
    split: str | None = None


__all__ = [
    "EVENTS_FILE",
    "GAMES_FILE",
    "METADATA_FILE",
    "TURNS_FILE",
    "WORLD_STATES_FILE",
    "ActorInfo",
    "GameRecord",
    "ModelInput",
    "ModelOutput",
    "TurnRecordModel",
]
