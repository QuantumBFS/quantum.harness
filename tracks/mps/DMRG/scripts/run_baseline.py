#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vmcrg_ref.config import load_experiment_config
from vmcrg_ref.workflow import run_traditional_baseline


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the traditional finite-coupling VMCRG baseline")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_experiment_config(args.config)
    seed = config.run.seeds[0] if args.seed is None else args.seed
    output = args.output or config.run.output / f"seed-{seed}"
    output.mkdir(parents=True, exist_ok=True)
    _, summary = run_traditional_baseline(config, seed, output)
    print(f"baseline complete J0={summary['linear_bias'][0]:.8g} output={output}", flush=True)


if __name__ == "__main__":
    main()
