"""Tests for minimal secret-safe application startup."""

from pathlib import Path

from autofinder import main as application


def test_foundation_startup_logs_safe_configuration(tmp_path: Path, monkeypatch) -> None:
    """Startup validates config and does not write a representative secret to logs."""
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(application, "PROJECT_ROOT", root)
    assert application.main() == 0
    log_output = (root / "logs" / "autofinder.log").read_text(encoding="utf-8")
    assert "AutoFinder v2 started." in log_output
    assert "No runtime pipeline has been implemented yet." in log_output
    assert "TELEGRAM_BOT_TOKEN" not in log_output
