

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import Phase, Role
from .events import Perception, PerceptionSource
from .memory import StructuredMemory
from .tasks import TaskSpec

                                                                                
                                                                         
                                                              
EMPTY_MEMORY = "Nothing has happened yet that you are aware of."
NO_RATIONALE = "(no rationale recorded yet)"


@dataclass
class PrivateState:
    pass

    perceptions: list[Perception] = field(default_factory=list)
    memory: StructuredMemory = field(default_factory=StructuredMemory)
    teammate_names: list[str] = field(default_factory=list)
    model_condensed_memory: str = EMPTY_MEMORY
    model_rationale: str = NO_RATIONALE

    def receive(self, perception: Perception) -> None:
        pass
        self.perceptions.append(perception)
        self.memory.absorb(perception)

    def heard_from(self, source: PerceptionSource) -> list[Perception]:
        pass
        return [p for p in self.perceptions if p.source is source]

    def to_dict(self) -> dict[str, object]:
        pass
        return {
            "teammate_names": list(self.teammate_names),
            "direct_observations": [
                p.to_dict()
                for p in self.perceptions
                if p.source in (PerceptionSource.DIRECT, PerceptionSource.CAMERA)
            ],
            "heard_statements": [
                p.to_dict() for p in self.perceptions if p.source is PerceptionSource.HEARD
            ],
            "public_facts": [
                p.to_dict() for p in self.perceptions if p.source is PerceptionSource.PUBLIC
            ],
            "structured_memory": self.memory.to_dict(),
            "model_condensed_memory": self.model_condensed_memory,
        }


@dataclass
class PlayerState:
    pass

    index: int
    color: str
    role: Role
    model: str
    location: str
    tasks: list[TaskSpec] = field(default_factory=list)
    completed_tasks: set[int] = field(default_factory=set)
    alive: bool = True
    ejected: bool = False
    personality: str | None = None
    kill_cooldown_remaining: int = 0
    private: PrivateState = field(default_factory=PrivateState)
    current_vote: str | None = None

    @property
    def name(self) -> str:
        pass
        return f"Player {self.index}: {self.color}"

    @property
    def is_impostor(self) -> bool:
        pass
        return self.role is Role.IMPOSTOR

    @property
    def tasks_remaining(self) -> int:
        pass
        return len(self.tasks) - len(self.completed_tasks)

    @property
    def all_tasks_done(self) -> bool:
        pass
        return self.tasks_remaining == 0


@dataclass
class GameState:
    pass

    game_index: str
    players: list[PlayerState]
    phase: Phase = Phase.TASK
    timestep: int = 0
    step: int = 0
    buttons_used: int = 0
    dead_bodies: dict[str, list[str]] = field(default_factory=dict)
    meeting_round: int = 0
    meeting_number: int = 0
    meeting_reason: str | None = None
    meeting_transcript: list[str] = field(default_factory=list)
    discussion_rounds: int = 3
    max_num_buttons: int = 2
    max_timesteps: int = 50
    finished: bool = False
    winner: int | None = None
    winner_reason: str | None = None

    def player_by_name(self, name: str) -> PlayerState | None:
        pass
        return next((p for p in self.players if p.name == name), None)

    def player_by_index(self, index: int) -> PlayerState | None:
        pass
        return next((p for p in self.players if p.index == index), None)

    def alive_players(self) -> list[PlayerState]:
        pass
        return [p for p in self.players if p.alive]

    def alive_impostors(self) -> list[PlayerState]:
        pass
        return [p for p in self.alive_players() if p.is_impostor]

    def alive_crewmates(self) -> list[PlayerState]:
        pass
        return [p for p in self.alive_players() if not p.is_impostor]

    def players_in_room(self, room: str, *, alive_only: bool = True) -> list[PlayerState]:
        pass
        return [p for p in self.players if p.location == room and (p.alive or not alive_only)]

    def rooms_in_play(self) -> list[str]:
        pass
        return sorted({p.location for p in self.alive_players()})

    def crewmate_tasks_complete(self, *, count_dead: bool = False) -> bool:
        pass
        crewmates = [p for p in self.players if not p.is_impostor and (count_dead or p.alive)]
        return bool(crewmates) and all(p.all_tasks_done for p in crewmates)


__all__ = [
    "EMPTY_MEMORY",
    "NO_RATIONALE",
    "GameState",
    "PlayerState",
    "PrivateState",
]
