"""Map AutoFinder's documented partial-success exit code for n8n orchestration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARTIAL_SUCCESS_EXIT_CODE = 2


def n8n_exit_code(runtime_exit_code: int) -> int:
    """Keep fatal codes visible while treating a reported partial success as n8n success."""
    return 0 if runtime_exit_code in {0, PARTIAL_SUCCESS_EXIT_CODE} else runtime_exit_code


def main() -> int:
    """Run the real AutoFinder entrypoint and expose its safe orchestration result."""
    completed = subprocess.run([sys.executable, "-m", "autofinder"], cwd=PROJECT_ROOT, check=False)
    return n8n_exit_code(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
