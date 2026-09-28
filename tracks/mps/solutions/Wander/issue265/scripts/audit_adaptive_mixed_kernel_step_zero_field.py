#!/usr/bin/env python3
"""Correct one coarse-kernel small-field point before the zero-field fit.

The correction is calibrated only from matched fine/coarse certificates at
two larger fields.  If ``y(h)=h D(h)``, the observed discretization difference
is parametrized as ``y_coarse-y_fine=c h^2``.  The midpoint of the two measured
``c`` values corrects the small-field point and their half-spread is propagated
through every field extrapolation.  No Heisenberg trajectory or target
Burgers coefficient is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (
    EXACT_D0_INFINITY_T,
    finite_field_spectral_regulator_diffusion,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fine", type=Path, nargs="+", required=True)
    parser.add_argument("--matched-fine", type=Path, nargs=2, required=True)
    parser.add_argument("--matched-coarse", type=Path, nargs=2, required=True)
    parser.add_argument("--small-field-coarse", type=Path, required=True)
    parser.add_argument("--tail-coarse", type=Path, nargs=2)
    parser.add_argument("--minimum-capture", type=float, default=0.985)
    parser.add_argument("--maximum-leading-relative-error", type=float, default=0.01)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _load(path: Path, *, require_single: bool = True) -> tuple[dict, dict | None]:
    payload = json.loads(path.read_text())
    if payload.get("uses_target_a_or_D") or payload.get("uses_target_trajectory"):
        raise RuntimeError(f"target-contaminated certificate: {path}")
    if require_single and len(payload["rows"]) != 1:
        raise ValueError(f"expected one row in {path}")
    return payload, payload["rows"][0] if require_single else None


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _regulator_without_kernel(payload: dict) -> dict:
    regulator = dict(payload["regulators"])
    regulator.pop("kernel_theta_step", None)
    regulator.pop("fields", None)
    return regulator


def _fit(field: np.ndarray, value: np.ndarray, model: str) -> dict:
    if model.startswith("polynomial_degree_"):
        degree = int(model.rsplit("_", 1)[1])
        coefficients = np.polyfit(field, value, degree)
        predicted = np.polyval(coefficients, field)
        intercept = coefficients[-1]
        coefficient_payload = {"coefficients_descending": coefficients.tolist()}
    elif model == "constant_plus_h_log_h_plus_h":
        design = np.column_stack((np.ones_like(field), field * np.log(field), field))
        coefficients, *_ = np.linalg.lstsq(design, value, rcond=None)
        predicted = design @ coefficients
        intercept = coefficients[0]
        coefficient_payload = {"coefficients": coefficients.tolist()}
    else:
        raise ValueError(model)
    return {
        "model": model,
        **coefficient_payload,
        "zero_field_intercept": float(intercept),
        "rms_residual": float(np.sqrt(np.mean((predicted - value) ** 2))),
    }


def _fixed_leading_fit(field: np.ndarray, value: np.ndarray, degree: int) -> dict:
    design = np.column_stack([field**power for power in range(1, degree + 1)])
    coefficients, *_ = np.linalg.lstsq(
        design, value - EXACT_D0_INFINITY_T, rcond=None
    )
    predicted = EXACT_D0_INFINITY_T + design @ coefficients
    return {
        "model": f"exact_D0_plus_degree_{degree}",
        "D1": float(coefficients[0]),
        "higher_coefficients": coefficients[1:].tolist(),
        "rms_residual": float(np.sqrt(np.mean((predicted - value) ** 2))),
        "physical_D1_certified": False,
    }


def main() -> None:
    args = _arguments()
    matched = []
    reference_regulator = None
    for fine_path, coarse_path in zip(args.matched_fine, args.matched_coarse):
        fine_payload, fine = _load(fine_path)
        coarse_payload, coarse = _load(coarse_path)
        h = float(fine["field"])
        if not np.isclose(h, float(coarse["field"]), rtol=0.0, atol=1e-14):
            raise ValueError("matched certificates have different fields")
        fine_regulator = _regulator_without_kernel(fine_payload)
        coarse_regulator = _regulator_without_kernel(coarse_payload)
        if fine_regulator != coarse_regulator:
            raise ValueError("matched certificates differ beyond kernel step")
        if reference_regulator is None:
            reference_regulator = fine_regulator
        elif fine_regulator != reference_regulator:
            raise ValueError("matched pairs use different non-kernel regulators")
        difference = float(coarse["h_times_spin_diffusion"]) - float(
            fine["h_times_spin_diffusion"]
        )
        matched.append(
            {
                "field": h,
                "fine_source": str(fine_path),
                "coarse_source": str(coarse_path),
                "coarse_minus_fine": difference,
                "coarse_minus_fine_over_h2": difference / h**2,
            }
        )

    c_values = np.asarray([row["coarse_minus_fine_over_h2"] for row in matched])
    c_center = float(np.mean(c_values))
    c_half_spread = float(0.5 * (np.max(c_values) - np.min(c_values)))

    coarse_payload, coarse_row = _load(args.small_field_coarse)
    if _regulator_without_kernel(coarse_payload) != reference_regulator:
        raise ValueError("small-field certificate differs beyond field/kernel step")
    h_small = float(coarse_row["field"])
    raw_small = float(coarse_row["h_times_spin_diffusion"])
    corrected_small = raw_small - c_center * h_small**2
    corrected_uncertainty = c_half_spread * h_small**2

    rows = []
    source_paths = list(args.fine) + list(args.matched_fine) + list(args.matched_coarse)
    source_paths.append(args.small_field_coarse)
    seen_fields: set[float] = set()
    for path in args.fine:
        payload, _ = _load(path, require_single=False)
        if _regulator_without_kernel(payload) != reference_regulator:
            raise ValueError(f"fine certificate has a different regulator: {path}")
        for row in payload["rows"]:
            h = float(row["field"])
            if h in seen_fields:
                raise ValueError(f"duplicate fine field {h}")
            seen_fields.add(h)
            rows.append(
                {
                    "field": h,
                    "h_times_spin_diffusion": float(row["h_times_spin_diffusion"]),
                    "value_uncertainty": 0.0,
                    "susceptibility_captured_fraction": float(
                        row["susceptibility_captured_fraction"]
                    ),
                    "source": str(path),
                    "kernel_step_correction": False,
                }
            )
    if h_small in seen_fields:
        raise ValueError("small coarse field duplicates a fine field")
    rows.append(
        {
            "field": h_small,
            "h_times_spin_diffusion": corrected_small,
            "raw_h_times_spin_diffusion": raw_small,
            "value_uncertainty": corrected_uncertainty,
            "susceptibility_captured_fraction": float(
                coarse_row["susceptibility_captured_fraction"]
            ),
            "source": str(args.small_field_coarse),
            "kernel_step_correction": True,
        }
    )
    rows.sort(key=lambda row: row["field"], reverse=True)

    field = np.asarray([row["field"] for row in rows])
    center_value = np.asarray([row["h_times_spin_diffusion"] for row in rows])
    uncertainty = np.asarray([row["value_uncertainty"] for row in rows])
    models = [
        "polynomial_degree_1",
        "polynomial_degree_2",
        "polynomial_degree_3",
        "constant_plus_h_log_h_plus_h",
    ]
    fits = []
    all_intercepts = []
    for model in models:
        central = _fit(field, center_value, model)
        low = _fit(field, center_value - uncertainty, model)
        high = _fit(field, center_value + uncertainty, model)
        intercept_range = sorted(
            [
                low["zero_field_intercept"],
                central["zero_field_intercept"],
                high["zero_field_intercept"],
            ]
        )
        central["zero_field_intercept_with_kernel_scheme"] = {
            "minimum": float(intercept_range[0]),
            "maximum": float(intercept_range[-1]),
        }
        fits.append(central)
        all_intercepts.extend((intercept_range[0], intercept_range[-1]))

    # Positive control for the field-extrapolation machinery.  The closed
    # spectral regulator is not the physical finite-field diffusion, but it
    # has the same exact leading singularity and a known regular expansion.
    # Applying precisely the same field grid and fit family distinguishes a
    # bad extrapolator from a failure of the finite-cutoff full operator to
    # realize the Eq. (16) order of limits.
    spectral_value = np.asarray(
        [h * finite_field_spectral_regulator_diffusion(h) for h in field]
    )
    spectral_control_fits = [
        _fit(field, spectral_value, model) for model in models
    ]
    spectral_control_error = min(
        abs(fit["zero_field_intercept"] / EXACT_D0_INFINITY_T - 1.0)
        for fit in spectral_control_fits
    )

    intercept_min = float(np.min(all_intercepts))
    intercept_max = float(np.max(all_intercepts))
    capture_ok = all(
        row["susceptibility_captured_fraction"] >= args.minimum_capture for row in rows
    )
    maximum_relative_error = max(
        abs(intercept_min / EXACT_D0_INFINITY_T - 1.0),
        abs(intercept_max / EXACT_D0_INFINITY_T - 1.0),
    )
    leading_ok = bool(
        capture_ok and maximum_relative_error <= args.maximum_leading_relative_error
    )

    tail_diagnostic = None
    if args.tail_coarse:
        left_payload, left = _load(args.tail_coarse[0])
        right_payload, right = _load(args.tail_coarse[1])
        if not np.isclose(float(left["field"]), float(right["field"]), atol=1e-14):
            raise ValueError("tail comparison uses different fields")
        tail_diagnostic = {
            "sources": [str(path) for path in args.tail_coarse],
            "field": float(left["field"]),
            "raw_difference": float(right["h_times_spin_diffusion"])
            - float(left["h_times_spin_diffusion"]),
            "relative_difference": float(
                right["h_times_spin_diffusion"] / left["h_times_spin_diffusion"] - 1.0
            ),
            "interpretation": "joint scaled-rapidity-tail/node path diagnostic only",
        }
        source_paths.extend(args.tail_coarse)

    result = {
        "schema": 1,
        "method": "matched_h2_kernel_step_correction_then_zero_field_extrapolation",
        "audited_quantity": (
            "finite_cutoff_full_non_diagonal_physical_spin_block"
        ),
        "eq16_required_quantity_for_D1": (
            "diagonal_contraction_after_the_infinite_string_limit"
        ),
        "eq16_order_of_limits_eligible": False,
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "source_sha256": {str(path): _digest(path) for path in source_paths},
        "matched_kernel_step_calibration": {
            "model": "y_coarse(h)-y_fine(h)=c*h^2",
            "rows": matched,
            "c_center": c_center,
            "c_half_pair_spread": c_half_spread,
        },
        "corrected_small_field_point": {
            "field": h_small,
            "raw_value": raw_small,
            "corrected_value": corrected_small,
            "scheme_uncertainty": corrected_uncertainty,
        },
        "rows": rows,
        "fits": fits,
        "closed_spectral_regulator_positive_control": {
            "physical_finite_field_D1": False,
            "rows": [
                {"field": float(h), "h_times_D": float(value)}
                for h, value in zip(field, spectral_value)
            ],
            "fits": spectral_control_fits,
            "minimum_relative_intercept_error": float(
                spectral_control_error
            ),
            "interpretation": (
                "the same field grid and polynomial fits recover the known "
                "leading limit; the rejected full-operator intercept is an "
                "order-of-limits failure, not merely a generic fit failure"
            ),
        },
        "exact_D0": float(EXACT_D0_INFINITY_T),
        "intercept_envelope": {
            "minimum": intercept_min,
            "maximum": intercept_max,
            "maximum_relative_error": maximum_relative_error,
        },
        "forced_exact_leading_diagnostics": [
            _fixed_leading_fit(field, center_value, degree) for degree in (1, 2)
        ],
        "tail_diagnostic": tail_diagnostic,
        "gates": {
            "minimum_susceptibility_capture": args.minimum_capture,
            "susceptibility_capture_pass": capture_ok,
            "maximum_leading_relative_error": args.maximum_leading_relative_error,
            "leading_D0_gate_pass": leading_ok,
            "eq16_order_of_limits_pass": False,
            "eligible_for_physical_D1": False,
        },
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
