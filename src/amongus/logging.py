

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
    "<level>{message}</level>"
)

_configured = False


def configure_logging(
    level: str = "INFO",
    *,
    log_file: Path | None = None,
    serialize: bool = False,
) -> None:
    pass
    global _configured
    logger.remove()
    logger.add(sys.stderr, level=level, format=_CONSOLE_FORMAT, enqueue=True)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            level=level,
            serialize=serialize,
            enqueue=True,
            rotation="50 MB",
            retention=10,
        )

    _configured = True


def get_logger():
    pass
    if not _configured:
        configure_logging()
    return logger


__all__ = ["configure_logging", "get_logger", "logger"]
