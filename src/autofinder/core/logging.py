"""Central, secret-safe console and rotating-file logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_directory: Path, level: str = "INFO", max_bytes: int = 1_048_576, backup_count: int = 5) -> logging.Logger:
    """Configure the AutoFinder root logger once.

    Args:
        log_directory: Directory where ``autofinder.log`` and rotations live.
        level: Standard logging level name.
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of rotated files to retain.

    Returns:
        The configured ``autofinder`` logger.

    Raises:
        ValueError: If the requested logging level is invalid.
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    log_directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("autofinder")
    logger.setLevel(numeric_level)
    logger.propagate = False
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    console = logging.StreamHandler()
    console.setLevel(numeric_level)
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(log_directory / "autofinder.log", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger
