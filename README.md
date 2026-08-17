# LLM Deception Among Us

LLM Deception Among Us is a research sandbox for generating, labeling, and analyzing deceptive behavior in multi-agent language models. LLM agents play Among Us on the Skeld map under partial observability, producing gameplay logs that can be converted into datasets for training and evaluating linear deception probes.

The project follows the experimental direction of [Among Us: A Sandbox for Measuring and Detecting Agentic Deception](https://arxiv.org/abs/2504.04072) and works with the published [7vik/amongus dataset](https://huggingface.co/datasets/7vik/amongus).

## Table of contents

- [Overview](#overview)
- [Installation](#installation)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Main workflows](#main-workflows)
- [Used technologies](#used-technologies)

## Overview

The repository supports the complete experimental pipeline:

1. Generate games with scripted, heuristic, Ollama, or OpenAI-compatible agents.
2. Validate logs for information leakage and schema errors.
3. Split games into training, validation, and test sets.
4. Build gameplay and contrastive Hugging Face datasets.
5. Train linear probes on model activations.
6. Evaluate and compare probes on gameplay data.
7. Review games, annotations, and probe results in the included visualizations.

All workflows are available through the `amongus` command and YAML configuration files.

## Installation

### Requirements

- Python 3.10, 3.11, or 3.12
- [uv](https://docs.astral.sh/uv/) for the recommended installation
- Ollama, an OpenAI-compatible endpoint, or neither when using scripted and heuristic agents
- A CUDA-capable GPU for practical probe training with larger models

### Clone and install

```bash
git clone https://github.com/h-gajdov/llm-deception-amongus.git
cd llm-deception-amongus
uv sync
```

Install the optional machine-learning, annotation, and development dependencies when needed:

```bash
uv sync --extra ml --extra annotate --extra dev
```

An editable pip installation is also supported:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[ml,annotate,dev]"
```

## Getting started

Run a deterministic smoke test that requires no model server, API key, or network access:

```bash
uv run amongus generate -c configs/generation/scripted_smoke.yaml
```

For a more realistic rule-based validation run:

```bash
uv run amongus generate -c configs/generation/heuristic_validation.yaml
```

To generate games with a local Ollama model, start Ollama and pull the configured model first:

```bash
ollama serve
ollama pull qwen3:8b
uv run amongus generate -c configs/generation/qwen3_8b_selfplay.yaml
```

For OpenAI-backed generation or annotation, create a local environment file:

```bash
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then load it for a command:

```bash
uv run --env-file .env amongus generate -c configs/generation/gpt4omini_vs_qwen3.yaml
```

Generated experiments are written under `expt-logs/`. The root `data/` directory is used for downloaded, processed, and trained artifacts and is intentionally excluded from version control.

## Configuration

Configuration is organized by workflow:

| Directory | Purpose |
|---|---|
| `configs/generation/` | Game rules, agent backends, model selection, visibility, seeds, and output settings |
| `configs/contrastive/` | TruthfulQA, DishonestQA, and Representation Engineering dataset construction |
| `configs/probes/` | Model activation extraction, pooling, layers, optimization, and experiment tracking |
| `configs/eval/` | Probe discovery, dataset selection, labeling, controls, metrics, and resumable evaluation |

Generation configurations commonly define:

- `experiment_name`, `num_games`, `seed`, `output_dir`, and `log_level`
- Player count, impostor count, task counts, discussion rounds, cooldowns, and timestep limits under `game`
- Impostor and crewmate backends, model choices, token limits, and retry behavior under `agent`
- Visibility and witness rules for controlling what each player can observe
- Whether compact logs, world-state traces, and annotations are written

Start from the closest existing YAML file and change one experimental factor at a time. Command-line options can override common generation settings without creating a new file.

## Main workflows

Validate a generated experiment:

```bash
uv run amongus validate expt-logs/<experiment-directory>
```

Create game-level splits:

```bash
uv run amongus split expt-logs/<experiment-directory> --strategy random --seed 0
```

Build the gameplay dataset:

```bash
uv run amongus build expt-logs -o data/processed/amongus --schema v2
```

Build the contrastive probe-training dataset:

```bash
uv run amongus contrastive build -c configs/contrastive/tqa_dqa.yaml
```

Train a probe:

```bash
uv run amongus probe train -c configs/probes/gpt2.yaml
```

Run the evaluation suite:

```bash
uv run amongus probe suite -c configs/eval/smoke.yaml
```

Launch or rebuild the repository viewer:

```bash
uv run amongus viz site
```

Use `uv run amongus --help` and the help option on any subcommand for the complete CLI reference.

## Used technologies

| Technology | Role in the project |
|---|---|
| Python | Game engine, data pipelines, model integrations, probe training, and CLI |
| Typer | Command-line interface |
| Pydantic and Pydantic Settings | Validated schemas and configuration models |
| PyYAML | Experiment configuration |
| HTTPX | Ollama and OpenAI-compatible HTTP clients |
| Hugging Face Datasets and Hub | Dataset ingestion, processing, and publication-compatible formats |
| pandas and PyArrow | Tabular processing and Parquet output |
| PyTorch and Transformers | Model inference and activation extraction |
| scikit-learn and joblib | Linear probe training, metrics, and artifact persistence |
| Matplotlib | Static evaluation charts |
| Loguru and tqdm | Structured logging and progress reporting |
| Weights & Biases and MLflow | Optional experiment tracking |
| OpenAI SDK | Optional batch and structured-output annotation |
| uv and Hatchling | Dependency management, reproducible locking, and packaging |
| Ruff, Pyright, and pytest | Linting, type checking, and testing |
