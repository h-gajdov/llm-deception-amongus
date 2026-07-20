

from __future__ import annotations

import sys
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


@app.callback()
def _main() -> None:
    pass
    from ..net import configure_tls

    configure_tls()


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
        None, "--model", "-m", help="Model for both roles (e.g. qwen3:8b or openai:gpt-4o-mini)."
    ),
    impostor_model: str | None = typer.Option(
        None, "--impostor-model", help="Model for impostors (backend prefix allowed)."
    ),
    crewmate_model: str | None = typer.Option(
        None, "--crewmate-model", help="Model for crewmates (backend prefix allowed)."
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
        impostor_model=impostor_model,
        crewmate_model=crewmate_model,
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


viz_app = typer.Typer(help="Visualize a game: timeline, ASCII map, or interactive HTML.")
app.add_typer(viz_app, name="viz")


@viz_app.command("timeline")
def viz_timeline(
    experiment_dir: Path = typer.Argument(..., help="Directory with agent-logs.json."),
    game: str | None = typer.Option(None, "--game", "-g", help="Game label, e.g. 'Game 43'."),
    events_only: bool = typer.Option(
        False, "--events-only", help="Hide routine moves/tasks; show only key events."
    ),
    color: bool = typer.Option(
        True, "--color/--no-color", help="Show impostor lines in red (stdout only)."
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write to a file instead."),
) -> None:
    pass
    from ..viz.reconstruct import load_game, reconstruct_frames
    from ..viz.timeline import render_timeline

    game_index, steps, winner, roster = load_game(experiment_dir, game)
    frames, roster = reconstruct_frames(steps, roster)
                                                                       
    use_color = color and output is None
    text = render_timeline(
        game_index, frames, roster, winner, events_only=events_only, color=use_color
    )
    _emit(text, output)


@viz_app.command("map")
def viz_map(
    experiment_dir: Path = typer.Argument(..., help="Directory with agent-logs.json."),
    game: str | None = typer.Option(None, "--game", "-g", help="Game label, e.g. 'Game 43'."),
    step: int | None = typer.Option(
        None, "--step", "-s", help="Step number to draw (default: last step)."
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write to a file instead."),
) -> None:
    pass
    from ..viz.ascii_map import render_ascii_map
    from ..viz.reconstruct import load_game, reconstruct_frames

    game_index, steps, _winner, roster = load_game(experiment_dir, game)
    frames, roster = reconstruct_frames(steps, roster)
    frame = _select_frame(frames, step)
    _emit(render_ascii_map(frame, roster, game_index), output)


@viz_app.command("html")
def viz_html(
    experiment_dir: Path = typer.Argument(..., help="Directory with agent-logs.json."),
    game: str | None = typer.Option(None, "--game", "-g", help="Game label, e.g. 'Game 43'."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output .html path (default: <dir>/viz_<game>.html)."
    ),
) -> None:
    pass
    from ..viz.reconstruct import load_game, reconstruct_frames
    from ..viz.render_html import build_html

    game_index, steps, winner, roster = load_game(experiment_dir, game)
    frames, roster = reconstruct_frames(steps, roster)
    html = build_html(game_index, frames, roster, winner)
    if output is None:
        slug = game_index.lower().replace(" ", "_")
        output = experiment_dir / f"viz_{slug}.html"
    output.write_text(html, encoding="utf-8")
    typer.echo(f"Wrote interactive visualization to: {output}")


def _select_frame(frames: list, step: int | None):
    pass
    if not frames:
        raise typer.BadParameter("No frames to visualize.")
    if step is None:
        return frames[-1]
    exact = next((f for f in frames if f.step == step), None)
    return exact or min(frames, key=lambda f: abs(f.step - step))


def _emit(text: str, output: Path | None) -> None:
    pass
    if output is not None:
        output.write_text(text, encoding="utf-8")
        typer.echo(f"Wrote visualization to: {output}")
        return
    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


contrastive_app = typer.Typer(
    help="Dataset 2: contrastive honest/dishonest data for training deception probes."
)
app.add_typer(contrastive_app, name="contrastive")


@contrastive_app.command("build")
def contrastive_build(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to a contrastive YAML config."
    ),
    sources: str | None = typer.Option(
        None, "--sources", help="Comma-separated sources: tqa,dqa,repeng."
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Dataset output directory."
    ),
    test_size: float | None = typer.Option(None, "--test-size", help="Held-out fraction."),
    seed: int | None = typer.Option(None, "--seed", help="Shuffle/split seed."),
    repeng_statements: Path | None = typer.Option(
        None, "--repeng-statements", help="CSV of true/false statements (for the repeng source)."
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    pass
    from ..data.contrastive.build import build_contrastive_dataset
    from ..data.contrastive.config import ContrastiveConfig
    from ..data.contrastive.schema import Source

    cfg = load_config(config, ContrastiveConfig) if config else ContrastiveConfig()
    update: dict[str, object] = {}
    if sources is not None:
        update["sources"] = [Source(s.strip()) for s in sources.split(",") if s.strip()]
    if output_dir is not None:
        update["output_dir"] = output_dir
    if test_size is not None:
        update["test_size"] = test_size
    if seed is not None:
        update["seed"] = seed
    if repeng_statements is not None:
        update["repeng_statements_path"] = repeng_statements
    cfg = cfg.model_copy(update=update)

    configure_logging(log_level)
    path = build_contrastive_dataset(cfg)
    typer.echo(f"Built contrastive dataset at: {path}")


@contrastive_app.command("viz")
def contrastive_viz(
    dataset: Path = typer.Argument(
        ..., help="Contrastive dataset dir or .parquet (from `contrastive build`)."
    ),
    html: Path | None = typer.Option(
        None, "--html", help="Write an interactive HTML browser to this path."
    ),
    limit: int = typer.Option(
        400, "--limit", help="Max contrast pairs to embed in the HTML (0 = all)."
    ),
) -> None:
    pass
    from ..viz.contrastive_viz import (
        build_contrastive_html,
        load_contrastive_rows,
        render_summary_text,
        summarize,
    )

    configure_logging("INFO")
    rows = load_contrastive_rows(dataset)
    _emit(render_summary_text(summarize(rows), dataset), None)
    if html is not None:
        html.write_text(build_contrastive_html(rows, dataset, limit=limit), encoding="utf-8")
        typer.echo(f"Wrote contrastive visualization to: {html}")


probe_app = typer.Typer(help="Train linear deception probes on dataset 2 activations.")
app.add_typer(probe_app, name="probe")


@probe_app.command("train")
def probe_train(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to a probe-training YAML config."
    ),
    dataset_dir: Path | None = typer.Option(
        None, "--dataset-dir", help="Contrastive DatasetDict dir (from `contrastive build`)."
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Where to write probe.joblib and metrics.json."
    ),
    model: str | None = typer.Option(None, "--model", help="HF model id to probe."),
    layers: str | None = typer.Option(
        None, "--layers", help="Comma-separated layer indices (default: all)."
    ),
    pooling: str | None = typer.Option(None, "--pooling", help="Token pooling: last | mean."),
    batch_size: int | None = typer.Option(None, "--batch-size", help="Prompts per forward pass."),
    limit: int | None = typer.Option(None, "--limit", help="Cap examples per split (quick runs)."),
    device: str | None = typer.Option(None, "--device", help="auto | cpu | cuda."),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    pass
    from ..probes.config import ProbeTrainConfig
    from ..probes.train import train_probes

    cfg = load_config(config, ProbeTrainConfig) if config else ProbeTrainConfig()
    update: dict[str, object] = {}
    if dataset_dir is not None:
        update["dataset_dir"] = dataset_dir
    if output_dir is not None:
        update["output_dir"] = output_dir
    if model is not None:
        update["model_name"] = model
    if layers is not None:
        update["layers"] = [int(x.strip()) for x in layers.split(",") if x.strip()]
    if pooling is not None:
        update["pooling"] = pooling
    if batch_size is not None:
        update["batch_size"] = batch_size
    if limit is not None:
        update["limit"] = limit
    if device is not None:
        update["device"] = device
    cfg = cfg.model_copy(update=update)

    configure_logging(log_level)
    result = train_probes(cfg)
    best = result.best()
    typer.echo(
        f"Trained probes on {result.n_train} examples "
        f"({result.model_name}, pooling={result.pooling}).\n"
        f"Best layer {best.layer}: acc={best.accuracy:.3f} f1={best.f1:.3f} "
        f"auroc={'n/a' if best.auroc is None else f'{best.auroc:.3f}'}\n"
        f"Saved probe -> {result.probe_path}\nMetrics -> {result.metrics_path}"
    )


def _apply_overrides(
    cfg: GenerationConfig,
    *,
    num_games: int | None,
    experiment_name: str | None,
    model: str | None,
    impostor_model: str | None = None,
    crewmate_model: str | None = None,
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
        agent_update.update(impostor_llm_choices=[model], crewmate_llm_choices=[model])
    if impostor_model is not None:
        agent_update["impostor_llm_choices"] = [impostor_model]
    if crewmate_model is not None:
        agent_update["crewmate_llm_choices"] = [crewmate_model]
    if agent_update:
        cfg = cfg.model_copy(update={"agent": cfg.agent.model_copy(update=agent_update)})
    return cfg


if __name__ == "__main__":
    app()
