#!/usr/bin/env python3
"""Audit the full-mode giant-string Mori scaling function without target data.

The input is produced by ``derive_regulated_infinite_mode_fghd.py`` with
``--scaled-wave-numbers`` and ``--scaled-laplace-frequencies``.  The audit
compares the zero-field regulator sequence at fixed

    q = k / h^2,  p = z / h^3,  tau = t h^3,

and measures how accurately the orthogonal-sector memory can be represented
by a constant, one positive pole, a contact plus one pole, or two positive
poles.  These are diagnostics, not model-selection inputs; no wall trajectory
or target Burgers coefficient is read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares


def _fit_models(p: np.ndarray, y: np.ndarray) -> dict[str, object]:
    def report(predicted: np.ndarray, parameters: dict[str, object]):
        residual = predicted - y
        return {
            "parameters": parameters,
            "predicted": predicted.tolist(),
            "relative_l2_residual": float(
                np.linalg.norm(residual) / np.linalg.norm(y)
            ),
            "maximum_pointwise_relative_residual": float(
                np.max(np.abs(residual) / np.maximum(np.abs(y), 1.0e-300))
            ),
        }

    constant = np.full_like(y, np.mean(y))

    def positive_fit(function, initial):
        result = least_squares(
            lambda x: function(np.exp(x)) - y,
            np.log(np.asarray(initial, dtype=float)),
            max_nfev=100000,
            xtol=1.0e-13,
            ftol=1.0e-13,
            gtol=1.0e-13,
        )
        positive = np.exp(result.x)
        return positive, function(positive), result

    one, one_pred, one_result = positive_fit(
        lambda x: x[0] / (p + x[1]), [2.0, 8.0]
    )
    contact, contact_pred, contact_result = positive_fit(
        lambda x: x[0] + x[1] / (p + x[2]), [0.02, 1.5, 6.0]
    )
    two, two_pred, two_result = positive_fit(
        lambda x: x[0] / (p + x[1]) + x[2] / (p + x[3]),
        [0.5, 3.0, 2.0, 18.0],
    )
    return {
        "constant": report(constant, {"value": float(np.mean(y))}),
        "one_positive_pole": report(
            one_pred,
            {
                "weight": float(one[0]),
                "rate": float(one[1]),
                "optimizer_success": bool(one_result.success),
            },
        ),
        "positive_contact_plus_one_positive_pole": report(
            contact_pred,
            {
                "contact": float(contact[0]),
                "weight": float(contact[1]),
                "rate": float(contact[2]),
                "optimizer_success": bool(contact_result.success),
            },
        ),
        "two_positive_poles": report(
            two_pred,
            {
                "weights": [float(two[0]), float(two[2])],
                "rates": [float(two[1]), float(two[3])],
                "optimizer_success": bool(two_result.success),
            },
        ),
    }


def audit(payload: dict[str, object]) -> dict[str, object]:
    rows = payload["rows"]
    if len(rows) < 2:
        raise ValueError("at least two finite-field regulators are required")
    per_field = []
    reference_p = None
    scaled_memories = []
    scaled_orthogonal = []
    structures = []
    for row in rows:
        h = float(row["field"])
        coordinates = row["hydrodynamic_coordinates"]
        waves = coordinates["wave_numbers"]
        if len(waves) != 1:
            raise ValueError("this audit currently requires exactly one scaled q")
        wave_key = str(waves[0])
        values = row["exact_full_complement_mori_resolvent"][wave_key]
        triples = sorted(
            (
                float(z) / h**3,
                h * float(value["continuity_memory"]["real"]),
                h * float(value["orthogonal_memory_correction"]["real"]),
            )
            for z, value in values.items()
        )
        p = np.asarray([item[0] for item in triples])
        total = np.asarray([item[1] for item in triples])
        orthogonal = np.asarray([item[2] for item in triples])
        if reference_p is None:
            reference_p = p
        elif not np.allclose(p, reference_p, rtol=1.0e-10, atol=1.0e-12):
            raise ValueError("scaled p grids do not agree across fields")
        structure = np.asarray(
            row["propagation"][wave_key][
                "structure_factor_over_susceptibility"
            ]["real"]
        )
        scaled_memories.append(total)
        scaled_orthogonal.append(orthogonal)
        structures.append(structure)
        per_field.append(
            {
                "field": h,
                "mode_count": int(row["mode_count"]),
                "susceptibility_captured_fraction": float(
                    row["susceptibility_captured_fraction"]
                ),
                "scaled_total_memory_hK": total.tolist(),
                "scaled_orthogonal_memory_hK_perp": orthogonal.tolist(),
                "scaled_structure_factor": structure.tolist(),
                "maximum_gmres_residual": float(
                    max(
                        value.get("linear_solve_relative_residual", 0.0)
                        for value in values.values()
                    )
                ),
            }
        )

    orthogonal_array = np.asarray(scaled_orthogonal)
    total_array = np.asarray(scaled_memories)
    structure_array = np.asarray(structures)
    last_step = lambda array: np.abs(array[-1] - array[-2]) / np.maximum(
        np.abs(array[-1]), 1.0e-300
    )
    fit = _fit_models(reference_p, orthogonal_array[-1])
    return {
        "schema": 1,
        "method": "target_free_joint_scaled_full_mode_mori_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "scaled_variables": {
            "q_equals_k_over_h2": float(
                rows[-1]["hydrodynamic_coordinates"][
                    "scaled_wave_numbers_k_over_h2"
                ][0]
            ),
            "p_equals_z_over_h3": reference_p.tolist(),
            "tau_equals_t_h3": rows[-1]["hydrodynamic_coordinates"][
                "scaled_times_t_h3"
            ],
        },
        "per_field": per_field,
        "last_field_step_convergence": {
            "maximum_relative_total_memory_change": float(
                np.max(last_step(total_array))
            ),
            "maximum_relative_orthogonal_memory_change": float(
                np.max(last_step(orthogonal_array))
            ),
            "maximum_absolute_structure_factor_change": float(
                np.max(np.abs(structure_array[-1] - structure_array[-2]))
            ),
        },
        "smallest_field_orthogonal_spectrum_fits": fit,
        "interpretation": {
            "constant_markov_kernel_rejected_on_this_p_grid": bool(
                fit["constant"]["relative_l2_residual"] > 0.1
            ),
            "one_pole_is_an_approximation_not_an_identity": True,
            "finite_pole_closure_used_in_propagation": False,
            "nonlinear_vertices_included": False,
            "zero_field_infinite_mode_limit_claimed": False,
            "reason": (
                "the linear full-mode scaling function is converging, but a physical "
                "F1 requires nonlinear vertices plus microscopic Mori/UV matching"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(json.loads(args.input.read_text(encoding="utf-8")))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
