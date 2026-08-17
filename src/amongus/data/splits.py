from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..logging import get_logger
from .ingest import iter_games, iter_turns
from .schema_v2 import GameRecord, TurnRecordModel

logger = get_logger()

SplitName = Literal["train", "validation", "test"]

SplitStrategy = Literal[
    "random",
    "held_out_model",
    "held_out_map",
    "held_out_prompt_template",
    "held_out_strategy",
    "held_out_deception_type",
    "held_out_game_configuration",
]

DEFAULT_RATIOS: dict[str, float] = {"train": 0.7, "validation": 0.15, "test": 0.15}


@dataclass
class SplitAssignment:
    strategy: str
    seed: int
    ratios: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_RATIOS))
    assignment: dict[str, str] = field(default_factory=dict)
    holdout_values: list[str] = field(default_factory=list)
    factor: str | None = None

    def games_in(self, split: str) -> list[str]:
        return sorted(g for g, s in self.assignment.items() if s == split)

    def counts(self) -> dict[str, int]:
        return dict(Counter(self.assignment.values()))

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "seed": self.seed,
            "ratios": self.ratios,
            "factor": self.factor,
            "holdout_values": self.holdout_values,
            "counts": self.counts(),
            "assignment": self.assignment,
        }


def build_splits(
    experiment_dir: str | Path,
    *,
    strategy: SplitStrategy = "random",
    seed: int = 0,
    ratios: dict[str, float] | None = None,
    holdout_values: list[str] | None = None,
) -> SplitAssignment:
    games = list(iter_games(experiment_dir))
    if not games:
        msg = f"No games.jsonl records under {experiment_dir}"
        raise ValueError(msg)

    if strategy == "random":
        return _random_split(games, seed, ratios or dict(DEFAULT_RATIOS))
    factor = _FACTORS[strategy]
    return _holdout_split(games, seed, strategy, factor, holdout_values, experiment_dir)


def _random_split(games: list[GameRecord], seed: int, ratios: dict[str, float]) -> SplitAssignment:
    total = sum(ratios.values())
    if total <= 0:
        msg = "Split ratios must sum to a positive number."
        raise ValueError(msg)
    bounds: list[tuple[str, float]] = []
    cumulative = 0.0
    for name in ("train", "validation", "test"):
        cumulative += ratios.get(name, 0.0) / total
        bounds.append((name, cumulative))

    assignment: dict[str, str] = {}
    for game in games:
        position = _stable_unit_hash(f"{seed}:{game.game_id}")
        assignment[game.game_id] = next(
            (name for name, upper in bounds if position < upper), "test"
        )
    return SplitAssignment(strategy="random", seed=seed, ratios=ratios, assignment=assignment)


def _holdout_split(
    games: list[GameRecord],
    seed: int,
    strategy: str,
    factor: str,
    holdout_values: list[str] | None,
    experiment_dir: str | Path,
) -> SplitAssignment:
    values = {game.game_id: _factor_value(game, factor, experiment_dir) for game in games}
    distinct = sorted({v for v in values.values() if v})
    if len(distinct) < 2:
        msg = (
            f"Cannot hold out '{factor}': the experiment has "
            f"{len(distinct)} distinct value(s) ({distinct}). Generate games that "
            f"vary this factor first."
        )
        raise ValueError(msg)
    holdout = holdout_values or [_rarest(values, distinct)]

    assignment: dict[str, str] = {}
    for game in games:
        if values.get(game.game_id) in holdout:
            assignment[game.game_id] = "test"
        else:
            position = _stable_unit_hash(f"{seed}:{game.game_id}")
            assignment[game.game_id] = "train" if position < 0.8 else "validation"
    return SplitAssignment(
        strategy=strategy,
        seed=seed,
        assignment=assignment,
        holdout_values=list(holdout),
        factor=factor,
    )


def _rarest(values: dict[str, str], distinct: list[str]) -> str:
    counts = Counter(values.values())
    return min(distinct, key=lambda value: (counts[value], value))


def _factor_value(game: GameRecord, factor: str, experiment_dir: str | Path) -> str:
    generation = game.generation_config or {}
    agent = generation.get("agent", {}) if isinstance(generation, dict) else {}
    config = game.game_config or {}
    if factor == "model":
        models = sorted({str(p.get("model", "")) for p in game.players if p.get("model")})
        return ",".join(models)
    if factor == "map":
        return str(config.get("map_name", "skeld"))
    if factor == "prompt_template":
        return str(agent.get("prompt_template", "v2")) if isinstance(agent, dict) else "v2"
    if factor == "strategy":
        if not isinstance(agent, dict):
            return "none"
        return "|".join(
            str(agent.get(key) or "none")
            for key in ("impostor_strategy_prompt", "crewmate_strategy_prompt")
        )
    if factor == "game_configuration":
        return _config_fingerprint(config)
    if factor == "deception_type":
        return _dominant_deception_type(experiment_dir, game.game_id)
    return ""


def _config_fingerprint(config: dict[str, object]) -> str:
    keys = (
        "num_players",
        "num_impostors",
        "kill_cooldown",
        "initial_kill_cooldown",
        "discussion_rounds",
        "max_timesteps",
        "visibility",
    )
    payload = json.dumps({k: config.get(k) for k in keys}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


_DECEPTION_TYPE_CACHE: dict[str, dict[str, str]] = {}


def _dominant_deception_type(experiment_dir: str | Path, game_id: str) -> str:
    key = str(Path(experiment_dir).resolve())
    if key not in _DECEPTION_TYPE_CACHE:
        per_game: dict[str, Counter[str]] = defaultdict(Counter)
        for turn in iter_turns(experiment_dir):
            for claim in turn.annotations.get("claims", []) or []:
                if isinstance(claim, dict) and claim.get("deception_type"):
                    per_game[turn.game_id][str(claim["deception_type"])] += 1
        _DECEPTION_TYPE_CACHE[key] = {
            gid: counter.most_common(1)[0][0] for gid, counter in per_game.items()
        }
    return _DECEPTION_TYPE_CACHE[key].get(game_id, "none")


_FACTORS: dict[str, str] = {
    "held_out_model": "model",
    "held_out_map": "map",
    "held_out_prompt_template": "prompt_template",
    "held_out_strategy": "strategy",
    "held_out_deception_type": "deception_type",
    "held_out_game_configuration": "game_configuration",
}


def _stable_unit_hash(text: str) -> float:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def check_split_isolation(assignment: SplitAssignment, turns: list[TurnRecordModel]) -> list[str]:
    seen: dict[str, set[str]] = defaultdict(set)
    for turn in turns:
        split = assignment.assignment.get(turn.game_id)
        if split is None:
            seen[turn.game_id].add("<unassigned>")
        else:
            seen[turn.game_id].add(split)
    violations = [
        f"Game {game_id} appears in multiple splits: {sorted(splits)}"
        for game_id, splits in seen.items()
        if len(splits) > 1
    ]
    violations.extend(
        f"Game {game_id} has turns but no split assignment."
        for game_id, splits in seen.items()
        if splits == {"<unassigned>"}
    )
    return violations


def write_splits(experiment_dir: str | Path, assignment: SplitAssignment) -> Path:
    path = Path(experiment_dir) / "splits.json"
    path.write_text(
        json.dumps(assignment.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Wrote split assignment ({}) -> {}", assignment.counts(), path)
    return path


def load_splits(experiment_dir: str | Path) -> SplitAssignment | None:
    path = Path(experiment_dir) / "splits.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SplitAssignment(
        strategy=str(raw.get("strategy", "random")),
        seed=int(raw.get("seed", 0)),
        ratios=dict(raw.get("ratios", DEFAULT_RATIOS)),
        assignment=dict(raw.get("assignment", {})),
        holdout_values=list(raw.get("holdout_values", [])),
        factor=raw.get("factor"),
    )


__all__ = [
    "DEFAULT_RATIOS",
    "SplitAssignment",
    "SplitStrategy",
    "build_splits",
    "check_split_isolation",
    "load_splits",
    "write_splits",
]
