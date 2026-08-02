

from __future__ import annotations

from .enums import Phase
from .view import PlayerView

_TASK_PHASE_BLURB = (
    "In this phase, crewmates complete tasks and gather evidence; impostors "
    "fake tasks and look for a chance to kill."
)
_MEETING_PHASE_BLURB = (
    "In this phase, players discuss and then vote to eject a suspected impostor. "
    "Only speech is possible."
)

_NO_WITNESSED = "You have not witnessed anything yet."
_NO_HEARD = "You have not heard anyone make a claim yet."
_NO_PUBLIC = "Nothing has been publicly announced yet."
_NO_ACTIONS = "You have not acted yet."

                                                                               
                                                                            
                                                    
_HEARSAY_NOTE = (
    "These are claims other players made. They may be true, mistaken, or "
    "deliberately false. Do not treat them as things you saw."
)

                                                                           
                                                                                
                                                                       
PLACEHOLDER_LINES: frozenset[str] = frozenset(
    {_NO_WITNESSED, _NO_HEARD, _NO_PUBLIC, _NO_ACTIONS, _HEARSAY_NOTE}
)


                                                                               
                                                                              
SECTION_SEPARATOR = "\n\n"


def render_sections(view: PlayerView) -> list[tuple[str, str]]:
    pass
    sections = [
        ("header", _header(view)),
        ("role_private_context", _role_private_section(view)),
        ("own_actions", _own_actions_section(view)),
        ("witnessed", _witnessed_section(view)),
        ("heard", _heard_section(view)),
        ("public_state", _public_section(view)),
        ("location", _location_section(view)),
        ("memory_context", _memory_section(view)),
        ("action_list", _available_actions_section(view)),
    ]
    return [(name, text) for name, text in sections if text]


def render_view(view: PlayerView) -> str:
    pass
    return SECTION_SEPARATOR.join(text for _, text in render_sections(view))


def _header(view: PlayerView) -> str:
    pass
    blurb = _TASK_PHASE_BLURB if view.phase is Phase.TASK else _MEETING_PHASE_BLURB
    return (
        f"Game time: {view.timestep}/{view.max_timesteps}\n"
        f"Current phase: {view.phase.value}\n"
        f"{blurb}"
    )


def _role_private_section(view: PlayerView) -> str:
    pass
    info = view.role_private
    lines = [
        "Your role-private information",
        f"You are {view.player_name}. Your role: {info.role.value}.",
        f"Objective: {info.objective}",
    ]
    if view.personality:
        lines.append(f"Your disposition: {view.personality}")
    if info.teammate_names:
        lines.append(
            "Your fellow impostors: " + ", ".join(info.teammate_names) + ". "
            "No one else knows this. Never kill or genuinely accuse them."
        )
    if info.kill_cooldown_remaining is not None:
        ready = (
            "ready now"
            if info.kill_cooldown_remaining == 0
            else (f"ready in {info.kill_cooldown_remaining} timestep(s)")
        )
        lines.append(f"Your kill ability is {ready}.")
    label = "Your fake tasks (cover only)" if info.tasks_are_fake else "Your assigned tasks"
    lines.append(f"{label}: " + ("; ".join(info.tasks) if info.tasks else "none"))
    return "\n".join(lines)


def _own_actions_section(view: PlayerView) -> str:
    pass
    body = "\n".join(view.own_actions) if view.own_actions else _NO_ACTIONS
    return f"Your own previous actions\n{body}"


def _witnessed_section(view: PlayerView) -> str:
    pass
    body = "\n".join(view.witnessed) if view.witnessed else _NO_WITNESSED
    return f"Events you directly witnessed\n{body}"


def _heard_section(view: PlayerView) -> str:
    pass
    if not view.heard:
        return f"Statements you heard\n{_NO_HEARD}"
    return f"Statements you heard\n{_HEARSAY_NOTE}\n" + "\n".join(view.heard)


def _public_section(view: PlayerView) -> str:
    pass
    lines = ["Current public game state"]
    lines.append("\n".join(view.public_facts) if view.public_facts else _NO_PUBLIC)
    if view.phase is Phase.MEETING:
        if view.meeting_reason:
            lines.append(f"Meeting called because: {view.meeting_reason}")
        lines.append("Players in this meeting: " + ", ".join(view.meeting_roster))
        transcript = (
            "\n".join(view.meeting_transcript)
            if view.meeting_transcript
            else ("No one has spoken yet this meeting.")
        )
        lines.append(f"Discussion so far:\n{transcript}")
    return "\n".join(lines)


def _location_section(view: PlayerView) -> str:
    pass
    if view.phase is Phase.MEETING:
        return "Current location\nEveryone has gathered in the meeting room."
    others = ", ".join(view.co_located) if view.co_located else "no one else"
    return (
        "Current location\n"
        f"You are in {view.location}. Also here: {others}.\n"
        f"Rooms you can walk to from here: {', '.join(view.adjacent_rooms)}."
    )


def _memory_section(view: PlayerView) -> str:
    pass
    return f"Your memory of the game so far\n{view.memory_text}"


def _available_actions_section(view: PlayerView) -> str:
    pass
    lines = "\n".join(f"{i}. {a}" for i, a in enumerate(view.available_actions, start=1))
    return f"Available actions\n{lines}"


__all__ = ["PLACEHOLDER_LINES", "SECTION_SEPARATOR", "render_sections", "render_view"]
