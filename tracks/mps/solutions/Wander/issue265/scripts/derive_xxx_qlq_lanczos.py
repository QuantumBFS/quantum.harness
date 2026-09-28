#!/usr/bin/env python3
"""Generate the microscopic QLQ Lanczos prefix seen by a slow current."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_xxx_slow_current_dynamics import projected_qlq_lanczos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=24)
    parser.add_argument("--external-mode", type=int, default=1)
    parser.add_argument("--cutoff-mode", type=int, default=3)
    parser.add_argument("--steps", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = projected_qlq_lanczos(
        args.length, args.external_mode, args.cutoff_mode, args.steps
    )
    result["schema"] = 1
    result["method"] = "exact_sparse_pauli_projected_qlq_lanczos"
    result["gates"] = {
        "positive_qlp_force_norm": result["qlp_force_norm"] > 0.0,
        "positive_lanczos_betas": all(value > 0.0 for value in result["betas"]),
        "q_orthogonality_preserved": result[
            "maximum_q_orthogonality_residual"
        ]
        <= 1.0e-10,
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
