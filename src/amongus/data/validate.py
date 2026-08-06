

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..game.observation import PLACEHOLDER_LINES
from ..logging import get_logger
from .ingest import iter_games, iter_turns, iter_world_states
from .schema_v2 import GameRecord, TurnRecordModel
from .splits import check_split_isolation, load_splits

logger = get_logger()

                                                                           
                                                           
MIN_DUPLICATE_LENGTH = 25


@dataclass
class ValidationReport:
    pass

    experiment_dir: str
    metrics: dict[str, float] = field(default_factory=dict)
    distributions: dict[str, dict[str, int]] = field(default_factory=dict)
    critical: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        pass
        return not self.critical

    def to_dict(self) -> dict[str, object]:
        pass
        return {
            "experiment_dir": self.experiment_dir,
            "ok": self.ok,
            "metrics": self.metrics,
            "distributions": self.distributions,
            "critical": self.critical,
            "warnings": self.warnings,
        }

    def render(self) -> str:
        pass
        lines = [f"Validation report for {self.experiment_dir}", "=" * 72, "", "Metrics:"]
        lines.extend(f"  {name:<44} {_fmt(value)}" for name, value in self.metrics.items())
        for name, dist in self.distributions.items():
            lines.append(f"\n{name}:")
            if not dist:
                lines.append("  (none)")
            total = sum(dist.values()) or 1
            lines.extend(
                f"  {key:<42} {count:>6}  ({100 * count / total:5.1f}%)"
                for key, count in sorted(dist.items(), key=lambda kv: -kv[1])
            )
        lines.append("")
        lines.append(f"Critical findings: {len(self.critical)}")
        lines.extend(f"  [CRITICAL] {item}" for item in self.critical)
        lines.append(f"Warnings: {len(self.warnings)}")
        lines.extend(f"  [warn] {item}" for item in self.warnings)
        lines.append("")
        lines.append("RESULT: PASS" if self.ok else "RESULT: FAIL")
        return "\n".join(lines)


def validate_experiment(experiment_dir: str | Path) -> ValidationReport:
    pass
    directory = Path(experiment_dir)
    if not (directory / "turns.jsonl").exists():
        msg = f"No turns.jsonl under {directory}; is this a schema 2.0 experiment?"
        raise FileNotFoundError(msg)

    turns = list(iter_turns(directory))
    games = list(iter_games(directory))
    report = ValidationReport(experiment_dir=str(directory))

    _check_basics(report, turns, games)
    _check_roles_and_speech(report, turns)
    _check_annotations(report, turns)
    _check_kills(report, directory, turns)
    _check_leakage(report, turns)
    _check_actions_and_parsing(report, turns)
    _check_memory(report, turns)
    _check_duplicates(report, turns)
    _check_splits(report, directory, turns)
    return report


                                                                               
                   
                                                                               
def _check_basics(
    report: ValidationReport, turns: list[TurnRecordModel], games: list[GameRecord]
) -> None:
    pass
    per_game = Counter(t.game_id for t in turns)
    report.metrics["games"] = len(games)
    report.metrics["turns"] = len(turns)
    report.metrics["mean_turns_per_game"] = (
        sum(per_game.values()) / len(per_game) if per_game else 0.0
    )
    lengths = [max((t.timestep for t in turns if t.game_id == g.game_id), default=0) for g in games]
    report.metrics["mean_game_length_timesteps"] = sum(lengths) / len(lengths) if lengths else 0.0
    immediate = sum(1 for length in lengths if length == 0)
    report.metrics["games_ending_immediately"] = immediate
    if immediate:
        report.warnings.append(
            f"{immediate} game(s) ended on timestep 0 -- check the initial kill cooldown."
        )
    report.distributions["winner_reason"] = dict(Counter(g.winner_reason for g in games))
    missing = {t.game_id for t in turns} - {g.game_id for g in games}
    if missing:
        report.critical.append(
            f"Turns reference games with no games.jsonl record: {sorted(missing)}"
        )


def _check_roles_and_speech(report: ValidationReport, turns: list[TurnRecordModel]) -> None:
    pass
    report.distributions["role"] = dict(Counter(t.actor.role for t in turns))
    speech = [t for t in turns if t.is_speech()]
    report.metrics["spoken_utterances"] = len(speech)
    report.metrics["speech_share_of_turns"] = len(speech) / len(turns) if turns else 0.0
    report.distributions["phase"] = dict(Counter(t.phase for t in turns))


def _check_annotations(report: ValidationReport, turns: list[TurnRecordModel]) -> None:
    pass
    speech = [t for t in turns if t.is_speech()]
    statuses = Counter(t.deception_status() for t in speech)
    report.distributions["utterance_deception_status"] = dict(statuses)
    report.distributions["utterance_truth_status"] = dict(
        Counter(str(t.annotations.get("utterance_truth_status", "unknown")) for t in speech)
    )

    subtypes: Counter[str] = Counter()
    unresolved = 0
    claims_total = 0
    for turn in speech:
        for claim in turn.annotations.get("claims", []) or []:
            if not isinstance(claim, dict):
                continue
            claims_total += 1
            if claim.get("resolution") != "resolved":
                unresolved += 1
                                                                            
                                                                               
                                                            
            if claim.get("deception_type") and claim.get("deception_intent") is True:
                subtypes[str(claim["deception_type"])] += 1
    report.distributions["deception_subtype"] = dict(subtypes)
    report.metrics["claims_extracted"] = claims_total
    report.metrics["claims_unresolved_pct"] = (
        100.0 * unresolved / claims_total if claims_total else 0.0
    )

    impostor_speech = [t for t in speech if t.actor.role.lower() == "impostor"]
    deceptive = [t for t in impostor_speech if t.deception_status() == "deceptive"]
    truthful = [t for t in impostor_speech if t.deception_status() == "truthful"]
    report.metrics["impostor_utterances"] = len(impostor_speech)
    report.metrics["impostor_utterances_deceptive_pct"] = (
        100.0 * len(deceptive) / len(impostor_speech) if impostor_speech else 0.0
    )
    report.metrics["impostor_utterances_truthful_pct"] = (
        100.0 * len(truthful) / len(impostor_speech) if impostor_speech else 0.0
    )
    crew_speech = [t for t in speech if t.actor.role.lower() != "impostor"]
    crew_deceptive = [t for t in crew_speech if t.deception_status() == "deceptive"]
    report.metrics["crewmate_utterances_deceptive_pct"] = (
        100.0 * len(crew_deceptive) / len(crew_speech) if crew_speech else 0.0
    )
    if impostor_speech and not truthful and not deceptive:
        report.warnings.append(
            "No impostor utterance resolved to either truthful or deceptive; "
            "claim extraction may not be firing."
        )


def _check_kills(report: ValidationReport, directory: Path, turns: list[TurnRecordModel]) -> None:
    pass
    del directory
    witnessed = 0
    unwitnessed = 0
    kills = 0
    for turn in turns:
        action = turn.model_output.action or {}
        if str(action.get("type", "")).upper() != "KILL":
            continue
        kills += 1
                                                                               
                                                                             
        if _kill_was_witnessed(turns, turn):
            witnessed += 1
        else:
            unwitnessed += 1
    report.metrics["kills"] = kills
    report.metrics["kills_witnessed"] = witnessed
    report.metrics["kills_unwitnessed"] = unwitnessed


def _kill_was_witnessed(turns: list[TurnRecordModel], kill_turn: TurnRecordModel) -> bool:
    pass
    killer = kill_turn.actor.player_id
    for turn in turns:
        if turn.game_id != kill_turn.game_id or turn.step <= kill_turn.step:
            continue
        if turn.actor.player_id == killer:
            continue
        for observation in turn.private_state.get("direct_observations", []) or []:
            if not isinstance(observation, dict):
                continue
            if (
                observation.get("event_type") == "kill"
                and observation.get("timestep") == kill_turn.timestep
            ):
                return True
    return False


def _check_leakage(report: ValidationReport, turns: list[TurnRecordModel]) -> None:
    pass
    engine_reported = 0
    derived: Counter[str] = Counter()
    for turn in turns:
        violations = turn.evaluation.get("leakage_violations") or []
        engine_reported += len(violations)
        for code in _derive_leakage(turn):
            derived[code] += 1

    report.metrics["leakage_violations_reported_by_engine"] = engine_reported
    report.metrics["leakage_violations_derived_from_records"] = sum(derived.values())
    report.distributions["leakage_violation_code"] = dict(derived)
    total = engine_reported + sum(derived.values())
    if total:
        report.critical.append(
            f"{total} leakage violation(s) across {len(turns)} turns: {dict(derived)}"
        )


def _derive_leakage(turn: TurnRecordModel) -> list[str]:
    pass
    codes: list[str] = []
    prompt = f"{turn.model_input.system_prompt}\n{turn.model_input.user_prompt}"
    sections = turn.model_input.sections or {}

                                                                     
    for token in ("deception_intent", "world_truth", "speaker_knows", "role_label"):
        if token in prompt:
            codes.append("evaluator_metadata_in_prompt")
            break

                                                       
    role_block = str(sections.get("role_private_context", ""))
    if turn.actor.role.lower() != "impostor" and "fellow impostors" in role_block.lower():
        codes.append("crewmate_told_impostors")

                                                                               
    observed = {
        str(o.get("text", ""))
        for o in (turn.private_state.get("direct_observations") or [])
        if isinstance(o, dict)
    }
    witnessed_block = str(sections.get("witnessed", ""))
    for line in _content_lines(witnessed_block):
        if _strip_timestamp(line) not in observed:
            codes.append("unperceived_observation_line")
            break

                                                                            
                                                                           
    if _names_a_killer(witnessed_block) and not any(
        o.get("event_type") == "kill"
        for o in (turn.private_state.get("direct_observations") or [])
        if isinstance(o, dict)
    ):
        codes.append("unwitnessed_killer_named")
    return codes


                                                                              
                                                                            
                                                                               
                                 
_KILL_ATTRIBUTION_RE = re.compile(r"You saw\s+\S.*?\s+kill\b|killed by\s+Player\b", re.IGNORECASE)


def _content_lines(block: str) -> list[str]:
    pass
    return [
        line.strip()
        for line in block.splitlines()[1:]
        if line.strip() and line.strip() not in PLACEHOLDER_LINES
    ]


def _names_a_killer(block: str) -> bool:
    pass
    return any(
        _KILL_ATTRIBUTION_RE.search(line) and "could not tell" not in line.lower()
        for line in _content_lines(block)
    )


def _strip_timestamp(line: str) -> str:
    pass
    return re.sub(r"^\[t=\d+\]\s*", "", line.strip())


def _check_actions_and_parsing(report: ValidationReport, turns: list[TurnRecordModel]) -> None:
    pass
    invalid = [t for t in turns if t.evaluation.get("action_valid") is False]
    report.metrics["invalid_actions"] = len(invalid)
    report.metrics["invalid_action_pct"] = 100.0 * len(invalid) / len(turns) if turns else 0.0
    report.distributions["action_rejection_code"] = dict(
        Counter(str((t.evaluation.get("rejection") or {}).get("code", "unknown")) for t in invalid)
    )
    report.distributions["parse_status"] = dict(Counter(t.model_output.parse_status for t in turns))
                                                                         
                                                                               
    failures = sum(1 for t in turns if t.model_output.parse_status in ("fallback", "recovered"))
    report.metrics["parser_failures"] = failures
    report.metrics["parser_failure_pct"] = 100.0 * failures / len(turns) if turns else 0.0
    normalized = sum(1 for t in turns if t.model_output.parse_status == "normalized")
    report.metrics["actions_matched_after_normalization"] = normalized

                                                                              
    report.distributions["execution_source"] = dict(
        Counter(t.model_output.execution_source for t in turns)
    )
    report.distributions["fallback_reason"] = dict(
        Counter(
            str(t.model_output.fallback_reason) for t in turns if t.model_output.fallback_reason
        )
    )
    unusable = sum(1 for t in turns if not t.model_output.requested_action_valid)
    report.metrics["unusable_requested_actions"] = unusable
    report.metrics["unusable_requested_action_pct"] = (
        100.0 * unusable / len(turns) if turns else 0.0
    )

    warnings: Counter[str] = Counter()
    for turn in turns:
        for warning in turn.annotations.get("validation_warnings", []) or []:
            warnings[str(warning)] += 1
    report.distributions["validation_warning"] = dict(warnings)
                                                                           
                                                                         
                                             
    report.metrics["contradictory_teammate_references"] = warnings[
        "rationale_calls_known_teammate_a_crewmate"
    ]
    report.metrics["speech_naming_own_teammate_as_suspect"] = warnings[
        "speech_names_known_teammate_as_suspect"
    ]
    report.distributions["action_type"] = dict(
        Counter(str((t.model_output.action or {}).get("type", "unknown")) for t in turns)
    )


def _check_memory(report: ValidationReport, turns: list[TurnRecordModel]) -> None:
    pass
    empty = 0
    for turn in turns:
        memory = turn.private_state.get("structured_memory") or {}
        populated = any(
            memory.get(key)
            for key in (
                "witnessed_events",
                "heard_statements",
                "public_meeting_facts",
                "own_actions",
            )
        )
        if not populated:
            empty += 1
    report.metrics["records_with_empty_memory"] = empty
    report.metrics["records_with_empty_memory_pct"] = 100.0 * empty / len(turns) if turns else 0.0
                                                                                
                         
    if turns and empty / len(turns) > 0.35:
        report.warnings.append(
            f"{100 * empty / len(turns):.0f}% of records have an empty derived memory."
        )


def _check_duplicates(report: ValidationReport, turns: list[TurnRecordModel]) -> None:
    pass
    utterances = [
        (t.model_output.speech or "").strip()
        for t in turns
        if t.is_speech() and len(t.model_output.speech or "") >= MIN_DUPLICATE_LENGTH
    ]
    if not utterances:
        report.metrics["duplicate_utterance_pct"] = 0.0
        return
    normalised = [re.sub(r"\s+", " ", u.lower()) for u in utterances]
    counts = Counter(normalised)
    duplicated = sum(count - 1 for count in counts.values() if count > 1)
    report.metrics["duplicate_utterance_pct"] = 100.0 * duplicated / len(normalised)
    if duplicated / len(normalised) > 0.3:
        report.warnings.append(
            f"{100 * duplicated / len(normalised):.0f}% of utterances are exact repeats."
        )


def _check_splits(report: ValidationReport, directory: Path, turns: list[TurnRecordModel]) -> None:
    pass
    assignment = load_splits(directory)
    if assignment is None:
        report.metrics["splits_defined"] = 0
        return
    report.metrics["splits_defined"] = 1
    violations = check_split_isolation(assignment, turns)
    if violations:
        report.critical.extend(violations)

    per_split: dict[str, Counter[str]] = defaultdict(Counter)
    games_per_split: Counter[str] = Counter(assignment.assignment.values())
    for turn in turns:
        split = assignment.assignment.get(turn.game_id, "<unassigned>")
        per_split[split][turn.actor.role] += 1
        if turn.is_speech():
            per_split[split][f"speech:{turn.deception_status()}"] += 1
    report.distributions["games_per_split"] = dict(games_per_split)
    for split, counter in per_split.items():
        report.distributions[f"class_balance:{split}"] = dict(counter)


def _fmt(value: float) -> str:
    pass
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


def validate_world_states(experiment_dir: str | Path) -> int:
    pass
    return sum(1 for _ in iter_world_states(experiment_dir))


__all__ = ["MIN_DUPLICATE_LENGTH", "ValidationReport", "validate_experiment"]
