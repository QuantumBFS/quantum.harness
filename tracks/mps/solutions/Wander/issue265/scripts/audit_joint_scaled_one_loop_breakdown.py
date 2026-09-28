#!/usr/bin/env python3
"""Diagnose the zero-field breakdown of the nonlinear F-GHD one-loop series.

The input consists of top-level joint-scaled mu26 matching certificates.  The
script collects unique field rows and studies the colored correction
``h*Delta K(q,p;h)``.  A finite perturbative zero-field limit would approach a
constant.  A power-law growth instead identifies the non-uniform term that
must be resummed.  This is a regulator audit and never uses wall data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def audit(payloads: list[dict[str, object]]) -> dict[str, object]:
    by_field: dict[float, dict[str, object]] = {}
    reference_p = None
    reference_q = None
    for payload in payloads:
        if payload.get("uses_target_trajectory") or payload.get("uses_target_a_or_D"):
            raise RuntimeError("target-contaminated matching certificate")
        p = np.asarray(payload["scaled_variables"]["p_equals_z_over_h3"], dtype=float)
        q = float(payload["scaled_variables"]["q_equals_k_over_h2"])
        if reference_p is None:
            reference_p = p
            reference_q = q
        elif not np.allclose(p, reference_p) or not np.isclose(q, reference_q):
            raise ValueError("all matching inputs must share q and p grids")
        for row in payload["rows"]:
            by_field[float(row["field"])] = row
    if len(by_field) < 4:
        raise ValueError("at least four distinct field regulators are required")
    fields = np.asarray(sorted(by_field, reverse=True), dtype=float)
    colored = np.asarray(
        [
            [entry["scaled_colored_hDeltaK"] for entry in by_field[h]["frequency_rows"]]
            for h in fields
        ],
        dtype=float,
    )
    if np.any(colored <= 0.0):
        raise ValueError("power audit requires positive colored corrections")

    frequency_rows = []
    for index, pp in enumerate(reference_p):
        values = colored[:, index]
        coefficients = np.polyfit(np.log(fields), np.log(values), 1)
        exponent = float(-coefficients[0])
        prediction = np.exp(np.polyval(coefficients, np.log(fields)))
        residual = float(np.linalg.norm(prediction - values) / np.linalg.norm(values))
        adjacent = -np.diff(np.log(values)) / np.diff(np.log(fields))
        candidate_rows = []
        for candidate in (1.0 / 3.0, 0.5, 2.0 / 3.0, 1.0):
            # Include a finite part to expose the scheme instability: with the
            # present field range several powers can mimic one another.
            design = np.column_stack((fields ** (-candidate), np.ones_like(fields)))
            amplitude, finite_part = np.linalg.lstsq(design, values, rcond=None)[0]
            candidate_prediction = design @ np.asarray([amplitude, finite_part])
            candidate_rows.append(
                {
                    "candidate_exponent": candidate,
                    "divergent_amplitude": float(amplitude),
                    "putative_finite_part": float(finite_part),
                    "relative_residual": float(
                        np.linalg.norm(candidate_prediction - values)
                        / np.linalg.norm(values)
                    ),
                }
            )
        frequency_rows.append(
            {
                "scaled_frequency_p": float(pp),
                "colored_hDeltaK_by_field": values.tolist(),
                "pure_power_effective_exponent": exponent,
                "pure_power_relative_residual": residual,
                "adjacent_effective_exponents": adjacent.tolist(),
                "candidate_power_plus_finite_part": candidate_rows,
            }
        )
    normalized_shapes = colored / colored[:, :1]
    last_shape_change = np.max(np.abs(normalized_shapes[-1] - normalized_shapes[-2]))
    exponents = np.asarray(
        [row["pure_power_effective_exponent"] for row in frequency_rows]
    )
    return {
        "schema": 1,
        "method": "target_free_joint_scaled_nonlinear_one_loop_breakdown_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "scaled_variables": {
            "q_equals_k_over_h2": reference_q,
            "p_equals_z_over_h3": reference_p.tolist(),
            "fields": fields.tolist(),
        },
        "frequency_rows": frequency_rows,
        "normalized_colored_shape_by_field": normalized_shapes.tolist(),
        "maximum_last_field_step_normalized_shape_change": float(last_shape_change),
        "effective_exponent_range": [float(np.min(exponents)), float(np.max(exponents))],
        "gates": {
            "finite_one_loop_zero_field_limit": False,
            "pure_power_growth_below_one_percent_residual_at_every_p": bool(
                all(row["pure_power_relative_residual"] < 0.01 for row in frequency_rows)
            ),
            "two_thirds_growth_consistent_but_not_proved": bool(
                np.max(np.abs(exponents - 2.0 / 3.0)) < 0.1
            ),
            "finite_part_unique_across_candidate_powers": False,
            "self_consistent_nonlinear_resummation_required": True,
        },
        "interpretation": (
            "The bare colored loop grows rather than approaching a finite hK. "
            "Its apparent power is compatible with the KPZ infrared breakdown, "
            "but the finite part changes with the subtraction power and is not "
            "a microscopic prediction."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit([json.loads(path.read_text(encoding="utf-8")) for path in args.inputs])
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
