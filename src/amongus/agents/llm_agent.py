

from __future__ import annotations

from ..config import AgentConfig
from ..game.agent_api import Decision, DecisionContext
from ..game.enums import ActionType
from ..logging import get_logger
from .llm.base import LLMClient, LLMResponse
from .parser import ActionMatch, match_action, parse_sections, parse_speech_intent, strip_think_tags
from .prompts import PromptBundle, build_prompt

logger = get_logger()


class LLMAgent:
    pass

    def __init__(self, client: LLMClient, config: AgentConfig | None = None) -> None:
        pass
        self._client = client
        self._config = config or AgentConfig()
        self.model_name = client.model

    def act(self, ctx: DecisionContext) -> Decision:
        pass
        attempts: list[dict[str, str]] = []
        warnings: list[str] = []
        hint: str | None = ctx.retry_hint
        bundle = build_prompt(ctx.view, self._config, hint)
        outcome: _Attempt | None = None

        for attempt_no in range(self._config.max_parse_retries + 1):
            bundle = build_prompt(ctx.view, self._config, hint)
            completion = self._client.chat(bundle.system_prompt, bundle.user_prompt)
            candidate = _parse(completion, ctx)
            attempts.append(
                {
                    "attempt": str(attempt_no),
                    "raw": candidate.raw,
                    "status": candidate.match.status,
                }
            )
            if candidate.match.status != "none":
                outcome = candidate
                break
            hint = "the [Action] line did not match any available action."
            warnings.append("unparseable_action_retried")
            logger.debug("Unparseable action from {}; retrying.", self.model_name)
            outcome = candidate

        assert outcome is not None
        warnings.extend(_consistency_warnings(outcome, ctx))
        return _build_decision(outcome, bundle, attempts, warnings, ctx)


class _Attempt:
    pass

    __slots__ = ("declared", "match", "raw", "sections", "thinking")

    def __init__(
        self,
        raw: str,
        sections: dict[str, str],
        match: ActionMatch,
        thinking: str,
        declared: dict[str, object] | None,
    ) -> None:
        pass
        self.raw = raw
        self.sections = sections
        self.match = match
        self.thinking = thinking
        self.declared = declared


def _parse(completion: LLMResponse, ctx: DecisionContext) -> _Attempt:
    pass
    raw = completion.combined()
    sections = parse_sections(strip_think_tags(raw))
    match = match_action(sections["Action"], ctx.actions)
    declared = (
        parse_speech_intent(sections.get("Speech Intent", ""))
        if match.action.type is ActionType.SPEAK
        else None
    )
    return _Attempt(raw, sections, match, completion.thinking, declared)


def _consistency_warnings(attempt: _Attempt, ctx: DecisionContext) -> list[str]:
    pass
    warnings: list[str] = []
    if attempt.match.status == "fuzzy":
        warnings.append("action_recovered_by_fuzzy_match")
    if not attempt.sections["Condensed Memory"].strip():
        warnings.append("empty_condensed_memory")

    text = f"{attempt.sections['Thinking Process']} {attempt.match.speech or ''}".lower()
    known_names = {p.lower() for p in ctx.view.role_private.teammate_names}
    for name in known_names:
        if name != ctx.player.name.lower() and name in text and "crewmate" in text:
            warnings.append("rationale_calls_known_teammate_a_crewmate")
            break

    if attempt.match.speech and attempt.declared:
        target = attempt.declared.get("target_player")
        if (
            isinstance(target, str)
            and target
            and target.lower() not in (attempt.match.speech or "").lower()
        ):
            warnings.append("declared_target_absent_from_utterance")
    return warnings


def _build_decision(
    attempt: _Attempt,
    bundle: PromptBundle,
    attempts: list[dict[str, str]],
    warnings: list[str],
    ctx: DecisionContext,
) -> Decision:
    pass
    action, speech = attempt.match.action, attempt.match.speech
    status = {"exact": "valid", "fuzzy": "recovered", "none": "fallback"}[attempt.match.status]
    rationale = attempt.sections["Thinking Process"] or attempt.thinking
    response = {
        "Condensed Memory": attempt.sections["Condensed Memory"] or ctx.view.memory_text,
        "Thinking Process": rationale,
        "Action": action.render() if speech is None else f"SPEAK: {speech}",
    }
    spans = dict(bundle.spans)
    spans.update(_response_spans(attempt, bundle))
    return Decision(
        action=action,
        system_prompt=bundle.system_prompt,
        prompt_sections=bundle.sections,
        user_prompt=bundle.user_prompt,
        response=response,
        full_response=attempt.raw,
        speech=speech,
        declared_speech=attempt.declared,
        parse_status=status,
        attempts=attempts,
        validation_warnings=warnings,
        spans=spans,
    )


def _response_spans(attempt: _Attempt, bundle: PromptBundle) -> dict[str, list[int]]:
    pass
    base = bundle.response_offset()
    raw = attempt.raw
    spans: dict[str, list[int]] = {"raw_response": [base, base + len(raw)]}
    for name, needle in (
        ("generated_rationale", attempt.sections["Thinking Process"]),
        ("generated_action", attempt.sections["Action"]),
        ("spoken_utterance", attempt.match.speech or ""),
    ):
        if not needle:
            continue
        idx = raw.find(needle)
        if idx >= 0:
            spans[name] = [base + idx, base + idx + len(needle)]
    return spans


__all__ = ["LLMAgent"]
