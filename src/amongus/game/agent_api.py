

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .actions import Action
from .game_map import GameMap
from .state import GameState, PlayerState


@dataclass
class DecisionContext:
    pass

    state: GameState
    player: PlayerState
    actions: list[Action]
    game_map: GameMap


@dataclass
class Decision:
    pass

    action: Action
    system_prompt: str
    prompt: dict[str, str]
    response: dict[str, str]
    full_response: str
    speech: str | None = None


class Agent(Protocol):
    pass

    model_name: str
    pass

    def act(self, ctx: DecisionContext) -> Decision:
        pass
        ...


@dataclass
class ScriptedAgent:
    pass

    model_name: str = "scripted"

    def act(self, ctx: DecisionContext) -> Decision:
        pass
        action = ctx.actions[0]
        rendered = action.render()
        response = {
            "Condensed Memory": ctx.player.last_memory,
            "Thinking Process": "(scripted agent) choosing the first legal action.",
            "Action": rendered,
        }
        prompt = {
            "All Info": "",
            "Memory": ctx.player.last_memory,
            "Phase": ctx.state.phase.value,
        }
        return Decision(
            action=action,
            system_prompt="(scripted agent)",
            prompt=prompt,
            response=response,
            full_response=rendered,
            speech="I have nothing to add." if rendered == "SPEAK" else None,
        )


__all__ = ["Agent", "Decision", "DecisionContext", "ScriptedAgent"]
