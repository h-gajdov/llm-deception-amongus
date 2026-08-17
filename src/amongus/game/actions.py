from __future__ import annotations

from dataclasses import dataclass

from .enums import ActionType, Phase
from .game_map import GameMap
from .state import GameState, PlayerState
from .tasks import TaskSpec


@dataclass(frozen=True)
class Action:
    type: ActionType
    source_room: str | None = None
    target_room: str | None = None
    target_name: str | None = None
    task: TaskSpec | None = None

    def render(self) -> str:
        match self.type:
            case ActionType.MOVE:
                return f"MOVE from {self.source_room} to {self.target_room}"
            case ActionType.VENT:
                return f"VENT from {self.source_room} to {self.target_room}"
            case ActionType.COMPLETE_TASK:
                return f"COMPLETE TASK: {self._task_label()}"
            case ActionType.FAKE_TASK:
                return f"FAKE TASK: {self._task_label()}"
            case ActionType.KILL:
                return f"KILL {self.target_name}"
            case ActionType.REPORT:
                return "REPORT DEAD BODY"
            case ActionType.CALL_MEETING:
                return f"CALL MEETING using the emergency button at {self.source_room}"
            case ActionType.CHECK_SECURITY:
                return "CHECK SECURITY CAMERA"
            case ActionType.SPEAK:
                return "SPEAK"
            case ActionType.VOTE:
                return f"VOTE {self.target_name}"
            case ActionType.WAIT:
                return "WAIT (do nothing this turn)"
        msg = f"Unhandled action type: {self.type}"
        raise ValueError(msg)

    def _task_label(self) -> str:
        if self.task is None:
            msg = "Task action requires a task"
            raise ValueError(msg)
        return f"{self.task.name} ({self.task.room})"


def available_actions(
    state: GameState,
    player: PlayerState,
    game_map: GameMap,
) -> list[Action]:
    if state.phase is Phase.MEETING:
        return _meeting_actions(state, player)
    return _task_actions(state, player, game_map)


def _task_actions(
    state: GameState,
    player: PlayerState,
    game_map: GameMap,
) -> list[Action]:
    room = player.location
    actions: list[Action] = []

    body_here = bool(state.dead_bodies.get(room))
    if body_here:
        actions.append(Action(ActionType.REPORT))

    for dest in sorted(game_map.neighbours(room)):
        actions.append(Action(ActionType.MOVE, source_room=room, target_room=dest))

    task_verb = ActionType.FAKE_TASK if player.is_impostor else ActionType.COMPLETE_TASK
    for idx, task in enumerate(player.tasks):
        if task.room == room and idx not in player.completed_tasks:
            actions.append(Action(task_verb, task=task))

    if player.is_impostor:
        for dest in sorted(game_map.vents(room)):
            actions.append(Action(ActionType.VENT, source_room=room, target_room=dest))
        if player.kill_cooldown_remaining == 0:
            for victim in state.players_in_room(room):
                if not victim.is_impostor and victim.index != player.index:
                    actions.append(Action(ActionType.KILL, target_name=victim.name))

    if room == game_map.security_camera_room:
        actions.append(Action(ActionType.CHECK_SECURITY))

    if (
        room == game_map.emergency_button_room
        and state.buttons_used < state.max_num_buttons
        and not body_here
    ):
        actions.append(Action(ActionType.CALL_MEETING, source_room=room))

    actions.append(Action(ActionType.WAIT))
    return actions


def _meeting_actions(state: GameState, player: PlayerState) -> list[Action]:
    if state.meeting_round < state.discussion_rounds:
        return [Action(ActionType.SPEAK)]

    actions = [
        Action(ActionType.VOTE, target_name=other.name)
        for other in state.alive_players()
        if other.index != player.index
    ]
    actions.append(Action(ActionType.VOTE, target_name="Skip"))
    return actions


__all__ = ["Action", "available_actions"]
