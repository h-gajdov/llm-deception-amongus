

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import TracebackType
from typing import TextIO

from ..config import SCHEMA_VERSION, GenerationConfig
from ..game.engine import GameResult, TurnRecord
from ..game.state import PlayerState
from .records import Interaction, PlayerLog, StepLog
from .schema_v2 import (
    EVENTS_FILE,
    GAMES_FILE,
    METADATA_FILE,
    TURNS_FILE,
    WORLD_STATES_FILE,
)

                                                                                 
_SUMMARY_SEPARATORS = (",", ": ")

                                                                              
                                                                              
PROBE_TEXT_RECIPE = "system_prompt + '\\n\\n' + user_prompt + '\\n\\n' + model_output.raw"


class ExperimentWriter:
    pass

    def __init__(self, config: GenerationConfig, commit: str = "unknown") -> None:
        pass
        self._config = config
        self._commit = commit
        self.directory = Path(config.output_dir) / config.experiment_dirname()
        self._handles: dict[str, TextIO] = {}

    def __enter__(self) -> ExperimentWriter:
        pass
        self.directory.mkdir(parents=True, exist_ok=True)
        self._open(TURNS_FILE)
        self._open(GAMES_FILE)
        if self._config.write_world_states:
            self._open(WORLD_STATES_FILE)
            self._open(EVENTS_FILE)
        if self._config.write_legacy_logs:
            self._open("agent-logs.json")
            self._open("summary.json")
            if self._config.write_compact_logs:
                self._open("agent-logs-compact.json")
        self._write_metadata()
        self._write_details()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass
        for handle in self._handles.values():
            handle.close()
        self._handles.clear()

    def _open(self, filename: str) -> None:
        pass
        self._handles[filename] = (self.directory / filename).open("w", encoding="utf-8")

    def _write_line(self, filename: str, payload: object) -> None:
        pass
        handle = self._handles.get(filename)
        if handle is None:
            return
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")

                                                                          
                
                                                                          
    def write_game(self, result: GameResult) -> None:
        pass
        for turn in result.turns:
            self._write_line(TURNS_FILE, turn.to_dict())
        for snapshot in result.world_states:
            self._write_line(WORLD_STATES_FILE, snapshot)
        if result.events:
            self._write_line(EVENTS_FILE, {"game_id": result.game_index, "events": result.events})
        self._write_line(GAMES_FILE, _game_record(result))
        if self._config.write_legacy_logs:
            self._write_legacy(result)

                                                                          
                            
                                                                          
    def _write_legacy(self, result: GameResult) -> None:
        pass
        full = self._handles.get("agent-logs.json")
        compact = self._handles.get("agent-logs-compact.json")
        for turn in result.turns:
            step_log = _to_step_log(turn)
            if full is not None:
                full.write(json.dumps(step_log.model_dump(), indent=2, ensure_ascii=False))
                full.write("\n")
            if compact is not None:
                compact.write(
                    json.dumps(step_log.compact().model_dump(), indent=2, ensure_ascii=False)
                )
                compact.write("\n")
        summary = self._handles.get("summary.json")
        if summary is not None:
            payload = {result.game_index: _to_summary(result)}
            summary.write(json.dumps(payload, separators=_SUMMARY_SEPARATORS, ensure_ascii=False))
            summary.write("\n")

                                                                          
              
                                                                          
    def _write_metadata(self) -> None:
        pass
        payload = {
            "schema_version": SCHEMA_VERSION,
            "experiment_name": self._config.experiment_name,
            "num_games": self._config.num_games,
            "seed": self._config.seed,
            "commit": self._commit,
            "created": date.today().isoformat(),
            "generation_config": self._config.model_dump(mode="json"),
            "probe_text_recipe": PROBE_TEXT_RECIPE,
            "files": {
                "turns": TURNS_FILE,
                "world_states": WORLD_STATES_FILE,
                "events": EVENTS_FILE,
                "games": GAMES_FILE,
            },
        }
        (self.directory / METADATA_FILE).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _write_details(self) -> None:
        pass
        args = _experiment_args(self._config)
        text = (
            f"Experiment {self.directory.as_posix()}\n"
            f"Date: {date.today().isoformat()}\n"
            f"Commit: {self._commit}\n"
            f"Schema: {SCHEMA_VERSION}\n"
            f"Experiment args: {args}\n"
            f"Generator: amongus.rollout.generator\n\n"
            f"Experiment args: {args}\n"
        )
        (self.directory / "experiment-details.txt").write_text(text, encoding="utf-8")


                                                                               
                    
                                                                               
def _game_record(result: GameResult) -> dict[str, object]:
    pass
    return {
        "schema_version": SCHEMA_VERSION,
        "game_id": result.game_index,
        "winner": result.winner,
        "winner_reason": result.winner_reason,
        "seed": result.seed,
        "num_turns": len(result.turns),
        "players": [_player_summary(p) for p in result.players],
        "game_config": result.config.model_dump(mode="json"),
        "generation_config": result.generation_config,
    }


def _to_step_log(turn: TurnRecord) -> StepLog:
    pass
    model_input = turn.model_input
    model_output = turn.model_output
    sections = model_input.get("sections", {})
    return StepLog(
        game_index=turn.game_id,
        step=turn.step,
        timestamp=turn.timestamp,
        player=PlayerLog(
            name=str(turn.actor.get("player_id", "")),
            identity=str(turn.actor.get("role", "")),
            personality=turn.actor.get("personality"),                          
            model=str(turn.actor.get("model", "unknown")),
            location=_location_of(turn),
        ),
        interaction=Interaction(
            system_prompt=str(model_input.get("system_prompt", "")),
            prompt={
                "All Info": str(model_input.get("user_prompt", "")),
                "Memory": str(sections.get("memory_context", ""))
                if isinstance(sections, dict)
                else "",
                "Summarization": str(model_output.get("generated_rationale", "")),
                "Phase": turn.phase,
            },
            response={
                "Condensed Memory": str(model_output.get("generated_condensed_memory", "")),
                "Thinking Process": str(model_output.get("generated_rationale", "")),
                "Action": str(_rendered_action(model_output)),
            },
            full_response=str(model_output.get("raw", "")),
        ),
    )


def _rendered_action(model_output: dict[str, object]) -> str:
    pass
    speech = model_output.get("speech")
    if isinstance(speech, str) and speech:
        return f"SPEAK: {speech}"
    action = model_output.get("action")
    if isinstance(action, dict):
        return str(action.get("rendered", ""))
    return ""


def _location_of(turn: TurnRecord) -> str:
    pass
    memory = turn.private_state.get("structured_memory")
    if isinstance(memory, dict):
        locations = memory.get("last_known_locations")
        actor = turn.actor.get("player_id")
        if isinstance(locations, dict) and isinstance(actor, str):
            belief = locations.get(actor)
            if isinstance(belief, dict):
                return str(belief.get("room", ""))
    return ""


def _to_summary(result: GameResult) -> dict[str, object]:
    pass
    summary: dict[str, object] = {"config": result.config.model_dump(mode="json")}
    for player in result.players:
        summary[f"Player {player.index}"] = _player_summary(player)
    summary["winner"] = result.winner
    summary["winner_reason"] = result.winner_reason
    return summary


def _player_summary(player: PlayerState) -> dict[str, object]:
    pass
    return {
        "name": player.name,
        "color": player.color,
        "identity": player.role.value,
        "personality": player.personality,
        "tasks": [task.name for task in player.tasks],
    }


def _experiment_args(config: GenerationConfig) -> dict[str, object]:
    pass
    agent = config.agent
    return {
        "game_config": config.game.model_dump(mode="json"),
        "include_human": False,
        "test": False,
        "personality": agent.personality_mode != "none",
        "agent_config": {
            "Impostor": agent.impostor_backend,
            "Crewmate": agent.crewmate_backend,
            "IMPOSTOR_LLM_CHOICES": agent.impostor_llm_choices,
            "CREWMATE_LLM_CHOICES": agent.crewmate_llm_choices,
        },
        "UI": False,
    }


__all__ = ["PROBE_TEXT_RECIPE", "ExperimentWriter"]
