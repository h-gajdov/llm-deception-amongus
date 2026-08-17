from __future__ import annotations

import random

from ..game.agent_api import Decision, DecisionContext
from ..game.enums import ActionType
from .prompts import build_prompt


_RISKY_KILL_CHANCE = 0.2


_IMPOSTOR_HONEST_CHANCE = 0.35


class HeuristicAgent:
    def __init__(self, seed: int = 0, model_name: str = "heuristic") -> None:
        self._rng = random.Random(seed)
        self.model_name = model_name

    def act(self, ctx: DecisionContext) -> Decision:
        action = self._choose(ctx)
        speech = self._speak(ctx) if action.type is ActionType.SPEAK else None
        bundle = build_prompt(ctx.view)
        rendered = action.render() if speech is None else f"SPEAK: {speech}"
        raw = (
            f"[Condensed Memory]\n{ctx.view.memory_text}\n"
            f"[Thinking Process]\n(heuristic policy)\n"
            f"[Action] {rendered}"
        )
        return Decision(
            action=action,
            system_prompt=bundle.system_prompt,
            prompt_sections=bundle.sections,
            user_prompt=bundle.user_prompt,
            response={
                "Condensed Memory": ctx.view.memory_text,
                "Thinking Process": "(heuristic policy)",
                "Action": rendered,
            },
            full_response=raw,
            speech=speech,
            parse_status="valid",
            requested_action=action,
            requested_action_text=rendered,
            spans=bundle.spans,
        )

    def _choose(self, ctx: DecisionContext):
        actions = ctx.actions
        by_type: dict[ActionType, list] = {}
        for action in actions:
            by_type.setdefault(action.type, []).append(action)

        if ActionType.VOTE in by_type:
            return self._vote(ctx, by_type[ActionType.VOTE])
        if ActionType.SPEAK in by_type:
            return by_type[ActionType.SPEAK][0]
        if ActionType.REPORT in by_type:
            return by_type[ActionType.REPORT][0]
        if ActionType.KILL in by_type and self._take_kill(ctx):
            return self._rng.choice(by_type[ActionType.KILL])
        for verb in (ActionType.COMPLETE_TASK, ActionType.FAKE_TASK):
            if verb in by_type:
                return by_type[verb][0]
        if ActionType.MOVE in by_type:
            return self._move(ctx, by_type[ActionType.MOVE])
        return actions[0]

    def _take_kill(self, ctx: DecisionContext) -> bool:
        bystanders = len(ctx.view.co_located) - 1
        if bystanders <= 0:
            return True
        return self._rng.random() < _RISKY_KILL_CHANCE

    def _move(self, ctx: DecisionContext, moves: list):
        target_room = self._next_task_room(ctx)
        if target_room is not None:
            path = ctx.game_map.shortest_walk_path(ctx.view.location, target_room)
            if len(path) > 1:
                step = next((m for m in moves if m.target_room == path[1]), None)
                if step is not None:
                    return step
        return self._rng.choice(moves)

    @staticmethod
    def _next_task_room(ctx: DecisionContext) -> str | None:
        for entry in ctx.view.role_private.tasks:
            if entry.endswith("[DONE]"):
                continue
            start, end = entry.rfind("("), entry.rfind(")")
            if 0 < start < end:
                return entry[start + 1 : end]
        return None

    def _vote(self, ctx: DecisionContext, votes: list):
        suspicions = ctx.player.private.memory.suspicions
        if suspicions:
            ranked = sorted(suspicions.items(), key=lambda kv: (-len(kv[1]), kv[0]))
            for name, _ in ranked:
                choice = next((v for v in votes if v.target_name == name), None)
                if choice is not None:
                    return choice
        return next((v for v in votes if v.target_name == "Skip"), votes[0])

    def _speak(self, ctx: DecisionContext) -> str:
        view = ctx.view
        witnessed_kill = next(
            (p for p in ctx.player.private.perceptions if p.event_type.value == "kill"),
            None,
        )
        is_impostor = view.role_private.tasks_are_fake

        if witnessed_kill is not None and (
            not is_impostor or self._rng.random() < _IMPOSTOR_HONEST_CHANCE
        ):
            victim = witnessed_kill.target_name or "someone"
            if witnessed_kill.actor_identified and witnessed_kill.actor_name:
                return (
                    f"I saw {witnessed_kill.actor_name} kill {victim} in "
                    f"{witnessed_kill.room}. {witnessed_kill.actor_name} is the impostor."
                )
            guess = self._guess_suspect(ctx)
            if guess:
                return (
                    f"I saw {victim} killed in {witnessed_kill.room}. "
                    f"I think {guess} is the impostor."
                )

        if is_impostor and self._rng.random() >= _IMPOSTOR_HONEST_CHANCE:
            elsewhere = self._room_i_was_not_in(ctx)
            return f"I was in {elsewhere} doing my tasks. I am not the impostor."

        last_room = self._last_own_room(ctx)
        body = next(
            (p for p in ctx.player.private.perceptions if p.event_type.value == "body_sighted"),
            None,
        )
        if body is not None:
            return (
                f"I was in {last_room}. I found {body.target_name or 'a body'} dead in {body.room}."
            )
        return f"I was in {last_room}. I did not see anything."

    @staticmethod
    def _last_own_room(ctx: DecisionContext) -> str:
        route = ctx.player.private.memory.own_route
        return route[-1][1] if route else ctx.view.location

    def _room_i_was_not_in(self, ctx: DecisionContext) -> str:
        here = ctx.view.location
        far = [
            room
            for room in ctx.game_map.rooms
            if len(ctx.game_map.shortest_walk_path(here, room)) >= 4
        ]
        candidates = far or [room for room in ctx.game_map.rooms if room != here]
        return self._rng.choice(candidates) if candidates else here

    def _guess_suspect(self, ctx: DecisionContext) -> str | None:
        others = [name for name in ctx.view.meeting_roster if name != ctx.player.name]
        return self._rng.choice(others) if others else None


__all__ = ["HeuristicAgent"]
