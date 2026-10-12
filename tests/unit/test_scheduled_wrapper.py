"""Tests for n8n-safe mapping of documented AutoFinder process exit codes."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[2] / "scripts" / "run_scheduled_autofinder.py"
SPEC = importlib.util.spec_from_file_location("scheduled_wrapper", SCRIPT)
assert SPEC and SPEC.loader
wrapper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wrapper)


@pytest.mark.parametrize(("runtime_code", "n8n_code"), [(0, 0), (2, 0), (1, 1), (7, 7)])
def test_n8n_exit_code_preserves_failures_and_accepts_partial_success(runtime_code: int, n8n_code: int) -> None:
    assert wrapper.n8n_exit_code(runtime_code) == n8n_code
