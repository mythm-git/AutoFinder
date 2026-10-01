"""Tests for central rotating logging."""

import logging
from pathlib import Path

from autofinder.core.logging import configure_logging


def test_logging_creates_and_rotates_utf8_file(tmp_path: Path) -> None:
    """A small log threshold proves rotating-file behavior without external services."""
    logger = configure_logging(tmp_path, level="DEBUG", max_bytes=100, backup_count=1)
    logger.debug("ä" * 100)
    logger.debug("second record triggers rotation")
    for handler in logger.handlers:
        handler.flush()
    assert (tmp_path / "autofinder.log").exists()
    assert (tmp_path / "autofinder.log.1").exists()
    assert "second record" in (tmp_path / "autofinder.log").read_text(encoding="utf-8")
    logging.getLogger("autofinder").handlers.clear()
