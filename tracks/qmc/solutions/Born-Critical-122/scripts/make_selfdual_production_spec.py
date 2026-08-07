#!/usr/bin/env python3
"""Generate the frozen Stage-4D production cell map."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROWS_BY_SIZE = {
    6: 786_432,
    8: 262_144,
    10: 327_680,
    12: 262_144,
    16: 262_144,
    20: 262_144,
    24: 262_144,
    30: 262_144,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base_seed = 422607280100
    cells = []
    for size, measurement_rows in ROWS_BY_SIZE.items():
        for replica in range(64):
            key = f"{base_seed}:selfdual:{size}:{replica}:production"
            seed = int.from_bytes(
                hashlib.blake2b(key.encode(), digest_size=8).digest(), "big"
            )
            cells.append(
                {
                    "cell_id": f"L{size:02d}-r{replica:03d}-q08",
                    "params": {
                        "size": size,
                        "replica": replica,
                        "seed": seed,
                        "qr_interval": 8,
                        "measurement_rows": measurement_rows,
                        "role": "production",
                    },
                }
            )
    payload = {
        "schema_version": 1,
        "run_id": "selfdual-production-v1",
        "model": "selfdual",
        "geometry": {
            "bc_x": "periodic",
            "sector": "vacuum-even",
            "gate_order": "MZ-site-order-then-MX-site-order",
            "spacetime_sublayers_per_cycle": 2,
        },
        "couplings": {"theta": "pi/4", "beta": "ln(1+sqrt(2))"},
        "settings": {
            "base_seed": base_seed,
            "burnin_rows_per_size": 50,
            "block_rows_floor": 2048,
            "block_rows_per_size": 16,
            "spacetime_sublayers_per_cycle": 2,
            "alpha": 1.0,
            "estimator": "rao-blackwell-conditional-binary-entropy",
            "pilot_source": "selfdual-pilot-v2",
            "target_standard_error": 2e-6,
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
