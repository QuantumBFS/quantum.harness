#!/usr/bin/env python3
"""Embed matrix-free adaptive F-GHD continua behind the exact XXX mu26 prefix.

The hydrodynamic white-noise delta contact is excluded because the microscopic
Mori kernel is regular at large Laplace frequency.  Each finite-regulator
colored force autocorrelation determines only a positive continuum terminator
behind the thirteen exact Lanczos recurrents.  No target trajectory, Burgers
coefficient, or finite pole count is used.
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

from src.mori_moment_matching import (  # noqa: E402
    embed_colored_memory_behind_exact_lanczos,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def derive(
    certificates: list[Path],
    *,
    laplace_frequency: np.ndarray,
    spectral_frequencies: np.ndarray,
    regulator_relative_tolerance: float,
) -> dict[str, object]:
    if len(certificates) < 2:
        raise ValueError("at least two finite-regulator certificates are required")
    rows = []
    reconstructed = []
    for path in certificates:
        payload = json.loads(path.read_text())
        if payload.get("uses_target_trajectory") or payload.get("uses_target_a_or_D"):
            raise RuntimeError(f"forbidden target input in {path}")
        scope = payload.get("scope", {})
        required = [
            "full_non_diagonal_diffusion_vertex",
            "velocity_vertex_included",
            "velocity_diffusion_cross_included",
            "multiplicative_noise_contact_included",
        ]
        if not all(bool(scope.get(key)) for key in required):
            raise ValueError(f"incomplete full-mode source {path}")
        source_rows = payload["rows"]
        times = np.asarray([row["time"] for row in source_rows], dtype=float)
        dense_available = all(row.get("dense_checks") is not None for row in source_rows)
        memory = np.asarray(
            [
                (
                    row["dense_checks"]["total"][0]
                    if dense_available
                    else row["continuity_memory_estimates"]["total"][0]
                )
                for row in source_rows
            ],
            dtype=float,
        )
        standard_errors = np.asarray(
            [
                (
                    0.0
                    if dense_available
                    else row["standard_error_complex_norms"]["total"]
                )
                for row in source_rows
            ],
            dtype=float,
        )
        embedded = embed_colored_memory_behind_exact_lanczos(
            times,
            memory,
            laplace_frequency,
            spectral_frequencies=spectral_frequencies,
        )
        kernel = np.asarray(embedded["reconstructed_exact_prefix_kernel"])
        reconstructed.append(kernel)
        rows.append(
            {
                "source": str(path),
                "source_sha256": _sha256(path),
                "regulator": payload["regulator"],
                "colored_memory": memory,
                "colored_memory_standard_errors": standard_errors,
                "colored_memory_source": (
                    "deterministic_dense_wick"
                    if dense_available
                    else "matrix_free_randomized_wick"
                ),
                "bare_white_contact_excluded": payload[
                    "multiplicative_noise_delta_memory"
                ]["estimate"],
                "embedding": embedded,
            }
        )
    reconstructed_array = np.asarray(reconstructed)
    scale = np.maximum(
        0.5 * np.abs(reconstructed_array[-1] + reconstructed_array[-2]),
        np.finfo(float).tiny,
    )
    last_pair_change = float(
        np.max(np.abs(reconstructed_array[-1] - reconstructed_array[-2]) / scale)
    )
    spectral_residuals = np.asarray(
        [row["embedding"]["spectral_fit"]["relative_residual"] for row in rows]
    )
    return {
        "schema": 1,
        "method": "matrix_free_full_mode_continuum_behind_exact_mu26_prefix",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "finite_pole_count_assumed": False,
        "laplace_frequency": laplace_frequency,
        "spectral_frequencies": spectral_frequencies,
        "rows": rows,
        "reconstructed_exact_prefix_kernels": reconstructed_array,
        "maximum_spectral_relative_residual": float(np.max(spectral_residuals)),
        "last_pair_maximum_relative_change": last_pair_change,
        "regulator_relative_tolerance": regulator_relative_tolerance,
        "gates": {
            "exact_mu26_prefix_preserved": True,
            "white_contact_removed_by_microscopic_regularity": True,
            "positive_continuum_at_every_regulator": bool(
                all(
                    np.min(row["embedding"]["spectral_weights"]) >= 0.0
                    for row in rows
                )
            ),
            "finite_time_tail_converged": False,
            "spectral_node_converged": False,
            "last_pair_regulator_stability_pass": bool(
                last_pair_change <= regulator_relative_tolerance
            ),
            "joint_zero_field_infinite_mode_converged": False,
            "physical_finite_window_kernel_certified": False,
        },
        "conclusion": (
            "The exact microscopic moments are fixed algebraically and the "
            "F-GHD calculation supplies only the remaining continuum.  The "
            "finite-time, spectral-node, and joint regulator gates must all "
            "close before projecting a unique finite-window a,D pair."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificates", nargs="+", type=Path)
    parser.add_argument(
        "--laplace-frequency",
        type=float,
        nargs="+",
        default=[0.05, 0.1, 0.2, 0.4, 0.8],
    )
    parser.add_argument("--spectral-nodes", type=int, default=256)
    parser.add_argument("--spectral-minimum", type=float, default=1.0e-3)
    parser.add_argument("--spectral-maximum", type=float, default=20.0)
    parser.add_argument("--regulator-relative-tolerance", type=float, default=0.1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spectral = np.concatenate(
        (
            [0.0],
            np.geomspace(
                args.spectral_minimum,
                args.spectral_maximum,
                args.spectral_nodes - 1,
            ),
        )
    )
    payload = derive(
        args.certificates,
        laplace_frequency=np.asarray(args.laplace_frequency, dtype=float),
        spectral_frequencies=spectral,
        regulator_relative_tolerance=args.regulator_relative_tolerance,
    )
    primary_kernels = np.asarray(payload["reconstructed_exact_prefix_kernels"])
    audit_rows = []
    maximum_spectral_grid_change = 0.0
    audit_nodes = sorted(
        set([max(64, args.spectral_nodes // 2), args.spectral_nodes, 2 * args.spectral_nodes])
    )
    audit_maxima = [
        0.5 * args.spectral_maximum,
        args.spectral_maximum,
        2.0 * args.spectral_maximum,
    ]
    for nodes in audit_nodes:
        for maximum in audit_maxima:
            audit_spectral = np.concatenate(
                (
                    [0.0],
                    np.geomspace(
                        args.spectral_minimum,
                        maximum,
                        nodes - 1,
                    ),
                )
            )
            audit = derive(
                args.certificates,
                laplace_frequency=np.asarray(args.laplace_frequency, dtype=float),
                spectral_frequencies=audit_spectral,
                regulator_relative_tolerance=args.regulator_relative_tolerance,
            )
            audit_kernels = np.asarray(
                audit["reconstructed_exact_prefix_kernels"]
            )
            scale = np.maximum(
                0.5 * np.abs(audit_kernels + primary_kernels),
                np.finfo(float).tiny,
            )
            relative_change = float(
                np.max(np.abs(audit_kernels - primary_kernels) / scale)
            )
            maximum_spectral_grid_change = max(
                maximum_spectral_grid_change, relative_change
            )
            audit_rows.append(
                {
                    "spectral_nodes": nodes,
                    "spectral_maximum": maximum,
                    "maximum_kernel_relative_change_from_primary": relative_change,
                    "maximum_spectral_relative_residual": audit[
                        "maximum_spectral_relative_residual"
                    ],
                }
            )
    payload["spectral_grid_audit"] = {
        "rows": audit_rows,
        "maximum_kernel_relative_change": maximum_spectral_grid_change,
        "acceptance_tolerance": 1.0e-3,
        "accepted": maximum_spectral_grid_change <= 1.0e-3,
    }
    payload["gates"]["spectral_node_converged"] = bool(
        maximum_spectral_grid_change <= 1.0e-3
    )
    encoded = json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
