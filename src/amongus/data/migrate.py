

from __future__ import annotations

from pathlib import Path

from ..annotation.schema import UtteranceDeceptionStatus, UtteranceTruthStatus
from ..logging import get_logger
from .ingest import iter_step_logs
from .records import StepLog
from .schema_v2 import ActorInfo, ModelInput, ModelOutput, TurnRecordModel

logger = get_logger()

MIGRATION_WARNING = "migrated_from_v1"


def migrate_step_log(step: StepLog) -> TurnRecordModel:
    pass
    prompt = step.interaction.prompt
    response = step.interaction.response
    action_text = response.get("Action", "")
    speech = _speech_of(action_text)
    return TurnRecordModel(
        schema_version="2.0",
        game_id=step.game_index,
        turn_id=f"{step.game_index}#{step.step}",
        step=step.step,
        timestep=-1,
        phase=prompt.get("Phase", ""),
        timestamp=step.timestamp,
        actor=ActorInfo(
            player_id=step.player.name,
            role=step.player.identity,
            model=step.player.model,
            personality=step.player.personality,
        ),
        world_state_before_ref=-1,
        world_state_after_ref=-1,
        private_state={},
        model_input=ModelInput(
            system_prompt=step.interaction.system_prompt,
            user_prompt=prompt.get("All Info", ""),
            sections={"memory_context": prompt.get("Memory", "")},
        ),
        model_output=ModelOutput(
            raw=step.interaction.full_response,
            generated_rationale=response.get("Thinking Process", ""),
            generated_condensed_memory=response.get("Condensed Memory", ""),
            action={"rendered": action_text},
            speech=speech,
            parse_status="unknown",
        ),
        annotations={
            "role_label": step.player.identity,
            "speaker_role": step.player.identity,
            "utterance": speech or "",
            "claims": [],
            "utterance_truth_status": UtteranceTruthStatus.UNRESOLVED.value
            if speech
            else UtteranceTruthStatus.NOT_APPLICABLE.value,
            "utterance_deception_status": UtteranceDeceptionStatus.AMBIGUOUS.value
            if speech
            else UtteranceDeceptionStatus.NOT_APPLICABLE.value,
            "validation_warnings": [MIGRATION_WARNING],
        },
        evaluation={"action_valid": None, "migrated": True},
        probe_regions={},
    )


def _speech_of(action_text: str) -> str | None:
    pass
    stripped = action_text.strip()
    if not stripped.upper().startswith("SPEAK"):
        return None
    _, _, rest = stripped.partition(":")
    return rest.strip() or None


def migrate_directory(source: str | Path, dest: str | Path) -> Path:
    pass
    source_dir, dest_dir = Path(source), Path(dest)
    logs = source_dir / "agent-logs.json"
    if not logs.exists():
        msg = f"No agent-logs.json under {source_dir}"
        raise FileNotFoundError(msg)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / "turns.jsonl"
    count = 0
    with out.open("w", encoding="utf-8") as handle:
        for step in iter_step_logs(logs):
            handle.write(migrate_step_log(step).model_dump_json())
            handle.write("\n")
            count += 1
    logger.info("Migrated {} v1 records from {} -> {}", count, source_dir, out)
    return out


__all__ = ["MIGRATION_WARNING", "migrate_directory", "migrate_step_log"]
