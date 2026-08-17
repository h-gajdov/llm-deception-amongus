from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .actions import Action
from .game_map import GameMap
from .state import GameState, PlayerState
from .view import PlayerView


@dataclass
class DecisionContext:
    state: GameState
    player: PlayerState
    actions: list[Action]
    game_map: GameMap
    view: PlayerView
    retry_hint: str | None = None


@dataclass
class Decision:
    action: Action
    system_prompt: str
    prompt_sections: dict[str, str]
    user_prompt: str
    response: dict[str, str]
    full_response: str
    speech: str | None = None
    declared_speech: dict[str, object] | None = None
    parse_status: str = "valid"
    requested_action: Action | None = None
    requested_action_text: str = ""
    requested_action_valid: bool = True
    execution_source: str = "model"
    fallback_reason: str | None = None
    attempts: list[dict[str, str]] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    spans: dict[str, list[int]] = field(default_factory=dict)


class Agent(Protocol):
    model_name: str
    pass

    def act(self, ctx: DecisionContext) -> Decision: ...


@dataclass
class ScriptedAgent:
    model_name: str = "scripted"

    def act(self, ctx: DecisionContext) -> Decision:
        from .enums import ActionType

        action = ctx.actions[0]
        speech = None
        if action.type is ActionType.SPEAK:
            speech = f"I was in {ctx.player.location}."
        rendered = action.render() if speech is None else f"SPEAK: {speech}"
        return Decision(
            action=action,
            system_prompt="(scripted agent)",
            prompt_sections={"observation": "", "phase": ctx.state.phase.value},
            user_prompt="",
            response={
                "Condensed Memory": ctx.view.memory_text,
                "Thinking Process": "(scripted agent) choosing the first legal action.",
                "Action": rendered,
            },
            full_response=rendered,
            speech=speech,
            parse_status="valid",
            requested_action=action,
            requested_action_text=rendered,
        )


__all__ = ["Agent", "Decision", "DecisionContext", "ScriptedAgent"]
