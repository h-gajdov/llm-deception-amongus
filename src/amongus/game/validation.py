from __future__ import annotations

from dataclasses import dataclass

from .actions import Action
from .enums import ActionType, Phase
from .game_map import GameMap
from .state import GameState, PlayerState


@dataclass(frozen=True)
class ActionRejection:
    code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


_MEETING_ONLY = {ActionType.SPEAK, ActionType.VOTE}
_TASK_ONLY = {
    ActionType.MOVE,
    ActionType.VENT,
    ActionType.KILL,
    ActionType.COMPLETE_TASK,
    ActionType.FAKE_TASK,
    ActionType.REPORT,
    ActionType.CALL_MEETING,
    ActionType.CHECK_SECURITY,
}


def validate_action(
    state: GameState,
    player: PlayerState,
    action: Action,
    game_map: GameMap,
) -> ActionRejection | None:
    if not player.alive:
        return ActionRejection("actor_dead", f"{player.name} is dead and cannot act.")

    phase_error = _check_phase(state, action)
    if phase_error is not None:
        return phase_error

    checker = _CHECKS.get(action.type)
    return checker(state, player, action, game_map) if checker else None


def _check_phase(state: GameState, action: Action) -> ActionRejection | None:
    in_meeting = state.phase is Phase.MEETING
    if in_meeting and action.type in _TASK_ONLY:
        return ActionRejection(
            "wrong_phase", f"{action.type.value} is not available during a meeting."
        )
    if not in_meeting and action.type in _MEETING_ONLY:
        return ActionRejection(
            "wrong_phase", f"{action.type.value} is only available during a meeting."
        )
    return None


def _check_move(
    state: GameState, player: PlayerState, action: Action, game_map: GameMap
) -> ActionRejection | None:
    del state
    dest = action.target_room
    if dest is None:
        return ActionRejection("move_no_target", "MOVE without a destination room.")
    if dest not in game_map.neighbours(player.location):
        return ActionRejection(
            "move_not_adjacent", f"{player.location} is not walk-adjacent to {dest}."
        )
    return None


def _check_vent(
    state: GameState, player: PlayerState, action: Action, game_map: GameMap
) -> ActionRejection | None:
    del state
    if not player.is_impostor:
        return ActionRejection("vent_not_impostor", "Only impostors can use vents.")
    dest = action.target_room
    if dest is None:
        return ActionRejection("vent_no_target", "VENT without a destination room.")
    if dest not in game_map.vents(player.location):
        return ActionRejection(
            "vent_not_connected", f"No vent connects {player.location} to {dest}."
        )
    return None


def _check_kill(
    state: GameState, player: PlayerState, action: Action, game_map: GameMap
) -> ActionRejection | None:
    del game_map
    if not player.is_impostor:
        return ActionRejection("kill_not_impostor", "Only impostors can kill.")
    if player.kill_cooldown_remaining > 0:
        return ActionRejection(
            "kill_on_cooldown",
            f"Kill cooldown has {player.kill_cooldown_remaining} timestep(s) left.",
        )
    victim = state.player_by_name(action.target_name or "")
    if victim is None:
        return ActionRejection("kill_unknown_target", f"No such player: {action.target_name!r}.")
    if not victim.alive:
        return ActionRejection("kill_dead_target", f"{victim.name} is already dead.")
    if victim.index == player.index:
        return ActionRejection("kill_self", "A player cannot kill themselves.")
    if victim.location != player.location:
        return ActionRejection("kill_not_co_located", f"{victim.name} is not in {player.location}.")
    if victim.is_impostor:
        return ActionRejection("kill_teammate", f"{victim.name} is a fellow impostor.")
    return None


def _check_task(
    state: GameState, player: PlayerState, action: Action, game_map: GameMap
) -> ActionRejection | None:
    del state, game_map
    real = action.type is ActionType.COMPLETE_TASK
    if real and player.is_impostor:
        return ActionRejection("task_impostor_real", "Impostors have no real tasks.")
    if not real and not player.is_impostor:
        return ActionRejection("task_crewmate_fake", "Crewmates cannot fake tasks.")
    if action.task is None:
        return ActionRejection("task_missing", "Task action without a task.")
    if action.task not in player.tasks:
        return ActionRejection("task_not_assigned", f"{action.task.name} is not assigned.")
    index = player.tasks.index(action.task)
    if index in player.completed_tasks:
        return ActionRejection("task_already_done", f"{action.task.name} is already complete.")
    if action.task.room != player.location:
        return ActionRejection(
            "task_wrong_room",
            f"{action.task.name} is in {action.task.room}, not {player.location}.",
        )
    return None


def _check_report(
    state: GameState, player: PlayerState, action: Action, game_map: GameMap
) -> ActionRejection | None:
    del action, game_map
    if not state.dead_bodies.get(player.location):
        return ActionRejection("report_no_body", f"No unreported body in {player.location}.")
    return None


def _check_call_meeting(
    state: GameState, player: PlayerState, action: Action, game_map: GameMap
) -> ActionRejection | None:
    del action
    if player.location != game_map.emergency_button_room:
        return ActionRejection(
            "meeting_wrong_room",
            f"The emergency button is in {game_map.emergency_button_room}.",
        )
    if state.buttons_used >= state.max_num_buttons:
        return ActionRejection("meeting_budget_spent", "The emergency button budget is spent.")
    if state.dead_bodies.get(player.location):
        return ActionRejection(
            "meeting_body_present", "A body here must be reported, not button-pressed."
        )
    return None


def _check_security(
    state: GameState, player: PlayerState, action: Action, game_map: GameMap
) -> ActionRejection | None:
    del state, action
    if player.location != game_map.security_camera_room:
        return ActionRejection(
            "security_wrong_room", f"The cameras are in {game_map.security_camera_room}."
        )
    return None


def _check_vote(
    state: GameState, player: PlayerState, action: Action, game_map: GameMap
) -> ActionRejection | None:
    del game_map
    target = action.target_name
    if target is None:
        return ActionRejection("vote_no_target", "VOTE without a target.")
    if target == "Skip":
        return None
    victim = state.player_by_name(target)
    if victim is None:
        return ActionRejection("vote_unknown_target", f"No such player: {target!r}.")
    if not victim.alive:
        return ActionRejection("vote_dead_target", f"{target} is already out of the game.")
    if victim.index == player.index:
        return ActionRejection("vote_self", "A player cannot vote for themselves.")
    return None


_CHECKS = {
    ActionType.MOVE: _check_move,
    ActionType.VENT: _check_vent,
    ActionType.KILL: _check_kill,
    ActionType.COMPLETE_TASK: _check_task,
    ActionType.FAKE_TASK: _check_task,
    ActionType.REPORT: _check_report,
    ActionType.CALL_MEETING: _check_call_meeting,
    ActionType.CHECK_SECURITY: _check_security,
    ActionType.VOTE: _check_vote,
}


def safe_fallback(actions: list[Action]) -> Action:
    wait = next((a for a in actions if a.type is ActionType.WAIT), None)
    if wait is not None:
        return wait
    skip = next((a for a in actions if a.type is ActionType.VOTE and a.target_name == "Skip"), None)
    return skip or actions[0]


__all__ = ["ActionRejection", "safe_fallback", "validate_action"]
