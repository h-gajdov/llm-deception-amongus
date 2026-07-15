

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import TracebackType

from ..config import GenerationConfig
from ..game.engine import GameResult, StepRecord
from ..game.state import PlayerState
from .records import Interaction, PlayerLog, StepLog

                                                                                 
_SUMMARY_SEPARATORS = (",", ": ")


class ExperimentWriter:
    pass

    def __init__(self, config: GenerationConfig, commit: str = "unknown") -> None:
        pass
        self._config = config
        self._commit = commit
        self.directory = Path(config.output_dir) / config.experiment_dirname()
        self._full = None                            
        self._compact = None                            
        self._summary = None                            

    def __enter__(self) -> ExperimentWriter:
        pass
        self.directory.mkdir(parents=True, exist_ok=True)
        self._full = (self.directory / "agent-logs.json").open("w", encoding="utf-8")
        if self._config.write_compact_logs:
            self._compact = (self.directory / "agent-logs-compact.json").open("w", encoding="utf-8")
        self._summary = (self.directory / "summary.json").open("w", encoding="utf-8")
        self._write_details()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass
        for handle in (self._full, self._compact, self._summary):
            if handle is not None:
                handle.close()

    def write_game(self, result: GameResult) -> None:
        pass
        for record in result.steps:
            step_log = _to_step_log(record)
            self._append_full(step_log)
            self._append_compact(step_log)
        self._append_summary(result)

                                                                          
                      
                                                                          
    def _append_full(self, step_log: StepLog) -> None:
        pass
        assert self._full is not None
        self._full.write(json.dumps(step_log.model_dump(), indent=2, ensure_ascii=False))
        self._full.write("\n")

    def _append_compact(self, step_log: StepLog) -> None:
        pass
        if self._compact is None:
            return
        self._compact.write(
            json.dumps(step_log.compact().model_dump(), indent=2, ensure_ascii=False)
        )
        self._compact.write("\n")

    def _append_summary(self, result: GameResult) -> None:
        pass
        assert self._summary is not None
        summary = {result.game_index: _to_summary(result)}
        self._summary.write(json.dumps(summary, separators=_SUMMARY_SEPARATORS, ensure_ascii=False))
        self._summary.write("\n")

    def _write_details(self) -> None:
        pass
        args = _experiment_args(self._config)
        text = (
            f"Experiment {self.directory.as_posix()}\n"
            f"Date: {date.today().isoformat()}\n"
            f"Commit: {self._commit}\n"
            f"Experiment args: {args}\n"
            f"Generator: amongus.rollout.generator\n\n"
            f"Experiment args: {args}\n"
        )
        (self.directory / "experiment-details.txt").write_text(text, encoding="utf-8")


                                                                               
                    
                                                                               
def _to_step_log(record: StepRecord) -> StepLog:
    pass
    return StepLog(
        game_index=record.game_index,
        step=record.step,
        timestamp=record.timestamp,
        player=PlayerLog(
            name=record.player_name,
            identity=record.player_identity,
            personality=record.player_personality,
            model=record.player_model,
            location=record.player_location,
        ),
        interaction=Interaction(
            system_prompt=record.system_prompt,
            prompt=record.prompt,
            response=record.response,
            full_response=record.full_response,
        ),
    )


def _to_summary(result: GameResult) -> dict[str, object]:
    pass
    summary: dict[str, object] = {"config": result.config.model_dump()}
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
        "game_config": config.game.model_dump(),
        "include_human": False,
        "test": False,
        "personality": False,
        "agent_config": {
            "Impostor": agent.impostor_backend,
            "Crewmate": agent.crewmate_backend,
            "IMPOSTOR_LLM_CHOICES": agent.impostor_llm_choices,
            "CREWMATE_LLM_CHOICES": agent.crewmate_llm_choices,
        },
        "UI": False,
    }


__all__ = ["ExperimentWriter"]
