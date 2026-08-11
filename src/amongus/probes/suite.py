

from __future__ import annotations

import fnmatch
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..data.ingest import HOLISTIC_DIRNAME, KIND_HOLISTIC, KIND_V2, find_log_datasets
from ..logging import get_logger
from .activations import extract_activations, load_model_and_tokenizer, resolve_device
from .config import ModelConfig
from .eval import LoadedProbe, load_probe, render_eval_text
from .suite_config import EvalSuiteConfig
from .train import TorchProbeState

if TYPE_CHECKING:                                  
    import numpy as np

logger = get_logger()

RESULTS_FILE = "results.json"
CHART_FILE = "suite.png"

                                                                             
                                                                               
                                                                                
                             
_GROUNDED_LABEL = {"truthful": 0, "deceptive": 1}

VARIANT_BASE = "base"
VARIANT_TRAINED = "trained"


                                                                               
         
                                                                               
@dataclass
class SuiteRow:
    pass

    dataset: str
    dataset_path: str
    dataset_kind: str
    label_source: str
    probe: str
    probe_path: str
                                                                                
                                                                              
                                        
    probe_fingerprint: str
    model_name: str
    layer: int
    variant: str                                           
    n: int
    n_positive: int
    positive_rate: float
    accuracy: float
    f1: float
    precision: float
    recall: float
    auroc: float | None
    baseline_accuracy: float                           
    chance_auroc: float = 0.5
                                                                         
    auroc_std: float | None = None
    accuracy_std: float | None = None
    seeds: int = 1
    text_mode: str = "response"
    speak_only: bool = False


@dataclass
class SuiteReport:
    pass

    rows: list[SuiteRow] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    probes: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    results_path: str = ""
    chart_path: str = ""

    def lift(self) -> list[tuple[str, str, float]]:
        pass
        base = {
            (r.probe, r.dataset): r.auroc
            for r in self.rows
            if r.variant == VARIANT_BASE and r.auroc is not None
        }
        out: list[tuple[str, str, float]] = []
        for row in self.rows:
            if row.variant != VARIANT_TRAINED or row.auroc is None:
                continue
            floor = base.get((row.probe, row.dataset))
            if floor is not None:
                out.append((row.probe, row.dataset, row.auroc - floor))
        return sorted(out, key=lambda t: t[2], reverse=True)


                                                                               
             
                                                                               
@dataclass
class EvalRow:
    pass

    text: str
    label: int
    is_speak: bool


def _lines(path: Path):
    pass
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield line


def resolve_label_source(kind: str, requested: str) -> str:
    pass
    if requested == "auto":
        return "grounded" if kind == KIND_V2 else "holistic"
    if requested == "grounded" and kind != KIND_V2:
        msg = (
            "label_source='grounded' needs schema 2.0 annotations; this is a v1 dataset. "
            "Use 'holistic' (GPT ratings), 'impostor' (role proxy), or 'auto'."
        )
        raise ValueError(msg)
    if requested == "holistic" and kind != KIND_HOLISTIC:
        msg = "label_source='holistic' needs a gpt4omini_holistic/ folder; this dataset has none."
        raise ValueError(msg)
    return requested


def load_eval_rows(
    directory: Path, kind: str, config: EvalSuiteConfig
) -> tuple[list[EvalRow], str]:
    pass
    source = resolve_label_source(kind, config.label_source)
    reader = _v2_rows if kind == KIND_V2 else _holistic_rows
    rows = list(reader(directory, source, config))
    if config.datasets.speak_only:
        rows = [r for r in rows if r.is_speak]
    return _subsample(rows, config.datasets.max_rows), source


def _subsample(rows: list[EvalRow], max_rows: int | None) -> list[EvalRow]:
    pass
    if max_rows is None or len(rows) <= max_rows:
        return rows
    stride = len(rows) / max_rows
    return [rows[int(i * stride)] for i in range(max_rows)]


def _v2_rows(directory: Path, source: str, config: EvalSuiteConfig):
    pass
    for line in _lines(directory / "turns.jsonl"):
        turn = json.loads(line)
        output = turn.get("model_output") or {}
        speech = output.get("speech") or ""
        if source == "impostor":
            label: int | None = int(
                str((turn.get("actor") or {}).get("role", "")).lower() == "impostor"
            )
        else:
            annotations = turn.get("annotations") or {}
            status = str(annotations.get("utterance_deception_status", ""))
            label = _GROUNDED_LABEL.get(status)
        if label is None:
            continue
        yield EvalRow(text=_v2_text(turn, config.text_mode), label=label, is_speak=bool(speech))


def _v2_text(turn: dict[str, Any], mode: str) -> str:
    pass
    model_input = turn.get("model_input") or {}
    raw = str((turn.get("model_output") or {}).get("raw", "")).strip()
    if mode == "response":
        return raw or "(no response)"
    parts = [
        str(model_input.get("system_prompt", "")),
        str(model_input.get("user_prompt", "")),
        raw,
    ]
    return "\n\n".join(p for p in parts if p) or "(no response)"


def _holistic_rows(directory: Path, source: str, config: EvalSuiteConfig):
    pass
                                                                              
                                                                       
    from ..viz.reconstruct import EventKind, logged_action, parse_action

    path = directory / HOLISTIC_DIRNAME / "turns.jsonl"
    for line in _lines(path):
        row = json.loads(line)
        interaction = row.get("interaction") or {}
        response = interaction.get("response") or {}
        full_response = str(interaction.get("full_response") or "")
        action, _ = logged_action(response, full_response)

        if source == "impostor":
            label: int | None = int(
                str((row.get("player") or {}).get("identity", "")).lower() == "impostor"
            )
        else:
            rating = row.get("holistic_rating")
            score = rating.get("deception") if isinstance(rating, dict) else None
            label = None if score is None else int(int(score) >= config.holistic_threshold)
        if label is None:
            continue

                                                                         
                                                                     
        legacy = {
            "full_response": full_response,
            "thinking": _as_text(response.get("Thinking Process")),
            "action": action,
            "system_prompt": str(interaction.get("system_prompt") or ""),
            "all_info": str((interaction.get("prompt") or {}).get("All Info", "")),
        }
        yield EvalRow(
            text=render_eval_text(legacy, config.text_mode),                          
            label=label,
            is_speak=parse_action(action)[0] is EventKind.SPEAK,
        )


def _as_text(value: object) -> str:
    pass
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        inner = value.get("thought")
        return inner.strip() if isinstance(inner, str) else json.dumps(value, ensure_ascii=False)
    return ""


                                                                               
           
                                                                               
def _matches(name: str, include: list[str], exclude: list[str]) -> bool:
    pass
    if include and not any(fnmatch.fnmatch(name, pattern) for pattern in include):
        return False
    return not any(fnmatch.fnmatch(name, pattern) for pattern in exclude)


def select_datasets(config: EvalSuiteConfig) -> list[tuple[Path, str]]:
    pass
    found: dict[Path, str] = {}
    for root in config.datasets.roots:
        for directory, kind in find_log_datasets(root):
            found[directory] = kind
    return [
        (directory, kind)
        for directory, kind in sorted(found.items())
        if _matches(directory.name, config.datasets.include, config.datasets.exclude)
    ]


def select_probes(config: EvalSuiteConfig) -> list[Path]:
    pass
    paths: list[Path] = [Path(p) for p in config.probes.paths]
    for root in config.probes.discover:
        paths.extend(sorted(Path(root).rglob("probe.joblib")))
    seen: dict[Path, None] = {}
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen and _matches(path.parent.name, [], config.probes.exclude):
            seen[resolved] = None
    return [Path(p) for p in seen]


                                                                               
         
                                                                               
def _random_state(probe: LoadedProbe, seed: int) -> TorchProbeState:
    pass
    import numpy as np

    state = probe.state
    rng = np.random.default_rng(seed)
    weight = rng.standard_normal(state.weight.shape) / np.sqrt(state.weight.shape[0])
    return TorchProbeState(
        weight=weight,
        bias=0.0,
        mean=state.mean,
        std=state.std,
        layer=state.layer,
    )


def _metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict[str, Any]:
    pass
    import numpy as np
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    both = len(set(y_true.tolist())) > 1
    rate = float(y_true.mean()) if len(y_true) else 0.0
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0.0)),                          
        "precision": float(precision_score(y_true, y_pred, zero_division=0.0)),                          
        "recall": float(recall_score(y_true, y_pred, zero_division=0.0)),                          
        "auroc": float(roc_auc_score(y_true, y_prob)) if both else None,
        "baseline_accuracy": float(max(rate, 1.0 - rate)),
        "n_positive": int(np.sum(y_true)),
        "positive_rate": rate,
    }


def _score_state(state: TorchProbeState, x: np.ndarray, y_true: np.ndarray) -> dict[str, Any]:
    pass
    return _metrics(y_true, state.predict(x), state.predict_proba(x))


def _mean_std(values: list[float | None]) -> tuple[float | None, float | None]:
    pass
    import numpy as np

    defined = [v for v in values if v is not None]
    if not defined:
        return None, None
    return float(np.mean(defined)), float(np.std(defined))


def _base_metrics(
    probe: LoadedProbe, x: np.ndarray, y_true: np.ndarray, config: EvalSuiteConfig
) -> dict[str, Any]:
    pass
    runs = [
        _score_state(_random_state(probe, config.baseline.seed + i), x, y_true)
        for i in range(config.baseline.seeds)
    ]
    auroc, auroc_std = _mean_std([r["auroc"] for r in runs])
    accuracy, accuracy_std = _mean_std([r["accuracy"] for r in runs])
    return {
        **runs[0],                                                                
        "accuracy": accuracy if accuracy is not None else runs[0]["accuracy"],
        "auroc": auroc,
        "f1": float(sum(r["f1"] for r in runs) / len(runs)),
        "precision": float(sum(r["precision"] for r in runs) / len(runs)),
        "recall": float(sum(r["recall"] for r in runs) / len(runs)),
        "auroc_std": auroc_std,
        "accuracy_std": accuracy_std,
        "seeds": config.baseline.seeds,
    }


                                                                               
         
                                                                               
def run_suite(config: EvalSuiteConfig) -> SuiteReport:
    pass
    datasets = select_datasets(config)
    probe_paths = select_probes(config)
    if not probe_paths:
        msg = (
            f"No probe.joblib found (paths={config.probes.paths}, "
            f"discover={config.probes.discover})."
        )
        raise FileNotFoundError(msg)
    if not datasets:
        msg = f"No gameplay datasets found under {config.datasets.roots}."
        raise FileNotFoundError(msg)

    probes = {path: load_probe(path) for path in probe_paths}
    labels = _probe_labels(probe_paths)
    fingerprints = {path: _fingerprint(path) for path in probe_paths}
    groups = _by_model(probe_paths, probes)
    logger.info(
        "Suite: {} probe(s) over {} base model(s) x {} dataset(s), base + trained.",
        len(probe_paths),
        len(groups),
        len(datasets),
    )

    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = SuiteReport(
        datasets=[d.name for d, _ in datasets],
        probes=[labels[p] for p in probe_paths],
    )
    if config.reuse:
        done = _load_cached(out_dir / RESULTS_FILE, config, labels, fingerprints)
        report.rows.extend(done.values())
        if done:
            logger.info("Resuming: {} row(s) already on disk under these settings.", len(done))
    device = resolve_device(config.device)
    rows_cache: dict[Path, tuple[list[EvalRow], str]] = {}

                                                                                
                                                                                
                                              
    for model_name, group in groups.items():
        skipped = _skipped(report)
        outstanding = [
            (directory, kind)
            for directory, kind in datasets
            if directory.name not in skipped and _pending_probes(group, directory, labels, report)
        ]
        if not outstanding:
            logger.info("{}: every dataset already scored; not loading the model.", model_name)
            continue
        _run_model_pass(
            model_name=model_name,
            group=group,
            outstanding=outstanding,
            probes=probes,
            labels=labels,
            fingerprints=fingerprints,
            rows_cache=rows_cache,
            device=device,
            config=config,
            report=report,
            out_dir=out_dir,
        )

    _persist(report, out_dir, config, chart=True)
    return report


def _skipped(report: SuiteReport) -> set[str]:
    pass
    return {entry["dataset"] for entry in report.skipped}


def _pending_probes(
    group: list[Path], directory: Path, labels: dict[Path, str], report: SuiteReport
) -> list[Path]:
    pass
    have = {(row.probe, row.dataset, row.variant) for row in report.rows}
    return [
        path
        for path in group
        if not all(
            (labels[path], directory.name, variant) in have
            for variant in (VARIANT_BASE, VARIANT_TRAINED)
        )
    ]


def _run_model_pass(
    *,
    model_name: str,
    group: list[Path],
    outstanding: list[tuple[Path, str]],
    probes: dict[Path, LoadedProbe],
    labels: dict[Path, str],
    fingerprints: dict[Path, str],
    rows_cache: dict[Path, tuple[list[EvalRow], str]],
    device: str,
    config: EvalSuiteConfig,
    report: SuiteReport,
    out_dir: Path,
) -> None:
    pass
    import numpy as np

    layers = sorted({probes[p].layer for p in group})
    reference = probes[group[0]]
    logger.info(
        "Loading {} once for {} probe(s), layers {}, over {} dataset(s).",
        model_name,
        len(group),
        layers,
        len(outstanding),
    )
    model, tokenizer = load_model_and_tokenizer(ModelConfig(name=model_name), device)
    tokenizer.truncation_side = "left"
    try:
        for directory, kind in outstanding:
            pending = _pending_probes(group, directory, labels, report)
            if not pending:
                continue
            loaded = _dataset_rows(directory, kind, config, rows_cache, report)
            if loaded is None:
                continue
            rows, source = loaded
            y_true = np.array([r.label for r in rows])
            logger.info(
                "{} / {}: {} rows, label={}, positives {:.1%}",
                model_name,
                directory.name,
                len(rows),
                source,
                float(y_true.mean()),
            )
            report.rows.extend(
                _score_dataset(
                    model=model,
                    tokenizer=tokenizer,
                    model_name=model_name,
                    group=pending,
                    layers=layers,
                    reference=reference,
                    probes=probes,
                    labels=labels,
                    fingerprints=fingerprints,
                    texts=[r.text for r in rows],
                    y_true=y_true,
                    directory=directory,
                    kind=kind,
                    source=source,
                    config=config,
                )
            )
                                                                             
                                                                           
            _persist(report, out_dir, config, chart=False)
    finally:
        _release(model)


def _dataset_rows(
    directory: Path,
    kind: str,
    config: EvalSuiteConfig,
    cache: dict[Path, tuple[list[EvalRow], str]],
    report: SuiteReport,
) -> tuple[list[EvalRow], str] | None:
    pass
    if directory in cache:
        return cache[directory]
    try:
        rows, source = load_eval_rows(directory, kind, config)
    except (OSError, ValueError) as err:
        logger.warning("Skipping {}: {}", directory.name, err)
        report.skipped.append({"dataset": directory.name, "reason": str(err)})
        return None
    if not rows:
        reason = "no labelled rows under this label source and filters"
        logger.warning("Skipping {}: {}.", directory.name, reason)
        report.skipped.append({"dataset": directory.name, "reason": reason})
        return None
    if config.cache_rows:
        cache[directory] = (rows, source)
    return rows, source


def _release(model: Any) -> None:
    pass
    import gc

    del model
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:                                               
        pass


def _score_dataset(
    *,
    model: Any,
    tokenizer: Any,
    model_name: str,
    group: list[Path],
    layers: list[int],
    reference: LoadedProbe,
    probes: dict[Path, LoadedProbe],
    labels: dict[Path, str],
    fingerprints: dict[Path, str],
    texts: list[str],
    y_true: np.ndarray,
    directory: Path,
    kind: str,
    source: str,
    config: EvalSuiteConfig,
) -> list[SuiteRow]:
    pass
    prompts = _apply_template(texts, tokenizer) if config.apply_chat_template else texts
    activations = extract_activations(
        model,
        tokenizer,
        prompts,
        layers=layers,
        pooling=reference.pooling,
        batch_size=config.batch_size,
        max_length=reference.max_length,
        desc=f"{model_name} / {directory.name}",
    )

    rows: list[SuiteRow] = []
    for path in group:
        probe = probes[path]
        x = activations[:, layers.index(probe.layer), :]
        common = {
            "dataset": directory.name,
            "dataset_path": str(directory),
            "dataset_kind": kind,
            "label_source": source,
            "probe": labels[path],
            "probe_path": str(path),
            "probe_fingerprint": fingerprints[path],
            "model_name": probe.model_name,
            "layer": probe.layer,
            "n": len(texts),
            "text_mode": config.text_mode,
            "speak_only": config.datasets.speak_only,
        }
        rows.append(
            SuiteRow(**common, variant=VARIANT_BASE, **_base_metrics(probe, x, y_true, config))
        )
        rows.append(
            SuiteRow(**common, variant=VARIANT_TRAINED, **_score_state(probe.state, x, y_true))
        )
        trained, base = rows[-1], rows[-2]
        logger.info(
            "  {} @ layer {}: trained AUROC {} vs base {} ({} random directions)",
            labels[path],
            probe.layer,
            _fmt(trained.auroc),
            _fmt(base.auroc),
            config.baseline.seeds,
        )
    return rows


def _fmt(value: float | None) -> str:
    pass
    return "n/a" if value is None else f"{value:.3f}"


def _apply_template(texts: list[str], tokenizer: Any) -> list[str]:
    pass
    if getattr(tokenizer, "chat_template", None) is None:
        logger.warning("apply_chat_template is on but this tokenizer has none; using raw text.")
        return texts
    return [
        tokenizer.apply_chat_template(
            [{"role": "user", "content": text}], tokenize=False, add_generation_prompt=True
        )
        for text in texts
    ]


def _by_model(paths: list[Path], probes: dict[Path, LoadedProbe]) -> dict[str, list[Path]]:
    pass
    groups: dict[str, list[Path]] = {}
    for path in paths:
        groups.setdefault(probes[path].model_name, []).append(path)
    return groups


def _probe_labels(paths: list[Path]) -> dict[Path, str]:
    pass
    seen: dict[str, int] = {}
    out: dict[Path, str] = {}
    for path in paths:
        label = path.parent.name or path.stem
        seen[label] = seen.get(label, 0) + 1
        out[path] = label if seen[label] == 1 else f"{label}#{seen[label]}"
    return out


def _fingerprint(path: Path) -> str:
    pass
    import hashlib

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:                                                            
        return ""


def _load_cached(
    path: Path,
    config: EvalSuiteConfig,
    labels: dict[Path, str],
    fingerprints: dict[Path, str],
) -> dict[tuple[str, str, str], SuiteRow]:
    pass
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    settings = payload.get("settings") or {}
    if settings != _settings(config):
        logger.info("Ignoring {}: it was written under different settings.", path)
        return {}
    from dataclasses import fields

    known = {f.name for f in fields(SuiteRow)}
    current = {labels[p]: fingerprints[p] for p in labels}
    out: dict[tuple[str, str, str], SuiteRow] = {}
    stale: set[str] = set()
    for raw in payload.get("rows") or []:
        try:
            row = SuiteRow(**{k: v for k, v in raw.items() if k in known})
        except TypeError:
            continue
        expected = current.get(row.probe)
        if expected is None:
            continue                                      
        if row.probe_fingerprint != expected:
            stale.add(row.probe)
            continue
        out[(row.probe, row.dataset, row.variant)] = row
    for name in sorted(stale):
        logger.info("{}: artifact changed since the cached run; rescoring it.", name)
    return out


def _settings(config: EvalSuiteConfig) -> dict[str, Any]:
    pass
    return {
        "label_source": config.label_source,
        "holistic_threshold": config.holistic_threshold,
        "text_mode": config.text_mode,
        "apply_chat_template": config.apply_chat_template,
        "speak_only": config.datasets.speak_only,
        "max_rows": config.datasets.max_rows,
        "baseline_seeds": config.baseline.seeds,
        "baseline_seed": config.baseline.seed,
    }


def _persist(
    report: SuiteReport, out_dir: Path, config: EvalSuiteConfig, *, chart: bool = True
) -> None:
    pass
    results = out_dir / RESULTS_FILE
    payload = {
        "settings": _settings(config),
        "datasets": report.datasets,
        "probes": report.probes,
        "skipped": report.skipped,
        "rows": [asdict(r) for r in report.rows],
    }
                                                                          
                                                                           
    tmp = results.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(results)
    report.results_path = str(results)
    logger.info("Wrote {} rows to {}.", len(report.rows), results)

    if not chart or not config.chart.enabled or not report.rows:
        return
    from ..viz.probe_eval_viz import render_suite_png

    chart_path = render_suite_png(
        [asdict(r) for r in report.rows],
        out_dir / CHART_FILE,
        metric=config.chart.metric,
        dpi=config.chart.dpi,
    )
    report.chart_path = str(chart_path)
    logger.info("Wrote paired base-vs-trained chart to {}.", chart_path)


__all__ = [
    "CHART_FILE",
    "RESULTS_FILE",
    "VARIANT_BASE",
    "VARIANT_TRAINED",
    "EvalRow",
    "SuiteReport",
    "SuiteRow",
    "load_eval_rows",
    "resolve_label_source",
    "run_suite",
    "select_datasets",
    "select_probes",
]
