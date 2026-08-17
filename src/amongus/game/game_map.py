from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

CAFETERIA = "Cafeteria"
WEAPONS = "Weapons"
NAVIGATION = "Navigation"
O2 = "O2"
SHIELDS = "Shields"
COMMUNICATIONS = "Communications"
STORAGE = "Storage"
ADMIN = "Admin"
ELECTRICAL = "Electrical"
LOWER_ENGINE = "Lower Engine"
SECURITY = "Security"
REACTOR = "Reactor"
UPPER_ENGINE = "Upper Engine"
MEDBAY = "Medbay"


_WALK_EDGES: tuple[tuple[str, str], ...] = (
    (CAFETERIA, WEAPONS),
    (CAFETERIA, ADMIN),
    (CAFETERIA, UPPER_ENGINE),
    (CAFETERIA, MEDBAY),
    (WEAPONS, O2),
    (WEAPONS, NAVIGATION),
    (O2, NAVIGATION),
    (O2, SHIELDS),
    (NAVIGATION, SHIELDS),
    (SHIELDS, COMMUNICATIONS),
    (SHIELDS, STORAGE),
    (COMMUNICATIONS, STORAGE),
    (STORAGE, ADMIN),
    (STORAGE, ELECTRICAL),
    (STORAGE, LOWER_ENGINE),
    (ADMIN, CAFETERIA),
    (ELECTRICAL, LOWER_ENGINE),
    (LOWER_ENGINE, REACTOR),
    (LOWER_ENGINE, SECURITY),
    (REACTOR, SECURITY),
    (REACTOR, UPPER_ENGINE),
    (SECURITY, UPPER_ENGINE),
    (UPPER_ENGINE, MEDBAY),
    (MEDBAY, ELECTRICAL),
)


_VENT_EDGES: tuple[tuple[str, str], ...] = (
    (CAFETERIA, ADMIN),
    (WEAPONS, NAVIGATION),
    (NAVIGATION, SHIELDS),
    (ELECTRICAL, MEDBAY),
    (ELECTRICAL, SECURITY),
    (MEDBAY, SECURITY),
    (LOWER_ENGINE, REACTOR),
    (REACTOR, UPPER_ENGINE),
)


EMERGENCY_BUTTON_ROOM = CAFETERIA
SECURITY_CAMERA_ROOM = SECURITY


def _symmetric(edges: tuple[tuple[str, str], ...]) -> dict[str, frozenset[str]]:
    adj: dict[str, set[str]] = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return {room: frozenset(neighbours) for room, neighbours in adj.items()}


@dataclass(frozen=True)
class GameMap:
    rooms: tuple[str, ...]
    walk_adjacency: dict[str, frozenset[str]] = field(default_factory=dict)
    vent_adjacency: dict[str, frozenset[str]] = field(default_factory=dict)
    emergency_button_room: str = EMERGENCY_BUTTON_ROOM
    security_camera_room: str = SECURITY_CAMERA_ROOM

    def neighbours(self, room: str) -> frozenset[str]:
        return self.walk_adjacency.get(room, frozenset())

    def vents(self, room: str) -> frozenset[str]:
        return self.vent_adjacency.get(room, frozenset())

    def has_vent(self, room: str) -> bool:
        return bool(self.vent_adjacency.get(room))

    def shortest_walk_path(self, start: str, goal: str) -> list[str]:
        if start == goal:
            return [start]
        queue: deque[str] = deque([start])
        came_from: dict[str, str] = {start: start}
        while queue:
            current = queue.popleft()
            for nxt in sorted(self.walk_adjacency.get(current, frozenset())):
                if nxt in came_from:
                    continue
                came_from[nxt] = current
                if nxt == goal:
                    return self._reconstruct(came_from, start, goal)
                queue.append(nxt)
        return []

    @staticmethod
    def _reconstruct(came_from: dict[str, str], start: str, goal: str) -> list[str]:
        path = [goal]
        while path[-1] != start:
            path.append(came_from[path[-1]])
        path.reverse()
        return path


def build_skeld() -> GameMap:
    rooms = (
        CAFETERIA,
        WEAPONS,
        NAVIGATION,
        O2,
        SHIELDS,
        COMMUNICATIONS,
        STORAGE,
        ADMIN,
        ELECTRICAL,
        LOWER_ENGINE,
        SECURITY,
        REACTOR,
        UPPER_ENGINE,
        MEDBAY,
    )
    return GameMap(
        rooms=rooms,
        walk_adjacency=_symmetric(_WALK_EDGES),
        vent_adjacency=_symmetric(_VENT_EDGES),
    )


SKELD_MAP_DESCRIPTION = """Map Configuration of the Skeld:
Rooms and Features
Cafeteria: Vent to Admin, Special (Emergency Button).
Weapons: Vent to Navigation.
Navigation: Vent to Shields and Weapons.
O2: Nothing Special
Shields: Vent to Navigation.
Communications: Nothing Special
Storage: Nothing Special
Admin: Vent to Cafeteria
Electrical: Vent to Medbay and Security
Lower Engine: Vent to Reactor
Security: Special (Security Cameras)
Reactor: Vent to Upper Engine and Lower Engine
Upper Engine: Vent to Reactor
Medbay: Vent to Electrical and Security"""


__all__ = ["SKELD_MAP_DESCRIPTION", "GameMap", "build_skeld"]
