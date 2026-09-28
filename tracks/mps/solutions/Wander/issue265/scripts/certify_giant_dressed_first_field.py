#!/usr/bin/env python3
"""Certify the outer giant-string dressed kernel through first field order."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.integrate import quad


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    giant_bare_scattering_fourier_kernel,
    giant_dressed_scattering_common_shift_derivative_fourier_kernel,
    giant_dressed_scattering_first_field_real_kernel,
    giant_dressed_scattering_first_field_fourier_quadrature,
    giant_dressed_scattering_fourier_kernel,
    giant_dressed_scattering_real_kernel,
)


def derive() -> dict:
    xi = 1.1
    zeta = 0.8
    residual_rows = []
    for wave_number in (0.0, 0.8, 2.0, 3.4):
        dressed = float(
            giant_dressed_scattering_fourier_kernel(xi, zeta, wave_number)
        )
        convolution = quad(
            lambda q: float(
                giant_bare_scattering_fourier_kernel(xi, q, wave_number)
                * giant_dressed_scattering_fourier_kernel(
                    q, zeta, wave_number
                )
                / np.sinh(q) ** 2
            ),
            0.0,
            30.0,
            epsabs=2.0e-10,
            limit=300,
        )[0]
        bare = float(
            giant_bare_scattering_fourier_kernel(xi, zeta, wave_number)
        )
        residual_rows.append(
            {
                "scaled_wave_number": wave_number,
                "dressed_kernel": dressed,
                "fredholm_residual": dressed - (bare - convolution),
            }
        )

    convergence_rows = []
    for cutoff, order in ((12.0, 320), (14.0, 640), (16.0, 720)):
        convergence_rows.append(
            {
                "xi_cutoff": cutoff,
                "quadrature_order": order,
                "first_dressed_kernel": (
                    giant_dressed_scattering_first_field_fourier_quadrature(
                        xi,
                        zeta,
                        2.0,
                        xi_cutoff=cutoff,
                        order=order,
                    )
                ),
            }
        )
    values = np.asarray(
        [row["first_dressed_kernel"] for row in convergence_rows]
    )
    relative_spread = float(np.ptp(values) / abs(np.mean(values)))
    common_shift_value = float(
        giant_dressed_scattering_common_shift_derivative_fourier_kernel(
            xi, zeta, 2.0
        )
    )
    common_shift_residual = float(np.max(np.abs(values - common_shift_value)))
    max_residual = float(
        max(abs(row["fredholm_residual"]) for row in residual_rows)
    )
    real_rows = []
    for rapidity_difference in (0.0, 0.4, 1.0):
        leading_sequence = [
            giant_dressed_scattering_real_kernel(
                1.3,
                0.7,
                rapidity_difference,
                wave_number_cutoff=cutoff,
                wave_number_order=order,
            )
            for cutoff, order in ((32.0, 240), (48.0, 320), (64.0, 400))
        ]
        first_sequence = [
            giant_dressed_scattering_first_field_real_kernel(
                1.3,
                0.7,
                rapidity_difference,
                wave_number_cutoff=cutoff,
                wave_number_order=order,
                xi_cutoff=14.0,
                xi_order=180,
            )
            for cutoff, order in ((24.0, 80), (36.0, 120), (48.0, 160))
        ]
        real_rows.append(
            {
                "scaled_rapidity_difference": rapidity_difference,
                "leading_sequences": leading_sequence,
                "first_sequences": first_sequence,
                "leading_last_relative_change": abs(
                    leading_sequence[-1] / leading_sequence[-2] - 1.0
                ),
                "first_last_relative_change": abs(
                    first_sequence[-1] / first_sequence[-2] - 1.0
                ),
            }
        )
    leading_real_change = max(
        row["leading_last_relative_change"] for row in real_rows
    )
    first_real_change = max(
        row["first_last_relative_change"] for row in real_rows
    )
    return {
        "schema": 1,
        "method": "natural_string_coordinate_even_field_expansion_and_exact_common_shift_derivative",
        "equations": {
            "natural_coordinate": "x=h*(s+1)",
            "leading_operator": (
                "[-d_xi^2+(abs(k)/2)^2+2*csch(xi)^2] X0 = 2 delta"
            ),
            "natural_expansion": "h*Tdr_h(x,y;h*K)=X0(x,y;K)+O(h^2)",
            "old_coordinate_first": "X1_old=(d_xi+d_zeta)X0",
        },
        "sample": {"xi": xi, "zeta": zeta},
        "leading_fredholm_residuals": residual_rows,
        "first_order_convergence": convergence_rows,
        "common_shift_derivative_value": common_shift_value,
        "maximum_common_shift_identity_residual": common_shift_residual,
        "real_rapidity_inverse_fourier_convergence": real_rows,
        "gates": {
            "leading_max_absolute_residual": max_residual,
            "leading_residual_below_2e-8": max_residual < 2.0e-8,
            "first_order_relative_spread": relative_spread,
            "first_order_spread_below_2e-3": relative_spread < 2.0e-3,
            "common_shift_identity_below_1e-12": common_shift_residual < 1.0e-12,
            "leading_real_kernel_max_relative_change": leading_real_change,
            "leading_real_kernel_change_below_1e-5": leading_real_change < 1.0e-5,
            "first_real_kernel_max_relative_change": first_real_change,
            "first_real_kernel_change_below_1e-4": first_real_change < 1.0e-4,
            "pointwise_inverse_fourier_complete": (
                leading_real_change < 1.0e-5 and first_real_change < 1.0e-4
            ),
            "outer_dressed_kernel_complete": (
                max_residual < 2.0e-8
                and relative_spread < 2.0e-3
                and common_shift_residual < 1.0e-12
                and leading_real_change < 1.0e-5
                and first_real_change < 1.0e-4
            ),
            "full_diagonal_integrand_complete": False,
            "fixed_string_inner_match_complete": False,
            "physical_D1_certified": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/giant_dressed_first_field_certificate.json",
    )
    args = parser.parse_args()
    result = derive()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
