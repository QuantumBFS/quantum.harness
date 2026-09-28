#!/usr/bin/env python3
"""Project an F-GHD continuum behind the exact mu26 prefix to a wall window.

The input terminator is obtained from target-free full-mode F-GHD colored
force correlations.  Its positive symmetric spectral quadrature is coupled
to the thirteen exact microscopic Lanczos recurrents as a finite Jacobi-bath
representation.  Diagonalizing that representation gives the full positive
kernel spectrum without a Laplace inversion or a chosen pole count.  The
scalar Mori equation is then propagated and passed through the frozen weak
wall estimator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.derive_freud_mori_wall_projection import (  # noqa: E402
    _solve_mori_volterra,
    _wall_profiles,
)
from src.heisenberg_burgers_bridge import xxx_mori_long_wave_lanczos  # noqa: E402
from src.tension_resolution import fit_profiled_weak  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jacobi_bath(
    spectral_frequencies: np.ndarray,
    spectral_weights: np.ndarray,
    squared_recurrents: np.ndarray,
) -> np.ndarray:
    mask = spectral_weights > 1.0e-14
    omega = np.asarray(spectral_frequencies, dtype=float)[mask]
    weights = np.asarray(spectral_weights, dtype=float)[mask]
    weights = weights / np.sum(weights)
    bath_frequencies = np.concatenate((omega, -omega))
    bath_amplitudes = np.sqrt(np.concatenate((0.5 * weights, 0.5 * weights)))
    prefix_sites = squared_recurrents.size
    matrix = np.zeros(
        (prefix_sites + bath_frequencies.size,) * 2,
        dtype=float,
    )
    for index in range(prefix_sites - 1):
        coupling = np.sqrt(squared_recurrents[index])
        matrix[index, index + 1] = coupling
        matrix[index + 1, index] = coupling
    bath_start = prefix_sites
    final_coupling = np.sqrt(squared_recurrents[-1])
    matrix[prefix_sites - 1, bath_start:] = final_coupling * bath_amplitudes
    matrix[bath_start:, prefix_sites - 1] = final_coupling * bath_amplitudes
    matrix[bath_start:, bath_start:] = np.diag(bath_frequencies)
    return matrix


def _solve_scalar_mori_level(
    next_level: np.ndarray,
    times: np.ndarray,
    squared_coupling: float,
) -> np.ndarray:
    """Solve ``g'=-b2*(next_level*g)`` by the trapezoidal scheme."""

    dt = float(times[1] - times[0])
    if np.max(np.abs(np.diff(times) - dt)) > 1.0e-12:
        raise ValueError("Mori hierarchy time grid must be uniform")
    result = np.ones(times.size, dtype=float)
    convolution = 0.0
    denominator = 1.0 + 0.25 * dt**2 * squared_coupling * next_level[0]
    for index in range(1, times.size):
        interior = (
            0.0
            if index == 1
            else float(next_level[1:index][::-1] @ result[1:index])
        )
        known = dt * (interior + 0.5 * next_level[index] * result[0])
        current = (
            result[index - 1]
            - 0.5 * dt * squared_coupling * (known + convolution)
        ) / denominator
        result[index] = current
        convolution = known + 0.5 * dt * next_level[0] * current
    return result


def derive(args: argparse.Namespace) -> dict[str, object]:
    source = json.loads(args.matching.read_text())
    if source.get("uses_target_trajectory") or source.get("uses_target_a_or_D"):
        raise RuntimeError("matching certificate contains forbidden target data")
    lanczos = xxx_mori_long_wave_lanczos()
    mu0 = float(lanczos["mu0"])
    squared = np.asarray(lanczos["squared_recurrents"], dtype=float)
    laplace = np.asarray(source["laplace_frequency"], dtype=float)
    all_times = np.arange(0.0, args.profile_stop + 0.5 * args.dt, args.dt)
    wave_numbers = np.arange(
        0.0, args.k_maximum + 0.5 * args.k_step, args.k_step
    )
    x = (
        np.arange(args.length, dtype=float) - 0.5 * (args.length - 1)
    ) * args.dx
    select = all_times >= args.profile_start - 1.0e-12
    profile_times = all_times[select]
    outputs = []
    for row, expected_kernel in zip(
        source["rows"], source["reconstructed_exact_prefix_kernels"], strict=True
    ):
        embedded = row["embedding"]
        source_times = np.asarray(embedded["times"], dtype=float)
        source_terminator = np.asarray(
            embedded["normalized_colored_memory"], dtype=float
        )
        if source_times[-1] < all_times[-1] - 1.0e-12:
            raise ValueError("F-GHD terminator does not reach profile-stop")
        terminator_time = PchipInterpolator(
            source_times, source_terminator, extrapolate=False
        )(all_times)
        hierarchy = terminator_time
        for recurrent in squared[::-1]:
            hierarchy = _solve_scalar_mori_level(
                hierarchy, all_times, float(recurrent)
            )
        kernel = mu0 * hierarchy

        # Retain the discrete positive-spectrum realization only as a
        # diagnostic.  It exactly reproduces the sampled Laplace data but is
        # not used for time propagation because a sparse NNLS quadrature has
        # artificial finite-frequency recurrences.
        jacobi = _jacobi_bath(
            np.asarray(embedded["spectral_frequencies"]),
            np.asarray(embedded["spectral_weights"]),
            squared,
        )
        frequencies, eigenvectors = np.linalg.eigh(jacobi)
        root_weights = eigenvectors[0] ** 2
        jacobi_kernel = mu0 * (
            np.cos(np.outer(all_times, frequencies)) @ root_weights
        )
        reconstructed_laplace = mu0 * np.asarray(
            [
                np.sum(root_weights * value / (value**2 + frequencies**2))
                for value in laplace
            ]
        )
        expected = np.asarray(expected_kernel, dtype=float)
        laplace_residual = float(
            np.max(
                np.abs(reconstructed_laplace - expected)
                / np.maximum(np.abs(expected), np.finfo(float).tiny)
            )
        )
        structure = _solve_mori_volterra(kernel, all_times, wave_numbers)
        profiles = _wall_profiles(x, wave_numbers, structure[select])
        fit = fit_profiled_weak(
            x,
            profile_times,
            profiles,
            t_window=(args.fit_start, args.fit_stop),
            x_crop=(args.x_crop[0], args.x_crop[1]),
            gamma=0.0,
        )
        outputs.append(
            {
                "regulator": row["regulator"],
                "terminator_nonzero_spectral_weights": int(
                    np.count_nonzero(np.asarray(embedded["spectral_weights"]) > 1.0e-14)
                ),
                "full_jacobi_dimension": int(jacobi.shape[0]),
                "minimum_full_spectral_weight": float(np.min(root_weights)),
                "full_spectral_mass_residual": float(abs(np.sum(root_weights) - 1.0)),
                "laplace_reconstruction_maximum_relative_residual": laplace_residual,
                "kernel_zero_time_residual": float(abs(kernel[0] - mu0)),
                "time_domain_terminator_minimum": float(np.min(terminator_time)),
                "time_domain_hierarchy_used_for_propagation": True,
                "sparse_jacobi_kernel_used_for_propagation": False,
                "sparse_jacobi_kernel_minimum_diagnostic": float(
                    np.min(jacobi_kernel)
                ),
                "structure_minimum": float(np.min(structure)),
                "structure_maximum": float(np.max(structure)),
                "k_zero_conservation_error": float(
                    np.max(np.abs(structure[:, 0] - 1.0))
                ),
                "frozen_weak_projection": {
                    "a": float(fit.a),
                    "D": float(fit.D0),
                    "mse": float(fit.mse),
                    "n_obs": int(fit.n_obs),
                },
            }
        )
    pairs = np.asarray(
        [[row["frozen_weak_projection"]["a"], row["frozen_weak_projection"]["D"]] for row in outputs]
    )
    structure_nonnegative = all(
        float(row["structure_minimum"]) >= -1.0e-10 for row in outputs
    )
    last_pair_change = np.abs(pairs[-1] - pairs[-2]) if pairs.shape[0] >= 2 else np.full(2, np.nan)
    return {
        "schema": 1,
        "method": "time_domain_full_mode_fghd_terminator_behind_mu26_prefix",
        "source": str(args.matching),
        "source_sha256": _sha256(args.matching),
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "inputs": {
            "length": args.length,
            "profile_window": [args.profile_start, args.profile_stop],
            "fit_window": [args.fit_start, args.fit_stop],
            "dt": args.dt,
            "k_maximum": args.k_maximum,
            "k_step": args.k_step,
            "x_crop": args.x_crop,
        },
        "rows": outputs,
        "last_pair_absolute_change": {
            "a": float(last_pair_change[0]),
            "D": float(last_pair_change[1]),
        },
        "scope": {
            "exact_mu26_prefix": True,
            "positive_fghd_terminator": True,
            "finite_pole_count_assumed": False,
            "frozen_estimator_uses_target_profiles": False,
            "joint_regulator_convergence_complete": False,
            "fixed_k_t_order_of_limits_used": True,
            "structure_nonnegative": structure_nonnegative,
            "physical_projection_accepted": False,
            "rejection_reason": (
                "this diagnostic keeps physical k and t fixed instead of q=k/h^2 "
                "and tau=t*h^3; additionally the reconstructed structure is not "
                "nonnegative"
                if not structure_nonnegative
                else "this diagnostic keeps physical k and t fixed instead of "
                "q=k/h^2 and tau=t*h^3"
            ),
            "unique_a_D_proved": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matching", type=Path)
    parser.add_argument("--length", type=int, default=400)
    parser.add_argument("--dx", type=float, default=1.0)
    parser.add_argument("--dt", type=float, default=0.2)
    parser.add_argument("--profile-start", type=float, default=50.0)
    parser.add_argument("--profile-stop", type=float, default=200.0)
    parser.add_argument("--fit-start", type=float, default=52.0)
    parser.add_argument("--fit-stop", type=float, default=198.0)
    parser.add_argument("--x-crop", nargs=2, type=float, default=[-120.0, 120.0])
    parser.add_argument("--k-maximum", type=float, default=1.2)
    parser.add_argument("--k-step", type=float, default=0.01)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = derive(args)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
