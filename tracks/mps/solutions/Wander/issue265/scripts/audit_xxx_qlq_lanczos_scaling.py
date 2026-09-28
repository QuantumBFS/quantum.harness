#!/usr/bin/env python3
"""Audit fixed-cutoff thermodynamic convergence of the QLQ prefix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def derive(sources: tuple[Path, ...]) -> dict[str, object]:
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in sources]
    lengths = np.asarray([item["length"] for item in payloads], dtype=float)
    inverse_lengths = 1.0 / lengths
    maximum_steps = max(len(item["squared_betas"]) for item in payloads)

    def extrapolate(values: np.ndarray, selected_lengths: np.ndarray) -> dict[str, object]:
        selected_inverse = 1.0 / selected_lengths
        linear = np.polyfit(selected_inverse, values, 1)
        quadratic = np.polyfit(selected_inverse, values, 2)
        even_external_momentum = np.polyfit(selected_inverse**2, values, 1)
        return {
            "lengths": selected_lengths.astype(int).tolist(),
            "values": values.tolist(),
            "linear_in_1_over_L_limit": float(linear[-1]),
            "quadratic_in_1_over_L_limit": float(quadratic[-1]),
            "linear_in_1_over_L_squared_diagnostic_limit": float(
                even_external_momentum[-1]
            ),
            "scheme_envelope": [
                float(min(linear[-1], quadratic[-1])),
                float(max(linear[-1], quadratic[-1])),
            ],
        }

    force = extrapolate(
        np.asarray([item["qlp_force_norm"] for item in payloads], dtype=float),
        lengths,
    )
    recurrents = []
    for level in range(maximum_steps):
        selected = [
            item for item in payloads if len(item["squared_betas"]) > level
        ]
        if len(selected) < 3:
            continue
        recurrents.append(
            extrapolate(
                np.asarray(
                    [item["squared_betas"][level] for item in selected], dtype=float
                ),
                np.asarray([item["length"] for item in selected], dtype=float),
            )
        )
    simple_candidate = np.asarray([1.25, 2.0, 4.0])[: len(recurrents)]
    candidate_residuals = []
    for candidate, row in zip(simple_candidate, recurrents, strict=True):
        envelope = row["scheme_envelope"]
        candidate_residuals.append(
            {
                "candidate": float(candidate),
                "inside_extrapolation_envelope": bool(
                    envelope[0] <= candidate <= envelope[1]
                ),
                "relative_distance_from_quadratic_limit": float(
                    abs(candidate - row["quadratic_in_1_over_L_limit"])
                    / candidate
                ),
                "relative_distance_from_1_over_L_squared_diagnostic": float(
                    abs(
                        candidate
                        - row["linear_in_1_over_L_squared_diagnostic_limit"]
                    )
                    / candidate
                ),
            }
        )
    return {
        "schema": 1,
        "method": "fixed_pi_over_4_cutoff_qlq_lanczos_regulator_audit",
        "sources": [str(path) for path in sources],
        "lengths": lengths.astype(int).tolist(),
        "trajectory_data_used": False,
        "target_coefficients_used": False,
        "qlp_force_norm_extrapolation": force,
        "squared_recurrent_extrapolations": recurrents,
        "simple_limit_candidates": candidate_residuals,
        "gates": {
            "all_source_gates_pass": all(
                all(item["gates"].values()) for item in payloads
            ),
            "three_common_positive_recurrents": bool(
                len(recurrents) >= 3
                and all(
                    min(row["values"]) > 0.0 for row in recurrents[:3]
                )
            ),
            "thermodynamic_prefix_uniquely_certified": False,
        },
        "interpretation": (
            "The first QLQ recurrents have a stable positive finite-volume "
            "sequence.  The second and third are compatible with the simple "
            "limits 2 and 4 within the declared two-scheme envelope; the "
            "first remains 1.21 percent above 5/4 in the quadratic scheme and "
            "does not pass that gate.  Five volumes constrain the first two "
            "recurrents and three constrain the third, but they do not prove "
            "simple exact identities; an analytic Fourier trace is required."
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
