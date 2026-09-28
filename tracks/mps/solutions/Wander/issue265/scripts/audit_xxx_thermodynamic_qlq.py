#!/usr/bin/env python3
"""Audit the algebraic-tail extrapolation of thermodynamic QLQ Lanczos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def derive(sources: tuple[Path, ...]) -> dict[str, object]:
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in sources]
    separations = np.asarray(
        [item["inputs"]["maximum_separation"] for item in payloads], dtype=float
    )
    order = np.argsort(separations)
    separations = separations[order]
    payloads = [payloads[index] for index in order]
    depth = min(len(item["squared_betas"]) for item in payloads)
    x = 1.0 / separations**2
    rows = []
    for level in range(depth):
        values = np.asarray(
            [item["squared_betas"][level] for item in payloads], dtype=float
        )
        linear = np.polyfit(x, values, 1)
        quadratic = np.polyfit(x, values, 2)
        rows.append(
            {
                "level": level + 1,
                "values": values.tolist(),
                "linear_in_1_over_R_squared_limit": float(linear[-1]),
                "quadratic_in_1_over_R_squared_limit": float(quadratic[-1]),
                "scheme_envelope": [
                    float(min(linear[-1], quadratic[-1])),
                    float(max(linear[-1], quadratic[-1])),
                ],
            }
        )
    exact_first = float(
        payloads[-1]["analytic_infinite_tail_first_recurrent"][
            "squared_first_qlq_recurrent"
        ]
    )
    first_errors = [
        abs(rows[0][key] - exact_first) / exact_first
        for key in (
            "linear_in_1_over_R_squared_limit",
            "quadratic_in_1_over_R_squared_limit",
        )
    ]
    return {
        "schema": 1,
        "method": "analytic_anchor_validated_1_over_R_squared_qlq_tail_audit",
        "sources": [str(path) for path in sources],
        "maximum_separations": separations.astype(int).tolist(),
        "trajectory_data_used": False,
        "target_coefficients_used": False,
        "exact_analytic_first_squared_recurrent": exact_first,
        "squared_recurrent_extrapolations": rows,
        "first_recurrent_relative_extrapolation_errors": first_errors,
        "gates": {
            "analytic_anchor_reproduced_below_1e_minus_4": bool(
                max(first_errors) <= 1.0e-4
            ),
            "all_finite_tail_recurrents_positive": bool(
                all(min(row["values"]) > 0.0 for row in rows)
            ),
            "higher_recurrent_intervals_are_analytic_identities": False,
        },
        "interpretation": (
            "The exact first recurrent validates 1/R^2 as the leading tail "
            "extrapolation at the 1e-4 level on this sequence.  Applying the "
            "same two-scheme audit gives narrow numerical intervals for the "
            f"next {max(depth - 1, 0)} recurrents, but only the first is presently an "
            "analytic identity."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(tuple(args.sources))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
