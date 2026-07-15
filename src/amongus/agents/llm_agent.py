

from __future__ import annotations

from ..game.agent_api import Decision, DecisionContext
from ..game.enums import Role
from ..logging import get_logger
from .llm.base import LLMClient
from .parser import match_action, parse_sections, strip_think_tags
from .prompts import build_system_prompt, build_user_prompt, render_user_message

logger = get_logger()


class LLMAgent:
    pass

    def __init__(self, client: LLMClient) -> None:
        pass
        self._client = client
        self.model_name = client.model

    def act(self, ctx: DecisionContext) -> Decision:
        pass
        system_prompt = build_system_prompt(ctx.player, self._impostor_names(ctx))
        prompt = build_user_prompt(ctx.state, ctx.player, ctx.actions, ctx.game_map)
        user_message = render_user_message(prompt)

        completion = self._client.chat(system_prompt, user_message)
        raw = completion.combined()
        sections = parse_sections(strip_think_tags(raw))
        action, speech = match_action(sections["Action"], ctx.actions)

        response = {
            "Condensed Memory": sections["Condensed Memory"] or ctx.player.last_memory,
            "Thinking Process": sections["Thinking Process"] or completion.thinking,
            "Action": action.render() if speech is None else f"SPEAK: {speech}",
        }
        return Decision(
            action=action,
            system_prompt=system_prompt,
            prompt=prompt,
            response=response,
            full_response=raw,
            speech=speech,
        )

    @staticmethod
    def _impostor_names(ctx: DecisionContext) -> list[str]:
        pass
        if ctx.player.role is not Role.IMPOSTOR:
            return []
        return [p.name for p in ctx.state.players if p.is_impostor]


__all__ = ["LLMAgent"]
