#!/usr/bin/env python3
"""Audit paired convergence of stochastic internal-momentum sampling.

The lower- and higher-P calculations must use identical fields, Fourier/time
grids, trace distribution, and stochastic seeds.  Paired differences then
isolate the additional internal-momentum error.  No target trajectory or
transport coefficient is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(paths: list[Path]) -> dict[int, tuple[Path, dict[str, object]]]:
    rows = {}
    for path in paths:
        payload = json.loads(path.read_text())
        if payload.get("uses_target_a_or_D") or payload.get("uses_target_trajectory"):
            raise ValueError("target-dependent input is forbidden")
        if not payload["iteration"]["converged"]:
            raise ValueError(f"unconverged fixed point in {path}")
        if not payload.get("scope", {}).get("full_non_diagonal_diffusion"):
            raise ValueError(f"full non-diagonal diffusion not certified in {path}")
        if not payload.get("scope", {}).get("full_background_fdt_noise_covariance"):
            raise ValueError(f"full FDT noise covariance not certified in {path}")
        if not payload.get("fdt", {}).get("positive_semidefinite"):
            raise ValueError(f"non-positive FDT covariance in {path}")
        diagnostics = payload.get("matrix_diagnostics")
        if diagnostics is None:
            raise ValueError(f"missing matrix diagnostics in {path}")
        if diagnostics["diffusion_off_diagonal_frobenius_fraction"] <= 0.0:
            raise ValueError(f"diagonal diffusion used in {path}")
        if diagnostics["fdt_noise_off_diagonal_frobenius_fraction"] <= 0.0:
            raise ValueError(f"diagonal FDT noise used in {path}")
        if diagnostics["diffusion_static_metric_commutator_relative_norm"] > 1e-10:
            raise ValueError(f"thermodynamic metric mismatch in {path}")
        seed = int(payload["regulator"]["seed"])
        if seed in rows:
            raise ValueError("duplicate seed")
        rows[seed] = (path, payload)
    if len(rows) < 4:
        raise ValueError("at least four paired seeds are required")
    return rows


def _structure(payload: dict[str, object]) -> np.ndarray:
    return np.asarray(
        [[complex(*pair) for pair in row] for row in payload["structure_factors_over_chi_by_wave_then_time"]]
    )


def audit(
    lower_paths: list[Path],
    higher_paths: list[Path],
    *,
    tolerance: float = 1e-3,
    sigma_multiplier: float = 2.0,
) -> dict[str, object]:
    lower = _load(lower_paths)
    higher = _load(higher_paths)
    if set(lower) != set(higher):
        raise ValueError("lower- and higher-P seed sets differ")
    seeds = sorted(lower)
    differences = []
    reference = lower[seeds[0]][1]
    waves = np.asarray(reference["scaled_waves_q_equals_k_over_h2"], dtype=float)
    times = np.asarray(reference["scaled_times_tau_equals_t_h3"], dtype=float)
    fields = set()
    p_lower = set()
    p_higher = set()
    trace_pairings = set()
    for seed in seeds:
        lo = lower[seed][1]
        hi = higher[seed][1]
        for payload in (lo, hi):
            if not np.allclose(payload["scaled_waves_q_equals_k_over_h2"], waves):
                raise ValueError("Fourier grid mismatch")
            if not np.allclose(payload["scaled_times_tau_equals_t_h3"], times):
                raise ValueError("time grid mismatch")
            if payload["regulator"]["trace_source_layout"] != "shared_wave":
                raise ValueError("momentum pilot must use shared-wave probes")
            fields.add(float(payload["regulator"]["field"]))
            trace_pairings.add(int(payload["regulator"]["trace_pairings_per_frame"]))
        if lo["regulator"]["trace_distribution"] != hi["regulator"]["trace_distribution"]:
            raise ValueError("trace distribution mismatch")
        p_lower.add(int(lo["regulator"]["momentum_samples_per_external_wave"]))
        p_higher.add(int(hi["regulator"]["momentum_samples_per_external_wave"]))
        differences.append(_structure(hi) - _structure(lo))
    if len(fields) != 1 or len(p_lower) != 1 or len(p_higher) != 1 or len(trace_pairings) != 1:
        raise ValueError("pilot metadata are not uniform")
    lower_count = p_lower.pop()
    higher_count = p_higher.pop()
    if higher_count <= lower_count:
        raise ValueError("higher-P group does not have more momentum samples")
    delta = np.asarray(differences)
    mean = np.mean(delta, axis=0)
    centered = delta - mean
    sem = np.sqrt(
        np.sum(np.abs(centered) ** 2, axis=0)
        / ((delta.shape[0] - 1) * delta.shape[0])
    )
    bound = np.abs(mean) + sigma_multiplier * sem
    # k=0 is exactly conserved and supplies no convergence information.
    tested = bound[1:]
    flat_index = int(np.argmax(tested))
    wave_offset, time_index = np.unravel_index(flat_index, tested.shape)
    wave_index = wave_offset + 1
    maximum_bound = float(tested[wave_offset, time_index])
    return {
        "schema": 1,
        "method": "paired_internal_momentum_sampling_convergence",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "field": fields.pop(),
        "trace_pairings_per_frame": trace_pairings.pop(),
        "seeds": seeds,
        "lower_momentum_samples": lower_count,
        "higher_momentum_samples": higher_count,
        "sigma_multiplier": sigma_multiplier,
        "tolerance": tolerance,
        "maximum_paired_difference_sigma_bound": maximum_bound,
        "worst_scaled_wave": float(waves[wave_index]),
        "worst_scaled_time": float(times[time_index]),
        "worst_mean_difference": [
            float(mean[wave_index, time_index].real),
            float(mean[wave_index, time_index].imag),
        ],
        "worst_standard_error": float(sem[wave_index, time_index]),
        "accepted": bool(maximum_bound <= tolerance),
        "input_sha256_by_file": {
            str(path): _sha256(path)
            for path in lower_paths + higher_paths
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lower", nargs="+", required=True, type=Path)
    parser.add_argument("--higher", nargs="+", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--sigma-multiplier", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        args.lower,
        args.higher,
        tolerance=args.tolerance,
        sigma_multiplier=args.sigma_multiplier,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
