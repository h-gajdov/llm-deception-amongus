from __future__ import annotations

import random
from dataclasses import dataclass

from .enums import TaskLength
from .game_map import (
    ADMIN,
    CAFETERIA,
    COMMUNICATIONS,
    ELECTRICAL,
    LOWER_ENGINE,
    MEDBAY,
    NAVIGATION,
    O2,
    REACTOR,
    SHIELDS,
    STORAGE,
    UPPER_ENGINE,
    WEAPONS,
)


@dataclass(frozen=True)
class TaskSpec:
    name: str
    length: TaskLength
    room: str


TASK_CATALOG: tuple[TaskSpec, ...] = (
    TaskSpec("Fix Wiring", TaskLength.COMMON, ELECTRICAL),
    TaskSpec("Swipe Card", TaskLength.COMMON, ADMIN),
    TaskSpec("Clean O2 Filter", TaskLength.SHORT, O2),
    TaskSpec("Empty Chute", TaskLength.SHORT, STORAGE),
    TaskSpec("Empty Garbage", TaskLength.SHORT, CAFETERIA),
    TaskSpec("Calibrate Distributor", TaskLength.SHORT, ELECTRICAL),
    TaskSpec("Accept Diverted Power", TaskLength.SHORT, SHIELDS),
    TaskSpec("Chart Course", TaskLength.SHORT, NAVIGATION),
    TaskSpec("Prime Shields", TaskLength.SHORT, SHIELDS),
    TaskSpec("Stabilize Steering", TaskLength.SHORT, NAVIGATION),
    TaskSpec("Align Engine Output", TaskLength.SHORT, LOWER_ENGINE),
    TaskSpec("Upload Data", TaskLength.SHORT, COMMUNICATIONS),
    TaskSpec("Inspect Sample", TaskLength.LONG, MEDBAY),
    TaskSpec("Submit Scan", TaskLength.LONG, MEDBAY),
    TaskSpec("Fuel Engines", TaskLength.LONG, UPPER_ENGINE),
    TaskSpec("Divert Power", TaskLength.LONG, REACTOR),
    TaskSpec("Calibrate Weapons", TaskLength.LONG, WEAPONS),
    TaskSpec("Start Reactor", TaskLength.LONG, REACTOR),
)

_BY_LENGTH: dict[TaskLength, tuple[TaskSpec, ...]] = {
    length: tuple(t for t in TASK_CATALOG if t.length is length) for length in TaskLength
}


def _sample(pool: tuple[TaskSpec, ...], k: int, rng: random.Random) -> list[TaskSpec]:
    if k <= 0 or not pool:
        return []
    return rng.sample(pool, min(k, len(pool)))


def sample_common_tasks(num_common: int, rng: random.Random) -> list[TaskSpec]:
    return _sample(_BY_LENGTH[TaskLength.COMMON], num_common, rng)


def assign_crewmate_tasks(
    common: list[TaskSpec],
    num_short: int,
    num_long: int,
    rng: random.Random,
) -> list[TaskSpec]:
    short = _sample(_BY_LENGTH[TaskLength.SHORT], num_short, rng)
    long = _sample(_BY_LENGTH[TaskLength.LONG], num_long, rng)
    return [*common, *short, *long]


__all__ = [
    "TASK_CATALOG",
    "TaskSpec",
    "assign_crewmate_tasks",
    "sample_common_tasks",
]
