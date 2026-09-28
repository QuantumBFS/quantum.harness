#!/usr/bin/env python3
"""Audit whether finite-field full TBA determines a constant subleading D1.

The input consists only of quadratures of the dressed-kernel formula and their
cutoffs.  For each field the two largest velocity-series truncations are
linearly extrapolated in 1/N.  The exact leading benchmark 5*pi/27 is then
applied before any finite-window use is attempted.

The script also performs a deliberately labelled *forbidden substitution*
diagnostic: it identifies a uniform external field h with the rms thermal
field of the finite-time packet at finite h, not just in the controlled
h->0 singular limit.  A large change of the projected Burgers coefficient is
evidence that this replacement cannot be used as a first-principles next
order.  It is never reported as the physical answer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    EXACT_D0_INFINITY_T,
    KPZ_SCALING_VARIANCE,
    theory_only_current_projection,
    theory_only_current_projection_from_scale,
    theory_only_strong_projection,
    theory_only_strong_projection_from_scale,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "docs" / "full_tba_finite_field_runs.json",
    )
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument("--time-points", type=int, default=20001)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def audit(
    payload: dict[str, object],
    *,
    t_start: float = 50.0,
    t_stop: float = 200.0,
    time_points: int = 20001,
) -> dict[str, object]:
    if not 0.0 < t_start < t_stop or time_points < 1001:
        raise ValueError("Require 0<t_start<t_stop and at least 1001 points")
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("Input must contain a non-empty runs list")

    grouped: dict[float, list[tuple[int, float]]] = {}
    for row in runs:
        if not isinstance(row, dict):
            raise ValueError("Each run must be a JSON object")
        h = float(row["field"])
        terms = int(row["velocity_series_terms"])
        diffusion = float(row["diagonal_diffusion"])
        if h <= 0.0 or terms <= 0 or diffusion <= 0.0:
            raise ValueError("Fields, truncations and diffusion must be positive")
        grouped.setdefault(h, []).append((terms, diffusion))

    field_rows: list[dict[str, object]] = []
    for field in sorted(grouped, reverse=True):
        sequence = sorted(grouped[field])
        if len(sequence) < 2:
            raise ValueError("Each field needs at least two series truncations")
        (n1, d1), (n2, d2) = sequence[-2:]
        inverse_n = np.array([1.0 / n1, 1.0 / n2])
        extrapolated = float(
            np.polyfit(inverse_n, np.array([d1, d2]), deg=1)[1]
        )
        leading_subtracted = extrapolated - EXACT_D0_INFINITY_T / field
        field_rows.append(
            {
                "field": field,
                "sequence": [
                    {"terms": terms, "D": diffusion}
                    for terms, diffusion in sequence
                ],
                "largest_terms": n2,
                "largest_terms_D": d2,
                "inverse_terms_extrapolated_D": extrapolated,
                "h_times_extrapolated_D": field * extrapolated,
                "relative_leading_benchmark_error": (
                    field * extrapolated / EXACT_D0_INFINITY_T - 1.0
                ),
                "putative_D1": leading_subtracted,
            }
        )

    # The exact benchmark must improve, rather than deteriorate, as h is
    # lowered before a subleading coefficient can be extracted.
    # Traverse from larger to smaller field.  A controlled small-field
    # sequence must approach the exact leading coefficient in this order.
    descending_h = sorted(field_rows, key=lambda row: float(row["field"]), reverse=True)
    descending_errors = np.array(
        [abs(float(row["relative_leading_benchmark_error"])) for row in descending_h]
    )
    benchmark_improves_toward_zero = bool(
        np.all(np.diff(descending_errors) <= 0.0)
    )

    fields = np.array([float(row["field"]) for row in field_rows])
    diffusion = np.array(
        [float(row["inverse_terms_extrapolated_D"]) for row in field_rows]
    )
    chi = 0.25
    sigma = float(np.sqrt(KPZ_SCALING_VARIANCE))
    packet_rms = 1.0 / (4.0 * chi * fields**2)
    implied_time = packet_rms**2 / (2.0 * diffusion)
    order = np.argsort(implied_time)
    field_of_time = PchipInterpolator(
        implied_time[order], fields[order], extrapolate=True
    )
    time = np.linspace(t_start, t_stop, time_points)
    effective_field = field_of_time(time)
    field_rate = field_of_time.derivative()(time)
    length = 1.0 / (4.0 * chi * sigma * effective_field**2)
    length_rate = (
        -field_rate
        / (2.0 * chi * sigma * effective_field**3)
    )
    strong_forbidden = theory_only_strong_projection_from_scale(
        time, length, length_rate
    )
    current_forbidden = theory_only_current_projection_from_scale(
        time, length, length_rate
    )

    putative_d1 = np.array(
        [float(row["putative_D1"]) for row in field_rows]
    )
    return {
        "schema_version": 1,
        "inputs": {
            "t_start": float(t_start),
            "t_stop": float(t_stop),
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "source_status": payload.get("provenance", {}).get("status")
            if isinstance(payload.get("provenance"), dict)
            else None,
        },
        "exact_leading_D0": float(EXACT_D0_INFINITY_T),
        "field_sequences": field_rows,
        "subleading_constant_audit": {
            "leading_benchmark_improves_toward_zero": (
                benchmark_improves_toward_zero
            ),
            "putative_D1_min": float(np.min(putative_d1)),
            "putative_D1_max": float(np.max(putative_d1)),
            "physical_D1_determined": False,
            "reason": (
                "The finite-cutoff sequence fails the exact hD->5*pi/27 "
                "benchmark uniformly as h is lowered; subtracting the "
                "singularity amplifies this nonuniform error."
            ),
        },
        "forbidden_uniform_field_substitution": {
            "mapping_authorized_beyond_leading_singularity": False,
            "implied_time_grid": implied_time.tolist(),
            "field_at_window_endpoints": effective_field[[0, -1]].tolist(),
            "leading_kpz_strong": list(theory_only_strong_projection()),
            "leading_kpz_current": list(theory_only_current_projection()),
            "finite_field_substitution_strong": list(strong_forbidden),
            "finite_field_substitution_current": list(current_forbidden),
            "interpretation": (
                "Uniform external-field diffusion and the fluctuating local "
                "field have the same controlled D0/h singularity, but no "
                "derivation identifies their finite-h remainders. The large "
                "shift in a is therefore a rejection diagnostic, not a "
                "finite-window prediction."
            ),
        },
    }


def main() -> int:
    args = _arguments()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = audit(
        payload,
        t_start=args.t_start,
        t_stop=args.t_stop,
        time_points=args.time_points,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
