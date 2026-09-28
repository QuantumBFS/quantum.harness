#!/usr/bin/env python3
"""Audit what target-free wall inversions actually identify.

This script deliberately does not accept reference values for ``a`` or ``D``.
It combines one or more outputs of ``invert_finite_time_mori_from_walls.py``
with the frozen convergence gate and separates three different objects:

* the exact zero-field quadratic Kubo vertex of the physical spin current;
* the orientation-conditioned finite-window current vertex;
* the linear finite-frequency Mori kernel and a declared scalar projection of it.

Numerical agreement between the last two projections is not promoted to a
unique, asymptotic constant-coefficient scalar PDE.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.heisenberg_burgers_bridge import (  # noqa: E402
    mori_lanczos_stieltjes_bounds,
    physical_quadratic_current_kubo_vertex,
    xxx_mori_even_moments,
    xxx_mori_long_wave_lanczos,
)


def audit(
    inversions: dict[str, dict[str, Any]],
    validation: dict[str, Any],
    *,
    declared_window: tuple[float, float] = (50.0, 200.0),
) -> dict[str, Any]:
    """Return a machine-readable identifiability verdict.

    Resolution labels are supplied by the caller and are not inferred from
    filenames.  Three accepted, full-window resolutions are required to call
    the finite-time kernel frozen, but even that would not turn it into a
    unique constant diffusivity without choosing a Markov/projector map.
    """

    if not inversions:
        raise ValueError("at least one inversion record is required")
    start, stop = map(float, declared_window)
    if not 0.0 < start < stop:
        raise ValueError("declared window must be positive and ordered")

    records: list[dict[str, Any]] = []
    for resolution, payload in sorted(inversions.items()):
        inputs = payload.get("inputs", {})
        window = inputs.get("t_window")
        if not isinstance(window, list) or len(window) != 2:
            raise ValueError(f"{resolution}: missing two-entry inputs.t_window")
        target_free = inputs.get("target_coefficients_used") is False
        covers = float(window[0]) <= start and float(window[1]) >= stop
        vertex = payload.get("microscopic_current_vertex")
        current_a = None if vertex is None else float(vertex["orientation_average_a"])
        weak = payload.get("frozen_weak_projection", {})
        weak_a = float(weak["a"]) if "a" in weak else None
        weak_d = float(weak["D"]) if "D" in weak else None
        mori = payload.get("mori_k0_correction", {})
        s = np.asarray(mori.get("s", []), dtype=float)
        delta = np.asarray(mori.get("delta_K1_total_truncated", []), dtype=float)
        delta_at_one = None
        if s.size and s.shape == delta.shape:
            index = int(np.argmin(np.abs(s - 1.0)))
            if abs(float(s[index]) - 1.0) <= 1e-10:
                delta_at_one = float(delta[index])
        records.append(
            {
                "resolution": resolution,
                "t_window": [float(window[0]), float(window[1])],
                "target_coefficients_used": not target_free,
                "covers_declared_window": covers,
                "conditional_current_a": current_a,
                "declared_weak_projection_a": weak_a,
                "declared_weak_projection_D": weak_d,
                "mori_delta_K1_s_equals_1": delta_at_one,
            }
        )

    convergence_accepted = validation.get("convergence_accepted") is True
    all_target_free = all(not item["target_coefficients_used"] for item in records)
    full_window = [item for item in records if item["covers_declared_window"]]
    frozen_kernel = convergence_accepted and all_target_free and len(full_window) >= 3
    physical_vertex = physical_quadratic_current_kubo_vertex()
    exact_moments = xxx_mori_even_moments(np.asarray(0.0))
    lanczos = xxx_mori_long_wave_lanczos()
    moment_frequencies = np.asarray([1.0 / start, 1.0 / stop])
    moment_bounds = mori_lanczos_stieltjes_bounds(
        moment_frequencies,
        float(lanczos["mu0"]),
        np.asarray(lanczos["squared_recurrents"]),
    )

    return {
        "schema": 1,
        "declared_window": [start, stop],
        "exact_microscopic_result": {
            "physical_zero_field_quadratic_current_vertex": physical_vertex,
            "derivation": (
                "global pi spin rotation gives <j_m>[h]= -<j_m>[-h], so every "
                "even functional derivative at h=0 vanishes"
            ),
            # The finite-k closed forms presently stop at mu16, while the
            # continuity-equation reduction to the uniform-current chain
            # fixes the strict k->0 values of mu18 through mu26 independently.
            "highest_even_mori_moment_order": 26,
            "highest_finite_momentum_closed_form_order": max(exact_moments),
            "exact_lanczos_recurrent_count": int(
                np.asarray(lanczos["squared_recurrents"]).size
            ),
            "moment_only_low_frequency_interval": {
                "z": moment_frequencies.tolist(),
                "lower": moment_bounds["lower"].tolist(),
                "upper": moment_bounds["upper"].tolist(),
                "interpretation": (
                    "the exact short-time moments alone leave a broad positive-spectrum "
                    "interval at the declared hydrodynamic frequencies"
                ),
            },
        },
        "records": records,
        "gate_audit": {
            "convergence_accepted": convergence_accepted,
            "all_records_target_free": all_target_free,
            "full_window_resolution_count": len(full_window),
            "required_full_window_resolution_count": 3,
            "finite_time_kernel_frozen": frozen_kernel,
        },
        "identifiability_verdict": {
            "unique_physical_scalar_burgers_pair_proven": False,
            "conditional_finite_window_vertex_available": any(
                item["conditional_current_a"] is not None for item in records
            ),
            "finite_frequency_mori_correction_available": any(
                item["mori_delta_K1_s_equals_1"] is not None for item in records
            ),
            "constant_long_time_coefficients_proven": False,
            "reason": (
                "the exact physical quadratic Kubo vertex is zero; a nonzero a is an "
                "orientation-conditioned nonanalytic finite-window projection, while D "
                "is a separately declared Markov/weak projection of a frequency-dependent "
                "Mori kernel"
            ),
            "next_missing_object": (
                "accepted full-window fine-resolution F1(q), or an independent microscopic "
                "calculation of the finite-scale projected-Liouvillian spectrum"
            ),
        },
    }


def _parse_inversions(entries: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError("each --inversion must be LABEL=PATH")
        label, encoded_path = entry.split("=", 1)
        if not label or label in result:
            raise ValueError("resolution labels must be non-empty and unique")
        path = Path(encoded_path)
        result[label] = json.loads(path.read_text(encoding="utf-8"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inversion", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--t-start", type=float, default=50.0)
    parser.add_argument("--t-stop", type=float, default=200.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        _parse_inversions(args.inversion),
        json.loads(args.validation.read_text(encoding="utf-8")),
        declared_window=(args.t_start, args.t_stop),
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
