#!/usr/bin/env python3
"""Audit the full finite-field contraction and the xi,u boundary layer."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_full_tba_diffusion import (  # noqa: E402
    fixed_string_inner_weights_field,
)
from scripts.evaluate_giant_diagonal_outer import (  # noqa: E402
    evaluate_adaptive_rapidity_fft,
)
from src.heisenberg_burgers_bridge import EXACT_D0_INFINITY_T  # noqa: E402


FINITE_SCHEMES = (
    {"field": 0.1, "nodes": 34, "ratio_extent": 10.0, "xi_cutoff": 6.0},
    {"field": 0.05, "nodes": 42, "ratio_extent": 10.0, "xi_cutoff": 8.0},
    {"field": 0.025, "nodes": 46, "ratio_extent": 10.0, "xi_cutoff": 6.0},
)


def _finite_field_contraction(parameters: dict[str, float | int]) -> dict[str, object]:
    h = float(parameters["field"])
    cutoff = float(parameters["xi_cutoff"])
    count = int(np.ceil(cutoff / h))
    diagonal = 0.0
    cross = 0.0
    rows = []
    batch = 4 if h <= 0.025 else 8
    for lower in range(1, count + 1, batch):
        selected = np.arange(lower, min(count + 1, lower + batch))
        result = fixed_string_inner_weights_field(
            h,
            selected,
            partner_xi_cutoff=cutoff,
            partner_xi_buffer=6.0,
            rapidity_ratio_extent=float(parameters["ratio_extent"]),
            nodes_per_string=int(parameters["nodes"]),
            kernel_theta_step=0.5,
        )
        diagonal += sum(row["diagonal_weight"] for row in result["rows"])
        cross += sum(row["cross_weight"] for row in result["rows"])
        if lower == 1:
            rows.extend(result["rows"][: min(4, len(result["rows"]))])
        del result
        gc.collect()
    return {
        "inputs": parameters,
        "active_strings": count,
        "hD_diagonal": h * diagonal,
        "hD_cross": h * cross,
        "hD_full": h * (diagonal - cross),
        "naive_constant_remainder": (h * (diagonal - cross) - EXACT_D0_INFINITY_T)
        / h,
        "first_fixed_rows": rows,
    }


def derive() -> dict[str, object]:
    outer_rows = []
    for eta in (0.1, 0.05, 0.025):
        outer_rows.append(
            evaluate_adaptive_rapidity_fft(
                matching_scale=eta,
                xi_extent=8.0,
                xi_points=5,
                xi_geometric_panels=True,
                dressing_xi_extent=16.0,
                dressing_xi_points=120,
                rapidity_extent=24.0,
                rapidity_step=0.125,
                rapidity_nodes_per_string=36,
            )
        )
    finite_rows = [_finite_field_contraction(dict(row)) for row in FINITE_SCHEMES]
    fields = np.asarray([row["inputs"]["field"] for row in finite_rows])
    fixed_s1 = np.asarray(
        [row["first_fixed_rows"][0]["diagonal_weight"] for row in finite_rows]
    )
    fixed_s1_power = float(np.polyfit(np.log(fields), np.log(fixed_s1), 1)[0])
    scaled_cross = np.asarray([row["hD_cross"] for row in finite_rows])
    naive_remainder = np.asarray(
        [row["naive_constant_remainder"] for row in finite_rows]
    )
    return {
        "schema": 1,
        "method": "selected_rows_fixed_h_then_small_h_with_adaptive_outer_boundary",
        "source_equations": {
            "full_contraction": "supplement Eq. (12)-(14)",
            "diagonal_claim_under_test": (
                "supplement Eq. (13),(16): off-diagonal terms are stated to "
                "be arguable/expected to vanish, not derived there"
            ),
            "regulated_string_measure": "supplement Eq. (32)-(33)",
            "exact_leading_value": "supplement Eq. (22)-(23)",
        },
        "exact_D0": float(EXACT_D0_INFINITY_T),
        "outer_rows": outer_rows,
        "finite_field_rows": finite_rows,
        "derived": {
            "fixed_s1_field_power": fixed_s1_power,
            "scaled_cross_range": [float(np.min(scaled_cross)), float(np.max(scaled_cross))],
            "naive_constant_remainder_range": [
                float(np.min(naive_remainder)),
                float(np.max(naive_remainder)),
            ],
        },
        "gates": {
            "fixed_finite_string_weight_vanishes_quadratically": bool(
                1.7 < fixed_s1_power < 2.3
            ),
            "cross_is_subleading_Oh_in_tested_iterated_sequence": False,
            "diagonal_reduction_is_a_proved_identity": False,
            "supplement_eq16_eligible_for_D1_extraction": False,
            "uniform_u_outer_certificate_superseded": True,
            "u_over_xi_boundary_layer_resolved": True,
            "regulated_xi_boundary_counterterm_derived": False,
            "constant_D1_existence_certified": False,
            "physical_D1_certified": False,
        },
        "interpretation": (
            "The previous fixed-du outer scan did not resolve u=O(xi).  The "
            "adaptive calculation retains a leading cross contraction, while "
            "each fixed finite string vanishes as h^2.  The missing operation "
            "is therefore the regulated xi,u edge layer encoded by the "
            "quantum Euler-Maclaurin measure.  The primary source only argues "
            "that off-diagonal terms should vanish; it does not prove that "
            "reduction.  The exact full diagonal-minus-cross contraction is "
            "therefore authoritative.  Until its edge matching is derived, "
            "neither Eq. (16) nor a constant D1 is an eligible extraction route."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/iterated_full_diffusion_limit_audit.json",
    )
    args = parser.parse_args()
    result = derive()
    encoded = json.dumps(result, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
