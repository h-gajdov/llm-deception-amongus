from __future__ import annotations

from dataclasses import dataclass, field

from .events import Perception, PerceptionSource


MAX_WITNESSED = 20
MAX_HEARD = 20
MAX_OWN_ACTIONS = 20
MAX_PUBLIC_FACTS = 15


@dataclass
class LocationBelief:
    room: str
    timestep: int
    source: PerceptionSource

    def to_dict(self) -> dict[str, object]:
        return {"room": self.room, "timestep": self.timestep, "source": self.source.value}


@dataclass
class HeardStatement:
    timestep: int
    speaker: str
    text: str

    def to_dict(self) -> dict[str, object]:
        return {"timestep": self.timestep, "speaker": self.speaker, "text": self.text}


@dataclass
class WitnessedEvent:
    timestep: int
    text: str
    event_type: str
    actor_identified: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "timestep": self.timestep,
            "text": self.text,
            "event_type": self.event_type,
            "actor_identified": self.actor_identified,
        }


@dataclass
class StructuredMemory:
    last_known_locations: dict[str, LocationBelief] = field(default_factory=dict)
    witnessed_events: list[WitnessedEvent] = field(default_factory=list)
    heard_statements: list[HeardStatement] = field(default_factory=list)
    public_meeting_facts: list[str] = field(default_factory=list)
    suspicions: dict[str, list[str]] = field(default_factory=dict)
    own_actions: list[str] = field(default_factory=list)
    own_route: list[tuple[int, str]] = field(default_factory=list)

    def absorb(self, perception: Perception) -> None:
        if perception.source is PerceptionSource.HEARD:
            self._absorb_heard(perception)
        elif perception.source is PerceptionSource.PUBLIC:
            self._absorb_public(perception)
        else:
            self._absorb_direct(perception)

    def _absorb_direct(self, perception: Perception) -> None:
        self.witnessed_events.append(
            WitnessedEvent(
                timestep=perception.timestep,
                text=perception.text,
                event_type=perception.event_type.value,
                actor_identified=perception.actor_identified,
            )
        )
        del self.witnessed_events[:-MAX_WITNESSED]
        if perception.actor_name and perception.actor_identified and perception.room:
            self.last_known_locations[perception.actor_name] = LocationBelief(
                room=perception.room,
                timestep=perception.timestep,
                source=perception.source,
            )

    def _absorb_heard(self, perception: Perception) -> None:
        self.heard_statements.append(
            HeardStatement(
                timestep=perception.timestep,
                speaker=perception.speaker_name or "unknown",
                text=_unquote(perception.text),
            )
        )
        del self.heard_statements[:-MAX_HEARD]

    def _absorb_public(self, perception: Perception) -> None:
        self.public_meeting_facts.append(f"[t={perception.timestep}] {perception.text}")
        del self.public_meeting_facts[:-MAX_PUBLIC_FACTS]

    def note_own_action(self, timestep: int, phase_label: str, rendered: str) -> None:
        self.own_actions.append(f"[t={timestep}] [{phase_label}] {rendered}")
        del self.own_actions[:-MAX_OWN_ACTIONS]

    def note_own_location(self, name: str, room: str, timestep: int) -> None:
        self.last_known_locations[name] = LocationBelief(
            room=room, timestep=timestep, source=PerceptionSource.SELF
        )
        if not self.own_route or self.own_route[-1][1] != room:
            self.own_route.append((timestep, room))
            del self.own_route[:-MAX_OWN_ACTIONS]

    def route_since(self, timestep: int) -> list[str]:
        rooms = [room for when, room in self.own_route if when >= timestep]
        if rooms:
            return rooms
        return [self.own_route[-1][1]] if self.own_route else []

    def note_accusation(self, accuser: str, target: str) -> None:
        accusers = self.suspicions.setdefault(target, [])
        if accuser not in accusers:
            accusers.append(accuser)

    def render_condensed(self) -> str:
        parts: list[str] = []
        if self.own_route:
            route = " -> ".join(room for _, room in self.own_route[-6:])
            parts.append(f"Where you have been (most recent last): {route}.")
        if self.last_known_locations:
            seen = ", ".join(
                f"{name} in {belief.room} (t={belief.timestep}, {belief.source.value})"
                for name, belief in sorted(self.last_known_locations.items())
            )
            parts.append(f"Last known positions: {seen}.")
        if self.witnessed_events:
            recent = "; ".join(e.text for e in self.witnessed_events[-5:])
            parts.append(f"Recently witnessed: {recent}")
        if self.public_meeting_facts:
            parts.append("Public record: " + " ".join(self.public_meeting_facts[-3:]))
        if self.suspicions:
            accused = ", ".join(
                f"{target} (named by {', '.join(accusers)})"
                for target, accusers in sorted(self.suspicions.items())
            )
            parts.append(f"Players others have accused: {accused}.")
        if not parts:
            return "Nothing has happened yet that you are aware of."
        return "\n".join(parts)

    def to_dict(self) -> dict[str, object]:
        return {
            "last_known_locations": {
                name: belief.to_dict() for name, belief in self.last_known_locations.items()
            },
            "witnessed_events": [e.to_dict() for e in self.witnessed_events],
            "heard_statements": [s.to_dict() for s in self.heard_statements],
            "public_meeting_facts": list(self.public_meeting_facts),
            "suspicions": {k: list(v) for k, v in self.suspicions.items()},
            "own_actions": list(self.own_actions),
            "own_route": [[when, room] for when, room in self.own_route],
        }


def _unquote(text: str) -> str:
    marker = ' said: "'
    idx = text.find(marker)
    if idx == -1:
        return text
    return text[idx + len(marker) :].rstrip('"')


__all__ = [
    "MAX_HEARD",
    "MAX_OWN_ACTIONS",
    "MAX_PUBLIC_FACTS",
    "MAX_WITNESSED",
    "HeardStatement",
    "LocationBelief",
    "StructuredMemory",
    "WitnessedEvent",
]
