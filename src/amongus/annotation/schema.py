

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ClaimType(str, Enum):
    pass

    LOCATION_CLAIM = "location_claim"
    pass

    NEGATIVE_LOCATION_CLAIM = "negative_location_claim"
    pass

    OTHER_LOCATION_CLAIM = "other_location_claim"
    pass

    OBSERVATION_CLAIM = "observation_claim"
    pass

    TASK_OBSERVATION_CLAIM = "task_observation_claim"
    pass

    KILL_WITNESS_CLAIM = "kill_witness_claim"
    pass

    VENT_WITNESS_CLAIM = "vent_witness_claim"
    pass

    BODY_FOUND_CLAIM = "body_found_claim"
    pass

    SELF_ROLE_CLAIM = "self_role_claim"
    pass

    TEAMMATE_CLAIM = "teammate_claim"
    pass

    ACCUSATION = "accusation"
    pass

    DEFENCE = "defence"
    pass

    DENIAL_OF_ACTION = "denial_of_action"
    pass

    TASK_CLAIM = "task_claim"
    pass

    IGNORANCE_CLAIM = "ignorance_claim"
    pass

    NEGATIVE_OBSERVATION_CLAIM = "negative_observation_claim"
    pass

    KNOWLEDGE_CLAIM = "knowledge_claim"
    pass

    SOLITUDE_CLAIM = "solitude_claim"
    pass

    VOTE_INTENT = "vote_intent"
    pass

    OTHER = "other"
    pass


class SpeakerKnowledge(str, Enum):
    pass

    KNOWS_TRUE = "speaker_knows_true"
    pass

    KNOWS_FALSE = "speaker_knows_false"
    pass

    BELIEVES_TRUE = "speaker_believes_true"
    pass

    BELIEVES_FALSE = "speaker_believes_false"
    pass

    UNCERTAIN = "speaker_uncertain"
    pass

    UNKNOWN = "unknown"
    pass


class DeceptionType(str, Enum):
    pass

    FALSE_ALIBI = "false_alibi"
    FALSE_ACCUSATION = "false_accusation"
    DENIAL_OF_TRUE_ACTION = "denial_of_true_action"
    FABRICATED_OBSERVATION = "fabricated_observation"
    ACCOMPLICE_DEFENCE = "accomplice_defence"
    STRATEGIC_OMISSION = "strategic_omission"
    MISLEADING_TRUTH = "misleading_truth"
    IDENTITY_DENIAL = "identity_denial"
    OTHER = "other"


class UtteranceTruthStatus(str, Enum):
    pass

    TRUE = "true"
    FALSE = "false"
    MIXED = "mixed"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


class UtteranceDeceptionStatus(str, Enum):
    pass

    TRUTHFUL = "truthful"
    DECEPTIVE = "deceptive"
    MISTAKEN = "mistaken"
    UNSUPPORTED_SUSPICION = "unsupported_suspicion"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"


class SpeechAct(str, Enum):
    pass

    ACCUSE = "accuse"
    DEFEND = "defend"
    CLAIM_ALIBI = "claim_alibi"
    REPORT_OBSERVATION = "report_observation"
    DENY = "deny"
    ASK = "ask"
    PROPOSE_VOTE = "propose_vote"
    INFORM = "inform"
    OTHER = "other"


class StrategicIntent(str, Enum):
    pass

    SHIFT_SUSPICION = "shift_suspicion"
    ESTABLISH_ALIBI = "establish_alibi"
    PROTECT_ALLY = "protect_ally"
    BUILD_TRUST = "build_trust"
    SEEK_INFORMATION = "seek_information"
    SHARE_EVIDENCE = "share_evidence"
    COORDINATE_VOTE = "coordinate_vote"
    NONE = "none"


class KnowledgeBasis(str, Enum):
    pass

    FIRST_PERSON = "first_person"
    pass

    ROLE_PRIVATE = "role_private"
    pass

    INFERENCE = "inference"
    pass

    NONE = "none"
    pass


class IntentEvidence(str, Enum):
    pass

    FIRST_PERSON_KNOWLEDGE = "first_person_knowledge"
    pass

    ROLE_PRIVATE_KNOWLEDGE = "role_private_knowledge"
    pass

    OBJECTIVE_ACTION = "objective_action"
    pass

    PRIVATE_REASONING = "private_reasoning"
    pass

    DECLARED_STRATEGY = "declared_strategy"
    pass

    NONE = "none"
    pass


@dataclass
class Claim:
    pass

    claim_type: ClaimType
    text_span: str
    normalized_claim: dict[str, object] = field(default_factory=dict)
    world_truth: bool | None = None
    speaker_knowledge: SpeakerKnowledge = SpeakerKnowledge.UNKNOWN
    deception_intent: bool | None = None
    deception_type: DeceptionType | None = None
    knowledge_basis: KnowledgeBasis = KnowledgeBasis.NONE
    intent_evidence: IntentEvidence = IntentEvidence.NONE
    target: str | None = None
    confidence: float = 1.0
    resolution: str = "unresolved"
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        pass
        return {
            "claim_type": self.claim_type.value,
            "text_span": self.text_span,
            "normalized_claim": dict(self.normalized_claim),
            "world_truth": self.world_truth,
            "speaker_knowledge": self.speaker_knowledge.value,
            "deception_intent": self.deception_intent,
            "deception_type": self.deception_type.value if self.deception_type else None,
            "knowledge_basis": self.knowledge_basis.value,
            "intent_evidence": self.intent_evidence.value,
            "target": self.target,
            "confidence": self.confidence,
            "resolution": self.resolution,
            "notes": self.notes,
        }


@dataclass
class StructuredSpeech:
    pass

    speech_act: SpeechAct = SpeechAct.OTHER
    target_player: str | None = None
    intended_claims: list[dict[str, object]] = field(default_factory=list)
    strategic_intent: StrategicIntent = StrategicIntent.NONE
    declared: bool = False

    def to_dict(self) -> dict[str, object]:
        pass
        return {
            "speech_act": self.speech_act.value,
            "target_player": self.target_player,
            "intended_claims": list(self.intended_claims),
            "strategic_intent": self.strategic_intent.value,
            "declared": self.declared,
        }


@dataclass
class UtteranceAnnotation:
    pass

    speaker_role: str
    utterance: str
    claims: list[Claim] = field(default_factory=list)
    utterance_truth_status: UtteranceTruthStatus = UtteranceTruthStatus.NOT_APPLICABLE
    utterance_deception_status: UtteranceDeceptionStatus = UtteranceDeceptionStatus.NOT_APPLICABLE
    structured_speech: StructuredSpeech = field(default_factory=StructuredSpeech)
    intent_evidence: IntentEvidence = IntentEvidence.NONE
    intent_evidence_detail: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        pass
        return {
            "speaker_role": self.speaker_role,
            "utterance": self.utterance,
            "claims": [c.to_dict() for c in self.claims],
            "utterance_truth_status": self.utterance_truth_status.value,
            "utterance_deception_status": self.utterance_deception_status.value,
            "structured_speech": self.structured_speech.to_dict(),
            "intent_evidence": self.intent_evidence.value,
            "intent_evidence_detail": self.intent_evidence_detail,
            "notes": self.notes,
        }

    @staticmethod
    def not_applicable(role: str) -> UtteranceAnnotation:
        pass
        return UtteranceAnnotation(speaker_role=role, utterance="")


__all__ = [
    "Claim",
    "ClaimType",
    "DeceptionType",
    "IntentEvidence",
    "KnowledgeBasis",
    "SpeakerKnowledge",
    "SpeechAct",
    "StrategicIntent",
    "StructuredSpeech",
    "UtteranceAnnotation",
    "UtteranceDeceptionStatus",
    "UtteranceTruthStatus",
]
