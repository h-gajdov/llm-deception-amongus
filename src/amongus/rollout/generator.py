from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from tqdm import tqdm

from ..agents.factory import AgentFactoryBuilder
from ..config import GenerationConfig
from ..game.engine import AmongUsGame, GameResult
from ..logging import get_logger

logger = get_logger()


def generate_dataset(config: GenerationConfig) -> Path:
    from ..data.writer import ExperimentWriter

    master_rng = random.Random(config.seed)
    builder = AgentFactoryBuilder(config.agent, master_rng)
    outcomes: Counter[str] = Counter()
    directory = Path(config.output_dir) / config.experiment_dirname()

    budget = f", stopping early at ~{config.max_turns} turns" if config.max_turns else ""
    logger.info(
        "Generating {} games for experiment '{}'{} -> {}",
        config.num_games,
        config.experiment_name,
        budget,
        directory,
    )
    turns_written = 0
    games_played = 0
    longest_game = 0
    try:
        with ExperimentWriter(config) as writer:
            progress = tqdm(range(1, config.num_games + 1), desc="games", unit="game")
            for game_number in progress:
                if _budget_spent(config.max_turns, turns_written, longest_game):
                    progress.close()
                    logger.info(
                        "Turn budget reached: {} turns over {} games (cap {}). "
                        "Stopping before game {}, which could not fit in the remaining {}.",
                        turns_written,
                        games_played,
                        config.max_turns,
                        game_number,
                        (config.max_turns or 0) - turns_written,
                    )
                    break
                result = _play_one_game(game_number, config, builder, master_rng)
                writer.write_game(result)
                turns_written += len(result.turns)
                longest_game = max(longest_game, len(result.turns))
                games_played += 1
                outcomes[result.winner_reason] += 1
                progress.set_postfix(turns=turns_written)
    finally:
        builder.close()

    _log_outcomes(outcomes)
    logger.info("Wrote {} turns across {} games.", turns_written, games_played)
    return directory


def _budget_spent(max_turns: int | None, turns_written: int, longest_game: int) -> bool:
    if max_turns is None or longest_game == 0:
        return False
    return turns_written + longest_game > max_turns


def _play_one_game(
    game_number: int,
    config: GenerationConfig,
    builder: AgentFactoryBuilder,
    master_rng: random.Random,
) -> GameResult:
    seed = master_rng.getrandbits(64)
    game = AmongUsGame(
        game_index=f"Game {game_number}",
        config=config.game,
        agent_factory=builder.build_agent,
        rng=random.Random(seed),
        agent_config=config.agent,
        generation_config=config.model_dump(mode="json"),
        seed=seed,
    )
    return game.run()


def _log_outcomes(outcomes: Counter[str]) -> None:
    total = sum(outcomes.values())
    if not total:
        return
    logger.info("Finished {} games. Outcome breakdown:", total)
    for reason, count in outcomes.most_common():
        logger.info("  {:>4} ({:5.1f}%)  {}", count, 100 * count / total, reason)


__all__ = ["generate_dataset"]
