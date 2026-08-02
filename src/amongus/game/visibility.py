

from __future__ import annotations

import random
from collections.abc import Callable

from ..config import VisibilityConfig
from .events import EventType, Perception, PerceptionSource, WorldEvent
from .state import GameState, PlayerState

                                                                              
UNKNOWN_ACTOR = "someone"


def resolve_perceptions(
    event: WorldEvent,
    state: GameState,
    config: VisibilityConfig,
    rng: random.Random,
) -> list[Perception]:
    pass
    handler = _HANDLERS.get(event.type)
    if handler is None:
        return []
    return handler(event, state, config, rng)


                                                                               
                  
                                                                               
def _observers(
    state: GameState,
    config: VisibilityConfig,
    rooms: tuple[str | None, ...],
    exclude: tuple[int | None, ...] = (),
) -> list[PlayerState]:
    pass
    blocked = {i for i in exclude if i is not None}
    wanted = {r for r in rooms if r is not None}
    seen: set[int] = set()
    out: list[PlayerState] = []
    for player in state.players:
        if player.index in blocked or player.index in seen:
            continue
        if not player.alive and not config.ghosts_observe:
            continue
        if player.location in wanted:
            seen.add(player.index)
            out.append(player)
    return out


def _audience(state: GameState, config: VisibilityConfig) -> list[PlayerState]:
    pass
    return [p for p in state.players if p.alive or config.ghosts_observe]


def _name(state: GameState, index: int | None) -> str | None:
    pass
    if index is None:
        return None
    player = state.player_by_index(index)
    return player.name if player else None


def _rolls(rng: random.Random, probability: float) -> bool:
    pass
    if probability >= 1.0:
        return True
    if probability <= 0.0:
        return False
    return rng.random() < probability


def _perception(
    event: WorldEvent,
    observer: PlayerState,
    source: PerceptionSource,
    text: str,
    *,
    actor_name: str | None = None,
    actor_identified: bool = True,
    target_name: str | None = None,
    room: str | None = None,
    speaker_name: str | None = None,
) -> Perception:
    pass
    return Perception(
        event_seq=event.seq,
        observer=observer.index,
        event_type=event.type,
        timestep=event.timestep,
        phase=event.phase,
        source=source,
        text=text,
        actor_name=actor_name,
        actor_identified=actor_identified,
        target_name=target_name,
        room=room if room is not None else event.room,
        speaker_name=speaker_name,
    )


                                                                               
                      
                                                                               
def _move_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    actor = _name(state, event.actor)
    out: list[Perception] = []
    if config.movement_visible_in_source_room:
        for observer in _observers(state, config, (event.room,), exclude=(event.actor,)):
            if not _rolls(rng, config.movement_witness_probability):
                continue
            out.append(
                _perception(
                    event,
                    observer,
                    PerceptionSource.DIRECT,
                    f"You saw {actor} leave {event.room} towards {event.to_room}.",
                    actor_name=actor,
                    room=event.room,
                )
            )
    if config.movement_visible_in_destination_room:
        for observer in _observers(state, config, (event.to_room,), exclude=(event.actor,)):
            if not _rolls(rng, config.movement_witness_probability):
                continue
            out.append(
                _perception(
                    event,
                    observer,
                    PerceptionSource.DIRECT,
                    f"You saw {actor} arrive in {event.to_room} from {event.room}.",
                    actor_name=actor,
                    room=event.to_room,
                )
            )
    return out


def _vent_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    actor = _name(state, event.actor)
    out: list[Perception] = []
    for room, verb in ((event.room, "climb into"), (event.to_room, "climb out of")):
        for observer in _observers(state, config, (room,), exclude=(event.actor,)):
            if not _rolls(rng, config.vent_witness_probability):
                continue
            identified = _rolls(rng, config.vent_identification_probability)
            who = actor if identified else UNKNOWN_ACTOR
            out.append(
                _perception(
                    event,
                    observer,
                    PerceptionSource.DIRECT,
                    f"You saw {who} {verb} the vent in {room}.",
                    actor_name=actor if identified else None,
                    actor_identified=identified,
                    room=room,
                )
            )
    return out


def _task_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    actor = _name(state, event.actor)
    out: list[Perception] = []
    for observer in _observers(state, config, (event.room,), exclude=(event.actor,)):
        if not _rolls(rng, config.task_witness_probability):
            continue
        out.append(
            _perception(
                event,
                observer,
                PerceptionSource.DIRECT,
                f"You saw {actor} working on a task console in {event.room}.",
                actor_name=actor,
            )
        )
    return out


def _kill_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    actor = _name(state, event.actor)
    victim = _name(state, event.target)
    out: list[Perception] = []
    for observer in _observers(state, config, (event.room,), exclude=(event.actor, event.target)):
        if not _rolls(rng, config.kill_witness_probability):
            continue
        identified = _rolls(rng, config.kill_identification_probability)
        if identified:
            text = f"You saw {actor} kill {victim} in {event.room}."
        else:
            text = f"You saw {victim} killed in {event.room}, but you could not tell who did it."
        out.append(
            _perception(
                event,
                observer,
                PerceptionSource.DIRECT,
                text,
                actor_name=actor if identified else None,
                actor_identified=identified,
                target_name=victim,
            )
        )
    return out


def _body_sighted_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    del rng
    victim = event.payload.get("victim_name")
    out: list[Perception] = []
    for observer in _audience(state, config):
        if observer.index not in event.private_to:
            continue
        out.append(
            _perception(
                event,
                observer,
                PerceptionSource.DIRECT,
                f"You found the body of {victim} in {event.room}. You do not know who killed them.",
                target_name=str(victim) if victim else None,
            )
        )
    return out


def _body_reported_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    del rng
    reporter = _name(state, event.actor)
    victim = event.payload.get("victim_name")
    text = f"{reporter} reported the body of {victim} in {event.room}. "
    text += "Nobody has been shown to be the killer."
    if config.body_report_reveals_killer:                                  
        killer = event.payload.get("killer_name")
        text = f"{reporter} reported the body of {victim} in {event.room}, killed by {killer}."
    return [
        _perception(event, observer, PerceptionSource.PUBLIC, text)
        for observer in _audience(state, config)
        if observer.index != event.actor
    ]


def _meeting_called_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    del rng
    caller = _name(state, event.actor)
    text = f"{caller} called an emergency meeting."
    return [
        _perception(event, observer, PerceptionSource.PUBLIC, text)
        for observer in _audience(state, config)
        if observer.index != event.actor
    ]


def _speech_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    del rng
    speaker = _name(state, event.actor)
    text = f'{speaker} said: "{event.text}"'
    return [
        _perception(
            event,
            observer,
            PerceptionSource.HEARD,
            text,
            speaker_name=speaker,
        )
        for observer in _audience(state, config)
        if observer.index != event.actor
    ]


def _vote_result_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    del rng
    if not config.reveal_votes:
        return []
    text = f"Vote result: {event.text}"
    return [
        _perception(event, observer, PerceptionSource.PUBLIC, text)
        for observer in _audience(state, config)
    ]


def _ejection_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    del rng
    ejected = _name(state, event.target)
    if ejected is None:
        text = "The vote was inconclusive. No one was ejected."
    elif config.reveal_role_on_ejection:
        role = event.payload.get("role")
        text = f"{ejected} was ejected. They were {role}."
    else:
        text = f"{ejected} was ejected."
    return [
        _perception(event, observer, PerceptionSource.PUBLIC, text)
        for observer in _audience(state, config)
    ]


def _camera_rule(
    event: WorldEvent, state: GameState, config: VisibilityConfig, rng: random.Random
) -> list[Perception]:
    pass
    del rng
    sightings = event.payload.get("sightings")
    text = f"You checked the cameras. They show: {sightings}"
    return [
        _perception(event, observer, PerceptionSource.CAMERA, text)
        for observer in _audience(state, config)
        if observer.index in event.private_to
    ]


def camera_sightings(state: GameState, config: VisibilityConfig, viewer: int) -> str:
    pass
    covered = [r for r in config.camera_rooms if r in set(state.rooms_in_play())]
    lines: list[str] = []
    for room in covered:
        present = [p for p in state.players_in_room(room) if p.index != viewer]
        if not present:
            lines.append(f"{room}: empty")
        elif config.camera_shows_identity:
            lines.append(f"{room}: " + ", ".join(p.name for p in present))
        else:
            lines.append(f"{room}: {len(present)} unidentifiable figure(s)")
    return "; ".join(lines) if lines else "no cameras are online"


_Handler = Callable[[WorldEvent, GameState, VisibilityConfig, random.Random], list[Perception]]
_HANDLERS: dict[EventType, _Handler] = {
    EventType.MOVE: _move_rule,
    EventType.VENT: _vent_rule,
    EventType.TASK_COMPLETED: _task_rule,
    EventType.TASK_FAKED: _task_rule,
    EventType.KILL: _kill_rule,
    EventType.BODY_SIGHTED: _body_sighted_rule,
    EventType.BODY_REPORTED: _body_reported_rule,
    EventType.MEETING_CALLED: _meeting_called_rule,
    EventType.SPEECH: _speech_rule,
    EventType.VOTE_RESULT: _vote_result_rule,
    EventType.EJECTION: _ejection_rule,
    EventType.CAMERA_CHECK: _camera_rule,
}


__all__ = ["UNKNOWN_ACTOR", "camera_sightings", "resolve_perceptions"]
