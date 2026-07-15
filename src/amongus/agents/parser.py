

from __future__ import annotations

import re

from ..game.actions import Action
from ..game.enums import ActionType

_SECTION_RE = re.compile(
    r"\[\s*(Condensed Memory|Thinking Process|Action)\s*\]\s*:?\s*",
    re.IGNORECASE,
)
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_LEADING_ENUM_RE = re.compile(r"^\s*\d+[.)]\s*")


def strip_think_tags(text: str) -> str:
    pass
    return _THINK_TAG_RE.sub("", text)


def parse_sections(text: str) -> dict[str, str]:
    pass
    result = {"Condensed Memory": "", "Thinking Process": "", "Action": ""}
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
    return "Action"


def _normalise(text: str) -> str:
    pass
    text = _LEADING_ENUM_RE.sub("", text.strip())
    return re.sub(r"\s+", " ", text).lower().rstrip(".")


def match_action(action_text: str, actions: list[Action]) -> tuple[Action, str | None]:
    pass
    first_line = action_text.strip().splitlines()[0] if action_text.strip() else ""
    cleaned = _LEADING_ENUM_RE.sub("", first_line).strip()

    speak = next((a for a in actions if a.type is ActionType.SPEAK), None)
    if speak is not None and cleaned.upper().startswith("SPEAK"):
        return speak, _extract_speech(cleaned)

    target = _normalise(cleaned)
    for action in actions:
        if _normalise(action.render()) == target:
            return action, None

    best = _best_overlap(target, actions)
    return best or actions[0], None


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


__all__ = ["match_action", "parse_sections", "strip_think_tags"]
