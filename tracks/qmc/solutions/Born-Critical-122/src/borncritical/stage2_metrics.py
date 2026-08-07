"""Clean critical-Ising finite-size evidence and stability visualization."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np

from .casimir_fit import CasimirFit, fit_casimir
from .clean_ising import (
    CRITICAL_PHI_INFINITY,
    critical_log_dominant_eigenvalue,
    critical_phi,
    explicit_dominant_eigenpair,
)
from .conventions import CLEAN_ISING_C

PRODUCTION_SIZES = np.array(
    [4, 6, 8, 10, 12, 16, 20, 24, 32, 48, 64], dtype=np.float64
)
EXPLICIT_SIZES = (2, 4, 6, 8, 10)


def _fit_record(fit: CasimirFit, minimum_size: int) -> dict[str, Any]:
    residual_scale = float(np.sqrt(fit.reduced_chi_squared))
    return {
        "model": fit.model,
        "minimum_size": minimum_size,
        "sizes": fit.sizes.astype(int).tolist(),
        "coefficients": fit.coefficients.tolist(),
        "central_charge": fit.central_charge,
        "ols_truncation_standard_error": (
            fit.central_charge_error * residual_scale
        ),
        "maximum_absolute_residual": float(np.max(np.abs(fit.residuals))),
        "design_condition_number": fit.design_condition_number,
        "well_conditioned": fit.well_conditioned,
    }


def collect_stage2_evidence() -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Run explicit checks and all predeclared clean-Ising fit windows."""

    explicit_rows: list[dict[str, Any]] = []
    for circumference in EXPLICIT_SIZES:
        explicit = explicit_dominant_eigenpair(circumference)
        analytic = critical_log_dominant_eigenvalue(circumference)
        explicit_rows.append(
            {
                "L": circumference,
                "explicit_log_lambda0": explicit.log_eigenvalue,
                "analytic_log_lambda0": analytic,
                "absolute_error": abs(explicit.log_eigenvalue - analytic),
                "relative_residual": explicit.relative_residual,
                "iterations": explicit.iterations,
            }
        )

    size_rows = [
        {
            "L": int(size),
            "inverse_L_squared": float(size**-2),
            "log_lambda0": critical_log_dominant_eigenvalue(int(size)),
            "phi_L": critical_phi(int(size)),
        }
        for size in PRODUCTION_SIZES
    ]
    values = np.array([row["phi_L"] for row in size_rows], dtype=np.float64)

    fit_records: list[dict[str, Any]] = []
    fits: dict[tuple[str, int], CasimirFit] = {}
    for model, minimum_sizes in (
        ("M0", (12, 16, 20, 24)),
        ("M1", (4, 8, 12)),
    ):
        for minimum_size in minimum_sizes:
            selected = PRODUCTION_SIZES >= minimum_size
            fit = fit_casimir(
                PRODUCTION_SIZES[selected],
                values[selected],
                model=model,
                quantity="phi",
            )
            fits[(model, minimum_size)] = fit
            fit_records.append(_fit_record(fit, minimum_size))

    # The L_min scan identifies the asymptotic plateaus without selecting on
    # the target value: M0 starts at L=16, while the additional L^-4 term
    # permits M1 to start at L=12.  Dropping the two smallest M0 sizes leaves
    # L_min=24.  Exact analytic data have no sampling standard error, so the
    # declared 0.5% acceptance band is used as the systematic tolerance.
    main = fits[("M0", 16)]
    drop_two = fits[("M0", 24)]
    correction = fits[("M1", 12)]
    main_error = abs(main.central_charge - CLEAN_ISING_C) / CLEAN_ISING_C
    drop_shift = abs(drop_two.central_charge - main.central_charge)
    systematic_tolerance = 0.005 * CLEAN_ISING_C
    main_ols_error = (
        main.central_charge_error * np.sqrt(main.reduced_chi_squared)
    )
    m0_m1_difference = (
        abs(main.central_charge - correction.central_charge) / CLEAN_ISING_C
    )
    gates = {
        "explicit_transfer_matches_dispersion": bool(
            max(row["absolute_error"] for row in explicit_rows) < 2.0e-11
        ),
        "main_relative_error_below_0p5_percent": bool(main_error < 0.005),
        "drop_two_shift_within_systematic_tolerance": (
            bool(drop_shift <= systematic_tolerance)
        ),
        "m0_m1_difference_below_0p5_percent": bool(
            m0_m1_difference < 0.005
        ),
        "casimir_coefficient_has_positive_sign": bool(
            main.coefficients[1] > 0.0
        ),
        "all_fit_windows_well_conditioned": all(
            record["well_conditioned"] for record in fit_records
        ),
    }
    metrics: dict[str, Any] = {
        "critical_phi_infinity_exact": CRITICAL_PHI_INFINITY,
        "target_central_charge": CLEAN_ISING_C,
        "explicit_max_log_lambda0_absolute_error": max(
            row["absolute_error"] for row in explicit_rows
        ),
        "explicit_max_relative_residual": max(
            row["relative_residual"] for row in explicit_rows
        ),
        "main_model": "M0",
        "main_minimum_size": 16,
        "main_central_charge": main.central_charge,
        "main_relative_error": main_error,
        "main_phi_infinity": float(main.coefficients[0]),
        "main_phi_infinity_absolute_error": abs(
            float(main.coefficients[0]) - CRITICAL_PHI_INFINITY
        ),
        "main_ols_truncation_standard_error": float(main_ols_error),
        "systematic_absolute_tolerance": systematic_tolerance,
        "drop_two_minimum_size": 24,
        "drop_two_central_charge": drop_two.central_charge,
        "drop_two_absolute_shift": drop_shift,
        "m1_correction_minimum_size": 12,
        "m1_correction_central_charge": correction.central_charge,
        "m0_m1_relative_difference": m0_m1_difference,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
    }
    return metrics, size_rows, explicit_rows, fit_records


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    destination = Path(path)
    if not rows:
        raise ValueError("cannot write empty CSV")
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_stage2_svg(
    path: str | Path,
    size_rows: list[dict[str, Any]],
    fit_records: list[dict[str, Any]],
) -> None:
    """Write data/fit and L_min-stability panels without plotting dependencies."""

    width, height = 1120, 500
    margin_y, panel_width = 55, 455
    left_a, left_b = 85, 640
    plot_height = 350
    bottom = margin_y + plot_height
    x_values = np.array(
        [row["inverse_L_squared"] for row in size_rows], dtype=np.float64
    )
    y_values = np.array([row["phi_L"] for row in size_rows], dtype=np.float64)
    y_padding = 0.08 * float(np.ptp(y_values))
    y_min = float(np.min(y_values) - y_padding)
    y_max = float(np.max(y_values) + y_padding)

    def xa(value: float) -> float:
        return left_a + value / float(np.max(x_values)) * panel_width

    def ya(value: float) -> float:
        return margin_y + (y_max - value) / (y_max - y_min) * plot_height

    stability_x = [record["minimum_size"] for record in fit_records]
    stability_y = [record["central_charge"] for record in fit_records]
    sx_min, sx_max = min(stability_x), max(stability_x)
    sy_min = min(stability_y + [CLEAN_ISING_C])
    sy_max = max(stability_y + [CLEAN_ISING_C])
    sy_padding = max(2.0e-5, 0.15 * (sy_max - sy_min))
    sy_min -= sy_padding
    sy_max += sy_padding

    def xb(value: float) -> float:
        return left_b + (value - sx_min) / (sx_max - sx_min) * panel_width

    def yb(value: float) -> float:
        return margin_y + (sy_max - value) / (sy_max - sy_min) * plot_height

    main = next(
        record
        for record in fit_records
        if record["model"] == "M0" and record["minimum_size"] == 16
    )
    a0, a2 = main["coefficients"][:2]
    elements = [
        f'<rect width="{width}" height="{height}" fill="white"/>',
        (
            f'<text x="{width / 2}" y="28" text-anchor="middle" '
            'font-family="sans-serif" font-size="20">'
            "Stage 2: clean critical Ising Casimir fit</text>"
        ),
    ]
    for left in (left_a, left_b):
        elements.extend(
            [
                (
                    f'<line x1="{left}" y1="{bottom}" '
                    f'x2="{left + panel_width}" y2="{bottom}" stroke="#111827"/>'
                ),
                (
                    f'<line x1="{left}" y1="{margin_y}" '
                    f'x2="{left}" y2="{bottom}" stroke="#111827"/>'
                ),
            ]
        )

    curve = []
    for index in range(101):
        x = float(np.max(x_values)) * index / 100
        curve.append(f"{xa(x):.2f},{ya(a0 + a2 * x):.2f}")
    elements.append(
        f'<polyline points="{" ".join(curve)}" fill="none" '
        'stroke="#dc2626" stroke-width="2"/>'
    )
    for row in size_rows:
        elements.append(
            f'<circle cx="{xa(row["inverse_L_squared"]):.2f}" '
            f'cy="{ya(row["phi_L"]):.2f}" r="4" fill="#2563eb"/>'
        )
    target_y = yb(CLEAN_ISING_C)
    elements.append(
        f'<line x1="{left_b}" y1="{target_y:.2f}" '
        f'x2="{left_b + panel_width}" y2="{target_y:.2f}" '
        'stroke="#111827" stroke-dasharray="6 5"/>'
    )
    colors = {"M0": "#dc2626", "M1": "#059669"}
    for model in ("M0", "M1"):
        records = [record for record in fit_records if record["model"] == model]
        points = " ".join(
            f'{xb(record["minimum_size"]):.2f},'
            f'{yb(record["central_charge"]):.2f}'
            for record in records
        )
        elements.append(
            f'<polyline points="{points}" fill="none" '
            f'stroke="{colors[model]}" stroke-width="2"/>'
        )
        for record in records:
            elements.append(
                f'<circle cx="{xb(record["minimum_size"]):.2f}" '
                f'cy="{yb(record["central_charge"]):.2f}" r="4" '
                f'fill="{colors[model]}"/>'
            )

    elements.extend(
        [
            (
                f'<text x="{left_a + panel_width / 2}" y="475" '
                'text-anchor="middle" font-family="sans-serif" font-size="15">'
                "1/L²</text>"
            ),
            (
                f'<text x="{left_b + panel_width / 2}" y="475" '
                'text-anchor="middle" font-family="sans-serif" font-size="15">'
                "minimum fitted size L_min</text>"
            ),
            (
                f'<text x="{left_a + 12}" y="{margin_y + 23}" '
                'font-family="sans-serif" font-size="14" fill="#dc2626">'
                f'M0 L_min=16: c={main["central_charge"]:.8f}</text>'
            ),
            (
                f'<text x="{left_b + 12}" y="{margin_y + 23}" '
                'font-family="sans-serif" font-size="14">'
                '<tspan fill="#dc2626">M0</tspan>'
                '<tspan dx="18" fill="#059669">M1</tspan>'
                '<tspan dx="18" fill="#111827">exact c=0.5</tspan></text>'
            ),
            (
                f'<text x="22" y="{margin_y + plot_height / 2}" '
                'transform="rotate(-90 22 '
                f'{margin_y + plot_height / 2})" text-anchor="middle" '
                'font-family="sans-serif" font-size="15">phi_L</text>'
            ),
            (
                f'<text x="585" y="{margin_y + plot_height / 2}" '
                'transform="rotate(-90 585 '
                f'{margin_y + plot_height / 2})" text-anchor="middle" '
                'font-family="sans-serif" font-size="15">fitted c</text>'
            ),
        ]
    )
    Path(path).write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        + "\n".join(elements)
        + "\n</svg>\n",
        encoding="utf-8",
    )
