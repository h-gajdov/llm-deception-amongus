from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..logging import get_logger
from .activations import (
    TokenActivations,
    build_prompt_with_span,
    default_layers,
    describe_selected_tokens,
    extract_token_activations,
    load_model_and_tokenizer,
    resolve_device,
)
from .config import ProbeConfig, ProbeTrainConfig
from .tracking import ExperimentTracker

if TYPE_CHECKING:
    import numpy as np

logger = get_logger()


@dataclass
class TorchProbeState:
    weight: np.ndarray
    bias: float
    mean: np.ndarray
    std: np.ndarray
    layer: int

    def _logits(self, x: np.ndarray) -> np.ndarray:
        return ((x - self.mean) / self.std) @ self.weight + self.bias

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        import numpy as np

        return 1.0 / (1.0 + np.exp(-self._logits(x)))

    def predict(self, x: np.ndarray) -> np.ndarray:
        return (self._logits(x) > 0.0).astype(int)


@dataclass
class LayerMetrics:
    layer: int
    accuracy: float
    f1: float
    auroc: float | None


@dataclass
class ProbeTrainResult:
    model_name: str
    pooling: str
    best_layer: int
    n_train: int
    n_test: int
    layer_metrics: list[LayerMetrics] = field(default_factory=list)
    probe_path: str = ""
    metrics_path: str = ""
    pooling_tokens: int = 1
    n_train_tokens: int = 0
    n_test_tokens: int = 0

    def best(self) -> LayerMetrics:
        return next(m for m in self.layer_metrics if m.layer == self.best_layer)


def example_scores(token_scores: np.ndarray, owner: np.ndarray, n_examples: int) -> np.ndarray:
    import numpy as np

    totals = np.zeros(n_examples, dtype=np.float64)
    counts = np.zeros(n_examples, dtype=np.float64)
    np.add.at(totals, owner, np.asarray(token_scores, dtype=np.float64))
    np.add.at(counts, owner, 1.0)
    return np.where(counts > 0, totals / np.maximum(counts, 1.0), 0.5)


def _standardize(
    x_train: np.ndarray, x_test: np.ndarray, enabled: bool
) -> tuple[Any, Any, Any, Any]:
    import numpy as np

    if not enabled:
        hidden = x_train.shape[1]
        return x_train, x_test, np.zeros(hidden, np.float32), np.ones(hidden, np.float32)
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std = np.where(std < 1e-6, 1.0, std).astype(np.float32)
    mean = mean.astype(np.float32)
    return (x_train - mean) / std, (x_test - mean) / std, mean, std


def _score(y_true: Any, y_pred: Any, y_prob: Any) -> tuple[float, float, float | None]:
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    acc = float(accuracy_score(y_true, y_pred))

    f1 = float(f1_score(y_true, y_pred, zero_division=0.0))
    auroc: float | None = None
    if len(set(y_true.tolist())) > 1:
        auroc = float(roc_auc_score(y_true, y_prob))
    return acc, f1, auroc


def train_probe(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    layer: int,
    config: ProbeConfig,
    seed: int,
    *,
    tracker: ExperimentTracker | None = None,
    global_step: int = 0,
    test_owner: np.ndarray | None = None,
) -> tuple[TorchProbeState, LayerMetrics, int]:
    import numpy as np
    import torch

    xtr, xte, mean, std = _standardize(x_train, x_test, config.standardize)
    hidden = xtr.shape[1]

    y_test_tokens = y_test if test_owner is None else y_test[test_owner]

    torch.manual_seed(seed)
    x = torch.from_numpy(np.ascontiguousarray(xtr, dtype=np.float32))
    y = torch.from_numpy(np.ascontiguousarray(y_train, dtype=np.float32))
    xv = torch.from_numpy(np.ascontiguousarray(xte, dtype=np.float32))

    linear = torch.nn.Linear(hidden, 1)
    optimizer = torch.optim.Adam(
        linear.parameters(), lr=config.lr, weight_decay=config.weight_decay
    )
    loss_fn = torch.nn.BCEWithLogitsLoss()
    generator = torch.Generator().manual_seed(seed)

    for epoch in range(1, config.epochs + 1):
        linear.train()
        order = torch.randperm(x.shape[0], generator=generator)
        epoch_loss = 0.0
        for start in range(0, x.shape[0], config.batch_size):
            idx = order[start : start + config.batch_size]
            optimizer.zero_grad()
            logits = linear(x[idx]).squeeze(1)
            loss = loss_fn(logits, y[idx])
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(idx)
        if tracker is not None and (epoch % config.log_every == 0 or epoch == config.epochs):
            train_acc = _accuracy(linear, x, y)
            test_acc = _accuracy(linear, xv, torch.from_numpy(y_test_tokens.astype(np.float32)))
            tracker.log(
                {
                    f"layer_{layer}/train_loss": epoch_loss / x.shape[0],
                    f"layer_{layer}/train_acc": train_acc,
                    f"layer_{layer}/test_acc": test_acc,
                },
                step=global_step,
            )
            global_step += 1

    state, metrics = _finalize_probe(linear, xv, y_test, mean, std, layer, test_owner)
    logger.info(
        "Layer {:>3}: acc={:.3f} f1={:.3f} auroc={}",
        layer,
        metrics.accuracy,
        metrics.f1,
        f"{metrics.auroc:.3f}" if metrics.auroc is not None else "n/a",
    )
    return state, metrics, global_step


def _accuracy(linear: Any, x: Any, y: Any) -> float:
    import torch

    linear.eval()
    with torch.no_grad():
        preds = (linear(x).squeeze(1) > 0).float()
    return float((preds == y).float().mean())


def _finalize_probe(
    linear: Any,
    xv: Any,
    y_test: np.ndarray,
    mean: Any,
    std: Any,
    layer: int,
    test_owner: np.ndarray | None = None,
) -> tuple[TorchProbeState, LayerMetrics]:
    import numpy as np
    import torch

    linear.eval()
    with torch.no_grad():
        logits = linear(xv).squeeze(1).numpy()
    weight = linear.weight.detach().squeeze(0).numpy()
    bias = float(linear.bias.detach().item())
    y_prob = 1.0 / (1.0 + np.exp(-logits))
    if test_owner is not None:
        y_prob = example_scores(y_prob, test_owner, len(y_test))
    y_pred = (y_prob > 0.5).astype(int)
    acc, f1, auroc = _score(y_test, y_pred, y_prob)
    state = TorchProbeState(weight=weight, bias=bias, mean=mean, std=std, layer=layer)
    return state, LayerMetrics(layer=layer, accuracy=acc, f1=f1, auroc=auroc)


def train_layer_probes(
    x_train: np.ndarray | TokenActivations,
    y_train: np.ndarray,
    x_test: np.ndarray | TokenActivations,
    y_test: np.ndarray,
    layers: list[int],
    config: ProbeTrainConfig,
    *,
    tracker: ExperimentTracker | None = None,
) -> tuple[list[LayerMetrics], dict[int, TorchProbeState]]:
    train = _as_tokens(x_train, layers)
    test = _as_tokens(x_test, layers)
    multi = train.max_tokens > 1 or test.max_tokens > 1
    if multi:
        logger.info("Train activations — {}", train.describe())
        logger.info("Test activations  — {}", test.describe())

    metrics: list[LayerMetrics] = []
    probes: dict[int, TorchProbeState] = {}
    global_step = 0
    for position, layer in enumerate(layers):
        x_tr, _ = train.layer_tokens(position)
        x_te, owner_te = test.layer_tokens(position)
        state, layer_metrics, global_step = train_probe(
            x_tr,
            train.expand(y_train),
            x_te,
            y_test,
            layer,
            config.probe,
            config.seed,
            tracker=tracker,
            global_step=global_step,
            test_owner=owner_te if multi else None,
        )
        metrics.append(layer_metrics)
        probes[layer] = state
    return metrics, probes


def _as_tokens(x: np.ndarray | TokenActivations, layers: list[int]) -> TokenActivations:
    return x if isinstance(x, TokenActivations) else TokenActivations.from_pooled(x, layers)


def _select_best(metrics: list[LayerMetrics]) -> LayerMetrics:
    return max(metrics, key=lambda m: (m.auroc or 0.0, m.accuracy, m.f1))


def _load_rows(
    dataset_dir: Path, limit: int | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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


def _tracking_params(config: ProbeTrainConfig, device: str, layers: list[int]) -> dict[str, Any]:
    return {
        "model_name": config.model.name,
        "device": device,
        "quantization": (
            "4bit"
            if config.model.quantization.load_in_4bit
            else "8bit"
            if config.model.quantization.load_in_8bit
            else "none"
        ),
        "pooling": config.pooling,
        "pooling_tokens": config.tokens_per_example,
        "layers": layers,
        "epochs": config.probe.epochs,
        "lr": config.probe.lr,
        "weight_decay": config.probe.weight_decay,
        "standardize": config.probe.standardize,
    }


def train_probes(config: ProbeTrainConfig) -> ProbeTrainResult:
    import numpy as np

    train_rows, test_rows = _load_rows(config.dataset_dir, config.limit)
    logger.info("Loaded {} train / {} test contrastive rows.", len(train_rows), len(test_rows))

    device = resolve_device(config.model.device)
    model, tokenizer = load_model_and_tokenizer(config.model, device)
    layers = config.layers or default_layers(model)

    def rendered(rows: list[dict[str, Any]]) -> tuple[list[str], list[tuple[int, int] | None]]:
        pairs = [
            build_prompt_with_span(r, tokenizer, use_chat_template=config.use_chat_template)
            for r in rows
        ]
        return [text for text, _ in pairs], [span for _, span in pairs]

    def activations_for(rows: list[dict[str, Any]], desc: str) -> TokenActivations:
        texts, spans = rendered(rows)
        return extract_token_activations(
            model,
            tokenizer,
            texts,
            layers=layers,
            pooling=config.pooling,
            batch_size=config.extraction_batch_size,
            max_length=config.max_length,
            pooling_tokens=config.pooling_tokens,
            content_spans=spans,
            desc=desc,
        )

    if config.debug_tokens and config.pooling == "last_n":
        texts, spans = rendered(train_rows)
        logger.info(
            "Token selection preview ({} tokens per example):\n{}",
            config.pooling_tokens,
            describe_selected_tokens(
                tokenizer,
                texts,
                pooling_tokens=config.pooling_tokens,
                max_length=config.max_length,
                content_spans=spans,
                limit=config.debug_tokens,
            ),
        )

    x_train = activations_for(train_rows, "Extracting train activations")
    x_test = activations_for(test_rows, "Extracting test activations")
    y_train = np.array([int(r["label"]) for r in train_rows])
    y_test = np.array([int(r["label"]) for r in test_rows])

    with ExperimentTracker(config.tracking, _tracking_params(config, device, layers)) as tracker:
        metrics, probes = train_layer_probes(
            x_train, y_train, x_test, y_test, layers, config, tracker=tracker
        )
        best = _select_best(metrics)
        logger.info("Best layer: {} (acc={:.3f}).", best.layer, best.accuracy)
        tracker.summary(
            {
                "best_layer": float(best.layer),
                "best_test_acc": best.accuracy,
                "best_test_auroc": best.auroc if best.auroc is not None else 0.0,
            }
        )

    return _persist(
        config,
        metrics,
        probes,
        best,
        len(train_rows),
        len(test_rows),
        device,
        token_counts=(x_train.n_tokens, x_test.n_tokens),
    )


def _persist(
    config: ProbeTrainConfig,
    metrics: list[LayerMetrics],
    probes: dict[int, TorchProbeState],
    best: LayerMetrics,
    n_train: int,
    n_test: int,
    device: str,
    *,
    token_counts: tuple[int, int] = (0, 0),
) -> ProbeTrainResult:
    import joblib

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    probe_path = output_dir / "probe.joblib"
    metrics_path = output_dir / "metrics.json"

    joblib.dump(
        {
            "state": probes[best.layer],
            "model_name": config.model.name,
            "layer": best.layer,
            "pooling": config.pooling,
            "pooling_tokens": config.tokens_per_example,
            "use_chat_template": config.use_chat_template,
            "max_length": config.max_length,
        },
        probe_path,
    )

    payload = {
        "model_name": config.model.name,
        "device": device,
        "pooling": config.pooling,
        "pooling_tokens": config.tokens_per_example,
        "best_layer": best.layer,
        "n_train": n_train,
        "n_test": n_test,
        "n_train_tokens": token_counts[0],
        "n_test_tokens": token_counts[1],
        "config": json.loads(config.model_dump_json()),
        "layer_metrics": [asdict(m) for m in metrics],
    }
    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Saved probe to {} and metrics to {}.", probe_path, metrics_path)

    return ProbeTrainResult(
        model_name=config.model.name,
        pooling=config.pooling,
        best_layer=best.layer,
        n_train=n_train,
        n_test=n_test,
        layer_metrics=metrics,
        probe_path=str(probe_path),
        metrics_path=str(metrics_path),
        pooling_tokens=config.tokens_per_example,
        n_train_tokens=token_counts[0],
        n_test_tokens=token_counts[1],
    )


__all__ = [
    "LayerMetrics",
    "ProbeTrainResult",
    "TorchProbeState",
    "example_scores",
    "train_layer_probes",
    "train_probe",
    "train_probes",
]
