#!/usr/bin/env python3
"""Match replicated full-matrix F-GHD dynamics to exact XXX Mori moments.

This is a microscopic/hydrodynamic splice, not a fit to a spin trajectory.
The complete finite-field structure factor is first inverted by continuity to
the physical top-level Mori kernel, retaining its finite-frequency amplitude.
The exact XXX commutator moments fix the first eight finite-k Lanczos
recurrents; peeling them from the top-level kernel leaves a deep terminator.
A positive continuum quadrature represents that unresolved spectrum; no
number of poles or extra hydrodynamic fields is assumed.  The separately
stored colored force memory certifies that the full velocity/diffusion/FDT
vertices were propagated, but is not normalized and inserted as an arbitrary
deep terminator.
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

from src.mori_moment_matching import (  # noqa: E402
    density_structure_from_mori_kernels,
    match_hydrodynamic_structure_through_exact_lanczos,
    mori_hierarchy_kernel_from_terminator,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _complex_rows(rows: list[list[list[float]]]) -> np.ndarray:
    return np.asarray(
        [[complex(float(pair[0]), float(pair[1])) for pair in row] for row in rows]
    )


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, complex):
        return [float(value.real), float(value.imag)]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _relative_change(left: np.ndarray, right: np.ndarray) -> float:
    scale = np.maximum(
        0.5 * (np.abs(left) + np.abs(right)), np.finfo(float).tiny
    )
    return float(np.max(np.abs(left - right) / scale))


def derive(
    payloads: list[dict[str, object]],
    *,
    laplace_frequencies: np.ndarray,
    spectral_nodes: int,
    spectral_maximum: float,
    time_tail_fraction: float,
    hierarchy_dt: float = 0.5,
    wave_index: int = 1,
) -> dict[str, object]:
    if len(payloads) < 2:
        raise ValueError("at least two independent replicas are required")
    z = np.asarray(laplace_frequencies, dtype=float)
    if z.ndim != 1 or z.size < 3 or np.any(z <= 0.0) or np.any(np.diff(z) <= 0.0):
        raise ValueError("Laplace frequencies must be an increasing positive vector")
    if spectral_nodes < 16 or spectral_maximum <= 0.0:
        raise ValueError("spectral quadrature is too small")
    if not 0.5 <= time_tail_fraction < 1.0:
        raise ValueError("time-tail fraction must lie in [0.5,1)")
    if not np.isfinite(hierarchy_dt) or hierarchy_dt <= 0.0:
        raise ValueError("hierarchy time step must be positive")

    reference = payloads[0]
    times = np.asarray(reference["times"], dtype=float)
    waves = np.asarray(reference["waves"], dtype=float)
    regulator = reference["regulator"]
    if not 0 < wave_index < waves.size:
        raise ValueError("wave index must select a nonzero retained wave")
    required_scope = {
        "full_non_diagonal_diffusion": True,
        "full_background_fdt_noise_covariance": True,
        "colored_memory_available_for_exact_mori_prefix_matching": True,
        "white_noise_contact_inserted_into_colored_memory": False,
    }
    memories = []
    structures = []
    seeds = []
    for payload in payloads:
        if payload.get("uses_target_trajectory") or payload.get("uses_target_a_or_D"):
            raise RuntimeError("forbidden target information in F-GHD certificate")
        if np.asarray(payload["times"], dtype=float).shape != times.shape or not np.allclose(
            payload["times"], times, rtol=0.0, atol=1.0e-12
        ):
            raise ValueError("replica time grids differ")
        if not np.allclose(payload["waves"], waves, rtol=0.0, atol=1.0e-14):
            raise ValueError("replica wave grids differ")
        row_regulator = payload["regulator"]
        for key in (
            "field",
            "mode_count",
            "nodes_per_string",
            "string_xi_cutoff",
            "fourier_points",
            "wave_step",
            "trace_pairings_per_frame",
            "trace_source_layout",
        ):
            if row_regulator.get(key) != regulator.get(key):
                raise ValueError(f"replica regulator mismatch in {key}")
        scope = payload.get("scope", {})
        for key, expected in required_scope.items():
            if scope.get(key) is not expected:
                raise RuntimeError(f"required F-GHD scope gate failed: {key}")
        if not payload.get("iteration", {}).get("converged", False):
            raise RuntimeError("finite-regulator Dyson fixed point not reached")
        matrix = _complex_rows(
            payload["projected_colored_continuity_memory_by_wave_then_time"]
        )
        if matrix.shape != (waves.size, times.size):
            raise ValueError("colored-memory array has the wrong shape")
        memories.append(matrix[wave_index])
        structure_matrix = _complex_rows(
            payload["structure_factors_over_chi_by_wave_then_time"]
        )
        if structure_matrix.shape != (waves.size, times.size):
            raise ValueError("structure-factor array has the wrong shape")
        structures.append(structure_matrix[wave_index])
        seeds.append(int(row_regulator["seed"]))
    if len(set(seeds)) != len(seeds):
        raise ValueError("replica seeds must be distinct")

    samples = np.asarray(memories)
    mean_complex = np.mean(samples, axis=0)
    centered = samples - mean_complex[None, :]
    sem_complex = np.sqrt(
        np.sum(np.abs(centered) ** 2, axis=0)
        / (samples.shape[0] * (samples.shape[0] - 1))
    )
    mean_memory = mean_complex.real
    if mean_memory[0] <= 0.0:
        raise RuntimeError("replicated colored memory is nonpositive at zero time")
    imaginary_fraction = float(
        np.linalg.norm(mean_complex.imag)
        / max(np.linalg.norm(mean_complex.real), np.finfo(float).tiny)
    )
    maximum_relative_sem = float(
        np.max(sem_complex / np.maximum(np.abs(mean_complex), np.finfo(float).tiny))
    )
    maximum_sem_in_zero_time_units = float(
        np.max(sem_complex) / abs(mean_complex[0])
    )
    l2_sem_to_signal_ratio = float(
        np.linalg.norm(sem_complex)
        / max(np.linalg.norm(mean_complex), np.finfo(float).tiny)
    )

    raw_structure_mean = np.mean(np.asarray(structures), axis=0)
    structure_for_matching = raw_structure_mean.real

    def match(time_values: np.ndarray, structure_values: np.ndarray, nodes: int):
        omega = np.concatenate(
            ([0.0], np.geomspace(float(np.min(z)) / 50.0, spectral_maximum, nodes - 1))
        )
        return match_hydrodynamic_structure_through_exact_lanczos(
            time_values,
            structure_values,
            z,
            spectral_frequencies=omega,
            wavenumber=float(waves[wave_index]),
        )

    full_coarse = match(times, structure_for_matching, spectral_nodes)
    full_fine = match(times, structure_for_matching, 2 * spectral_nodes)
    cut_size = max(3, int(np.floor(time_tail_fraction * (times.size - 1))) + 1)
    truncated = match(
        times[:cut_size], structure_for_matching[:cut_size], 2 * spectral_nodes
    )
    coarse_kernel = np.asarray(full_coarse["reconstructed_exact_prefix_kernel"])
    fine_kernel = np.asarray(full_fine["reconstructed_exact_prefix_kernel"])
    truncated_kernel = np.asarray(truncated["reconstructed_exact_prefix_kernel"])
    spectral_change = _relative_change(coarse_kernel, fine_kernel)
    tail_change = _relative_change(truncated_kernel, fine_kernel)
    spectral_residual = float(full_fine["spectral_fit"]["relative_residual"])
    top_level_residual = float(full_fine["top_level_relative_residual"])
    fine_weights = np.asarray(full_fine["spectral_weights"], dtype=float)
    fine_frequencies = np.asarray(full_fine["spectral_frequencies"], dtype=float)

    def complete_time_domain(maximum_dt: float):
        steps = int(np.ceil(times[-1] / maximum_dt))
        grid = np.linspace(0.0, times[-1], steps + 1)
        terminator = np.cos(grid[:, None] * fine_frequencies[None, :]) @ fine_weights
        kernel = mori_hierarchy_kernel_from_terminator(
            grid,
            terminator,
            mu0=float(full_fine["exact_mu0"]),
            squared_recurrents=np.asarray(
                full_fine["exact_squared_recurrents"], dtype=float
            ),
        )
        structure = density_structure_from_mori_kernels(
            grid,
            np.asarray([waves[wave_index]]),
            kernel[:, None],
        )[:, 0]
        return grid, terminator, kernel, structure

    coarse_time = complete_time_domain(hierarchy_dt)
    fine_time = complete_time_domain(0.5 * hierarchy_dt)
    refined_times, refined_terminator, exact_kernel_time, exact_prefix_structure = fine_time
    actual_hierarchy_dt = float(refined_times[1] - refined_times[0])
    coarse_structure_on_fine = PchipInterpolator(
        coarse_time[0], coarse_time[3], extrapolate=False
    )(refined_times)
    hierarchy_dt_change = float(
        np.max(np.abs(coarse_structure_on_fine - exact_prefix_structure))
        / max(np.max(np.abs(exact_prefix_structure)), np.finfo(float).tiny)
    )
    raw_structure_refined = PchipInterpolator(
        times, raw_structure_mean.real, extrapolate=False
    )(refined_times)

    return {
        "schema": 1,
        "method": "replicated_full_matrix_colored_continuum_behind_exact_finite_k_mu16",
        "inputs": {
            "trajectory_data_used": False,
            "target_coefficients_used": False,
            "replicas": len(payloads),
            "seeds": seeds,
            "wave_index": wave_index,
            "wavenumber": float(waves[wave_index]),
            "laplace_frequencies": z,
            "spectral_nodes_coarse": spectral_nodes,
            "spectral_nodes_fine": 2 * spectral_nodes,
            "spectral_maximum": spectral_maximum,
            "time_tail_fraction": time_tail_fraction,
            "requested_hierarchy_dt_maximum": hierarchy_dt,
            "actual_hierarchy_dt": actual_hierarchy_dt,
        },
        "replicated_colored_memory": {
            "times": times,
            "mean_complex": mean_complex,
            "sem_complex_norm": sem_complex,
            "imaginary_to_real_l2_fraction": imaginary_fraction,
            "maximum_pointwise_relative_sem": maximum_relative_sem,
            "maximum_sem_in_zero_time_memory_units": maximum_sem_in_zero_time_units,
            "l2_sem_to_signal_ratio": l2_sem_to_signal_ratio,
        },
        "fine_exact_prefix_match": full_fine,
        "time_domain_microscopic_completion": {
            "times": refined_times,
            "interpolated_normalized_colored_terminator": refined_terminator,
            "exact_prefix_mori_kernel": exact_kernel_time,
            "exact_prefix_structure_factor_over_chi": exact_prefix_structure,
            "raw_full_matrix_structure_factor_mean_on_source_grid": raw_structure_mean,
            "raw_full_matrix_structure_factor_real_interpolated": raw_structure_refined,
            "maximum_absolute_structure_change": float(
                np.max(np.abs(exact_prefix_structure - raw_structure_refined))
            ),
            "short_time_moments_supplied_by_exact_prefix_not_hydrodynamic_contact": True,
            "terminator_obtained_by_top_level_continuity_inversion": True,
        },
        "convergence": {
            "spectral_node_maximum_relative_kernel_change": spectral_change,
            "time_tail_maximum_relative_kernel_change": tail_change,
            "fine_spectral_relative_residual": spectral_residual,
            "fine_top_level_relative_residual": top_level_residual,
            "hierarchy_dt_halving_maximum_relative_structure_change": hierarchy_dt_change,
        },
        "gates": {
            "full_non_diagonal_diffusion_and_fdt_noise_propagated": True,
            "white_hydrodynamic_contact_excluded": True,
            "exact_finite_k_mu16_prefix_preserved": bool(
                full_fine["exact_moment_order_preserved"] == 16
            ),
            "positive_continuum_terminator": bool(
                np.min(full_fine["spectral_weights"]) >= 0.0
            ),
            "hydrodynamic_input_inside_exact_moment_interval": bool(
                full_fine["hydrodynamic_input_inside_exact_moment_interval"]
            ),
            "top_level_match_converged_at_2_percent": bool(
                top_level_residual <= 0.02
            ),
            "spectral_node_converged_at_2_percent": bool(spectral_change <= 0.02),
            "finite_time_tail_converged_at_5_percent": bool(tail_change <= 0.05),
            "hierarchy_dt_converged_at_2_percent": bool(hierarchy_dt_change <= 0.02),
            "replica_sem_below_5_percent_of_zero_time_memory": bool(
                maximum_sem_in_zero_time_units <= 0.05
            ),
            "zero_field_limit_complete": False,
            "physical_F1_certified": False,
        },
        "scope": {
            "finite_pole_count_assumed": False,
            "second_hydrodynamic_field_assumed": False,
            "target_fit_performed": False,
            "finite_field_regulator_only": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificates", type=Path, nargs="+")
    parser.add_argument("--laplace", type=float, nargs="+", required=True)
    parser.add_argument("--spectral-nodes", type=int, default=256)
    parser.add_argument("--spectral-maximum", type=float, default=20.0)
    parser.add_argument("--time-tail-fraction", type=float, default=0.75)
    parser.add_argument("--hierarchy-dt", type=float, default=0.5)
    parser.add_argument("--wave-index", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payloads = [json.loads(path.read_text()) for path in args.certificates]
    result = derive(
        payloads,
        laplace_frequencies=np.asarray(args.laplace, dtype=float),
        spectral_nodes=args.spectral_nodes,
        spectral_maximum=args.spectral_maximum,
        time_tail_fraction=args.time_tail_fraction,
        hierarchy_dt=args.hierarchy_dt,
        wave_index=args.wave_index,
    )
    result["sources"] = {str(path): _sha256(path) for path in args.certificates}
    encoded = json.dumps(_jsonable(result), indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
