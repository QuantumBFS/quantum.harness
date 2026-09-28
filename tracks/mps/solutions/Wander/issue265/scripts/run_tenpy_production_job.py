#!/usr/bin/env python3
"""Run one production-v2 job without changing the frozen convergence source."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_tenpy_research_job as base_runner
from src.production_initial_conditions import (
    production_initial_magnetization,
    production_source_closure,
)


def main() -> None:
    production_source_closure(ROOT)
    base_runner.condition_initial_magnetization = (
        production_initial_magnetization
    )
    base_runner.main()


if __name__ == "__main__":
    main()
