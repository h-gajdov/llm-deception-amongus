

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlayerLog(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    name: str
    identity: str
    personality: str | None = None
    model: str
    location: str


class Interaction(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    system_prompt: str = ""
    prompt: dict[str, str] = Field(default_factory=dict)
    response: dict[str, str] = Field(default_factory=dict)
    full_response: str = ""


class StepLog(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    game_index: str
    step: int
    timestamp: str
    player: PlayerLog
    interaction: Interaction

    def compact(self) -> StepLog:
        pass
        data = self.model_dump()
        data["interaction"]["system_prompt"] = ""
        return StepLog.model_validate(data)


class PlayerSummary(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    name: str
    color: str
    identity: str
    personality: str | None = None
    tasks: list[str] = Field(default_factory=list)


class GameSummary(BaseModel):
    pass

    model_config = ConfigDict(extra="allow")

    config: dict[str, int] = Field(default_factory=dict)
    winner: int
    winner_reason: str

    def players(self) -> dict[str, PlayerSummary]:
        pass
        extras = self.__pydantic_extra__ or {}
        out: dict[str, PlayerSummary] = {}
        for key, value in extras.items():
            if key.startswith("Player ") and isinstance(value, dict):
                out[key] = PlayerSummary.model_validate(value)
        return out


__all__ = [
    "GameSummary",
    "Interaction",
    "PlayerLog",
    "PlayerSummary",
    "StepLog",
]
