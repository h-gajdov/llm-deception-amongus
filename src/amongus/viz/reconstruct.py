from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ..data.ingest import iter_game_summaries, iter_step_logs
from ..data.records import StepLog
from .layout import color_of

STARTING_ROOM = "Cafeteria"


_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•]\s*)?(?:\d+\s*[.)]\s*)?")


_ACTION_TAG_RE = re.compile(r"\[\s*Action\s*\]\s*(.+?)\s*$", re.IGNORECASE | re.DOTALL)

_MOVE_RE = re.compile(r"^\s*(?:MOVE|VENT)\s+from\s+(.+?)\s+to\s+(.+?)\s*$", re.IGNORECASE)
_KILL_RE = re.compile(r"^\s*KILL\s+(.+?)\s*$", re.IGNORECASE)
_VOTE_RE = re.compile(r"^\s*VOTE\s+(.+?)\s*$", re.IGNORECASE)
_SPEAK_RE = re.compile(r"^\s*SPEAK\s*:?\s*(.*)$", re.IGNORECASE | re.DOTALL)


class EventKind(str, Enum):
    MOVE = "move"
    VENT = "vent"
    KILL = "kill"
    REPORT = "report"
    MEETING = "meeting"
    SPEAK = "speak"
    VOTE = "vote"
    TASK = "task"
    OTHER = "other"


@dataclass
class PlayerInfo:
    name: str
    color: str
    role: str


@dataclass
class Frame:
    step: int
    phase: str
    actor: str
    actor_color: str
    actor_role: str
    kind: EventKind
    text: str
    speech: str | None
    positions: dict[str, str] = field(default_factory=dict)
    alive: dict[str, bool] = field(default_factory=dict)
    bodies: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "step": self.step,
            "phase": self.phase,
            "actor": self.actor,
            "actor_color": self.actor_color,
            "actor_role": self.actor_role,
            "kind": self.kind.value,
            "text": self.text,
            "speech": self.speech,
            "positions": self.positions,
            "alive": self.alive,
            "bodies": self.bodies,
        }


def build_roster(steps: list[StepLog]) -> list[PlayerInfo]:
    seen: dict[str, PlayerInfo] = {}
    for step in steps:
        name = step.player.name
        if name not in seen:
            seen[name] = PlayerInfo(name=name, color=color_of(name), role=step.player.identity)
        _register_target(step, seen)
    return sorted(seen.values(), key=lambda p: _player_number(p.name))


def _register_target(step: StepLog, seen: dict[str, PlayerInfo]) -> None:
    action, _ = logged_action(step.interaction.response, step.interaction.full_response)
    kind, fields = parse_action(action)
    target = fields.get("target", "")
    if kind not in (EventKind.KILL, EventKind.VOTE):
        return
    if target.startswith("Player ") and target not in seen:
        role = "Crewmate" if kind is EventKind.KILL else "Unknown"
        seen[target] = PlayerInfo(name=target, color=color_of(target), role=role)


def roster_from_summary(directory: Path, game_index: str) -> list[PlayerInfo] | None:
    summary_path = directory / "summary.json"
    if not summary_path.exists():
        return None
    for idx, summary in iter_game_summaries(summary_path):
        if idx != game_index:
            continue
        roster = [
            PlayerInfo(name=ps.name, color=ps.color or color_of(ps.name), role=ps.identity)
            for ps in summary.players().values()
        ]
        return sorted(roster, key=lambda p: _player_number(p.name))
    return None


def _player_number(name: str) -> int:
    match = re.search(r"Player\s+(\d+)", name)
    return int(match.group(1)) if match else 0


def parse_action(action: str) -> tuple[EventKind, dict[str, str]]:
    text = _LIST_MARKER_RE.sub("", action.strip(), count=1).strip()
    upper = text.upper()
    if move := _MOVE_RE.match(text):
        kind = EventKind.VENT if upper.startswith("VENT") else EventKind.MOVE
        return kind, {"from": move.group(1), "to": move.group(2)}
    if kill := _KILL_RE.match(text):
        return EventKind.KILL, {"target": kill.group(1)}
    if upper.startswith("REPORT"):
        return EventKind.REPORT, {}
    if upper.startswith("CALL MEETING"):
        return EventKind.MEETING, {}
    if speak := _SPEAK_RE.match(text):
        return EventKind.SPEAK, {"speech": speak.group(1).strip()}
    if vote := _VOTE_RE.match(text):
        return EventKind.VOTE, {"target": vote.group(1)}
    if "TASK" in upper:
        return EventKind.TASK, {}
    return EventKind.OTHER, {}


def _usable_action(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return "" if text.startswith("{") else text


def logged_action(response: dict[str, str], full_response: str = "") -> tuple[str, bool]:
    action = _usable_action(response.get("Action"))
    if action:
        return action, False
    match = _ACTION_TAG_RE.search(full_response or "")
    if not match:
        return "", False

    for line in match.group(1).splitlines():
        if line.strip():
            return line.strip(), True
    return "", False


def reconstruct_frames(
    steps: list[StepLog], roster: list[PlayerInfo] | None = None
) -> tuple[list[Frame], list[PlayerInfo]]:
    roster = roster or build_roster(steps)
    positions = {p.name: STARTING_ROOM for p in roster}
    alive = {p.name: True for p in roster}
    bodies: dict[str, str] = {}

    frames: list[Frame] = []
    for step in steps:
        actor = step.player.name
        positions[actor] = step.player.location
        action, _ = logged_action(step.interaction.response, step.interaction.full_response)
        kind, fields = parse_action(action)
        speech = apply_board_event(kind, fields, actor, positions, alive, bodies)
        frames.append(
            Frame(
                step=step.step,
                phase=step.interaction.prompt.get("Phase", ""),
                actor=actor,
                actor_color=color_of(actor),
                actor_role=step.player.identity,
                kind=kind,
                text=_describe(kind, fields, actor),
                speech=speech,
                positions=dict(positions),
                alive=dict(alive),
                bodies=dict(bodies),
            )
        )
    return frames, roster


def apply_board_event(
    kind: EventKind,
    fields: dict[str, str],
    actor: str,
    positions: dict[str, str],
    alive: dict[str, bool],
    bodies: dict[str, str],
) -> str | None:
    if kind in (EventKind.MOVE, EventKind.VENT):
        positions[actor] = fields.get("to", positions[actor])
    elif kind is EventKind.KILL:
        target = fields.get("target", "")
        if target in alive:
            alive[target] = False
            bodies[target] = positions.get(actor, positions.get(target, "?"))
    elif kind in (EventKind.REPORT, EventKind.MEETING):
        bodies.clear()
    elif kind is EventKind.SPEAK:
        return fields.get("speech") or None
    return None


def _describe(kind: EventKind, fields: dict[str, str], actor: str) -> str:
    match kind:
        case EventKind.MOVE:
            return f"{actor} moved from {fields.get('from')} to {fields.get('to')}"
        case EventKind.VENT:
            return f"{actor} vented from {fields.get('from')} to {fields.get('to')}"
        case EventKind.KILL:
            return f"{actor} killed {fields.get('target')}"
        case EventKind.REPORT:
            return f"{actor} reported a dead body"
        case EventKind.MEETING:
            return f"{actor} called an emergency meeting"
        case EventKind.SPEAK:
            return f"{actor} spoke"
        case EventKind.VOTE:
            return f"{actor} voted for {fields.get('target')}"
        case EventKind.TASK:
            return f"{actor} worked on a task"
        case _:
            return f"{actor} waited"


def load_game(
    experiment_dir: str | Path, game_index: str | None = None
) -> tuple[str, list[StepLog], str | None, list[PlayerInfo] | None]:
    directory = Path(experiment_dir)
    logs = directory / "agent-logs.json"
    if not logs.exists():
        msg = f"No agent-logs.json in {directory}"
        raise FileNotFoundError(msg)

    all_steps = list(iter_step_logs(logs))
    if game_index is None:
        if not all_steps:
            msg = f"No records found in {logs}"
            raise ValueError(msg)
        game_index = all_steps[0].game_index

    steps = [s for s in all_steps if s.game_index == game_index]
    if not steps:
        msg = f"No records for {game_index!r} in {logs}"
        raise ValueError(msg)

    winner = _load_winner(directory, game_index)
    roster = roster_from_summary(directory, game_index)
    return game_index, steps, winner, roster


def _load_winner(directory: Path, game_index: str) -> str | None:
    summary_path = directory / "summary.json"
    if not summary_path.exists():
        return None
    for idx, summary in iter_game_summaries(summary_path):
        if idx == game_index:
            return summary.winner_reason
    return None


__all__ = [
    "STARTING_ROOM",
    "EventKind",
    "Frame",
    "PlayerInfo",
    "apply_board_event",
    "build_roster",
    "load_game",
    "logged_action",
    "parse_action",
    "reconstruct_frames",
    "roster_from_summary",
]
