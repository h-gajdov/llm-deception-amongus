from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..logging import get_logger

if TYPE_CHECKING:
    from .config import TrackingConfig

logger = get_logger()


class ExperimentTracker:
    def __init__(self, config: TrackingConfig, params: dict[str, Any]) -> None:
        self._params = params
        self._wandb = None
        self._mlflow = None
        if config.wandb.enabled:
            self._wandb = _init_wandb(config, params)
        if config.mlflow.enabled:
            self._mlflow = _init_mlflow(config, params)

    @property
    def active(self) -> bool:
        return self._wandb is not None or self._mlflow is not None

    def log(self, metrics: dict[str, float], step: int) -> None:
        if self._wandb is not None:
            self._wandb.log(metrics, step=step)
        if self._mlflow is not None:
            for key, value in metrics.items():
                self._mlflow.log_metric(key, value, step=step)

    def summary(self, metrics: dict[str, float]) -> None:
        if self._wandb is not None:
            self._wandb.summary.update(metrics)
        if self._mlflow is not None:
            for key, value in metrics.items():
                self._mlflow.log_metric(key, value)

    def finish(self) -> None:
        if self._wandb is not None:
            self._wandb.finish()
            self._wandb = None
        if self._mlflow is not None:
            self._mlflow.end_run()
            self._mlflow = None

    def __enter__(self) -> ExperimentTracker:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.finish()


def _has_wandb_credentials() -> bool:
    import os
    from pathlib import Path

    if os.environ.get("WANDB_API_KEY"):
        return True
    home = Path.home()
    for name in (".netrc", "_netrc"):
        path = home / name
        try:
            if path.exists() and "api.wandb.ai" in path.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


def _init_wandb(config: TrackingConfig, params: dict[str, Any]) -> Any:
    try:
        import wandb
    except ImportError:
        logger.warning("wandb enabled but not installed; skipping. `pip install wandb`.")
        return None

    mode = config.wandb.mode
    if mode == "online" and not _has_wandb_credentials():
        logger.warning(
            "wandb: no API key found (run `wandb login` or set WANDB_API_KEY); "
            "logging offline to ./wandb instead."
        )
        mode = "offline"

    try:
        wandb.init(
            project=config.wandb.project,
            entity=config.wandb.entity,
            name=config.wandb.run_name,
            mode=mode,
            config=params,
        )
        logger.info("wandb tracking active (project={}, mode={}).", config.wandb.project, mode)
    except Exception as exc:
        logger.warning("wandb init failed ({}); continuing without it.", exc)
        return None
    return wandb


def _init_mlflow(config: TrackingConfig, params: dict[str, Any]) -> Any:
    import os

    try:
        import mlflow
    except ImportError:
        logger.warning("mlflow enabled but not installed; skipping. `pip install mlflow`.")
        return None

    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    try:
        if config.mlflow.tracking_uri:
            mlflow.set_tracking_uri(config.mlflow.tracking_uri)
        mlflow.set_experiment(config.mlflow.experiment)
        mlflow.start_run(run_name=config.mlflow.run_name)
        mlflow.log_params(_stringify(params))
        logger.info("mlflow tracking active (experiment={}).", config.mlflow.experiment)
    except Exception as exc:
        logger.warning("mlflow init failed ({}); continuing without it.", exc)
        return None
    return mlflow


def _stringify(params: dict[str, Any]) -> dict[str, str]:
    return {key: str(value) for key, value in params.items()}


__all__ = ["ExperimentTracker"]
