"""Rotating file logging under ``%LOCALAPPDATA%\\MediaFormat\\logs``."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.paths import log_dir

LOGGER_NAME = "mediaformat"
_MAX_BYTES = 1_000_000
_BACKUPS = 3


def setup_logging(level: int = logging.INFO, log_file: Path | None = None) -> logging.Logger:
    """Configure the app logger once and return it."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        logger.setLevel(level)
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    target = log_file or (log_dir() / "mediaformat.log")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        rotating = RotatingFileHandler(
            target, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
        )
        rotating.setFormatter(formatter)
        logger.addHandler(rotating)
    except OSError:
        logger.warning("No se pudo abrir el log en %s; solo consola", target)

    return logger
