from __future__ import annotations

from .layout import DEAD_EMOJI, emoji_for
from .reconstruct import EventKind, Frame, PlayerInfo

_RULE = "─" * 62


_RED = "\033[31m"
_RESET = "\033[0m"


_ROUTINE = {EventKind.MOVE, EventKind.TASK, EventKind.OTHER}


def render_timeline(
    game_index: str,
    frames: list[Frame],
    roster: list[PlayerInfo],
    winner: str | None = None,
    *,
    events_only: bool = False,
    color: bool = False,
) -> str:
    lines = [game_index, _RULE, "", _roster_line(roster, color), ""]
    for frame in frames:
        if events_only and frame.kind in _ROUTINE:
            continue
        lines.append(f"Step {frame.step}")
        body = _render_frame(frame)
        if color and frame.actor_role == "Impostor":
            body = [_red(line) for line in body]
        lines.extend(body)
        lines.append("")
    lines.append(_RULE)
    lines.append(f"Winner: {winner}" if winner else "Winner: (unknown)")
    return "\n".join(lines)


def _red(text: str) -> str:
    return f"{_RED}{text}{_RESET}"


def _roster_line(roster: list[PlayerInfo], color: bool = False) -> str:
    parts = []
    for p in roster:
        entry = f"{emoji_for(p.color)} {p.color.capitalize()} ({p.role})"
        parts.append(_red(entry) if color and p.role == "Impostor" else entry)
    return "Players: " + "   ".join(parts)


def _render_frame(frame: Frame) -> list[str]:
    icon = emoji_for(frame.actor_color)
    who = f"{icon} {frame.actor_color.capitalize()}"
    match frame.kind:
        case EventKind.SPEAK:
            speech = frame.speech or "(says nothing)"
            return [f"{who}:", f'  "{speech}"']
        case EventKind.KILL:
            target = frame.text.split("killed", 1)[-1].strip()
            return [f"{DEAD_EMOJI} Kill: {frame.actor_color.capitalize()} killed {target}"]
        case EventKind.MEETING:
            return [f"📢 Emergency Meeting (called by {frame.actor_color.capitalize()})"]
        case EventKind.REPORT:
            return [f"🚨 Body Reported by {frame.actor_color.capitalize()}"]
        case EventKind.VOTE:
            target = frame.text.split("voted for", 1)[-1].strip()
            return [f"🗳  {frame.actor_color.capitalize()} voted for {target}"]
        case EventKind.VENT:
            dest = frame.text.split(" to ", 1)[-1].strip()
            return [f"🕳  {who} vented to {dest}"]
        case EventKind.TASK:
            return [f"🔧 {who} worked on a task in {frame.positions.get(frame.actor, '?')}"]
        case EventKind.MOVE:
            dest = frame.text.split(" to ", 1)[-1].strip()
            return [f"{who} → {dest}"]
        case _:
            return [f"⏸  {who} waited"]


__all__ = ["render_timeline"]
