

from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import Claim, ClaimType

                                                                                
_TIME_REFERENCES: tuple[tuple[str, str], ...] = (
    (r"\bjust now\b|\bright now\b|\bcurrently\b", "current"),
    (r"\bearlier\b|\blast (?:round|meeting|turn)\b|\bbefore\b", "earlier"),
    (r"\bthe whole (?:time|game)\b|\ball (?:game|round)\b", "whole_game"),
)
DEFAULT_TIME_REFERENCE = "previous_task_phase"


@dataclass(frozen=True)
class Gazetteer:
    pass

    players: dict[str, str]
    rooms: dict[str, str]

    @staticmethod
    def build(player_names: list[str], rooms: list[str]) -> Gazetteer:
        pass
        players: dict[str, str] = {}
        for name in player_names:
            players[name.lower()] = name
            head, _, color = name.partition(": ")
            if head:
                players[head.lower()] = name
            if color:
                players[color.lower()] = name
        return Gazetteer(players=players, rooms={r.lower(): r for r in rooms})

    def player_pattern(self) -> str:
        pass
        forms = sorted(self.players, key=len, reverse=True)
        return "(?:" + "|".join(re.escape(f) for f in forms) + ")"

    def room_pattern(self) -> str:
        pass
        forms = sorted(self.rooms, key=len, reverse=True)
        return "(?:" + "|".join(re.escape(f) for f in forms) + ")"

    def player(self, surface: str) -> str | None:
        pass
        return self.players.get(surface.strip().lower().rstrip(".,!?'s"))

    def room(self, surface: str) -> str | None:
        pass
        return self.rooms.get(surface.strip().lower().rstrip(".,!?"))


def time_reference(utterance: str) -> str:
    pass
    lowered = utterance.lower()
    for pattern, label in _TIME_REFERENCES:
        if re.search(pattern, lowered):
            return label
    return DEFAULT_TIME_REFERENCE


def extract_claims(utterance: str, speaker: str, gazetteer: Gazetteer) -> list[Claim]:
    pass
    text = utterance.strip()
    if not text:
        return []
    claims: list[Claim] = []
    when = time_reference(text)
    for sentence in _sentences(text):
        claims.extend(_claims_in_sentence(sentence, speaker, gazetteer, when))
    if not claims:
        claims.append(
            Claim(
                claim_type=ClaimType.OTHER,
                text_span=text,
                normalized_claim={"raw": text},
                confidence=0.0,
                resolution="unresolved",
                notes="No checkable claim pattern matched; utterance preserved verbatim.",
            )
        )
    return claims


def _sentences(text: str) -> list[str]:
    pass
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _claims_in_sentence(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    out: list[Claim] = []
    for extractor in _EXTRACTORS:
        out.extend(extractor(sentence, speaker, gaz, when))
    return out


                                                                               
                                                                
                                                                               
def _kill_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    player = gaz.player_pattern()
    pattern = re.compile(
        rf"(?P<saw>i\s+(?:saw|watched)\s+)?(?P<killer>{player})\s+"
        rf"(?:kill|killed|killing|murdered)\s+(?P<victim>{player})"
        rf"(?:\s+in\s+(?P<room>{gaz.room_pattern()}))?",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        killer = gaz.player(match.group("killer"))
        victim = gaz.player(match.group("victim"))
        if killer is None or victim is None:
            continue
        room = gaz.room(match.group("room")) if match.group("room") else None
        out.append(
            Claim(
                claim_type=ClaimType.KILL_WITNESS_CLAIM,
                text_span=match.group(0),
                normalized_claim={
                    "subject": killer,
                    "object": victim,
                    "location": room,
                    "time_reference": when,
                    "first_hand": bool(match.group("saw")),
                },
                target=killer,
            )
        )
    return out


def _vent_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    player = gaz.player_pattern()
    pattern = re.compile(
        rf"(?P<saw>i\s+(?:saw|watched)\s+)?(?P<who>{player})\s+"
        rf"(?:\w+\s+){{0,3}}?(?:vent|vented|venting|use[d]?\s+(?:a|the)\s+vent)"
        rf"(?:\s+(?:in|from)\s+(?P<room>{gaz.room_pattern()}))?",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        who = gaz.player(match.group("who"))
        if who is None:
            continue
        out.append(
            Claim(
                claim_type=ClaimType.VENT_WITNESS_CLAIM,
                text_span=match.group(0),
                normalized_claim={
                    "subject": who,
                    "location": gaz.room(match.group("room")) if match.group("room") else None,
                    "time_reference": when,
                    "first_hand": bool(match.group("saw")),
                },
                target=who,
            )
        )
    return out


                                                                                
                                                                                
                                                     
_REPORTING_VERB_RE = re.compile(
    r"\bi\s+(?:saw|seen|watched|spotted|heard|think|thought|believe|suspect|know)\b",
    re.IGNORECASE,
)


def _self_location_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    if _REPORTING_VERB_RE.search(sentence):
        return []
    pattern = re.compile(
        r"\bi\s*(?:'m|'ve)?\s*(?:was|am|have been|had been|went|stayed|got|came|headed)?\s*"
        r"(?:just |only |still |over |back |down |up |off )*"
        rf"(?:in|at|inside|into|to)\s+(?:the\s+)?(?P<room>{gaz.room_pattern()})",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        room = gaz.room(match.group("room"))
        if room is None:
            continue
        out.append(
            Claim(
                claim_type=ClaimType.LOCATION_CLAIM,
                text_span=match.group(0),
                normalized_claim={
                    "subject": speaker,
                    "location": room,
                    "time_reference": when,
                },
                target=speaker,
            )
        )
    return out


def _other_location_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    player = gaz.player_pattern()
    pattern = re.compile(
        rf"(?P<saw>i\s+(?:saw|spotted|watched)\s+)?(?P<who>{player})\s+"
        rf"(?:was|is|were|has been)?\s*(?:in|at)\s+(?:the\s+)?(?P<room>{gaz.room_pattern()})",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        who = gaz.player(match.group("who"))
        room = gaz.room(match.group("room"))
        if who is None or room is None or who == speaker:
            continue
        first_hand = bool(match.group("saw"))
        out.append(
            Claim(
                claim_type=(
                    ClaimType.OBSERVATION_CLAIM if first_hand else ClaimType.OTHER_LOCATION_CLAIM
                ),
                text_span=match.group(0),
                normalized_claim={
                    "subject": who,
                    "location": room,
                    "time_reference": when,
                    "first_hand": first_hand,
                },
                target=who,
            )
        )
    return out


def _body_found_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    player = gaz.player_pattern()
    pattern = re.compile(
        rf"(?:i\s+(?:found|saw|discovered)\s+)?(?P<who>{player})(?:'s\s+body)?\s+"
        rf"(?:was\s+|were\s+|lying\s+)?(?:dead|killed|'s\s+body)"
        rf"(?:\s+(?:in|at)\s+(?:the\s+)?(?P<room>{gaz.room_pattern()}))",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        who = gaz.player(match.group("who"))
        room = gaz.room(match.group("room")) if match.group("room") else None
        if who is None or room is None:
            continue
        out.append(
            Claim(
                claim_type=ClaimType.BODY_FOUND_CLAIM,
                text_span=match.group(0),
                normalized_claim={
                    "subject": who,
                    "location": room,
                    "time_reference": when,
                },
                target=who,
            )
        )
    return out


def _self_role_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    del gaz
    pattern = re.compile(
        r"\bi(?:'m| am|m)\s+(?P<neg>not\s+)?(?:the\s+|an\s+|a\s+)?(?P<role>impostor|crewmate)\b",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        claimed_impostor = match.group("role").lower() == "impostor"
        negated = bool(match.group("neg"))
                                                                              
        asserts_crewmate = (claimed_impostor and negated) or (not claimed_impostor and not negated)
        out.append(
            Claim(
                claim_type=ClaimType.SELF_ROLE_CLAIM,
                text_span=match.group(0),
                normalized_claim={
                    "subject": speaker,
                    "claimed_role": "Crewmate" if asserts_crewmate else "Impostor",
                    "time_reference": when,
                },
                target=speaker,
            )
        )
    return out


def _accusation_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    player = gaz.player_pattern()
    out: list[Claim] = []
    is_impostor = re.compile(
        rf"(?P<who>{player})\s+(?:is|seems|looks|might be|could be|must be)\s+"
        rf"(?:the\s+|an\s+|a\s+|very\s+|really\s+)*"
        rf"(?P<verdict>impostor|sus|suspicious|suspect|guilty)",
        re.IGNORECASE,
    )
    for match in is_impostor.finditer(sentence):
        who = gaz.player(match.group("who"))
        if who is None:
            continue
        out.append(
            Claim(
                claim_type=ClaimType.ACCUSATION,
                text_span=match.group(0),
                normalized_claim={
                    "subject": who,
                    "asserted_role": "Impostor",
                    "hedged": match.group(0).lower().find("might") >= 0
                    or match.group(0).lower().find("could") >= 0,
                    "time_reference": when,
                },
                target=who,
            )
        )
    vote = re.compile(
        rf"\b(?:vote|voting|eject|ejecting)\s+(?:for\s+|out\s+)?(?P<who>{player})", re.IGNORECASE
    )
    for match in vote.finditer(sentence):
        who = gaz.player(match.group("who"))
        if who is None:
            continue
        out.append(
            Claim(
                claim_type=ClaimType.VOTE_INTENT,
                text_span=match.group(0),
                normalized_claim={"subject": speaker, "object": who, "time_reference": when},
                target=who,
            )
        )
    return out


def _defence_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    player = gaz.player_pattern()
    out: list[Claim] = []
    innocent = re.compile(
        rf"(?P<who>{player})\s+(?:is|seems|looks)\s+(?:not\s+the\s+impostor|innocent|clear|"
        rf"cleared|safe|trustworthy|fine)",
        re.IGNORECASE,
    )
    for match in innocent.finditer(sentence):
        who = gaz.player(match.group("who"))
        if who is None:
            continue
        out.append(
            Claim(
                claim_type=ClaimType.DEFENCE,
                text_span=match.group(0),
                normalized_claim={
                    "subject": who,
                    "asserted_role": "Crewmate",
                    "time_reference": when,
                },
                target=who,
            )
        )
    together = re.compile(rf"\bi\s+was\s+with\s+(?P<who>{player})", re.IGNORECASE)
    for match in together.finditer(sentence):
        who = gaz.player(match.group("who"))
        if who is None:
            continue
        out.append(
            Claim(
                claim_type=ClaimType.DEFENCE,
                text_span=match.group(0),
                normalized_claim={
                    "subject": who,
                    "co_located_with": speaker,
                    "time_reference": when,
                },
                target=who,
            )
        )
    return out


def _denial_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    del gaz
    pattern = re.compile(
        r"\bi\s+(?:did\s*n[o']?t|didnt|never|have\s+not|haven't)\s+"
        r"(?P<what>kill\w*|vent\w*|murder\w*)",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        what = match.group("what").lower()
        out.append(
            Claim(
                claim_type=ClaimType.DENIAL_OF_ACTION,
                text_span=match.group(0),
                normalized_claim={
                    "subject": speaker,
                    "denied_action": "kill" if what.startswith(("kill", "murder")) else "vent",
                    "time_reference": when,
                },
                target=speaker,
            )
        )
    return out


def _task_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    pattern = re.compile(
        rf"\bi\s+(?:just\s+)?(?:completed|finished|did|was\s+doing|have\s+done|"
        rf"was\s+working\s+on)\s+(?:my\s+|a\s+|the\s+)?tasks?"
        rf"(?:\s+in\s+(?:the\s+)?(?P<room>{gaz.room_pattern()}))?",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        out.append(
            Claim(
                claim_type=ClaimType.TASK_CLAIM,
                text_span=match.group(0),
                normalized_claim={
                    "subject": speaker,
                    "location": gaz.room(match.group("room")) if match.group("room") else None,
                    "time_reference": when,
                },
                target=speaker,
            )
        )
    return out


def _ignorance_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pass
    del gaz
    pattern = re.compile(
        r"\bi\s+(?:did\s*n[o']?t|didnt|have\s*n[o']?t|havent|don'?t)\s+"
        r"(?:see|seen|notice|witness|know)\s+(?:anything|anyone|nothing|much)"
        r"|\bi\s+have\s+no\s+(?:information|evidence|idea)\b",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        out.append(
            Claim(
                claim_type=ClaimType.IGNORANCE_CLAIM,
                text_span=match.group(0),
                normalized_claim={"subject": speaker, "time_reference": when},
                target=speaker,
            )
        )
    return out


_EXTRACTORS = (
    _kill_claims,
    _vent_claims,
    _body_found_claims,
    _self_role_claims,
    _accusation_claims,
    _defence_claims,
    _denial_claims,
    _task_claims,
    _ignorance_claims,
    _self_location_claims,
    _other_location_claims,
)


__all__ = ["DEFAULT_TIME_REFERENCE", "Gazetteer", "extract_claims", "time_reference"]
