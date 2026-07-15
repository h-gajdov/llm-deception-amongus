

from __future__ import annotations

from pathlib import Path

import typer

from ..config import GenerationConfig, load_config
from ..logging import configure_logging, get_logger

app = typer.Typer(
    name="amongus",
    help="Among Us deception sandbox: dataset generation and preprocessing.",
    no_args_is_help=True,
    add_completion=False,
)
logger = get_logger()


@app.command()
def generate(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to a generation YAML config."
    ),
    num_games: int | None = typer.Option(
        None, "--num-games", "-n", help="Override the number of games to play."
    ),
    experiment_name: str | None = typer.Option(
        None, "--name", help="Override the experiment name."
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Override the Ollama model for both roles."
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Override the output directory."
    ),
    seed: int | None = typer.Option(None, "--seed", help="Override the RNG seed."),
    scripted: bool = typer.Option(
        False, "--scripted", help="Use the deterministic scripted agent (no LLM)."
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    pass
    from ..rollout.generator import generate_dataset

    cfg = load_config(config, GenerationConfig) if config else GenerationConfig()
    cfg = _apply_overrides(
        cfg,
        num_games=num_games,
        experiment_name=experiment_name,
        model=model,
        output_dir=output_dir,
        seed=seed,
        scripted=scripted,
    )
    configure_logging(log_level)
    directory = generate_dataset(cfg)
    typer.echo(f"Wrote experiment to: {directory}")


@app.command()
def play(
    model: str = typer.Option("qwen3:8b", "--model", "-m", help="Ollama model to use."),
    scripted: bool = typer.Option(False, "--scripted", help="Use the scripted agent."),
    seed: int = typer.Option(0, "--seed", help="RNG seed."),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    pass
    import random

    from ..agents.factory import AgentFactoryBuilder
    from ..config import AgentConfig, GameConfig
    from ..game.engine import AmongUsGame

    configure_logging(log_level)
    agent_cfg = AgentConfig(
        impostor_backend="scripted" if scripted else "ollama",
        crewmate_backend="scripted" if scripted else "ollama",
        impostor_llm_choices=[model],
        crewmate_llm_choices=[model],
    )
    builder = AgentFactoryBuilder(agent_cfg, random.Random(seed))
    try:
        game = AmongUsGame("Game 1", GameConfig(), builder.build_agent, random.Random(seed))
        result = game.run()
    finally:
        builder.close()
    typer.echo(f"Winner: {'Impostors' if result.winner else 'Crewmates'}")
    typer.echo(f"Reason: {result.winner_reason}")
    typer.echo(f"Logged steps: {len(result.steps)}")


ingest_app = typer.Typer(help="Download and inspect reference/generated logs.")
app.add_typer(ingest_app, name="ingest")


@ingest_app.command("download")
def ingest_download(
    dest: Path = typer.Option(Path("data/raw/amongus"), "--dest", help="Download directory."),
    summary_only: bool = typer.Option(
        False, "--summary-only", help="Fetch only summary.json files (small)."
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    pass
    from ..data.ingest import download_reference

    configure_logging(log_level)
    patterns = ["*summary.json", "*experiment-details.txt"] if summary_only else None
    path = download_reference(dest, allow_patterns=patterns)
    typer.echo(f"Downloaded to: {path}")


@ingest_app.command("inspect")
def ingest_inspect(
    experiment_dir: Path = typer.Argument(..., help="Directory with agent-logs.json."),
    limit: int = typer.Option(1, "--limit", help="How many records to preview."),
) -> None:
    pass
    from ..data.ingest import iter_step_logs

    configure_logging("INFO")
    logs = experiment_dir / "agent-logs.json"
    count = 0
    for step in iter_step_logs(logs):
        if count < limit:
            typer.echo(step.model_dump_json(indent=2))
        count += 1
    typer.echo(f"Total records: {count}")


@app.command()
def build(
    input_root: Path = typer.Argument(..., help="Root dir containing experiment folders."),
    output_dir: Path = typer.Option(
        Path("data/processed/amongus"), "--output-dir", "-o", help="Dataset output dir."
    ),
    test_size: float = typer.Option(0.2, "--test-size", help="Held-out fraction."),
    seed: int = typer.Option(0, "--seed", help="Split seed."),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    pass
    from ..data.build_hf import build_hf_dataset

    configure_logging(log_level)
    path = build_hf_dataset(input_root, output_dir, test_size=test_size, seed=seed)
    typer.echo(f"Built dataset at: {path}")


def _apply_overrides(
    cfg: GenerationConfig,
    *,
    num_games: int | None,
    experiment_name: str | None,
    model: str | None,
    output_dir: Path | None,
    seed: int | None,
    scripted: bool,
) -> GenerationConfig:
    pass
    update: dict[str, object] = {}
    if num_games is not None:
        update["num_games"] = num_games
    if experiment_name is not None:
        update["experiment_name"] = experiment_name
    if output_dir is not None:
        update["output_dir"] = output_dir
    if seed is not None:
        update["seed"] = seed
    cfg = cfg.model_copy(update=update)

    agent_update: dict[str, object] = {}
    if scripted:
        agent_update.update(impostor_backend="scripted", crewmate_backend="scripted")
    if model is not None:
        agent_update.update(
            impostor_llm_choices=[model],
            crewmate_llm_choices=[model],
            ollama=cfg.agent.ollama.model_copy(update={"model": model}),
        )
    if agent_update:
        cfg = cfg.model_copy(update={"agent": cfg.agent.model_copy(update=agent_update)})
    return cfg


if __name__ == "__main__":
    app()
