

from __future__ import annotations

from .actions import Action
from .enums import Phase
from .game_map import GameMap
from .state import GameState, PlayerState

_TASK_PHASE_BLURB = (
    "In this phase, Crewmates should try to complete all tasks or identify "
    "Impostor. Impostor should try to kill Crewmates."
)
_MEETING_PHASE_BLURB = (
    "In this phase, players discuss and then vote to eject a suspected Impostor. "
    "Players can only speak; no movement or tasks are possible."
)

                                                                           
                                                                 
MAX_OBSERVATION_LINES = 15


def build_all_info(
    state: GameState,
    player: PlayerState,
    actions: list[Action],
    game_map: GameMap,
) -> str:
    pass
    sections = [
        _header(state),
        _location_section(state, player),
        _observation_section(player),
        _action_history_section(player),
    ]
    if state.phase is Phase.MEETING:
        sections.append(_discussion_section(state))
    else:
        sections.append(_tasks_section(player, game_map))
    sections.append(_available_actions_section(actions))
    return "\n\n".join(section for section in sections if section)


def _header(state: GameState) -> str:
    pass
    blurb = _TASK_PHASE_BLURB if state.phase is Phase.TASK else _MEETING_PHASE_BLURB
    return (
        f"Game Time: {state.timestep}/{state.max_timesteps}\n"
        f"Current phase: {state.phase.value}\n"
        f"{blurb}"
    )


def _location_section(state: GameState, player: PlayerState) -> str:
    pass
    if state.phase is Phase.MEETING:
        others = ", ".join(p.name for p in state.alive_players())
        return f"Meeting in progress.\nPlayers present: {others}"
    here = state.players_in_room(player.location)
    names = ", ".join(p.name for p in here)
    return f"Current Location: {player.location}\nPlayers in {player.location}: {names}"


def _observation_section(player: PlayerState) -> str:
    pass
    if not player.observations:
        return "Observation history:\nNo observations have been made yet."
    recent = player.observations[-MAX_OBSERVATION_LINES:]
    lines = "\n".join(f"{i}. {obs.render()}" for i, obs in enumerate(recent, start=1))
    return f"Observation history:\n{lines}"


def _action_history_section(player: PlayerState) -> str:
    pass
    if not player.action_history:
        return "Action history:\nNo actions have been taken yet."
    lines = "\n".join(player.action_history[-MAX_OBSERVATION_LINES:])
    return f"Action history:\n{lines}"


def _tasks_section(player: PlayerState, game_map: GameMap) -> str:
    pass
    label = "Your Assigned Tasks:" if not player.is_impostor else "Your Fake Tasks (for cover):"
    if not player.tasks:
        return f"{label}\nNone."
    lines: list[str] = []
    for i, task in enumerate(player.tasks, start=1):
        done = " [DONE]" if (i - 1) in player.completed_tasks else ""
        path = game_map.shortest_walk_path(player.location, task.room)
        path_str = "->".join(path) if path else "unreachable"
        lines.append(f"{i}. {task.length.value}: {task.name} ({task.room}){done}\nPath: {path_str}")
    return f"{label}\n" + "\n".join(lines)


def _discussion_section(state: GameState) -> str:
    pass
    header = "Discussion:"
    if state.meeting_reason:
        header = f"Meeting called: {state.meeting_reason}\n{header}"
    if not state.meeting_transcript:
        return f"{header}\nNo one has spoken yet."
    return f"{header}\n" + "\n".join(state.meeting_transcript)


def _available_actions_section(actions: list[Action]) -> str:
    pass
    lines = "\n".join(f"{i}. {a.render()}" for i, a in enumerate(actions, start=1))
    return f"Available actions:\n{lines}"


__all__ = ["MAX_OBSERVATION_LINES", "build_all_info"]
