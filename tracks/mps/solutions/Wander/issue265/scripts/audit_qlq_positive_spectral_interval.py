#!/usr/bin/env python3
"""Bound the QLQ resolvent from positive moments and its KPZ low-frequency tail.

The low-frequency density is fixed to c*omega^(1/3) on [0,omega_match].
Above that interval no pole count or smoothness ansatz is imposed: nonnegative
spectral weight on a convergence grid is constrained only by the microscopic
moments supplied by the QLQ Lanczos prefix.  Linear programming then gives
extremal Stieltjes resolvents at frequencies relevant to t=50..200.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.optimize import linprog


def _moments_from_squared_recurrents(squared: np.ndarray) -> np.ndarray:
    jacobi = np.zeros((squared.size + 1, squared.size + 1))
    for level, value in enumerate(np.sqrt(squared)):
        jacobi[level, level + 1] = value
        jacobi[level + 1, level] = value
    return np.asarray(
        [np.linalg.matrix_power(jacobi, 2 * order)[0, 0] for order in range(squared.size + 1)]
    )


def derive(
    recurrent_audit: Path,
    low_frequency_boundary: Path,
    *,
    omega_match: float,
    omega_maximum: float,
    spectral_nodes: int,
    laplace_frequencies: tuple[float, ...],
) -> dict[str, object]:
    if not 0.0 < omega_match < omega_maximum:
        raise ValueError("require 0<omega-match<omega-maximum")
    if spectral_nodes < 100:
        raise ValueError("at least 100 spectral nodes are required")
    audit = json.loads(recurrent_audit.read_text(encoding="utf-8"))
    boundary = json.loads(low_frequency_boundary.read_text(encoding="utf-8"))
    squared = np.asarray(
        [np.mean(row["scheme_envelope"]) for row in audit["squared_recurrent_extrapolations"]],
        dtype=float,
    )
    moments = _moments_from_squared_recurrents(squared)
    density_amplitude = float(
        boundary["qlq_low_frequency_boundary"]["spectral_density_amplitude"]
    )
    fixed_low_moments = np.asarray(
        [
            density_amplitude
            * omega_match ** (2 * order + 4.0 / 3.0)
            / (2 * order + 4.0 / 3.0)
            for order in range(moments.size)
        ]
    )
    residual_moments = moments - fixed_low_moments
    low_nodes = max(40, spectral_nodes // 3)
    omega = np.unique(
        np.concatenate(
            (
                np.geomspace(omega_match, 1.0, low_nodes),
                np.linspace(1.0, omega_maximum, spectral_nodes - low_nodes),
            )
        )
    )
    moment_matrix = np.asarray(
        [omega ** (2 * order) for order in range(moments.size)]
    )
    scaled_matrix = moment_matrix / moments[:, None]
    scaled_right = residual_moments / moments

    beta_zero_squared = float(boundary["microscopic_slow_current"]["beta_zero_squared"])
    current_norm = float(boundary["microscopic_slow_current"]["norm"])
    rows = []
    all_feasible = True
    for z in laplace_frequencies:
        objective = z / (z**2 + omega**2)
        minimum = linprog(
            objective,
            A_eq=scaled_matrix,
            b_eq=scaled_right,
            bounds=(0.0, None),
            method="highs",
        )
        maximum = linprog(
            -objective,
            A_eq=scaled_matrix,
            b_eq=scaled_right,
            bounds=(0.0, None),
            method="highs",
        )
        all_feasible = all_feasible and minimum.success and maximum.success
        if not minimum.success or not maximum.success:
            rows.append({"z": z, "feasible": False})
            continue
        fixed_low_resolvent = float(
            quad(
                lambda value: density_amplitude
                * value ** (1.0 / 3.0)
                * z
                / (z**2 + value**2),
                0.0,
                omega_match,
                epsabs=1.0e-12,
                epsrel=1.0e-12,
            )[0]
        )
        q_minimum = fixed_low_resolvent + float(minimum.fun)
        q_maximum = fixed_low_resolvent - float(maximum.fun)
        current_minimum = current_norm / (z + beta_zero_squared * q_maximum)
        current_maximum = current_norm / (z + beta_zero_squared * q_minimum)
        rows.append(
            {
                "z": z,
                "feasible": True,
                "fixed_low_resolvent": fixed_low_resolvent,
                "qlq_resolvent_interval": [q_minimum, q_maximum],
                "slow_current_resolvent_interval": [current_minimum, current_maximum],
                "minimum_extremizer_nonzero_nodes": int(np.count_nonzero(minimum.x > 1.0e-12)),
                "maximum_extremizer_nonzero_nodes": int(np.count_nonzero(maximum.x > 1.0e-12)),
            }
        )
    relative_widths = [
        (row["qlq_resolvent_interval"][1] - row["qlq_resolvent_interval"][0])
        / np.mean(row["qlq_resolvent_interval"])
        for row in rows
        if row.get("feasible")
    ]
    return {
        "schema_version": 1,
        "method": "positive_measure_linear_program_with_fixed_KPZ_low_tail",
        "inputs": {
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "omega_match": omega_match,
            "omega_maximum": omega_maximum,
            "spectral_nodes": int(omega.size),
            "laplace_frequencies": list(laplace_frequencies),
        },
        "microscopic_constraints": {
            "squared_qlq_recurrents": squared.tolist(),
            "even_moments": moments.tolist(),
            "fixed_low_tail_even_moments": fixed_low_moments.tolist(),
            "low_density_amplitude": density_amplitude,
        },
        "rows": rows,
        "gates": {
            "all_linear_programs_feasible": bool(all_feasible),
            "positive_spectral_measure_enforced": True,
            "pole_count_assumed": False,
            "finite_window_resolvent_unique": bool(
                relative_widths and max(relative_widths) < 0.05
            ),
        },
        "maximum_relative_qlq_interval_width": float(max(relative_widths, default=np.inf)),
        "conclusion": (
            f"The exact low-frequency amplitude and {squared.size} microscopic QLQ recurrents "
            "still permit distinct positive continua in the finite-window band.  "
            "Additional frequency-resolved microscopic/F-GHD information is required."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recurrent-audit",
        type=Path,
        default=Path("docs/xxx_thermodynamic_qlq_tail_audit_steps4.json"),
    )
    parser.add_argument(
        "--low-frequency-boundary",
        type=Path,
        default=Path("docs/qlq_kpz_low_frequency_boundary.json"),
    )
    parser.add_argument("--omega-match", type=float, default=0.05)
    parser.add_argument("--omega-maximum", type=float, default=20.0)
    parser.add_argument("--spectral-nodes", type=int, default=1000)
    parser.add_argument("--laplace-frequencies", nargs="+", type=float, default=[0.005, 0.01, 0.02, 0.05])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(
        args.recurrent_audit,
        args.low_frequency_boundary,
        omega_match=args.omega_match,
        omega_maximum=args.omega_maximum,
        spectral_nodes=args.spectral_nodes,
        laplace_frequencies=tuple(args.laplace_frequencies),
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
