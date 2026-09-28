#!/usr/bin/env python3
"""Audit replicated full-matrix fluctuating-GHD regulator sequences.

The inputs are theory-only low-rank matrix-Mori calculations.  Replicates at
fixed field estimate stochastic-trace uncertainty before any field-limit
extrapolation.  Candidate correction powers are used only to bound regulator
dependence; no wall trajectory and no target value of ``a`` or ``D`` enters.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

import numpy as np


POWERS = np.asarray([1 / 3, 1 / 2, 2 / 3, 1, 4 / 3, 2], dtype=float)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _complex_structure(payload: dict[str, object]) -> np.ndarray:
    return np.asarray(
        [
            [complex(*pair) for pair in wave_row]
            for wave_row in payload["structure_factors_over_chi_by_wave_then_time"]
        ],
        dtype=complex,
    )


def _sem(values: np.ndarray) -> np.ndarray:
    if values.shape[0] < 2:
        return np.full(values.shape[1:], np.inf, dtype=float)
    centered = values - np.mean(values, axis=0)
    # Complex magnitude variance treats real and imaginary stochastic errors
    # jointly and is conservative for the real structure factor used below.
    variance = np.sum(np.abs(centered) ** 2, axis=0) / (values.shape[0] - 1)
    return np.sqrt(variance / values.shape[0])


def audit(
    paths: list[Path],
    *,
    tolerance: float,
    sigma_multiplier: float = 2.0,
    required_replicates: int = 4,
    minimum_captured_fraction: float = 0.96,
) -> dict[str, object]:
    payloads = [(path, json.loads(path.read_text())) for path in paths]
    grouped: dict[float, list[tuple[Path, dict[str, object]]]] = defaultdict(list)
    for path, payload in payloads:
        if payload.get("uses_target_a_or_D") or payload.get("uses_target_trajectory"):
            raise ValueError(f"forbidden target dependency in {path}")
        grouped[float(payload["regulator"]["field"])].append((path, payload))
    fields = np.asarray(sorted(grouped, reverse=True), dtype=float)
    if fields.size < 4:
        raise ValueError("at least four distinct fields are required")

    reference = payloads[0][1]
    scaled_times = np.asarray(reference["scaled_times_tau_equals_t_h3"], dtype=float)
    scaled_waves = np.asarray(reference["scaled_waves_q_equals_k_over_h2"], dtype=float)
    means: list[np.ndarray] = []
    sems: list[np.ndarray] = []
    field_rows: list[dict[str, object]] = []
    all_finite_converged = True
    all_replicates_present = True
    all_fdt_valid = True
    all_capture_valid = True
    reference_regulator_signature = None
    for field in fields:
        entries = grouped[float(field)]
        all_replicates_present &= len(entries) >= required_replicates
        structures = []
        seeds = []
        for path, payload in entries:
            if not np.allclose(payload["scaled_times_tau_equals_t_h3"], scaled_times):
                raise ValueError(f"scaled-time mismatch in {path}")
            if not np.allclose(payload["scaled_waves_q_equals_k_over_h2"], scaled_waves):
                raise ValueError(f"scaled-wave mismatch in {path}")
            all_finite_converged &= bool(payload["iteration"]["converged"])
            all_fdt_valid &= bool(payload["fdt"]["positive_semidefinite"])
            captured_fraction = float(payload["static_susceptibility_captured_fraction"])
            all_capture_valid &= captured_fraction >= minimum_captured_fraction
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
            try:
                signature = tuple((key, regulator[key]) for key in signature_keys)
            except KeyError as error:
                raise ValueError(f"missing regulator provenance {error.args[0]} in {path}") from error
            signature += (
                (
                    "trace_pairings_per_frame",
                    regulator.get("trace_pairings_per_frame", 1),
                ),
            )
            if reference_regulator_signature is None:
                reference_regulator_signature = signature
            elif signature != reference_regulator_signature:
                raise ValueError(f"regulator mismatch in {path}")
            structures.append(_complex_structure(payload))
            seed = payload["regulator"].get("seed")
            if seed is None:
                match = re.search(r"seed(\d+)", path.name)
                seed = int(match.group(1)) if match else -1
            seeds.append(int(seed))
        stack = np.asarray(structures)
        mean = np.mean(stack, axis=0)
        standard_error = _sem(stack)
        if len(set(seeds)) != len(seeds):
            raise ValueError(f"duplicate stochastic seed at field {field}")
        means.append(mean)
        sems.append(standard_error)
        field_rows.append(
            {
                "field": float(field),
                "replicate_count": len(entries),
                "seeds": seeds,
                "maximum_structure_factor_sem": float(np.max(standard_error)),
                "captured_susceptibility_fraction_range": [
                    float(min(item[1]["static_susceptibility_captured_fraction"] for item in entries)),
                    float(max(item[1]["static_susceptibility_captured_fraction"] for item in entries)),
                ],
                "input_files": [str(item[0]) for item in entries],
            }
        )

    mean_array = np.asarray(means)
    sem_array = np.asarray(sems)
    accepted = bool(
        all_finite_converged
        and all_replicates_present
        and all_fdt_valid
        and all_capture_valid
    )
    wave_rows = []
    for wave_index, scaled_wave in enumerate(scaled_waves):
        if wave_index == 0:
            continue
        time_rows = []
        for time_index, scaled_time in enumerate(scaled_times):
            values = mean_array[:, wave_index, time_index]
            errors = sem_array[:, wave_index, time_index]
            fits = []
            interval_lows = []
            interval_highs = []
            for power in POWERS:
                design = np.column_stack([np.ones(fields.size), fields**power])
                pseudo = np.linalg.pinv(design)
                coefficients = pseudo @ values.real
                residual = values.real - design @ coefficients
                intercept_sem = float(np.sqrt(np.sum((pseudo[0] * errors) ** 2)))
                low = float(coefficients[0] - sigma_multiplier * intercept_sem)
                high = float(coefficients[0] + sigma_multiplier * intercept_sem)
                interval_lows.append(low)
                interval_highs.append(high)
                fits.append(
                    {
                        "power": float(power),
                        "zero_field_intercept": float(coefficients[0]),
                        "zero_field_intercept_sem": intercept_sem,
                        "sigma_interval": [low, high],
                        "rms_residual": float(np.sqrt(np.mean(residual**2))),
                    }
                )
            last_step_bound = float(
                abs(values[-1] - values[-2])
                + sigma_multiplier * np.hypot(errors[-1], errors[-2])
            )
            envelope = [float(min(interval_lows)), float(max(interval_highs))]
            envelope_width = envelope[1] - envelope[0]
            maximum_sem = float(np.max(errors))
            point_accepted = bool(
                last_step_bound <= tolerance
                and envelope_width <= 2 * tolerance
                and maximum_sem <= tolerance / sigma_multiplier
            )
            accepted &= point_accepted
            time_rows.append(
                {
                    "scaled_time": float(scaled_time),
                    "mean_values_by_descending_field": [
                        [float(value.real), float(value.imag)] for value in values
                    ],
                    "sem_by_descending_field": errors.tolist(),
                    "last_field_step_sigma_bound": last_step_bound,
                    "candidate_power_fits": fits,
                    "zero_field_intercept_sigma_envelope": envelope,
                    "zero_field_intercept_sigma_envelope_width": envelope_width,
                    "maximum_within_field_sem": maximum_sem,
                    "accepted": point_accepted,
                }
            )
        wave_rows.append(
            {"wave_index": int(wave_index), "scaled_wave": float(scaled_wave), "rows": time_rows}
        )

    return {
        "schema": 1,
        "method": "replicated_joint_field_full_matrix_structure_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "fields_descending": fields.tolist(),
        "scaled_times": scaled_times.tolist(),
        "scaled_waves": scaled_waves.tolist(),
        "required_replicates_per_field": required_replicates,
        "sigma_multiplier": sigma_multiplier,
        "tolerance": tolerance,
        "minimum_captured_susceptibility_fraction": minimum_captured_fraction,
        "common_regulator_signature": dict(reference_regulator_signature or ()),
        "input_sha256_by_file": {str(path): _sha256(path) for path, _ in payloads},
        "field_rows": field_rows,
        "all_required_replicates_present": bool(all_replicates_present),
        "all_finite_regulator_matrix_iterations_converged": bool(all_finite_converged),
        "all_fdt_covariances_positive_semidefinite": bool(all_fdt_valid),
        "all_captured_susceptibility_fractions_valid": bool(all_capture_valid),
        "wave_rows": wave_rows,
        "joint_field_limit_accepted": bool(accepted),
        "physical_a_or_D_identified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--sigma-multiplier", type=float, default=2.0)
    parser.add_argument("--required-replicates", type=int, default=4)
    parser.add_argument("--minimum-captured-fraction", type=float, default=0.96)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = audit(
        args.inputs,
        tolerance=args.tolerance,
        sigma_multiplier=args.sigma_multiplier,
        required_replicates=args.required_replicates,
        minimum_captured_fraction=args.minimum_captured_fraction,
    )
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
