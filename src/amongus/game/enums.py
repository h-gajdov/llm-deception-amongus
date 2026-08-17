from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    CREWMATE = "Crewmate"
    IMPOSTOR = "Impostor"


class Phase(str, Enum):
    TASK = "Task phase"
    MEETING = "Meeting phase"


class ActionType(str, Enum):
    MOVE = "MOVE"
    SPEAK = "SPEAK"
    VOTE = "VOTE"
    REPORT = "REPORT"
    CALL_MEETING = "CALL_MEETING"
    CHECK_SECURITY = "CHECK_SECURITY"
    COMPLETE_TASK = "COMPLETE_TASK"
    KILL = "KILL"
    FAKE_TASK = "FAKE_TASK"
    VENT = "VENT"
    WAIT = "WAIT"


class TaskLength(str, Enum):
    COMMON = "common"
    SHORT = "short"
    LONG = "long"


PLAYER_COLORS: tuple[str, ...] = (
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
    "cyan",
    "lime",
    "white",
    "black",
    "brown",
)


class WinReason(str, Enum):
    IMPOSTORS_OUTNUMBER = "Impostors win! (Crewmates being outnumbered or tied to impostors))"
    IMPOSTORS_TIME_UP = "Impostors win! (Time limit reached)"
    CREWMATES_TASKS_DONE = "Crewmates win! (All tasks completed)"
    CREWMATES_VOTED_OUT = "Crewmates win! (All impostors ejected)"


__all__ = [
    "PLAYER_COLORS",
    "ActionType",
    "Phase",
    "Role",
    "TaskLength",
    "WinReason",
]
