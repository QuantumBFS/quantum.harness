#!/usr/bin/env python3
"""Audit the zero-field limit of adaptive full-operator certificates.

The inputs are trajectory-free finite-field JSON files produced by
``derive_regulated_infinite_mode_fghd.py``.  Polynomial and ``h log h`` fits
are all reported; no scheme is selected using the target Burgers coefficients.
The leading gate passes only if the exact giant-string value ``5*pi/27`` lies
inside the regulator-plus-scheme envelope.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import EXACT_D0_INFINITY_T


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificates", type=Path, nargs="+")
    parser.add_argument("--minimum-capture", type=float, default=0.985)
    parser.add_argument("--maximum-leading-relative-error", type=float, default=0.01)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _fit(field: np.ndarray, value: np.ndarray, degree: int) -> dict:
    coefficients = np.polyfit(field, value, degree)
    predicted = np.polyval(coefficients, field)
    return {
        "model": f"polynomial_degree_{degree}",
        "coefficients_descending": coefficients.tolist(),
        "zero_field_intercept": float(coefficients[-1]),
        "rms_residual": float(np.sqrt(np.mean((predicted - value) ** 2))),
    }


def main() -> None:
    args = _arguments()
    rows = []
    for path in args.certificates:
        payload = json.loads(path.read_text())
        if payload.get("uses_target_a_or_D") or payload.get("uses_target_trajectory"):
            raise RuntimeError(f"target-contaminated certificate: {path}")
        for row in payload["rows"]:
            rows.append(
                {
                    "source": str(path),
                    "field": float(row["field"]),
                    "h_times_spin_diffusion": float(row["h_times_spin_diffusion"]),
                    "susceptibility_captured_fraction": float(
                        row["susceptibility_captured_fraction"]
                    ),
                    "h_times_spin_complement_coupling": float(
                        row["field"]
                        * row["diffusion_complement"]["spin_to_complement_norm"]
                    ),
                }
            )
    rows.sort(key=lambda row: row["field"], reverse=True)
    if len(rows) < 4:
        raise ValueError("need at least four finite-field points")
    field = np.asarray([row["field"] for row in rows])
    value = np.asarray([row["h_times_spin_diffusion"] for row in rows])
    fits = [_fit(field, value, degree) for degree in (1, 2, 3)]
    design = np.column_stack((np.ones_like(field), field * np.log(field), field))
    hlogh, *_ = np.linalg.lstsq(design, value, rcond=None)
    predicted = design @ hlogh
    fits.append(
        {
            "model": "constant_plus_h_log_h_plus_h",
            "coefficients": hlogh.tolist(),
            "zero_field_intercept": float(hlogh[0]),
            "rms_residual": float(np.sqrt(np.mean((predicted - value) ** 2))),
        }
    )
    intercepts = np.asarray([fit["zero_field_intercept"] for fit in fits])
    center = float(0.5 * (np.min(intercepts) + np.max(intercepts)))
    half_spread = float(0.5 * (np.max(intercepts) - np.min(intercepts)))
    relative_error = abs(center / EXACT_D0_INFINITY_T - 1.0)
    capture_ok = all(
        row["susceptibility_captured_fraction"] >= args.minimum_capture
        for row in rows
    )
    leading_ok = bool(
        capture_ok
        and relative_error + half_spread / EXACT_D0_INFINITY_T
        <= args.maximum_leading_relative_error
    )
    result = {
        "schema": 1,
        "method": "adaptive_full_operator_zero_field_extrapolation",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "rows": rows,
        "fits": fits,
        "exact_D0": float(EXACT_D0_INFINITY_T),
        "intercept_envelope": {
            "center": center,
            "half_scheme_spread": half_spread,
            "relative_center_error": relative_error,
        },
        "gates": {
            "minimum_susceptibility_capture": args.minimum_capture,
            "susceptibility_capture_pass": capture_ok,
            "maximum_leading_relative_error": args.maximum_leading_relative_error,
            "leading_D0_gate_pass": leading_ok,
            "eligible_for_subleading_finite_window_kernel": leading_ok,
        },
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
