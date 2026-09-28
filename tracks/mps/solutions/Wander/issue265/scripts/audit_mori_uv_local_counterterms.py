#!/usr/bin/env python3
"""Test whether finitely many local Mori counterterms remove loop-cutoff drift.

The colored one-loop memory is Laplace transformed without trajectory data.
At a declared matching frequency ``z0`` we subtract its Taylor polynomial of
order ``M``.  Such a polynomial is precisely the frequency-space form of a
finite collection of local/contact EFT counterterms.  The audit asks whether
one common ``M`` stabilizes every declared lower-frequency probe as the
hydrodynamic Fourier cutoff is raised.  Failure is reported rather than
selecting the order that happens to fit one frequency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificates", type=Path, nargs="+")
    parser.add_argument("--matching-frequency", type=float, default=0.5)
    parser.add_argument("--probe-frequencies", type=float, nargs="+", default=[0.1, 0.2])
    parser.add_argument("--maximum-order", type=int, default=4)
    parser.add_argument("--last-pair-relative-tolerance", type=float, default=0.1)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _laplace_derivative(times: np.ndarray, memory: np.ndarray, z: float, n: int) -> float:
    return float(np.trapezoid((-times) ** n * np.exp(-z * times) * memory, times))


def main() -> None:
    args = _arguments()
    if args.matching_frequency <= 0.0:
        raise ValueError("matching frequency must be positive")
    if any(z <= 0.0 or z >= args.matching_frequency for z in args.probe_frequencies):
        raise ValueError("probe frequencies must lie between zero and z0")
    if args.maximum_order < 0:
        raise ValueError("maximum order must be non-negative")

    rows = []
    reference_inputs = None
    reference_times = None
    for path in args.certificates:
        payload = json.loads(path.read_text())
        inputs = dict(payload["inputs"])
        if inputs.get("trajectory_data_used") or inputs.get("target_coefficients_used"):
            raise RuntimeError(f"target-contaminated certificate: {path}")
        inputs.pop("fourier_cutoffs", None)
        if reference_inputs is None:
            reference_inputs = inputs
        elif inputs != reference_inputs:
            raise ValueError("certificates use different physical/time regulators")
        times = np.asarray(payload["times"], dtype=float)
        if reference_times is None:
            reference_times = times
        elif not np.array_equal(times, reference_times):
            raise ValueError("certificates use different time grids")
        for row in payload["uv_rows"]:
            memory = np.asarray(
                row["colored_memory"]["total_colored_continuity_memory"]["values"],
                dtype=float,
            )
            if memory.shape != times.shape:
                raise ValueError("memory and time arrays have different lengths")
            rows.append(
                {
                    "source": str(path),
                    "fourier_points": int(row["fourier_points"]),
                    "maximum_resolved_wave_number": float(row["maximum_resolved_wave_number"]),
                    "memory": memory,
                    "multiplicative_noise_delta_memory": float(
                        row["multiplicative_noise_delta_memory"]
                    ),
                }
            )
    rows.sort(key=lambda item: item["maximum_resolved_wave_number"])
    if len(rows) < 4:
        raise ValueError("need at least four Fourier cutoffs")

    orders = []
    any_order_passes = False
    for order in range(args.maximum_order + 1):
        probe_rows = []
        order_pass = True
        for probe in args.probe_frequencies:
            values = []
            for row in rows:
                memory = row["memory"]
                raw = _laplace_derivative(reference_times, memory, probe, 0)
                derivatives = [
                    _laplace_derivative(
                        reference_times, memory, args.matching_frequency, n
                    )
                    for n in range(order + 1)
                ]
                local = sum(
                    derivatives[n]
                    * (probe - args.matching_frequency) ** n
                    / math.factorial(n)
                    for n in range(order + 1)
                )
                values.append(raw - local)
            last_center = 0.5 * (values[-1] + values[-2])
            last_relative_change = abs(values[-1] - values[-2]) / max(
                abs(last_center), np.finfo(float).tiny
            )
            probe_pass = bool(
                last_relative_change <= args.last_pair_relative_tolerance
            )
            order_pass = order_pass and probe_pass
            probe_rows.append(
                {
                    "frequency": float(probe),
                    "subtracted_values_by_cutoff": [float(value) for value in values],
                    "last_pair_relative_change": float(last_relative_change),
                    "cutoff_stability_pass": probe_pass,
                }
            )
        any_order_passes = any_order_passes or order_pass
        orders.append(
            {
                "local_counterterm_order": order,
                "probes": probe_rows,
                "all_probe_frequencies_stable": order_pass,
            }
        )

    serialized_rows = [
        {
            key: value
            for key, value in row.items()
            if key != "memory"
        }
        for row in rows
    ]
    result = {
        "schema": 1,
        "method": "laplace_bphz_local_counterterm_order_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "source_sha256": {str(path): _sha256(path) for path in args.certificates},
        "matching_frequency": args.matching_frequency,
        "probe_frequencies": args.probe_frequencies,
        "counterterm_interpretation": (
            "Taylor coefficients at z0 represent local/contact Mori-EFT terms; "
            "the delta-noise contact is contained in order zero and cancels from "
            "every order>=0 subtracted difference"
        ),
        "finite_time_laplace_maximum_time": float(reference_times[-1]),
        "cutoffs": serialized_rows,
        "orders": orders,
        "gates": {
            "last_pair_relative_tolerance": args.last_pair_relative_tolerance,
            "some_single_local_order_stabilizes_all_probes": any_order_passes,
            "finite_local_counterterm_uv_matching_complete": any_order_passes,
            "physical_F1_perp_certified": False,
        },
        "conclusion": (
            "A pass is only a necessary locality check, not a physical matching "
            "coefficient.  A failure proves that the tested finite local basis "
            "does not remove cutoff drift over the full frequency band."
        ),
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
