#!/usr/bin/env python3
"""Test a bare fluctuating-GHD loop against the exact XXX current norm.

If a positive zero-time loop is interpreted as the Kubo-orthogonal slow
component of the microscopic bond current, its norm cannot exceed the norm of
the full current.  This necessary projector bound is independent of any
Burgers fit and catches hydrodynamic/microscopic UV double counting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive(microscopic_path: Path, loop_path: Path) -> dict[str, object]:
    microscopic = json.loads(microscopic_path.read_text(encoding="utf-8"))
    loop = json.loads(loop_path.read_text(encoding="utf-8"))
    for payload in (microscopic, loop):
        inputs = payload.get("inputs", {})
        if inputs.get("trajectory_data_used") or inputs.get("target_coefficients_used"):
            raise RuntimeError("source certificate contains forbidden target data")
    mu0 = float(microscopic["long_wave_exact_prefix"]["mu0"])
    rows = []
    for row in loop["uv_rows"]:
        zero_time = float(
            row["colored_memory"]["total_colored_continuity_memory"]["values"][0]
        )
        rows.append(
            {
                "fourier_points": int(row["fourier_points"]),
                "external_wave_number": float(row["external_wave_number"]),
                "bare_slow_candidate_K_at_zero": zero_time,
                "exact_full_microscopic_K_at_zero": mu0,
                "candidate_to_full_norm_ratio": zero_time / mu0,
                "positive_projector_norm_bound_pass": bool(
                    zero_time >= 0.0 and zero_time <= mu0 * (1.0 + 1.0e-12)
                ),
            }
        )
    all_pass = all(row["positive_projector_norm_bound_pass"] for row in rows)
    return {
        "schema": 1,
        "method": "exact_xxx_kubo_projector_zero_time_norm_bound",
        "sources": {
            str(microscopic_path): _sha256(microscopic_path),
            str(loop_path): _sha256(loop_path),
        },
        "inputs": {
            "trajectory_data_used": False,
            "target_coefficients_used": False,
        },
        "identity": {
            "Pythagorean_Kubo_split": (
                "||j||^2=||P_slow j||^2+||Q_slow j||^2"
            ),
            "necessary_bound": "0<=K_slow(0)<=K_exact(0)=mu0",
            "exact_mu0": mu0,
        },
        "rows": rows,
        "gates": {
            "all_bare_loops_are_admissible_kubo_projections": all_pass,
            "microscopic_hydrodynamic_no_double_counting_complete": False,
            "bare_loop_can_be_added_to_exact_mori_kernel": False,
            "physical_F1_certified": False,
        },
        "conclusion": (
            "Failure means the cell-scale Gaussian loop is not a Kubo-orthogonal "
            "piece of the microscopic current.  A P/Q matching or equivalent "
            "subtraction is mandatory before any finite-window propagation."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("microscopic_certificate", type=Path)
    parser.add_argument("loop_certificate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(args.microscopic_certificate, args.loop_certificate)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
