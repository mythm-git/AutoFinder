"""Tests for the thin executable composition root."""

from pathlib import Path
from types import SimpleNamespace

from autofinder import main as application
from autofinder.notifications.runtime_models import RuntimeRunStatus


def test_module_entrypoint_constructs_and_runs_one_injected_pipeline(monkeypatch) -> None:
    """The entrypoint delegates runtime work to the pipeline and returns its code."""
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(application, "PROJECT_ROOT", root)
    observed: list[object] = []
    result = SimpleNamespace(summary=SimpleNamespace(status=RuntimeRunStatus.SUCCESS), exit_code=0)

    class _Pipeline:
        def run(self) -> object:
            observed.append("run")
            return result

    monkeypatch.setattr(application, "build_runtime_pipeline", lambda config, project_root: _Pipeline())
    assert application.main() == 0
    assert observed == ["run"]
