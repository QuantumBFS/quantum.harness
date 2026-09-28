#!/usr/bin/env python3
"""Audit matching-scale dependence of the giant diagonal outer integrals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_giant_diagonal_outer import evaluate  # noqa: E402


SCHEMES = {
    "medium": {
        "xi_extent": 10.0,
        "xi_points": 28,
        "dressing_xi_extent": 16.0,
        "dressing_xi_points": 140,
        "rapidity_extent": 18.0,
        "rapidity_points": 288,
    },
    "fine": {
        "xi_extent": 10.0,
        "xi_points": 36,
        "dressing_xi_extent": 16.0,
        "dressing_xi_points": 200,
        "rapidity_extent": 24.0,
        "rapidity_points": 384,
    },
}


def derive() -> dict[str, object]:
    matching_scales = (0.4, 0.2, 0.1, 0.05)
    rows = []
    for matching_scale in matching_scales:
        values = {
            name: evaluate(matching_scale=matching_scale, **parameters)
            for name, parameters in SCHEMES.items()
        }
        leading = np.asarray(
            [value["outer_leading_integral"] for value in values.values()]
        )
        first = np.asarray(
            [value["outer_first_integral"] for value in values.values()]
        )
        full_leading = np.asarray(
            [value["outer_full_leading_integral"] for value in values.values()]
        )
        full_first = np.asarray(
            [value["outer_full_first_integral"] for value in values.values()]
        )
        rows.append(
            {
                "matching_scale": matching_scale,
                "schemes": values,
                "leading_scheme_relative_spread": float(
                    np.ptp(leading) / abs(np.mean(leading))
                ),
                "first_scheme_absolute_spread": float(np.ptp(first)),
                "full_leading_scheme_relative_spread": float(
                    np.ptp(full_leading) / abs(np.mean(full_leading))
                ),
                "full_first_scheme_absolute_spread": float(np.ptp(full_first)),
            }
        )
    fine_first = np.asarray(
        [row["schemes"]["fine"]["outer_first_integral"] for row in rows]
    )
    fine_leading = np.asarray(
        [row["schemes"]["fine"]["outer_leading_integral"] for row in rows]
    )
    fine_cross_leading = np.asarray(
        [
            row["schemes"]["fine"]["outer_cross_leading_integral"]
            for row in rows
        ]
    )
    fine_full_leading = np.asarray(
        [
            row["schemes"]["fine"]["outer_full_leading_integral"]
            for row in rows
        ]
    )
    return {
        "schema": 1,
        "method": "matched_outer_giant_diagonal_scan",
        "schemes": SCHEMES,
        "rows": rows,
        "gates": {
            "outer_leading_monotone_as_eta_decreases": bool(
                np.all(np.diff(fine_leading) > 0.0)
            ),
            "outer_first_matching_scale_range": [
                float(np.min(fine_first)),
                float(np.max(fine_first)),
            ],
            "outer_first_has_matching_scale_plateau": False,
            "cross_has_nonzero_leading_on_fixed_u_grid": bool(
                fine_cross_leading[-1] > 0.1
            ),
            "smallest_eta_cross_leading": float(fine_cross_leading[-1]),
            "smallest_eta_full_leading": float(fine_full_leading[-1]),
            "smallest_eta_diagonal_leading": float(fine_leading[-1]),
            "fixed_u_rapidity_resolution_converged": False,
            "artifact_superseded_by_adaptive_u_over_xi_audit": True,
            "fixed_string_inner_overlap_evaluated": False,
            "outer_value_alone_eligible_for_physical_D1": False,
            "physical_D1_certified": False,
        },
        "interpretation": (
            "Both nominal schemes used the same fixed rapidity step du=0.125. "
            "Because the small-xi thermodynamic layer has width u=O(xi), this "
            "scan does not establish rapidity convergence and its limiting "
            "numbers are superseded by the adaptive u/xi audit."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/giant_diagonal_outer_matching_audit.json",
    )
    args = parser.parse_args()
    result = derive()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
