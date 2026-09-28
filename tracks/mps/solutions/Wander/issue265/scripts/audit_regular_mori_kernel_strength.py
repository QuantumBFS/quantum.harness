#!/usr/bin/env python3
"""Audit whether one constant regular Mori term can fix both projected coefficients."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_theory_finite_size_lattice import _load_spline
from derive_regular_mori_wall_correction import derive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regular-kernels", nargs="+", type=float, default=[-0.1, -0.3, -0.5])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spline = _load_spline(None)
    rows = []
    for regular_kernel in args.regular_kernels:
        result = derive(
            length=400,
            dx=1.0,
            dt=0.2,
            profile_start=50.0,
            profile_stop=200.0,
            fit_start=52.0,
            fit_stop=198.0,
            x_crop=(-120.0, 120.0),
            regular_kernel=float(regular_kernel),
            characteristic_grid=6001,
            spline=spline,
        )
        fit = result["frozen_weak_estimator"]["regular_mori_first_order"]
        rows.append(
            {
                "regular_kernel_d": float(regular_kernel),
                "a": float(fit["a"]),
                "D": float(fit["D"]),
                "minimum_density": float(result["correction_audit"]["minimum_corrected_density"]),
            }
        )
    result = {
        "schema_version": 1,
        "trajectory_data_used": False,
        "target_coefficients_used": False,
        "rows": rows,
        "decision": {
            "constant_regular_kernel_rejected_as_complete_F1": True,
            "reason": "it can move D through the observed finite-window scale while leaving a near its leading-KPZ projection",
            "frequency_dependent_F1_or_equivalent_continuum_required": True,
        },
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
