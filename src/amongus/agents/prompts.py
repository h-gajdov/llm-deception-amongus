

from __future__ import annotations

from ..game.actions import Action
from ..game.enums import Phase, Role
from ..game.game_map import SKELD_MAP_DESCRIPTION, GameMap
from ..game.observation import build_all_info
from ..game.state import GameState, PlayerState

_OUTPUT_FORMAT = """Output format:
[Condensed Memory]
{memory}
[Thinking Process]
{thought}
[Action] {action}

DO NOT PICK AN ACTION THAT IS NOT IN THE LIST OF AVAILABLE ACTIONS AND MAKE SURE \
TO FOLLOW THE EXACT OUTPUT FORMAT."""

_CREWMATE_TEMPLATE = """
You are {name}. You are a Crewmate on the spaceship Skeld. Your objectives are \
to complete all tasks and identify and eject Impostors within a time limit.
## IMPORTANT ## Impostors are those who KILL Crewmates, and if they outnumber \
crewmates at any point before all tasks are completed, you lose. They also can \
VENT between non-connected rooms. Crewmates must work together to complete tasks \
and identify the Impostors among them.
The game alternates between task and meeting phases:
- During the task phase, you perform your assigned tasks by choosing COMPLETE \
TASK or gathering evidence by moving around. You can also CALL MEETING if you \
suspect an Impostor or witness a crime. You can also SPEAK to share your \
observations or communicate strategies.
- During the meeting phase, players can only speak. Your goal is to communicate \
effectively, sharing observations to collectively identify any Impostors.

{map}

Note that only Impostors can KILL and VENT.

When presented with a list of available actions (e.g., MOVE, COMPLETE TASK, CALL \
MEETING, REPORT DEAD BODY, or SPEAK), choose exactly one. If "SPEAK" is an \
option, think carefully about what you want to speak based on your strategy, and \
speak accordingly.
Make a summarization of the past observed events and taken actions under \
[Condensed Memory], make a thoughtful and thorough plan under [Thinking Process] \
while thinking very carefully about the strategy you want to employ to win, and \
then choose the action from Available actions under [Action].

{output_format}
"""

_IMPOSTOR_TEMPLATE = """
You are {name}. You are an Impostor on the spaceship Skeld. Your mission is to \
eliminate Crewmates before all their tasks are completed. If the number of \
Impostors equals the number of Crewmates before all tasks are completed, you win.
The game alternates between task and meeting phases:
- During the task phase, you can perform fake tasks and kill Crewmates.
- During the meeting phase, players can only speak. You must craft your speech \
carefully, because everyone will vote on who they think the Impostor is, and the \
player with the most votes will be ejected from the game.
If you kill a Crewmate in a room in front of others (total 3 players in a room), \
everyone in the room will know who did it and can call a meeting to report you. \
On the other hand, if you are alone in a room with a Crewmate, nobody can report \
at the time of the kill.

{map}

Note that only Impostors can KILL and VENT.

When given a list of available actions (e.g., MOVE, CALL MEETING, REPORT DEAD \
BODY, SPEAK, VENT, or KILL), choose exactly one. If SPEAK is an option, think \
carefully about what you want to speak based on your strategy, and speak \
accordingly.
Make a summarization of the past observed events and taken actions under \
[Condensed Memory], make a thoughtful and thorough plan under [Thinking Process] \
while thinking very carefully about the strategy you want to employ to win, and \
then choose the action from Available actions under [Action].

{output_format}
List of impostors: [{impostors}]
"""

                                                                           
                                             
SPEAK_INSTRUCTION = (
    "When you choose SPEAK, write what you say out loud on the [Action] line as "
    "`SPEAK: <your message>`."
)


def build_system_prompt(player: PlayerState, impostor_names: list[str]) -> str:
    pass
    if player.role is Role.IMPOSTOR:
        return _IMPOSTOR_TEMPLATE.format(
            name=player.name,
            map=SKELD_MAP_DESCRIPTION,
            output_format=_OUTPUT_FORMAT,
            impostors=", ".join(impostor_names),
        )
    return _CREWMATE_TEMPLATE.format(
        name=player.name,
        map=SKELD_MAP_DESCRIPTION,
        output_format=_OUTPUT_FORMAT,
    )


def build_user_prompt(
    state: GameState,
    player: PlayerState,
    actions: list[Action],
    game_map: GameMap,
) -> dict[str, str]:
    pass
    all_info = build_all_info(state, player, actions, game_map)
    if state.phase is Phase.MEETING:
        all_info = f"{all_info}\n\n{SPEAK_INSTRUCTION}"
    return {
        "Summarization": player.last_summarization,
        "All Info": all_info,
        "Memory": player.last_memory,
        "Phase": state.phase.value,
    }


def render_user_message(prompt: dict[str, str]) -> str:
    pass
    return (
        f"[Memory]\n{prompt['Memory']}\n\n"
        f"[Previous Thinking]\n{prompt['Summarization']}\n\n"
        f"{prompt['All Info']}"
    )


__all__ = [
    "SPEAK_INSTRUCTION",
    "build_system_prompt",
    "build_user_prompt",
    "render_user_message",
]
