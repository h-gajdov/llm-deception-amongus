

from __future__ import annotations

from ..config import AgentConfig
from ..game.actions import Action
from ..game.agent_api import Decision, DecisionContext
from ..game.enums import ActionType
from ..game.validation import safe_fallback
from ..logging import get_logger
from .llm.base import LLMClient, LLMResponse
from .parser import ActionMatch, match_action, parse_sections, parse_speech_intent, strip_think_tags
from .prompts import PromptBundle, build_prompt

logger = get_logger()

                                                                             
                                                                               
                                
_RETRY_NOTES: dict[str, str] = {
    "empty_action_line": "the [Action] line was missing or empty.",
    "speak_not_available": (
        "you answered with SPEAK, but SPEAK is not one of the Available actions this turn."
    ),
    "wait_not_available": (
        "you answered with WAIT, but WAIT is not one of the Available actions this turn."
    ),
    "ambiguous_action_line": "the [Action] line did not identify a single available action.",
    "not_an_available_action": (
        "the [Action] line was not one of the Available actions. Copy one line from that "
        "list exactly, without changing the room, the target or the wording."
    ),
}
_DEFAULT_RETRY_NOTE = "the [Action] line did not match any available action."

                                                                   
_PARSE_STATUS = {"exact": "valid", "normalized": "normalized"}


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
                    "requested_action": candidate.match.requested_text,
                    "reason": candidate.match.reason,
                }
            )
            outcome = candidate
            if candidate.match.resolved:
                break
            hint = _RETRY_NOTES.get(candidate.match.reason, _DEFAULT_RETRY_NOTE)
            warnings.append(f"unmatched_action_retried:{candidate.match.reason or 'unknown'}")
            logger.debug(
                "{} asked for {!r}, which is not an available action ({}); retrying.",
                self.model_name,
                candidate.match.requested_text,
                candidate.match.reason,
            )

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
    speaking = match.action is not None and match.action.type is ActionType.SPEAK
    declared = parse_speech_intent(sections.get("Speech Intent", "")) if speaking else None
    return _Attempt(raw, sections, match, completion.thinking, declared)


def _fallback(actions: list[Action]) -> tuple[Action, str]:
    pass
    wait = next((a for a in actions if a.type is ActionType.WAIT), None)
    if wait is not None:
        return wait, "fallback_wait"
    return safe_fallback(actions), "fallback_safe_action"


def _consistency_warnings(attempt: _Attempt, ctx: DecisionContext) -> list[str]:
    pass
    warnings: list[str] = []
    if attempt.match.status == "normalized":
        warnings.append("action_matched_after_formatting_normalization")
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
    match = attempt.match
    if match.action is not None:
        action: Action = match.action
        speech = match.speech
        status = _PARSE_STATUS[match.status]
        source = "model" if match.status == "exact" else "model_normalized"
        fallback_reason: str | None = None
    else:
        action, source = _fallback(ctx.actions)
        speech = None
        status = "fallback"
        fallback_reason = match.reason or "unmatched_action_line"
        warnings.append("action_fallback_after_retries")
        logger.warning(
            "No available action matched after {} attempt(s); executing {}.",
            len(attempts),
            action.render(),
        )

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
        requested_action=match.action,
        requested_action_text=match.requested_text,
        requested_action_valid=match.resolved,
        execution_source=source,
        fallback_reason=fallback_reason,
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
