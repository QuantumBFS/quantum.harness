#!/usr/bin/env python3
"""Audit the joint-field limit of iterated full-matrix GHD structure factors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(paths: list[Path], tolerance: float) -> dict[str, object]:
    payloads = [_load(path) for path in paths]
    order = np.argsort([item["regulator"]["field"] for item in payloads])[::-1]
    payloads = [payloads[index] for index in order]
    paths = [paths[index] for index in order]
    fields = np.asarray(
        [item["regulator"]["field"] for item in payloads], dtype=float
    )
    scaled_times = [
        np.asarray(
            item.get(
                "scaled_times_tau_equals_t_h3",
                np.asarray(item["times"], dtype=float) * field**3,
            ),
            dtype=float,
        )
        for item, field in zip(payloads, fields)
    ]
    scaled_waves = [
        np.asarray(
            item.get(
                "scaled_waves_q_equals_k_over_h2",
                item.get("all_fourier_structure_factors_over_chi", {}).get(
                    "scaled_waves_q_equals_k_over_h2"
                ),
            ),
            dtype=float,
        )
        for item in payloads
    ]
    if any(not np.allclose(values, scaled_times[0]) for values in scaled_times[1:]):
        raise ValueError("input runs do not share a common scaled-time grid")
    if any(not np.allclose(values, scaled_waves[0]) for values in scaled_waves[1:]):
        raise ValueError("input runs do not share a common scaled-wave grid")
    structures = np.asarray(
        [
            [
                [complex(*pair) for pair in wave_row]
                for wave_row in item.get(
                    "structure_factors_over_chi_by_wave_then_time",
                    item.get("all_fourier_structure_factors_over_chi", {}).get(
                        "values_by_wave_then_time"
                    ),
                )
            ]
            for item in payloads
        ]
    )
    powers = np.asarray([1.0 / 3.0, 0.5, 2.0 / 3.0, 1.0, 4.0 / 3.0, 2.0])
    wave_rows = []
    accepted = True
    for wave_index, scaled_wave in enumerate(scaled_waves[0]):
        if wave_index == 0:
            continue
        time_rows = []
        for time_index, scaled_time in enumerate(scaled_times[0]):
            values = structures[:, wave_index, time_index]
            fits = []
            for power in powers:
                design = np.column_stack(
                    [np.ones(fields.size), fields**power]
                )
                coefficients, *_ = np.linalg.lstsq(
                    design, values.real, rcond=None
                )
                residual = values.real - design @ coefficients
                fits.append(
                    {
                        "power": float(power),
                        "zero_field_intercept": float(coefficients[0]),
                        "slope": float(coefficients[1]),
                        "rms_residual": float(np.sqrt(np.mean(residual**2))),
                    }
                )
            intercepts = np.asarray(
                [row["zero_field_intercept"] for row in fits]
            )
            last_step = float(abs(values[-1] - values[-2]))
            envelope = float(np.max(intercepts) - np.min(intercepts))
            point_accepted = bool(
                last_step <= tolerance and envelope <= 2.0 * tolerance
            )
            accepted = accepted and point_accepted
            time_rows.append(
                {
                    "scaled_time": float(scaled_time),
                    "values_by_descending_field": [
                        [float(value.real), float(value.imag)] for value in values
                    ],
                    "last_field_step_absolute": last_step,
                    "candidate_power_fits": fits,
                    "zero_field_intercept_envelope": [
                        float(np.min(intercepts)),
                        float(np.max(intercepts)),
                    ],
                    "zero_field_intercept_envelope_width": envelope,
                    "accepted": point_accepted,
                }
            )
        wave_rows.append(
            {
                "wave_index": wave_index,
                "scaled_wave": float(scaled_wave),
                "rows": time_rows,
            }
        )
    return {
        "schema": 1,
        "method": "joint_field_full_matrix_structure_extrapolation_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "input_files": [str(path) for path in paths],
        "fields_descending": fields.tolist(),
        "scaled_times": scaled_times[0].tolist(),
        "scaled_waves": scaled_waves[0].tolist(),
        "captured_susceptibility_fractions": [
            item["static_susceptibility_captured_fraction"] for item in payloads
        ],
        "all_finite_regulator_matrix_iterations_converged": all(
            item.get("iteration", item.get("matrix_dyson_iteration"))[
                "converged"
            ]
            for item in payloads
        ),
        "tolerance": tolerance,
        "wave_rows": wave_rows,
        "joint_field_limit_accepted": accepted,
        "physical_a_or_D_identified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--tolerance", type=float, default=1.0e-3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = audit(args.inputs, args.tolerance)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
