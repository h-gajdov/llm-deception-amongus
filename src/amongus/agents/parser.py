

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..game.actions import Action
from ..game.enums import ActionType

_SECTION_RE = re.compile(
    r"\[\s*(Condensed Memory|Thinking Process|Action|Speech Intent)\s*\]\s*:?\s*",
    re.IGNORECASE,
)
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_LEADING_ENUM_RE = re.compile(r"^\s*\d+[.)]\s*")


def strip_think_tags(text: str) -> str:
    pass
    return _THINK_TAG_RE.sub("", text)


def parse_sections(text: str) -> dict[str, str]:
    pass
    result = {
        "Condensed Memory": "",
        "Thinking Process": "",
        "Action": "",
        "Speech Intent": "",
    }
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
                                                                          
        result["Action"] = text.strip()
        return result
    for i, match in enumerate(matches):
        key = _canonical_key(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result[key] = text[start:end].strip()
    return result


def _canonical_key(raw: str) -> str:
    pass
    lowered = raw.lower()
    if "memory" in lowered:
        return "Condensed Memory"
    if "thinking" in lowered:
        return "Thinking Process"
    if "speech" in lowered:
        return "Speech Intent"
    return "Action"


def parse_speech_intent(text: str) -> dict[str, object] | None:
    pass
    stripped = text.strip()
    if not stripped:
        return None
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalise(text: str) -> str:
    pass
    text = _LEADING_ENUM_RE.sub("", text.strip())
    return re.sub(r"\s+", " ", text).lower().rstrip(".")


@dataclass(frozen=True)
class ActionMatch:
    pass

    action: Action
    speech: str | None
    status: str


def match_action(action_text: str, actions: list[Action]) -> ActionMatch:
    pass
    body = action_text.strip()
    first_line = body.splitlines()[0] if body else ""
    cleaned = _LEADING_ENUM_RE.sub("", first_line).strip()

    speak = next((a for a in actions if a.type is ActionType.SPEAK), None)
    if speak is not None and cleaned.upper().startswith("SPEAK"):
        return ActionMatch(speak, _extract_speech(cleaned), "exact")

    target = _normalise(cleaned)
    for action in actions:
        if _normalise(action.render()) == target:
            return ActionMatch(action, None, "exact")

    best = _best_overlap(target, actions)
    if best is not None:
        return ActionMatch(best, None, "fuzzy")
    return ActionMatch(actions[0], None, "none")


def _extract_speech(text: str) -> str:
    pass
    remainder = re.sub(r"^\s*SPEAK\s*:?\s*", "", text, flags=re.IGNORECASE)
    return remainder.strip() or "(says nothing of note)"


def _best_overlap(target: str, actions: list[Action]) -> Action | None:
    pass
    target_tokens = set(target.split())
    if not target_tokens:
        return None
    best: Action | None = None
    best_score = 0
    for action in actions:
        score = len(target_tokens & set(_normalise(action.render()).split()))
        if score > best_score:
            best, best_score = action, score
    return best if best_score > 0 else None


__all__ = [
    "ActionMatch",
    "match_action",
    "parse_sections",
    "parse_speech_intent",
    "strip_think_tags",
]
