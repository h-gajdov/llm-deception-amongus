

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..logging import get_logger
from .activations import (
    build_prompt,
    default_layers,
    extract_activations,
    load_model_and_tokenizer,
    resolve_device,
)
from .config import ProbeTrainConfig

if TYPE_CHECKING:                                  
    import numpy as np

logger = get_logger()


@dataclass
class LayerMetrics:
    pass

    layer: int
    accuracy: float
    f1: float
    auroc: float | None


@dataclass
class ProbeTrainResult:
    pass

    model_name: str
    pooling: str
    best_layer: int
    n_train: int
    n_test: int
    layer_metrics: list[LayerMetrics]
    probe_path: str
    metrics_path: str

    def best(self) -> LayerMetrics:
        pass
        return next(m for m in self.layer_metrics if m.layer == self.best_layer)


def _make_probe(config: ProbeTrainConfig) -> Any:
    pass
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    clf = LogisticRegression(
        C=config.reg_c,
        max_iter=config.max_iter,
        random_state=config.seed,
    )
    if config.standardize:
        return make_pipeline(StandardScaler(), clf)
    return make_pipeline(clf)


def _score(y_true: Any, y_pred: Any, y_prob: Any) -> tuple[float, float, float | None]:
    pass
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    acc = float(accuracy_score(y_true, y_pred))
                                                                                   
    f1 = float(f1_score(y_true, y_pred, zero_division=0.0))                          
    auroc: float | None = None
    if len(set(y_true.tolist())) > 1:
        auroc = float(roc_auc_score(y_true, y_prob))
    return acc, f1, auroc


def fit_layer_probes(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    layers: list[int],
    config: ProbeTrainConfig,
) -> tuple[list[LayerMetrics], dict[int, Any]]:
    pass
    metrics: list[LayerMetrics] = []
    probes: dict[int, Any] = {}
    for position, layer in enumerate(layers):
        xt, xv = x_train[:, position, :], x_test[:, position, :]
        probe = _make_probe(config)
        probe.fit(xt, y_train)
        y_pred = probe.predict(xv)
        y_prob = probe.predict_proba(xv)[:, 1]
        acc, f1, auroc = _score(y_test, y_pred, y_prob)
        metrics.append(LayerMetrics(layer=layer, accuracy=acc, f1=f1, auroc=auroc))
        probes[layer] = probe
        logger.info(
            "Layer {:>3}: acc={:.3f} f1={:.3f} auroc={}",
            layer,
            acc,
            f1,
            f"{auroc:.3f}" if auroc is not None else "n/a",
        )
    return metrics, probes


def _select_best(metrics: list[LayerMetrics]) -> LayerMetrics:
    pass
    return max(metrics, key=lambda m: (m.auroc or 0.0, m.accuracy, m.f1))


def _load_rows(
    dataset_dir: Path, limit: int | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pass
    from datasets import Dataset, DatasetDict, load_from_disk

    dataset = load_from_disk(str(dataset_dir))
    if not isinstance(dataset, DatasetDict) or "train" not in dataset or "test" not in dataset:
        msg = f"Expected a DatasetDict with 'train' and 'test' splits in {dataset_dir}."
        raise ValueError(msg)

    def rows(split: Dataset) -> list[dict[str, Any]]:
        if limit is not None:
            split = split.select(range(min(limit, split.num_rows)))
        return [dict(row) for row in split]

    return rows(dataset["train"]), rows(dataset["test"])


def train_probes(config: ProbeTrainConfig) -> ProbeTrainResult:
    pass
    import numpy as np

    train_rows, test_rows = _load_rows(config.dataset_dir, config.limit)
    logger.info("Loaded {} train / {} test contrastive rows.", len(train_rows), len(test_rows))

    device = resolve_device(config.device)
    model, tokenizer = load_model_and_tokenizer(config.model_name, device, config.dtype)
    layers = config.layers or default_layers(model)

    def activations_for(rows: list[dict[str, Any]]) -> np.ndarray:
        texts = [
            build_prompt(r, tokenizer, use_chat_template=config.use_chat_template) for r in rows
        ]
        return extract_activations(
            model,
            tokenizer,
            texts,
            layers=layers,
            pooling=config.pooling,
            batch_size=config.batch_size,
            max_length=config.max_length,
        )

    x_train = activations_for(train_rows)
    x_test = activations_for(test_rows)
    y_train = np.array([int(r["label"]) for r in train_rows])
    y_test = np.array([int(r["label"]) for r in test_rows])

    metrics, probes = fit_layer_probes(x_train, y_train, x_test, y_test, layers, config)
    best = _select_best(metrics)
    logger.info("Best layer: {} (acc={:.3f}).", best.layer, best.accuracy)

    return _persist(config, metrics, probes, best, len(train_rows), len(test_rows), device)


def _persist(
    config: ProbeTrainConfig,
    metrics: list[LayerMetrics],
    probes: dict[int, Any],
    best: LayerMetrics,
    n_train: int,
    n_test: int,
    device: str,
) -> ProbeTrainResult:
    pass
    import joblib

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    probe_path = output_dir / "probe.joblib"
    metrics_path = output_dir / "metrics.json"

    joblib.dump(
        {
            "pipeline": probes[best.layer],
            "model_name": config.model_name,
            "layer": best.layer,
            "pooling": config.pooling,
            "use_chat_template": config.use_chat_template,
            "max_length": config.max_length,
        },
        probe_path,
    )

    payload = {
        "model_name": config.model_name,
        "device": device,
        "pooling": config.pooling,
        "best_layer": best.layer,
        "n_train": n_train,
        "n_test": n_test,
        "config": json.loads(config.model_dump_json()),
        "layer_metrics": [asdict(m) for m in metrics],
    }
    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Saved probe to {} and metrics to {}.", probe_path, metrics_path)

    return ProbeTrainResult(
        model_name=config.model_name,
        pooling=config.pooling,
        best_layer=best.layer,
        n_train=n_train,
        n_test=n_test,
        layer_metrics=metrics,
        probe_path=str(probe_path),
        metrics_path=str(metrics_path),
    )


__all__ = [
    "LayerMetrics",
    "ProbeTrainResult",
    "fit_layer_probes",
    "train_probes",
]
