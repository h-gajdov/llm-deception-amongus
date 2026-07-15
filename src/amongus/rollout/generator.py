

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
    pass
    from ..data.writer import ExperimentWriter                                            

    master_rng = random.Random(config.seed)
    builder = AgentFactoryBuilder(config.agent, master_rng)
    outcomes: Counter[str] = Counter()
    directory = Path(config.output_dir) / config.experiment_dirname()

    logger.info(
        "Generating {} games for experiment '{}' -> {}",
        config.num_games,
        config.experiment_name,
        directory,
    )
    try:
        with ExperimentWriter(config) as writer:
            for game_number in tqdm(range(1, config.num_games + 1), desc="games", unit="game"):
                result = _play_one_game(game_number, config, builder, master_rng)
                writer.write_game(result)
                outcomes[result.winner_reason] += 1
    finally:
        builder.close()

    _log_outcomes(outcomes)
    return directory


def _play_one_game(
    game_number: int,
    config: GenerationConfig,
    builder: AgentFactoryBuilder,
    master_rng: random.Random,
) -> GameResult:
    pass
    game_rng = random.Random(master_rng.getrandbits(64))
    game = AmongUsGame(
        game_index=f"Game {game_number}",
        config=config.game,
        agent_factory=builder.build_agent,
        rng=game_rng,
    )
    return game.run()


def _log_outcomes(outcomes: Counter[str]) -> None:
    pass
    total = sum(outcomes.values())
    if not total:
        return
    logger.info("Finished {} games. Outcome breakdown:", total)
    for reason, count in outcomes.most_common():
        logger.info("  {:>4} ({:5.1f}%)  {}", count, 100 * count / total, reason)


__all__ = ["generate_dataset"]
