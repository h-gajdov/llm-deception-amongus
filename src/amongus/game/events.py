from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .enums import Phase


class PerceptionSource(str, Enum):
    SELF = "self"
    pass

    DIRECT = "direct"
    pass

    CAMERA = "camera"
    pass

    HEARD = "heard"
    pass

    PUBLIC = "public"
    pass


class EventType(str, Enum):
    GAME_START = "game_start"
    MOVE = "move"
    VENT = "vent"
    TASK_COMPLETED = "task_completed"
    TASK_FAKED = "task_faked"
    KILL = "kill"
    BODY_SIGHTED = "body_sighted"
    BODY_REPORTED = "body_reported"
    MEETING_CALLED = "meeting_called"
    MEETING_STARTED = "meeting_started"
    SPEECH = "speech"
    VOTE_CAST = "vote_cast"
    VOTE_RESULT = "vote_result"
    EJECTION = "ejection"
    CAMERA_CHECK = "camera_check"
    WAIT = "wait"
    GAME_END = "game_end"


PUBLIC_EVENTS: frozenset[EventType] = frozenset(
    {
        EventType.BODY_REPORTED,
        EventType.MEETING_CALLED,
        EventType.MEETING_STARTED,
        EventType.VOTE_RESULT,
        EventType.EJECTION,
    }
)


@dataclass(frozen=True)
class WorldEvent:
    seq: int
    timestep: int
    phase: Phase
    type: EventType
    actor: int | None = None
    target: int | None = None
    room: str | None = None
    to_room: str | None = None
    task_name: str | None = None
    text: str | None = None
    private_to: tuple[int, ...] = ()
    payload: dict[str, object] = field(default_factory=dict)

    @property
    def is_public(self) -> bool:
        return self.type in PUBLIC_EVENTS

    def to_dict(self) -> dict[str, object]:
        return {
            "seq": self.seq,
            "timestep": self.timestep,
            "phase": self.phase.value,
            "type": self.type.value,
            "actor": self.actor,
            "target": self.target,
            "room": self.room,
            "to_room": self.to_room,
            "task_name": self.task_name,
            "text": self.text,
            "private_to": list(self.private_to),
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class Perception:
    event_seq: int
    observer: int
    event_type: EventType
    timestep: int
    phase: Phase
    source: PerceptionSource
    text: str
    actor_name: str | None = None
    actor_identified: bool = True
    target_name: str | None = None
    room: str | None = None
    speaker_name: str | None = None

    def render(self) -> str:
        return f"[t={self.timestep}] {self.text}"

    def to_dict(self) -> dict[str, object]:
        return {
            "event_seq": self.event_seq,
            "event_type": self.event_type.value,
            "timestep": self.timestep,
            "phase": self.phase.value,
            "source": self.source.value,
            "text": self.text,
            "actor_name": self.actor_name,
            "actor_identified": self.actor_identified,
            "target_name": self.target_name,
            "room": self.room,
            "speaker_name": self.speaker_name,
        }


@dataclass
class EventLog:
    events: list[WorldEvent] = field(default_factory=list)
    _next_seq: int = 0

    def append(
        self,
        *,
        timestep: int,
        phase: Phase,
        type: EventType,
        actor: int | None = None,
        target: int | None = None,
        room: str | None = None,
        to_room: str | None = None,
        task_name: str | None = None,
        text: str | None = None,
        private_to: tuple[int, ...] = (),
        **payload: object,
    ) -> WorldEvent:
        event = WorldEvent(
            seq=self._next_seq,
            timestep=timestep,
            phase=phase,
            type=type,
            actor=actor,
            target=target,
            room=room,
            to_room=to_room,
            task_name=task_name,
            text=text,
            private_to=private_to,
            payload=payload,
        )
        self._next_seq += 1
        self.events.append(event)
        return event

    def of_type(self, *types: EventType) -> list[WorldEvent]:
        wanted = set(types)
        return [e for e in self.events if e.type in wanted]

    def since(self, seq: int) -> list[WorldEvent]:
        return [e for e in self.events if e.seq >= seq]

    def between(self, start_seq: int, end_seq: int) -> list[WorldEvent]:
        return [e for e in self.events if start_seq <= e.seq < end_seq]

    def to_list(self) -> list[dict[str, object]]:
        return [e.to_dict() for e in self.events]


__all__ = [
    "PUBLIC_EVENTS",
    "EventLog",
    "EventType",
    "Perception",
    "PerceptionSource",
    "WorldEvent",
]
