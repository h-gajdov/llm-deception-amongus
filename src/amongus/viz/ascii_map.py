from __future__ import annotations

from .layout import DEAD_EMOJI, GRID_COLS, GRID_ROWS, ROOM_GRID, emoji_for
from .reconstruct import Frame, PlayerInfo

_CELL_W = 22
_INNER = _CELL_W - 4


def render_ascii_map(frame: Frame, roster: list[PlayerInfo], game_index: str) -> str:
    occupants = _occupants_by_room(frame)
    room_at = {pos: room for room, pos in ROOM_GRID.items()}

    lines = [f"{game_index} — Step {frame.step} ({frame.phase})"]
    for row in range(GRID_ROWS):
        cells = [_cell(room_at.get((row, col)), occupants) for col in range(GRID_COLS)]
        for band in range(3):
            lines.append("".join(cell[band] for cell in cells))
    lines.append("")
    lines.append(f"➤ {frame.text}")
    if frame.speech:
        lines.append(f'  💬 "{frame.speech}"')
    return "\n".join(lines)


def _occupants_by_room(frame: Frame) -> dict[str, str]:
    rooms: dict[str, list[str]] = {}
    for name, room in frame.positions.items():
        if frame.alive.get(name, True):
            rooms.setdefault(room, []).append(emoji_for(_color(name)))
    for _name, room in frame.bodies.items():
        rooms.setdefault(room, []).append(DEAD_EMOJI)
    return {room: "".join(glyphs) for room, glyphs in rooms.items()}


def _color(name: str) -> str:
    return name.split(": ", 1)[1].strip().lower() if ": " in name else "unknown"


def _cell(room: str | None, occupants: dict[str, str]) -> tuple[str, str, str]:
    if room is None:
        blank = " " * _CELL_W
        return blank, blank, blank
    title = f"┌ {_clip(room, _CELL_W - 4)} "
    top = title + "─" * (_CELL_W - len(title) - 1) + "┐"
    glyphs = occupants.get(room, "·")
    mid = "│ " + _pad_display(glyphs, _INNER) + " │"
    bot = "└" + "─" * (_CELL_W - 2) + "┘"
    return top, mid, bot


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _display_width(text: str) -> int:
    return sum(2 if ord(ch) > 0x2500 else 1 for ch in text)


def _pad_display(text: str, width: int) -> str:
    pad = max(0, width - _display_width(text))
    return text + " " * pad


__all__ = ["render_ascii_map"]
