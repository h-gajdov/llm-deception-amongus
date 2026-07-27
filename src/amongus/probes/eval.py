

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..logging import get_logger
from .activations import extract_activations, load_model_and_tokenizer, resolve_device
from .config import ModelConfig
from .train import TorchProbeState

if TYPE_CHECKING:                                  
    from collections.abc import Sequence

    import numpy as np

logger = get_logger()

TextMode = Literal["response", "full"]
ChartFormat = Literal["png", "html"]


@dataclass
class LoadedProbe:
    pass

    state: TorchProbeState
    model_name: str
    layer: int
    pooling: str
    use_chat_template: bool
    max_length: int


def load_probe(probe_path: str | Path) -> LoadedProbe:
    pass
    import joblib

    payload = joblib.load(Path(probe_path))
    state = payload["state"]
    if not isinstance(state, TorchProbeState):                                
        msg = f"{probe_path} does not contain a TorchProbeState."
        raise TypeError(msg)
    return LoadedProbe(
        state=state,
        model_name=payload["model_name"],
        layer=int(payload["layer"]),
        pooling=payload.get("pooling", "last"),
        use_chat_template=bool(payload.get("use_chat_template", False)),
        max_length=int(payload.get("max_length", 512)),
    )


def render_eval_text(row: dict[str, Any], mode: TextMode) -> str:
    pass
    response = (row.get("full_response") or "").strip()
    if not response:
                                                                          
        thinking = (row.get("thinking") or "").strip()
        action = (row.get("action") or "").strip()
        response = "\n".join(p for p in (thinking, action) if p)

    if mode == "response":
        return response or (row.get("action") or "").strip() or "(no response)"

    system = (row.get("system_prompt") or "").strip()
    observation = (row.get("all_info") or row.get("memory") or "").strip()
    parts = [p for p in (system, observation, response) if p]
    return "\n\n".join(parts) or "(no response)"


@dataclass
class EvalReport:
    pass

    probe_path: str
    dataset_dir: str
    model_name: str
    layer: int
    pooling: str
    text_mode: str
    split: str
    speak_only: bool
    n: int
    n_impostor: int
    impostor_rate: float
    accuracy: float
    f1: float
    precision: float
    recall: float
    auroc: float | None
                                                                         
    baseline_accuracy: float
    baseline_auroc: float = 0.5
    report_path: str = ""
                                                                               
                                                                      
    label: str = ""

    def summary_line(self) -> str:
        pass
        auroc = "n/a" if self.auroc is None else f"{self.auroc:.3f}"
        return (
            f"AUROC={auroc} (chance 0.500) | acc={self.accuracy:.3f} "
            f"(majority {self.baseline_accuracy:.3f}) | f1={self.f1:.3f} | "
            f"n={self.n}, impostor_rate={self.impostor_rate:.3f}"
        )


@dataclass
class _Scored:
    pass

    y_true: np.ndarray
    y_pred: np.ndarray
    y_prob: np.ndarray
    texts: list[str] = field(default_factory=list)


def _load_rows(dataset_dir: Path, split: str, limit: int | None) -> list[dict[str, Any]]:
    pass
    from datasets import DatasetDict, concatenate_datasets, load_from_disk

    dataset = load_from_disk(str(dataset_dir))
    if not isinstance(dataset, DatasetDict):                            
        selected = dataset
    elif split == "all":
        selected = concatenate_datasets([dataset[s] for s in dataset])
    elif split in dataset:
        selected = dataset[split]
    else:
        msg = f"Split {split!r} not found in {dataset_dir} (have: {list(dataset)})."
        raise ValueError(msg)
    if limit is not None:
        selected = selected.select(range(min(limit, selected.num_rows)))
    return [dict(row) for row in selected]


def _score(probe: LoadedProbe, activations: np.ndarray, y_true: np.ndarray) -> _Scored:
    pass
    x = activations[:, 0, :]                                 
    y_prob = probe.state.predict_proba(x)
    y_pred = probe.state.predict(x)
    return _Scored(y_true=y_true, y_pred=y_pred, y_prob=y_prob)


def _metrics(scored: _Scored) -> dict[str, Any]:
    pass
    import numpy as np
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    y_true, y_pred, y_prob = scored.y_true, scored.y_pred, scored.y_prob
    both_classes = len(set(y_true.tolist())) > 1
    positive_rate = float(y_true.mean()) if len(y_true) else 0.0
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0.0)),                          
        "precision": float(precision_score(y_true, y_pred, zero_division=0.0)),                          
        "recall": float(recall_score(y_true, y_pred, zero_division=0.0)),                          
        "auroc": float(roc_auc_score(y_true, y_prob)) if both_classes else None,
        "baseline_accuracy": float(max(positive_rate, 1.0 - positive_rate)),
        "n_impostor": int(np.sum(y_true)),
        "impostor_rate": positive_rate,
    }


def _report_from_dict(data: dict[str, Any]) -> EvalReport | None:
    pass
    from dataclasses import fields

    known = {f.name for f in fields(EvalReport)}
    try:
        return EvalReport(**{k: v for k, v in data.items() if k in known})
    except TypeError:                                                  
        return None


def _cached_report(
    out: Path,
    *,
    dataset_dir: str | Path,
    split: str,
    text_mode: TextMode,
    speak_only: bool,
) -> EvalReport | None:
    pass
    try:
        data = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    report = _report_from_dict(data)
    if report is None:
        return None
    matches = (
        Path(report.dataset_dir) == Path(dataset_dir)
        and report.split == split
        and report.text_mode == text_mode
        and bool(report.speak_only) == bool(speak_only)
    )
    if not matches:
        return None
    report.report_path = str(out)
    return report


def evaluate_probe(
    *,
    probe_path: str | Path,
    dataset_dir: str | Path,
    split: str = "all",
    text_mode: TextMode = "response",
    speak_only: bool = False,
    device: str = "auto",
    batch_size: int = 16,
    limit: int | None = None,
    output_path: str | Path | None = None,
    reuse: bool = True,
) -> EvalReport:
    pass
    import numpy as np

    out = Path(output_path) if output_path else Path(probe_path).parent / "eval_amongus.json"
    if reuse and limit is None and out.exists():
        cached = _cached_report(
            out,
            dataset_dir=dataset_dir,
            split=split,
            text_mode=text_mode,
            speak_only=speak_only,
        )
        if cached is not None:
            logger.info("Reusing existing evaluation report {} (matching settings).", out)
            return cached

    probe = load_probe(probe_path)
    rows = _load_rows(Path(dataset_dir), split, limit)
    if speak_only:
        rows = [r for r in rows if r.get("is_speak")]
    if not rows:
        msg = f"No rows to evaluate in {dataset_dir} (split={split}, speak_only={speak_only})."
        raise ValueError(msg)
    logger.info(
        "Evaluating {} probe (layer {}) on {} game-log rows (mode={}, speak_only={}).",
        probe.model_name,
        probe.layer,
        len(rows),
        text_mode,
        speak_only,
    )

    device = resolve_device(device)
    model, tokenizer = load_model_and_tokenizer(ModelConfig(name=probe.model_name), device)
                                                                                 
                                                        
    tokenizer.truncation_side = "left"

    texts = [render_eval_text(r, text_mode) for r in rows]
    y_true = np.array([int(r["is_impostor"]) for r in rows])
    activations = extract_activations(
        model,
        tokenizer,
        texts,
        layers=[probe.layer],
        pooling=probe.pooling,
        batch_size=batch_size,
        max_length=probe.max_length,
        desc=f"Scoring {split} game logs",
    )

    scored = _score(probe, activations, y_true)
    metrics = _metrics(scored)

    report = EvalReport(
        probe_path=str(probe_path),
        dataset_dir=str(dataset_dir),
        model_name=probe.model_name,
        layer=probe.layer,
        pooling=probe.pooling,
        text_mode=text_mode,
        split=split,
        speak_only=speak_only,
        n=len(rows),
        **metrics,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    report.report_path = str(out)
    logger.info("Wrote evaluation report to {}.", out)
    return report


@dataclass
class ComparisonReport:
    pass

    reports: list[EvalReport]
    labels: list[str]
    dataset_dir: str
    split: str
    text_mode: str
    speak_only: bool
    chart_format: str = "png"
    chart_path: str = ""
    json_path: str = ""

    def best(self) -> EvalReport:
        pass
        return max(self.reports, key=lambda r: ((r.auroc or 0.0), r.accuracy))


def _label_for(probe_path: Path) -> str:
    pass
    parent = probe_path.parent.name
    return parent or probe_path.stem


def _dedupe_labels(labels: list[str]) -> list[str]:
    pass
    seen: dict[str, int] = {}
    out: list[str] = []
    for label in labels:
        seen[label] = seen.get(label, 0) + 1
        out.append(label if seen[label] == 1 else f"{label}#{seen[label]}")
    return out


def compare_probes(
    *,
    probe_paths: Sequence[str | Path],
    dataset_dir: str | Path,
    split: str = "all",
    text_mode: TextMode = "response",
    speak_only: bool = False,
    device: str = "auto",
    batch_size: int = 16,
    limit: int | None = None,
    output_dir: str | Path | None = None,
    labels: Sequence[str] | None = None,
    fmt: ChartFormat = "png",
    reuse: bool = True,
) -> ComparisonReport:
    pass
    paths = [Path(p) for p in probe_paths]
    if not paths:
        msg = "compare_probes needs at least one probe path."
        raise ValueError(msg)

    out_dir = Path(output_dir) if output_dir else Path("data/probes/comparison")
    out_dir.mkdir(parents=True, exist_ok=True)

    resolved_labels = list(labels) if labels else [_label_for(p) for p in paths]
    if len(resolved_labels) != len(paths):
        msg = f"Got {len(resolved_labels)} labels for {len(paths)} probes."
        raise ValueError(msg)
    resolved_labels = _dedupe_labels(resolved_labels)

    reports: list[EvalReport] = []
    for probe_path, label in zip(paths, resolved_labels, strict=True):
        logger.info("Comparison: evaluating probe {} ({}).", label, probe_path)
                                                                             
                                                                    
        report = evaluate_probe(
            probe_path=probe_path,
            dataset_dir=dataset_dir,
            split=split,
            text_mode=text_mode,
            speak_only=speak_only,
            device=device,
            batch_size=batch_size,
            limit=limit,
            output_path=None,
            reuse=reuse,
        )
        report.label = label
                                                                  
        (out_dir / f"eval_{label}.json").write_text(
            json.dumps(asdict(report), indent=2), encoding="utf-8"
        )
        reports.append(report)

    comparison = ComparisonReport(
        reports=reports,
        labels=resolved_labels,
        dataset_dir=str(dataset_dir),
        split=split,
        text_mode=text_mode,
        speak_only=speak_only,
        chart_format=fmt,
    )
    _persist_comparison(comparison, out_dir, fmt)
    return comparison


def _persist_comparison(comparison: ComparisonReport, out_dir: Path, fmt: ChartFormat) -> None:
    pass
    meta = {
        "dataset_dir": comparison.dataset_dir,
        "split": comparison.split,
        "text_mode": comparison.text_mode,
        "speak_only": comparison.speak_only,
    }
    if fmt == "png":
        from ..viz.probe_eval_viz import render_comparison_png

        chart_path = render_comparison_png(
            comparison.reports, comparison.labels, meta, out_dir / "comparison.png"
        )
    else:
        from ..viz.probe_eval_viz import render_comparison_html

        chart_path = out_dir / "comparison.html"
        chart_path.write_text(
            render_comparison_html(comparison.reports, comparison.labels, meta),
            encoding="utf-8",
        )

    json_path = out_dir / "comparison.json"
    payload = {**meta, "reports": [asdict(r) for r in comparison.reports]}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    comparison.chart_path = str(chart_path)
    comparison.json_path = str(json_path)
    logger.info("Wrote comparison chart to {} and JSON to {}.", chart_path, json_path)


__all__ = [
    "ChartFormat",
    "ComparisonReport",
    "EvalReport",
    "LoadedProbe",
    "TextMode",
    "compare_probes",
    "evaluate_probe",
    "load_probe",
    "render_eval_text",
]
