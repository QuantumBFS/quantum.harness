#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import config
import experiments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    records = experiments.run_sweep(config.default_smoke_sweep(), args.out, fast=args.fast)
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
