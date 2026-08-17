from __future__ import annotations

import sys
from pathlib import Path

import typer

from ..config import GenerationConfig, load_config
from ..logging import configure_logging, get_logger


from ..viz.contrastive_pages import DEFAULT_PAIR_LIMIT

app = typer.Typer(
    name="amongus",
    help="Among Us deception sandbox: dataset generation and preprocessing.",
    no_args_is_help=True,
    add_completion=False,
)
logger = get_logger()


@app.callback()
def _main() -> None:
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
    max_turns: int | None = typer.Option(
        None,
        "--max-turns",
        help="Stop once about this many turns are written (games are never cut in half).",
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
    from ..rollout.generator import generate_dataset

    cfg = load_config(config, GenerationConfig) if config else GenerationConfig()
    cfg = _apply_overrides(
        cfg,
        num_games=num_games,
        max_turns=max_turns,
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
        game = AmongUsGame(
            "Game 1",
            GameConfig(),
            builder.build_agent,
            random.Random(seed),
            agent_config=agent_cfg,
            seed=seed,
        )
        result = game.run()
    finally:
        builder.close()
    speech = sum(1 for t in result.turns if t.model_output.get("speech"))
    typer.echo(f"Winner: {'Impostors' if result.winner else 'Crewmates'}")
    typer.echo(f"Reason: {result.winner_reason}")
    typer.echo(f"Logged turns: {len(result.turns)} ({speech} utterances)")


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
    schema: str = typer.Option(
        "v2",
        "--schema",
        help="'v2' (game-level splits, statement labels) or 'v1' (legacy row split).",
    ),
    strategy: str = typer.Option(
        "random",
        "--strategy",
        help="v2 split strategy: random | held_out_model | held_out_map | "
        "held_out_prompt_template | held_out_strategy | held_out_deception_type | "
        "held_out_game_configuration.",
    ),
    speak_only: bool = typer.Option(
        False, "--speak-only", help="v2: keep only turns that produced an utterance."
    ),
    labelled_only: bool = typer.Option(
        False,
        "--labelled-only",
        help="v2: keep only rows labelled truthful or deceptive (a usable binary target).",
    ),
    test_size: float = typer.Option(0.2, "--test-size", help="v1 only: held-out fraction."),
    seed: int = typer.Option(0, "--seed", help="Split seed."),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..data.build_hf import build_hf_dataset, build_v2_dataset

    configure_logging(log_level)
    if schema not in ("v1", "v2"):
        raise typer.BadParameter("--schema must be 'v1' or 'v2'.")
    if schema == "v1":
        path = build_hf_dataset(input_root, output_dir, test_size=test_size, seed=seed)
    else:
        path = build_v2_dataset(
            input_root,
            output_dir,
            strategy=strategy,
            seed=seed,
            speak_only=speak_only,
            labelled_only=labelled_only,
        )
    typer.echo(f"Built dataset at: {path}")


@app.command()
def validate(
    experiment_dir: Path = typer.Argument(..., help="Schema 2.0 experiment dir (turns.jsonl)."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Also write the report as JSON to this path."
    ),
    log_level: str = typer.Option("WARNING", "--log-level", help="Logging level."),
) -> None:
    import json as _json

    from ..data.validate import validate_experiment

    configure_logging(log_level)
    report = validate_experiment(experiment_dir)
    _emit(report.render(), None)
    if output is not None:
        output.write_text(
            _json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        typer.echo(f"Wrote validation report to: {output}")
    if not report.ok:
        raise typer.Exit(code=1)


@app.command()
def split(
    experiment_dir: Path = typer.Argument(..., help="Schema 2.0 experiment dir (games.jsonl)."),
    strategy: str = typer.Option(
        "random",
        "--strategy",
        help="random | held_out_model | held_out_map | held_out_prompt_template | "
        "held_out_strategy | held_out_deception_type | held_out_game_configuration.",
    ),
    seed: int = typer.Option(0, "--seed", help="Deterministic split seed."),
    train: float = typer.Option(0.7, "--train", help="Train ratio (random strategy)."),
    validation: float = typer.Option(0.15, "--validation", help="Validation ratio."),
    test: float = typer.Option(0.15, "--test", help="Test ratio."),
    holdout: str | None = typer.Option(
        None, "--holdout", help="Comma-separated factor values to force into test."
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..data.splits import build_splits, check_split_isolation, write_splits

    configure_logging(log_level)
    values = [v.strip() for v in holdout.split(",")] if holdout else None
    assignment = build_splits(
        experiment_dir,
        strategy=strategy,
        seed=seed,
        ratios={"train": train, "validation": validation, "test": test},
        holdout_values=values,
    )
    path = write_splits(experiment_dir, assignment)

    from ..data.ingest import iter_turns

    violations = check_split_isolation(assignment, list(iter_turns(experiment_dir)))
    typer.echo(f"Split ({assignment.strategy}, seed={seed}): {assignment.counts()}")
    if assignment.holdout_values:
        typer.echo(f"Held out {assignment.factor} = {assignment.holdout_values}")
    typer.echo(f"Wrote: {path}")
    if violations:
        for violation in violations:
            typer.echo(f"[CRITICAL] {violation}")
        raise typer.Exit(code=1)


@app.command()
def migrate(
    source: Path = typer.Argument(..., help="v1 experiment dir containing agent-logs.json."),
    dest: Path = typer.Option(..., "--dest", "-d", help="Directory to write turns.jsonl into."),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..data.migrate import migrate_directory

    configure_logging(log_level)
    path = migrate_directory(source, dest)
    typer.echo(f"Migrated to: {path}")
    typer.echo(
        "Note: migrated records carry no private state, world-state references or "
        "claim annotations; their deception status is 'ambiguous'."
    )


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


@viz_app.command("site")
def viz_site(
    root: Path = typer.Argument(
        Path("expt-logs"), help="Tree of schema 2.0 experiments (or a single one)."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output folder (default: 'viewer' beside the root)."
    ),
    limit: int | None = typer.Option(
        None, "--limit", "-n", help="Only include the first N games per dataset."
    ),
    probes: Path = typer.Option(
        Path("data/probes"),
        "--probes",
        "-p",
        help="Probe folder for the training and eval-suite pages (top level only).",
    ),
    contrastive: Path = typer.Option(
        Path("data/processed/contrastive"),
        "--contrastive",
        help="Built contrastive dataset (dataset 2) for the training-data page.",
    ),
    contrastive_pairs: int = typer.Option(
        DEFAULT_PAIR_LIMIT,
        "--contrastive-pairs",
        help="Max contrast pairs to embed in that page (0 = all).",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..viz.site import build_site

    configure_logging(log_level)
    directory = build_site(
        root,
        output,
        limit=limit,
        probes_dir=probes,
        contrastive_dir=contrastive,
        contrastive_pairs=contrastive_pairs,
    )
    typer.echo(f"Wrote review site to: {directory / 'index.html'}")


def _select_frame(frames: list, step: int | None):
    if not frames:
        raise typer.BadParameter("No frames to visualize.")
    if step is None:
        return frames[-1]
    exact = next((f for f in frames if f.step == step), None)
    return exact or min(frames, key=lambda f: abs(f.step - step))


def _emit(text: str, output: Path | None) -> None:
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
    pooling: str | None = typer.Option(
        None, "--pooling", help="Token pooling: last | mean | last_n."
    ),
    pooling_tokens: int | None = typer.Option(
        None, "--pooling-tokens", help="Tokens per example for --pooling last_n."
    ),
    debug_tokens: int | None = typer.Option(
        None, "--debug-tokens", help="Print the selected tokens for N examples first."
    ),
    batch_size: int | None = typer.Option(
        None, "--batch-size", help="Prompts per forward pass (extraction)."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Cap examples per split (quick runs)."),
    device: str | None = typer.Option(None, "--device", help="auto | cpu | cuda."),
    load_in_4bit: bool = typer.Option(
        False, "--load-in-4bit", help="Quantize base model to 4-bit."
    ),
    load_in_8bit: bool = typer.Option(
        False, "--load-in-8bit", help="Quantize base model to 8-bit."
    ),
    wandb: bool = typer.Option(False, "--wandb", help="Enable Weights & Biases tracking."),
    mlflow: bool = typer.Option(False, "--mlflow", help="Enable MLflow tracking."),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..probes.config import ProbeTrainConfig
    from ..probes.train import train_probes

    cfg = load_config(config, ProbeTrainConfig) if config else ProbeTrainConfig()
    cfg = _override_probe_config(
        cfg,
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        model=model,
        layers=layers,
        pooling=pooling,
        pooling_tokens=pooling_tokens,
        debug_tokens=debug_tokens,
        batch_size=batch_size,
        limit=limit,
        device=device,
        load_in_4bit=load_in_4bit,
        load_in_8bit=load_in_8bit,
        wandb=wandb,
        mlflow=mlflow,
    )

    configure_logging(log_level)
    result = train_probes(cfg)
    best = result.best()
    tokens = (
        f", {result.pooling_tokens} tokens/example -> {result.n_train_tokens} samples"
        if result.pooling == "last_n"
        else ""
    )
    typer.echo(
        f"Trained probes on {result.n_train} examples "
        f"({result.model_name}, pooling={result.pooling}{tokens}).\n"
        f"Best layer {best.layer}: acc={best.accuracy:.3f} f1={best.f1:.3f} "
        f"auroc={'n/a' if best.auroc is None else f'{best.auroc:.3f}'}\n"
        f"Saved probe -> {result.probe_path}\nMetrics -> {result.metrics_path}"
    )


@probe_app.command("tokens")
def probe_tokens(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Probe-training YAML whose selection to preview."
    ),
    model: str | None = typer.Option(None, "--model", help="Override the tokenizer's model id."),
    pooling_tokens: int | None = typer.Option(
        None, "--pooling-tokens", help="Override N (default: the config's)."
    ),
    limit: int = typer.Option(3, "--limit", help="How many examples to print."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the preview to a file instead of stdout."
    ),
    log_level: str = typer.Option("WARNING", "--log-level", help="Logging level."),
) -> None:
    from transformers import AutoTokenizer

    from ..net import configure_tls
    from ..probes.activations import build_prompt_with_span, describe_selected_tokens
    from ..probes.config import ProbeTrainConfig
    from ..probes.train import _load_rows

    configure_logging(log_level)
    cfg = load_config(config, ProbeTrainConfig) if config else ProbeTrainConfig()
    count = pooling_tokens or cfg.tokens_per_example
    configure_tls()
    tokenizer = AutoTokenizer.from_pretrained(model or cfg.model.name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    train_rows, _ = _load_rows(cfg.dataset_dir, limit)
    pairs = [
        build_prompt_with_span(r, tokenizer, use_chat_template=cfg.use_chat_template)
        for r in train_rows
    ]
    _emit(
        describe_selected_tokens(
            tokenizer,
            [text for text, _ in pairs],
            pooling_tokens=count,
            max_length=cfg.max_length,
            content_spans=[span for _, span in pairs],
            limit=limit,
        ),
        output,
    )


@probe_app.command("eval")
def probe_eval(
    probe_path: Path = typer.Option(
        Path("data/probes/gpt2/probe.joblib"),
        "--probe",
        "-p",
        help="Trained probe.joblib to evaluate (from `probe train`).",
    ),
    dataset_dir: Path = typer.Option(
        Path("data/processed/amongus"),
        "--dataset-dir",
        help="Game-log DatasetDict dir (from `amongus build`).",
    ),
    split: str = typer.Option("all", "--split", help="Which split to score: all | train | test."),
    text_mode: str = typer.Option(
        "response",
        "--text-mode",
        help="Base-model input per row: 'response' (agent utterance) | 'full' (with context).",
    ),
    speak_only: bool = typer.Option(
        False, "--speak-only", help="Only score discussion utterances (is_speak)."
    ),
    device: str = typer.Option("auto", "--device", help="auto | cpu | cuda."),
    batch_size: int = typer.Option(16, "--batch-size", help="Prompts per forward pass."),
    limit: int | None = typer.Option(None, "--limit", help="Cap rows (quick runs)."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Report JSON path (default: <probe_dir>/eval_amongus.json)."
    ),
    reuse: bool = typer.Option(
        True,
        "--reuse/--no-reuse",
        help="Reuse an existing report at the output path when its settings match "
        "(skips re-running the model). Use --no-reuse to force recomputation.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..probes.eval import evaluate_probe

    if text_mode not in ("response", "full"):
        raise typer.BadParameter("--text-mode must be 'response' or 'full'.")

    configure_logging(log_level)
    report = evaluate_probe(
        probe_path=probe_path,
        dataset_dir=dataset_dir,
        split=split,
        text_mode=text_mode,
        speak_only=speak_only,
        device=device,
        batch_size=batch_size,
        limit=limit,
        output_path=output,
        reuse=reuse,
    )
    typer.echo(
        f"Evaluated {report.model_name} probe (layer {report.layer}) on "
        f"{report.n} game-log rows [{split}].\n"
        f"{report.summary_line()}\n"
        f"Report -> {report.report_path}"
    )


@probe_app.command("compare")
def probe_compare(
    probes: list[Path] = typer.Option(
        ...,
        "--probe",
        "-p",
        help="A probe.joblib to include (repeat -p for each model to compare).",
    ),
    dataset_dir: Path = typer.Option(
        Path("data/processed/amongus"),
        "--dataset-dir",
        help="Game-log DatasetDict dir (from `amongus build`).",
    ),
    output_dir: Path = typer.Option(
        Path("data/probes/comparison"),
        "--output-dir",
        "-o",
        help="Where to write comparison.html, comparison.json and per-probe reports.",
    ),
    labels: str | None = typer.Option(
        None, "--labels", help="Comma-separated display labels (default: each probe's dir name)."
    ),
    fmt: str = typer.Option(
        "png", "--format", help="Chart output: 'png' (matplotlib) | 'html' (interactive SVG)."
    ),
    split: str = typer.Option("all", "--split", help="Which split to score: all | train | test."),
    text_mode: str = typer.Option(
        "response",
        "--text-mode",
        help="Base-model input per row: 'response' (agent utterance) | 'full' (with context).",
    ),
    speak_only: bool = typer.Option(
        False, "--speak-only", help="Only score discussion utterances (is_speak)."
    ),
    device: str = typer.Option("auto", "--device", help="auto | cpu | cuda."),
    batch_size: int = typer.Option(16, "--batch-size", help="Prompts per forward pass."),
    limit: int | None = typer.Option(None, "--limit", help="Cap rows per probe (quick runs)."),
    reuse: bool = typer.Option(
        True,
        "--reuse/--no-reuse",
        help="Reuse each probe's existing eval_amongus.json when its settings match "
        "(skips re-running that model). Use --no-reuse to force recomputation.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..probes.eval import compare_probes

    if text_mode not in ("response", "full"):
        raise typer.BadParameter("--text-mode must be 'response' or 'full'.")
    if fmt not in ("png", "html"):
        raise typer.BadParameter("--format must be 'png' or 'html'.")
    label_list = [x.strip() for x in labels.split(",") if x.strip()] if labels is not None else None
    if label_list is not None and len(label_list) != len(probes):
        raise typer.BadParameter(
            f"Got {len(label_list)} --labels for {len(probes)} --probe options."
        )

    configure_logging(log_level)
    comparison = compare_probes(
        probe_paths=probes,
        dataset_dir=dataset_dir,
        split=split,
        text_mode=text_mode,
        speak_only=speak_only,
        device=device,
        batch_size=batch_size,
        limit=limit,
        output_dir=output_dir,
        labels=label_list,
        fmt=fmt,
        reuse=reuse,
    )
    typer.echo(f"Compared {len(comparison.reports)} probes on split [{split}]:")
    for report in comparison.reports:
        typer.echo(f"  {report.label:<20} {report.summary_line()}")
    best = comparison.best()
    typer.echo(
        f"Best AUROC: {best.label} "
        f"({'n/a' if best.auroc is None else f'{best.auroc:.3f}'}).\n"
        f"Chart -> {comparison.chart_path}\nJSON  -> {comparison.json_path}"
    )


@probe_app.command("suite")
def probe_suite(
    config_path: Path = typer.Option(
        ..., "--config", "-c", help="Evaluation-suite YAML (see configs/eval/)."
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Override the config's output_dir."
    ),
    datasets_root: list[Path] = typer.Option(
        [], "--root", help="Override the dataset roots to search (repeatable)."
    ),
    probe: list[Path] = typer.Option(
        [], "--probe", "-p", help="Evaluate only these probe.joblib paths (repeatable)."
    ),
    label_source: str | None = typer.Option(
        None,
        "--label-source",
        help="auto | grounded | holistic | impostor. Overrides the config.",
    ),
    max_rows: int | None = typer.Option(
        None, "--max-rows", help="Cap rows per dataset (quick runs)."
    ),
    speak_only: bool | None = typer.Option(
        None, "--speak-only/--all-turns", help="Restrict to discussion utterances."
    ),
    device: str | None = typer.Option(None, "--device", help="auto | cpu | cuda."),
    batch_size: int | None = typer.Option(None, "--batch-size", help="Prompts per forward pass."),
    reuse: bool | None = typer.Option(
        None,
        "--reuse/--no-reuse",
        help="Reuse matching rows from a previous results.json instead of re-running.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..probes.suite import run_suite
    from ..probes.suite_config import EvalSuiteConfig

    cfg = load_config(config_path, EvalSuiteConfig)
    if output_dir is not None:
        cfg = cfg.model_copy(update={"output_dir": output_dir})
    if datasets_root:
        cfg = cfg.model_copy(
            update={"datasets": cfg.datasets.model_copy(update={"roots": list(datasets_root)})}
        )
    if probe:
        cfg = cfg.model_copy(
            update={"probes": cfg.probes.model_copy(update={"paths": list(probe), "discover": []})}
        )
    if label_source is not None:
        if label_source not in ("auto", "grounded", "holistic", "impostor"):
            raise typer.BadParameter("--label-source must be auto, grounded, holistic or impostor.")
        cfg = cfg.model_copy(update={"label_source": label_source})
    if max_rows is not None:
        cfg = cfg.model_copy(
            update={"datasets": cfg.datasets.model_copy(update={"max_rows": max_rows})}
        )
    if speak_only is not None:
        cfg = cfg.model_copy(
            update={"datasets": cfg.datasets.model_copy(update={"speak_only": speak_only})}
        )
    if device is not None:
        cfg = cfg.model_copy(update={"device": device})
    if batch_size is not None:
        cfg = cfg.model_copy(update={"batch_size": batch_size})
    if reuse is not None:
        cfg = cfg.model_copy(update={"reuse": reuse})

    configure_logging(log_level)
    report = run_suite(cfg)

    lifts = report.lift()
    typer.echo(
        f"Scored {len(report.probes)} probe(s) on {len(report.datasets)} dataset(s) "
        f"-> {len(report.rows)} rows."
    )
    if lifts:
        typer.echo("\nAUROC lift over the untrained control (best first):")
        for probe_name, dataset_name, lift in lifts:
            typer.echo(f"  {lift:+.3f}  {probe_name:<18} {dataset_name}")
    for skip in report.skipped:
        typer.echo(f"  skipped {skip['dataset']}: {skip['reason']}")
    typer.echo(f"\nJSON  -> {report.results_path}")
    if report.chart_path:
        typer.echo(f"Chart -> {report.chart_path}")


annotate_app = typer.Typer(help="Post-hoc GPT-4o-mini annotation of a generated dataset.")
app.add_typer(annotate_app, name="annotate")


@annotate_app.command("gpt")
def annotate_gpt(
    dataset_dir: Path = typer.Argument(..., help="Schema 2.0 experiment dir (turns.jsonl)."),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Override the model (default: $OPENAI_ANNOTATION_MODEL, else gpt-4o-mini).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Restart a gpt4omini/ folder that is already fully annotated. Never needed to "
        "resume an incomplete one.",
    ),
    wait: bool = typer.Option(
        False, "--wait/--no-wait", help="Block, polling until the batch finishes, then merge."
    ),
    poll_interval: float = typer.Option(
        20.0, "--poll-interval", help="Seconds between polls when --wait is set."
    ),
    wait_timeout: float | None = typer.Option(
        None, "--wait-timeout", help="Optional wall-clock budget in seconds for --wait."
    ),
    batch_size: int = typer.Option(
        300,
        "--batch-size",
        help="Max turns processed per invocation (Batch API job size, or live-mode chunk "
        "size). Lower this if you hit 'token_limit_exceeded' (an org-wide enqueued-token "
        "cap); extra pending turns just wait for the next invocation.",
    ),
    live: bool = typer.Option(
        False,
        "--live",
        help="Skip the Batch API and call chat.completions directly, one turn at a time. "
        "No queueing delay or enqueued-token cap (ordinary rate limits apply and are waited "
        "out automatically), at full per-token price instead of the Batch API's ~50% "
        "discount. Ignores --wait/--poll-interval/--wait-timeout.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..gpt_annotation.pipeline import run_annotation

    configure_logging(log_level)
    result = run_annotation(
        dataset_dir,
        model=model,
        overwrite=overwrite,
        wait=wait,
        poll_interval_s=poll_interval,
        poll_timeout_s=wait_timeout,
        batch_size=batch_size,
        live=live,
    )
    typer.echo(f"[{result.status}] {result.message}")
    typer.echo(f"Output: {result.out_dir}")


@annotate_app.command("holistic")
def annotate_holistic(
    dataset_dir: Path = typer.Argument(
        ..., help="Dir containing agent-logs.json or agent-logs-compact.json."
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Override the model (default: $OPENAI_ANNOTATION_MODEL, else gpt-4o-mini).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Restart a gpt4omini_holistic/ folder that is already fully rated. Never needed to "
        "resume an incomplete one.",
    ),
    wait: bool = typer.Option(
        False, "--wait/--no-wait", help="Block, polling until the batch finishes, then merge."
    ),
    poll_interval: float = typer.Option(
        20.0, "--poll-interval", help="Seconds between polls when --wait is set."
    ),
    wait_timeout: float | None = typer.Option(
        None, "--wait-timeout", help="Optional wall-clock budget in seconds for --wait."
    ),
    batch_size: int = typer.Option(
        300,
        "--batch-size",
        help="Max rows processed per invocation (Batch API job size, or live-mode chunk "
        "size). Lower this if you hit 'token_limit_exceeded' (an org-wide enqueued-token "
        "cap); extra pending rows just wait for the next invocation.",
    ),
    live: bool = typer.Option(
        False,
        "--live",
        help="Skip the Batch API and call chat.completions directly, one row at a time. "
        "No queueing delay or enqueued-token cap (ordinary rate limits apply and are waited "
        "out automatically), at full per-token price instead of the Batch API's ~50% "
        "discount. Ignores --wait/--poll-interval/--wait-timeout.",
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    from ..gpt_annotation.legacy_pipeline import run_holistic_annotation

    configure_logging(log_level)
    result = run_holistic_annotation(
        dataset_dir,
        model=model,
        overwrite=overwrite,
        wait=wait,
        poll_interval_s=poll_interval,
        poll_timeout_s=wait_timeout,
        batch_size=batch_size,
        live=live,
    )
    typer.echo(f"[{result.status}] {result.message}")
    typer.echo(f"Output: {result.out_dir}")


def _override_probe_config(cfg, **flags):
    model_update: dict[str, object] = {}
    if flags["model"] is not None:
        model_update["name"] = flags["model"]
    if flags["device"] is not None:
        model_update["device"] = flags["device"]
    if flags["load_in_4bit"] or flags["load_in_8bit"]:
        model_update["quantization"] = cfg.model.quantization.model_copy(
            update={"load_in_4bit": flags["load_in_4bit"], "load_in_8bit": flags["load_in_8bit"]}
        )
    if model_update:
        cfg = cfg.model_copy(update={"model": cfg.model.model_copy(update=model_update)})

    if flags["wandb"] or flags["mlflow"]:
        tracking = cfg.tracking.model_copy()
        if flags["wandb"]:
            tracking.wandb = tracking.wandb.model_copy(update={"enabled": True})
        if flags["mlflow"]:
            tracking.mlflow = tracking.mlflow.model_copy(update={"enabled": True})
        cfg = cfg.model_copy(update={"tracking": tracking})

    top: dict[str, object] = {}
    if flags["dataset_dir"] is not None:
        top["dataset_dir"] = flags["dataset_dir"]
    if flags["output_dir"] is not None:
        top["output_dir"] = flags["output_dir"]
    if flags["layers"] is not None:
        top["layers"] = [int(x.strip()) for x in flags["layers"].split(",") if x.strip()]
    if flags["pooling"] is not None:
        top["pooling"] = flags["pooling"]
    if flags.get("pooling_tokens") is not None:
        top["pooling_tokens"] = flags["pooling_tokens"]
    if flags.get("debug_tokens") is not None:
        top["debug_tokens"] = flags["debug_tokens"]
    if flags["batch_size"] is not None:
        top["extraction_batch_size"] = flags["batch_size"]
    if flags["limit"] is not None:
        top["limit"] = flags["limit"]
    cfg = cfg.model_copy(update=top)

    if flags.get("pooling_tokens") is not None and cfg.pooling != "last_n":
        msg = f"--pooling-tokens needs --pooling last_n (pooling is {cfg.pooling!r})."
        raise typer.BadParameter(msg)
    return cfg


def _apply_overrides(
    cfg: GenerationConfig,
    *,
    num_games: int | None,
    experiment_name: str | None,
    max_turns: int | None = None,
    model: str | None,
    impostor_model: str | None = None,
    crewmate_model: str | None = None,
    output_dir: Path | None,
    seed: int | None,
    scripted: bool,
) -> GenerationConfig:
    update: dict[str, object] = {}
    if num_games is not None:
        update["num_games"] = num_games
    if max_turns is not None:
        update["max_turns"] = max_turns
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
