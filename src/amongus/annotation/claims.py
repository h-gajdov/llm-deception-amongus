from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import Claim, ClaimType


_TIME_REFERENCES: tuple[tuple[str, str], ...] = (
    (r"\bjust now\b|\bright now\b|\bcurrently\b", "current"),
    (r"\bearlier\b|\blast (?:round|meeting|turn)\b|\bbefore\b", "earlier"),
    (
        r"\bthe (?:whole|entire) (?:time|game|round|meeting)\b|\ball (?:game|round)\b"
        r"|\bnever\b|\balways\b|\bat any point\b|\bthe whole way\b",
        "whole_game",
    ),
)
DEFAULT_TIME_REFERENCE = "previous_task_phase"


_QUALIFIERS: tuple[tuple[str, str], ...] = (
    (r"\bthe (?:whole|entire) (?:time|game|round|meeting)\b", "the entire time"),
    (r"\bnever\b", "never"),
    (r"\balways\b", "always"),
    (r"\balone\b|\bby myself\b|\bon my own\b", "alone"),
    (r"\bonly\b", "only"),
    (r"\bbefore\b", "before"),
    (r"\bafter\b", "after"),
    (r"\bduring\b", "during"),
    (r"\bthe whole time\b", "the whole time"),
)


_CLAUSE_SPLIT_RE = re.compile(
    r"[;.!?]+\s+|\n+|,\s*(?:and|but|so|then|although|though|however|while)?\s*"
    r"|\s+(?:and|but|so|then|although|though|however|while)\s+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Gazetteer:
    players: dict[str, str]
    rooms: dict[str, str]

    @staticmethod
    def build(player_names: list[str], rooms: list[str]) -> Gazetteer:
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
        forms = sorted(self.players, key=len, reverse=True)
        return "(?:" + "|".join(re.escape(f) for f in forms) + ")"

    def room_pattern(self) -> str:
        forms = sorted(self.rooms, key=len, reverse=True)
        return "(?:" + "|".join(re.escape(f) for f in forms) + ")"

    def player(self, surface: str) -> str | None:
        return self.players.get(surface.strip().lower().rstrip(".,!?'s"))

    def room(self, surface: str) -> str | None:
        return self.rooms.get(surface.strip().lower().rstrip(".,!?"))


def time_reference(utterance: str) -> str:
    lowered = utterance.lower()
    for pattern, label in _TIME_REFERENCES:
        if re.search(pattern, lowered):
            return label
    return DEFAULT_TIME_REFERENCE


def qualifiers(text: str) -> list[str]:
    lowered = text.lower()
    found = [label for pattern, label in _QUALIFIERS if re.search(pattern, lowered)]
    return list(dict.fromkeys(found))


def extract_claims(utterance: str, speaker: str, gazetteer: Gazetteer) -> list[Claim]:
    text = utterance.strip()
    if not text:
        return []
    claims: list[Claim] = []
    seen: set[tuple[str, ...]] = set()
    when = time_reference(text)
    for sentence in _sentences(text):
        for claim in _claims_in_sentence(sentence, speaker, gazetteer, when):
            key = _claim_key(claim)
            if key in seen:
                continue
            seen.add(key)
            claims.append(claim)
    _resolve_pronoun_subjects(claims, speaker)
    if not claims:
        claims.append(
            Claim(
                claim_type=ClaimType.OTHER,
                text_span=text,
                normalized_claim={"raw": text, "qualifiers": qualifiers(text)},
                confidence=0.0,
                resolution="unresolved",
                notes="No checkable claim pattern matched; utterance preserved verbatim.",
            )
        )
    return claims


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _clauses(sentence: str) -> list[str]:
    parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(sentence) if p and p.strip()]
    return [p for p in parts if p != sentence]


def _claims_in_sentence(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    out: list[Claim] = []
    seen: set[tuple[str, ...]] = set()
    for fragment in [*_clauses(sentence), sentence]:
        local_when = _time_for(fragment, when)
        local_qualifiers = qualifiers(fragment)
        for extractor in _EXTRACTORS:
            for claim in extractor(fragment, speaker, gaz, local_when):
                key = _claim_key(claim)
                if key in seen:
                    continue
                seen.add(key)
                claim.normalized_claim.setdefault("qualifiers", local_qualifiers)
                out.append(claim)
    return out


def _resolve_pronoun_subjects(claims: list[Claim], speaker: str) -> None:
    antecedent: str | None = None
    for claim in claims:
        fields = claim.normalized_claim
        if fields.get("pronoun_subject") and fields.get("subject") is None:
            if antecedent is None:
                claim.notes = "Pronoun subject with no antecedent in the utterance."
            else:
                fields["subject"] = antecedent
                fields["subject_from_pronoun"] = True
                claim.target = antecedent
        for key in ("subject", "object"):
            value = fields.get(key)
            if isinstance(value, str) and value != speaker:
                antecedent = value


def _time_for(fragment: str, fallback: str) -> str:
    found = time_reference(fragment)
    return found if found != DEFAULT_TIME_REFERENCE else fallback


def _claim_key(claim: Claim) -> tuple[str, ...]:
    fields = claim.normalized_claim
    return (
        claim.claim_type.value,
        str(claim.target),
        *(
            str(fields.get(name))
            for name in (
                "subject",
                "object",
                "location",
                "denied_action",
                "claimed_role",
                "asserted_role",
                "co_located_with",
                "about",
            )
        ),
    )


_NEGATED_SIGHTING_RE = re.compile(
    r"\b(?:did\s*n[o']?t|didnt|do\s*n[o']?t|dont|have\s*n[o']?t|havent|never|no)\s+"
    r"(?:ever\s+)?(?:see|seen|saw|notice|spot|spotted|witness)\b",
    re.IGNORECASE,
)


def _negated_before(sentence: str, index: int) -> bool:
    return bool(_NEGATED_SIGHTING_RE.search(sentence[:index]))


def _kill_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
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
        if killer is None or victim is None or _negated_before(sentence, match.start()):
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
        if who is None or _negated_before(sentence, match.start()):
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


def _negative_self_location_claims(
    sentence: str, speaker: str, gaz: Gazetteer, when: str
) -> list[Claim]:
    pattern = re.compile(
        r"\bi\s+(?:was\s*n[o']?t|wasnt|am\s+not|'m\s+not|have\s*n[o']?t\s+been|havent\s+been"
        r"|had\s*n[o']?t\s+been|did\s*n[o']?t\s+go|didnt\s+go|never\s+(?:was|went|been|entered))"
        r"\s+(?:ever\s+|even\s+|anywhere\s+)?(?:in|at|to|into|near|inside)\s+(?:the\s+)?"
        rf"(?P<room>{gaz.room_pattern()})",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        room = gaz.room(match.group("room"))
        if room is None:
            continue
        out.append(
            Claim(
                claim_type=ClaimType.NEGATIVE_LOCATION_CLAIM,
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


def _task_observation_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    player = gaz.player_pattern()
    pattern = re.compile(
        r"\bi\s+(?:saw|see|watched|spotted|observed)\s+"
        rf"(?:(?P<who>{player})|(?P<pronoun>them|him|her|they|that player))\s+"
        r"(?:\w+\s+){0,2}?"
        r"(?:doing|do|complete|completing|finish|finishing|working\s+on|use|using|at)\s+"
        r"(?:a\s+|the\s+|their\s+|his\s+|her\s+|my\s+)?(?:task|tasks|console|panel|wires|scan)"
        rf"(?:\s+(?:in|at)\s+(?:the\s+)?(?P<room>{gaz.room_pattern()}))?",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        if _negated_before(sentence, match.start()):
            continue
        who = gaz.player(match.group("who")) if match.group("who") else None
        if who is None and not match.group("pronoun"):
            continue
        out.append(
            Claim(
                claim_type=ClaimType.TASK_OBSERVATION_CLAIM,
                text_span=match.group(0),
                normalized_claim={
                    "subject": who,
                    "observer": speaker,
                    "pronoun_subject": match.group("pronoun") if who is None else None,
                    "location": gaz.room(match.group("room")) if match.group("room") else None,
                    "time_reference": when,
                    "first_hand": True,
                },
                target=who,
            )
        )
    return out


def _other_location_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
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
        if _negated_before(sentence, match.start()):
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
    del gaz
    pattern = re.compile(
        r"\bi\s+(?:did\s*n[o']?t|didnt|do\s*n[o']?t|dont|never|have\s*n[o']?t|havent|"
        r"have\s+never|would\s+never|did\s+not\s+ever)\s+(?:ever\s+|even\s+|once\s+)?"
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
    del gaz
    pattern = re.compile(
        r"\bi\s+(?:did\s*n[o']?t|didnt|have\s*n[o']?t|havent|don'?t|never)\s+(?:ever\s+)?"
        r"(?:see|saw|seen|notice|witness|know)\s+(?:anything|anyone|anybody|nothing|much)"
        r"|\bi\s+(?:have|got)\s+no\s+(?:information|evidence|idea|clue)\b"
        r"|\bi\s+saw\s+(?:nothing|nobody|no one)\b",
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


def _negative_observation_claims(
    sentence: str, speaker: str, gaz: Gazetteer, when: str
) -> list[Claim]:
    player = gaz.player_pattern()
    pattern = re.compile(
        r"\bi\s+(?:did\s*n[o']?t|didnt|do\s*n[o']?t|dont|have\s*n[o']?t|havent|never)\s+"
        r"(?:ever\s+)?(?:see|saw|seen|notice|spot|spotted|witness)\s+"
        rf"(?P<who>{player})"
        rf"(?:\s+(?:in|at|near)\s+(?:the\s+)?(?P<room>{gaz.room_pattern()}))?",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        who = gaz.player(match.group("who"))
        if who is None:
            continue
        out.append(
            Claim(
                claim_type=ClaimType.NEGATIVE_OBSERVATION_CLAIM,
                text_span=match.group(0),
                normalized_claim={
                    "subject": who,
                    "observer": speaker,
                    "location": gaz.room(match.group("room")) if match.group("room") else None,
                    "time_reference": when,
                },
                target=who,
            )
        )
    return out


def _knowledge_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    del gaz
    pattern = re.compile(
        r"\bi\s+(?:do\s*n[o']?t|dont|did\s*n[o']?t|didnt|can\s*n[o']?t|cant)\s+"
        r"(?:know|tell|say)\s+who\s+(?P<about>killed|kills|did\s+it|the\s+impostor)"
        r"|\bi\s+(?:have|got)\s+no\s+(?:idea|clue)\s+who\s+(?P<about2>killed|did\s+it|the\s+impostor)",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        about_text = (match.group("about") or match.group("about2") or "").lower()
        about = "impostor_identity" if "impostor" in about_text else "killer_identity"
        out.append(
            Claim(
                claim_type=ClaimType.KNOWLEDGE_CLAIM,
                text_span=match.group(0),
                normalized_claim={"subject": speaker, "about": about, "time_reference": when},
                target=speaker,
            )
        )
    return out


def _solitude_claims(sentence: str, speaker: str, gaz: Gazetteer, when: str) -> list[Claim]:
    pattern = re.compile(
        r"\b(?:i\s+(?:was|am|'m|have\s+been|had\s+been|stayed|worked)\s+"
        r"(?:all\s+|completely\s+|totally\s+|just\s+)?(?:alone|by\s+myself|on\s+my\s+own)"
        r"|i\s+(?:was|am|'m)\s+the\s+only\s+(?:one|player|person)"
        r"|(?:nobody|no\s*body|no\s+one|noone)\s+else\s+(?:was|were|is)?\s*"
        r"(?:there|here|in\s+there|around|with\s+me)?"
        r"|(?:nobody|no\s*body|no\s+one|noone)\s+(?:was\s+|were\s+)?"
        r"(?:with\s+me|around\s+me|near\s+me|else)"
        r"|there\s+(?:was|were)\s+(?:nobody|no\s+one|no\s+body)\s+else)"
        rf"(?:\s+(?:in|at)\s+(?:the\s+)?(?P<room>{gaz.room_pattern()}))?",
        re.IGNORECASE,
    )
    out: list[Claim] = []
    for match in pattern.finditer(sentence):
        out.append(
            Claim(
                claim_type=ClaimType.SOLITUDE_CLAIM,
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


_EXTRACTORS = (
    _kill_claims,
    _vent_claims,
    _body_found_claims,
    _self_role_claims,
    _accusation_claims,
    _defence_claims,
    _denial_claims,
    _task_claims,
    _task_observation_claims,
    _ignorance_claims,
    _negative_observation_claims,
    _knowledge_claims,
    _solitude_claims,
    _negative_self_location_claims,
    _self_location_claims,
    _other_location_claims,
)


__all__ = [
    "DEFAULT_TIME_REFERENCE",
    "Gazetteer",
    "extract_claims",
    "qualifiers",
    "time_reference",
]
