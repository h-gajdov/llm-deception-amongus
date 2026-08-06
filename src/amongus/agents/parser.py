

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
                                                                          
_ACTION_MARKER_RE = re.compile(r"^\s*\[?\s*action\s*\]?\s*:?\s*", re.IGNORECASE)
                                                                        
_SMART_QUOTES = "\u201c\u201d\u2018\u2019"
_DASHES = "\u2013\u2014"
                                                                          
_DECORATION_RE = re.compile(rf"^[\s*`\"'>\-{_DASHES}{_SMART_QUOTES}]+|[\s*`\"'.{_SMART_QUOTES}]+$")
                                                                             
                                                                           
_SEPARATOR_RE = re.compile(rf"[:,\-{_DASHES}]+")


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
    text = _ACTION_MARKER_RE.sub("", text)
    text = _DECORATION_RE.sub("", text)
    text = _SEPARATOR_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


                                                                                 
                                                                             
                                  
_WAIT_SYNONYMS = frozenset(
    _normalise(phrase)
    for phrase in (
        "WAIT",
        "WAIT (do nothing)",
        "WAIT (do nothing this turn)",
        "WAIT this turn",
        "WAIT and do nothing",
        "DO NOTHING",
        "DO NOTHING this turn",
        "PASS",
        "STAY",
        "STAY PUT",
        "NO ACTION",
        "NONE",
    )
)


@dataclass(frozen=True)
class ActionMatch:
    pass

    action: Action | None
    speech: str | None
    status: str
    requested_text: str = ""
    reason: str = ""

    @property
    def resolved(self) -> bool:
        pass
        return self.action is not None


def match_action(action_text: str, actions: list[Action]) -> ActionMatch:
    pass
    body = action_text.strip()
    first_line = body.splitlines()[0] if body else ""
    requested = _DECORATION_RE.sub(
        "", _ACTION_MARKER_RE.sub("", _LEADING_ENUM_RE.sub("", first_line.strip()))
    ).strip()
    if not requested:
        return ActionMatch(None, None, "none", "", "empty_action_line")

    if requested.upper().startswith("SPEAK"):
        speak = next((a for a in actions if a.type is ActionType.SPEAK), None)
        if speak is None:
            return ActionMatch(None, None, "none", requested, "speak_not_available")
        return ActionMatch(speak, _extract_speech(body), "exact", requested)

    for action in actions:
        if action.render() == requested:
            return ActionMatch(action, None, "exact", requested)

    target = _normalise(requested)
    hits = [a for a in actions if _normalise(a.render()) == target]
    if len(hits) == 1:
        return ActionMatch(hits[0], None, "normalized", requested)
    if len(hits) > 1:                                                          
        return ActionMatch(None, None, "none", requested, "ambiguous_action_line")

    if target in _WAIT_SYNONYMS:
        wait = next((a for a in actions if a.type is ActionType.WAIT), None)
        if wait is not None:
            return ActionMatch(wait, None, "normalized", requested)
        return ActionMatch(None, None, "none", requested, "wait_not_available")

    return ActionMatch(None, None, "none", requested, "not_an_available_action")


def _extract_speech(text: str) -> str:
    pass
    body = _ACTION_MARKER_RE.sub("", _LEADING_ENUM_RE.sub("", text.strip()))
    remainder = re.sub(r"^\s*SPEAK\s*:?\s*", "", body, flags=re.IGNORECASE)
    return remainder.strip().strip("\"'" + _SMART_QUOTES) or "(says nothing of note)"


__all__ = [
    "ActionMatch",
    "match_action",
    "parse_sections",
    "parse_speech_intent",
    "strip_think_tags",
]
