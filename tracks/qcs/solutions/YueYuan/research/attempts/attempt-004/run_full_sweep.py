#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import config
import experiments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--task-index", type=int)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    sweep = config.default_full_sweep()
    records = experiments.run_sweep(
        sweep,
        args.out,
        selected_index=args.task_index,
        fast=args.fast,
    )
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
