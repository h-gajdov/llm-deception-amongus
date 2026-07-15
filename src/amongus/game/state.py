

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import Phase, Role
from .tasks import TaskSpec

                                                                               
                                                  
DEFAULT_MEMORY = "No memory has been processed."
DEFAULT_SUMMARIZATION = "No thought process has been made."


@dataclass
class Observation:
    pass

    timestep: int
    phase: Phase
    text: str

    def render(self) -> str:
        pass
        tag = "task" if self.phase is Phase.TASK else "meeting"
        return f"Timestep {self.timestep}: [{tag}] {self.text}"


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
    personality: str | None = None
    kill_cooldown_remaining: int = 0
    observations: list[Observation] = field(default_factory=list)
    action_history: list[str] = field(default_factory=list)
    last_memory: str = DEFAULT_MEMORY
    last_summarization: str = DEFAULT_SUMMARIZATION
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

    def crewmate_tasks_complete(self) -> bool:
        pass
        crewmates = [p for p in self.players if not p.is_impostor]
        return bool(crewmates) and all(p.all_tasks_done for p in crewmates)


__all__ = [
    "DEFAULT_MEMORY",
    "DEFAULT_SUMMARIZATION",
    "GameState",
    "Observation",
    "PlayerState",
]
