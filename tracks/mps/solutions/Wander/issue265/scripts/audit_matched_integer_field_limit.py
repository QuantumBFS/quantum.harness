#!/usr/bin/env python3
"""Audit the one-sided matched-asymptotic integer field expansion.

After resolving the small-string/giant-string boundary layer, the discrete
string measure has an Euler--Maclaurin expansion in ``|h|``.  This audit does
not select a correction exponent from the data.  It requires at least five
fields, tests degree-one through degree-three expansions by predicting the
finest held-out field, and bounds the zero-field intercept by their joint
two-sigma envelope.  No wall trajectory or target ``a,D`` is read.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

import numpy as np


DEGREES = (1, 2, 3)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _structure(payload: dict[str, object]) -> np.ndarray:
    return np.asarray(
        [
            [complex(*pair) for pair in wave_row]
            for wave_row in payload["structure_factors_over_chi_by_wave_then_time"]
        ],
        dtype=complex,
    )


def _sem(values: np.ndarray) -> np.ndarray:
    centered = values - np.mean(values, axis=0)
    variance = np.sum(np.abs(centered) ** 2, axis=0) / (values.shape[0] - 1)
    return np.sqrt(variance / values.shape[0])


def _weighted_fit(
    fields: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray,
    degree: int,
) -> tuple[np.ndarray, np.ndarray]:
    design = np.column_stack([fields**power for power in range(degree + 1)])
    floor = max(float(np.median(errors)) * 1.0e-6, np.finfo(float).eps)
    weights = 1.0 / np.maximum(errors, floor) ** 2
    normal = design.T @ (weights[:, None] * design)
    inverse = np.linalg.pinv(normal)
    coefficients = inverse @ (design.T @ (weights * values.real))
    return coefficients, inverse


def audit(
    paths: list[Path],
    *,
    tolerance: float = 1.0e-3,
    sigma_multiplier: float = 2.0,
    required_replicates: int = 4,
) -> dict[str, object]:
    grouped: dict[float, list[tuple[Path, dict[str, object]]]] = defaultdict(list)
    payloads = []
    for path in paths:
        payload = json.loads(path.read_text())
        if payload.get("uses_target_a_or_D") or payload.get("uses_target_trajectory"):
            raise ValueError(f"forbidden target dependency in {path}")
        grouped[float(payload["regulator"]["field"])].append((path, payload))
        payloads.append((path, payload))
    fields = np.asarray(sorted(grouped, reverse=True), dtype=float)
    if fields.size < 5:
        raise ValueError("at least five fields are required for a held-out cubic audit")

    reference = payloads[0][1]
    scaled_times = np.asarray(reference["scaled_times_tau_equals_t_h3"], dtype=float)
    scaled_waves = np.asarray(reference["scaled_waves_q_equals_k_over_h2"], dtype=float)
    means = []
    sems = []
    field_rows = []
    common_signature = None
    all_valid = True
    for field in fields:
        entries = grouped[float(field)]
        all_valid &= len(entries) >= required_replicates
        structures = []
        seeds = []
        for path, payload in entries:
            if not np.allclose(payload["scaled_times_tau_equals_t_h3"], scaled_times):
                raise ValueError(f"scaled-time mismatch in {path}")
            if not np.allclose(payload["scaled_waves_q_equals_k_over_h2"], scaled_waves):
                raise ValueError(f"scaled-wave mismatch in {path}")
            all_valid &= bool(payload["iteration"]["converged"])
            all_valid &= bool(payload["fdt"]["positive_semidefinite"])
            all_valid &= float(payload["static_susceptibility_captured_fraction"]) >= 0.96
            regulator = payload["regulator"]
            signature_keys = (
                "nodes_per_string",
                "string_xi_cutoff",
                "string_xi_buffer",
                "scaled_rapidity_extent",
                "scaled_rapidity_map_alpha",
                "kernel_theta_step",
                "fourier_points",
                "samples_per_internal_wave",
                "trace_distribution",
                "trace_source_layout",
                "lattice_wave_number",
            )
            signature = tuple((key, regulator[key]) for key in signature_keys)
            signature += (("trace_pairings_per_frame", regulator.get("trace_pairings_per_frame", 1)),)
            if common_signature is None:
                common_signature = signature
            elif signature != common_signature:
                raise ValueError(f"regulator mismatch in {path}")
            structures.append(_structure(payload))
            seed = regulator.get("seed")
            if seed is None:
                match = re.search(r"seed(\d+)", path.name)
                seed = int(match.group(1)) if match else -1
            seeds.append(int(seed))
        if len(set(seeds)) != len(seeds):
            raise ValueError(f"duplicate seed at field {field}")
        stack = np.asarray(structures)
        means.append(np.mean(stack, axis=0))
        sems.append(_sem(stack))
        field_rows.append({"field": float(field), "replicates": len(entries), "seeds": seeds})

    mean_array = np.asarray(means)
    sem_array = np.asarray(sems)
    accepted = bool(all_valid)
    wave_rows = []
    for wave_index, scaled_wave in enumerate(scaled_waves):
        if wave_index == 0:
            continue
        time_rows = []
        for time_index, scaled_time in enumerate(scaled_times):
            values = mean_array[:, wave_index, time_index]
            errors = sem_array[:, wave_index, time_index]
            model_rows = []
            interval_lows = []
            interval_highs = []
            models_valid = True
            for degree in DEGREES:
                coefficients, covariance = _weighted_fit(fields, values, errors, degree)
                intercept_sem = float(np.sqrt(max(covariance[0, 0], 0.0)))
                # Fit only the coarser fields and predict the independent
                # finest field.  Five fields leave four points for degree 3.
                coarse_coefficients, coarse_covariance = _weighted_fit(
                    fields[:-1], values[:-1], errors[:-1], degree
                )
                row = np.asarray([fields[-1] ** power for power in range(degree + 1)])
                prediction = float(row @ coarse_coefficients)
                prediction_sem = float(
                    np.sqrt(max(row @ coarse_covariance @ row, 0.0) + errors[-1] ** 2)
                )
                prediction_error = float(abs(values[-1].real - prediction))
                prediction_bound = sigma_multiplier * prediction_sem + tolerance
                model_valid = prediction_error <= prediction_bound
                models_valid &= model_valid
                low = float(coefficients[0] - sigma_multiplier * intercept_sem)
                high = float(coefficients[0] + sigma_multiplier * intercept_sem)
                interval_lows.append(low)
                interval_highs.append(high)
                model_rows.append(
                    {
                        "degree": degree,
                        "coefficients_ascending_power": coefficients.tolist(),
                        "zero_field_intercept": float(coefficients[0]),
                        "zero_field_intercept_sem": intercept_sem,
                        "finest_field_held_out_prediction": prediction,
                        "finest_field_prediction_error": prediction_error,
                        "finest_field_prediction_bound": prediction_bound,
                        "held_out_prediction_accepted": bool(model_valid),
                    }
                )
            envelope = [float(min(interval_lows)), float(max(interval_highs))]
            envelope_width = envelope[1] - envelope[0]
            point_accepted = bool(
                models_valid
                and envelope_width <= 2.0 * tolerance
                and float(np.max(errors)) <= tolerance / sigma_multiplier
            )
            accepted &= point_accepted
            time_rows.append(
                {
                    "scaled_time": float(scaled_time),
                    "mean_values_by_descending_field": [
                        [float(value.real), float(value.imag)] for value in values
                    ],
                    "sem_by_descending_field": errors.tolist(),
                    "integer_expansion_models": model_rows,
                    "zero_field_intercept_sigma_envelope": envelope,
                    "zero_field_intercept_sigma_envelope_width": envelope_width,
                    "accepted": point_accepted,
                }
            )
        wave_rows.append({"scaled_wave": float(scaled_wave), "rows": time_rows})

    return {
        "schema": 1,
        "method": "matched_euler_maclaurin_integer_field_limit_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "field_expansion": "S_h=S_0+c_1|h|+c_2|h|^2+c_3|h|^3+...",
        "degrees_tested": list(DEGREES),
        "fields_descending": fields.tolist(),
        "tolerance": tolerance,
        "sigma_multiplier": sigma_multiplier,
        "common_regulator_signature": dict(common_signature or ()),
        "field_rows": field_rows,
        "wave_rows": wave_rows,
        "input_sha256_by_file": {str(path): _sha256(path) for path, _ in payloads},
        "all_finite_regulator_inputs_valid": bool(all_valid),
        "matched_integer_field_limit_accepted": bool(accepted),
        "physical_a_or_D_identified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--tolerance", type=float, default=1.0e-3)
    parser.add_argument("--sigma-multiplier", type=float, default=2.0)
    parser.add_argument("--required-replicates", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        args.inputs,
        tolerance=args.tolerance,
        sigma_multiplier=args.sigma_multiplier,
        required_replicates=args.required_replicates,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
