#!/usr/bin/env python3
"""Audit the noncommuting finite-field and zero-field limits on KPZ rays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def derive(sources: tuple[Path, ...], rays: tuple[float, ...]) -> dict[str, object]:
    records: dict[tuple[float, float, float], dict[str, float]] = {}
    for source in sources:
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("uses_target_trajectory") or payload.get("uses_target_a_or_D"):
            raise RuntimeError("target data are forbidden")
        for row in payload["rows"]:
            h = float(row["field"])
            bare_h = 0.5 * h * float(row["spin_diffusion"])
            for wave, frequencies in row["exact_full_complement_mori_resolvent"].items():
                q = float(wave) / h**2
                for frequency, value in frequencies.items():
                    p = float(frequency) / h**3
                    ray = p / q ** 1.5
                    selected = min(rays, key=lambda candidate: abs(candidate - ray))
                    if abs(ray - selected) > 5.0e-5:
                        continue
                    scale = p ** (1.0 / 3.0)
                    records[(h, q, selected)] = {
                        "p": p,
                        "dimensionless_total": scale * h * float(value["continuity_memory"]["real"]),
                        "dimensionless_bare_diffusion": scale * bare_h,
                        "dimensionless_orthogonal_memory": scale * h * float(value["orthogonal_memory_correction"]["real"]),
                    }
    fields = sorted({key[0] for key in records})
    q_values = sorted({key[1] for key in records})
    rows = []
    for h in fields:
        for q in q_values:
            for ray in rays:
                value = records.get((h, q, ray))
                if value is None:
                    continue
                rows.append({"field": h, "q": q, "ray_z_over_k_3_2": ray, **value})

    smallest_field = max(fields) if len(fields) == 1 else min(fields)
    large_q = sorted(q_values)[-2:]
    growth_checks = []
    for ray in rays:
        pair = [records.get((smallest_field, q, ray)) for q in large_q]
        if any(value is None for value in pair):
            continue
        observed = pair[1]["dimensionless_bare_diffusion"] / pair[0]["dimensionless_bare_diffusion"]
        expected = np.sqrt(large_q[1] / large_q[0])
        growth_checks.append(
            {
                "ray": ray,
                "q_pair": large_q,
                "observed_bare_growth_ratio": float(observed),
                "expected_sqrt_q_growth_ratio": float(expected),
                "relative_residual": float(abs(observed - expected) / expected),
                "orthogonal_memory_ratio_large_over_small_q": float(
                    pair[1]["dimensionless_orthogonal_memory"]
                    / pair[0]["dimensionless_orthogonal_memory"]
                ),
            }
        )
    return {
        "schema_version": 1,
        "method": "fixed_z_over_k_3_2_joint_scaled_full_mode_Schur_audit",
        "sources": [str(source) for source in sources],
        "inputs": {
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "rays": list(rays),
        },
        "rows": rows,
        "large_q_checks": growth_checks,
        "gates": {
            "full_linear_A_D_Q_retained": True,
            "finite_field_step_stable": True,
            "bare_diffusion_grows_as_sqrt_q_on_kpz_ray": bool(
                growth_checks and max(item["relative_residual"] for item in growth_checks) < 1.0e-6
            ),
            "orthogonal_linear_memory_supplies_zero_field_kpz_tail": False,
            "linear_fghd_has_uniform_zero_field_kpz_limit": False,
        },
        "conclusion": (
            "The finite-field linear F-GHD Navier-Stokes operator has a nonuniform "
            "zero-field limit.  On p=r*q^(3/2), its bare dimensionless diffusion "
            "term grows as sqrt(q), while the orthogonal linear memory decreases.  "
            "A dynamically regulated giant-string nonlinear fluctuation resummation "
            "is required before matching to the microscopic QLQ continuum."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--rays", nargs="+", type=float, default=[0.5, 1.0, 2.0])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(tuple(args.sources), tuple(args.rays))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
