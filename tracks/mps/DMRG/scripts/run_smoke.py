#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vmcrg_ref.config import load_experiment_config
from vmcrg_ref.workflow import run_full_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the 9x9 -> 3x3 MPS VMCRG smoke test")
    parser.add_argument("--config", type=Path, default=ROOT / "config/mps_smoke.toml")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    config = load_experiment_config(args.config)
    seed = config.run.seeds[0] if args.seed is None else args.seed
    output = args.output or config.run.output / f"seed-{seed}"
    summary = run_full_experiment(config, seed=seed, output=output)
    print(f"smoke status={summary['status']} output={output}", flush=True)


if __name__ == "__main__":
    main()
