"""Run the fixture-only Step 12 pipeline verification without external services."""

from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Execute the deterministic pipeline cases and return pytest's exit code."""
    print("Runtime pipeline fixture verification")
    print("A: five collected / five seen -> SUCCESS, summary only")
    print("B: two old / three new -> one REVIEW alert, one REJECT, final summary")
    print("C: first listing failure / second STRONG -> PARTIAL_SUCCESS, alert then summary")
    return pytest.main(["-q", "tests/unit/test_runtime_pipeline.py"], plugins=[])


if __name__ == "__main__":
    raise SystemExit(main())
