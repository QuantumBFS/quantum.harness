#!/usr/bin/env python3
"""Generate the frozen Stage-4C pilot cell map."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", default="selfdual-pilot-v1")
    parser.add_argument("--block-rows-floor", type=int, default=512)
    parser.add_argument("--main-qr-interval", type=int, default=2)
    parser.add_argument("--main-only", action="store_true")
    args = parser.parse_args()
    base_seed = 422607280000
    cells: list[dict[str, object]] = []
    for size in (4, 6, 8, 10, 12):
        for replica in range(16):
            key = f"{base_seed}:selfdual:{size}:{replica}:trajectory:q2"
            seed = int.from_bytes(
                hashlib.blake2b(key.encode(), digest_size=8).digest(), "big"
            )
            cells.append(
                {
                    "cell_id": (
                        f"L{size:02d}-r{replica:03d}-"
                        f"q{args.main_qr_interval:02d}"
                    ),
                    "params": {
                        "size": size,
                        "replica": replica,
                        "seed": seed,
                        "qr_interval": args.main_qr_interval,
                        "role": "main",
                    },
                }
            )
        for qr_interval in (() if args.main_only else (1, 4, 8)):
            key = f"{base_seed}:selfdual:{size}:0:trajectory:q2"
            seed = int.from_bytes(
                hashlib.blake2b(key.encode(), digest_size=8).digest(), "big"
            )
            cells.append(
                {
                    "cell_id": f"L{size:02d}-r000-q{qr_interval:02d}",
                    "params": {
                        "size": size,
                        "replica": 0,
                        "seed": seed,
                        "qr_interval": qr_interval,
                        "role": "qr-stability",
                    },
                }
            )
    payload = {
        "schema_version": 1,
        "run_id": args.run_id,
        "model": "selfdual",
        "geometry": {
            "bc_x": "periodic",
            "sector": "vacuum-even",
            "gate_order": "MZ-site-order-then-MX-site-order",
        },
        "couplings": {"theta": "pi/4", "beta": "ln(1+sqrt(2))"},
        "settings": {
            "base_seed": base_seed,
            "burnin_rows_per_size": 50,
            "measurement_rows": 16384,
            "spacetime_sublayers_per_cycle": 2,
            "block_rows_floor": args.block_rows_floor,
            "block_rows_per_size": 16,
            "alpha": 1.0,
        },
        "cells": cells,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output)
    print(f"wrote {len(cells)} cells to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
