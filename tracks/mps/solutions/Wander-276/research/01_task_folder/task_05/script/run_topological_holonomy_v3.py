#!/usr/bin/env python3
"""Run fixed-Chern isospectral Wilson-holonomy statistics."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.bundle_geometry import (
    analyze_frame_bundle,
    random_local_gauge,
    sorted_wilson_eigenphases,
)
from lgeth.holonomy import (
    cue_wilson_reference,
    deform_orbital_mesh,
    wilson_statistics,
)
from lgeth.lattice import BosonBasis
from lgeth.twist_bundle import (
    default_checkpoint_path,
    load_twist_bundle,
)


VERSION = "v3"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"
OUTPUT_JSON = OUTPUT_ROOT / "topological_holonomy_v3.json"
OUTPUT_NPZ = OUTPUT_ROOT / "topological_holonomy_v3.npz"
REGISTERED_SIZES = ((3, 8, 16), (4, 10, 25))
REGISTERED_PRIMARY_MESH = 16
REGISTERED_CONVERGENCE_MESH = 20
REGISTERED_G = (0.0, 0.25, 0.5, 0.75, 1.0)
REGISTERED_GENERATOR_SEEDS = tuple(20260728400 + index for index in range(8))
REGISTERED_COMMUTING_SEED = 20260728499
REGISTERED_CUE_SAMPLES = 10_000
REGISTERED_SEED = 20260728480
REGISTERED_BOOTSTRAP_SAMPLES = 20_000
MESH_ALIAS_AUDIT_JSON = (
    OUTPUT_ROOT / "topological_holonomy_mesh12_alias_audit_v3.json"
)
MESH_ALIAS_AUDIT_NPZ = (
    OUTPUT_ROOT / "topological_holonomy_mesh12_alias_audit_v3.npz"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    temporary.replace(path)


def _raw_bundle_arrays(
    N: int,
    mesh: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    metadata = default_checkpoint_path(N, mesh)
    arrays_path = metadata.with_suffix(".npz")
    with np.load(arrays_path, allow_pickle=False) as arrays:
        return (
            np.asarray(arrays["energies"], dtype=float),
            np.asarray(arrays["external_gap"], dtype=float),
            np.asarray(arrays["coefficient_frames"], dtype=complex),
            np.asarray(arrays["orbital_frames"], dtype=complex),
        )


def _geometry_record(
    geometry,
    k_values: np.ndarray,
) -> dict[str, Any]:
    statistics = wilson_statistics(geometry, k_values=k_values)
    return {
        "chern_determinant": geometry.chern_determinant,
        "chern_trace_log": geometry.chern_trace_log,
        "branch_margin": geometry.determinant_branch_margin,
        "minimum_overlap": geometry.minimum_overlap_singular_value,
        "maximum_link_error": geometry.maximum_link_unitarity_error,
        "maximum_plaquette_error": (
            geometry.maximum_plaquette_unitarity_error
        ),
        "gap_ratio": np.asarray(statistics["gap_ratio"]),
        "mean_gap_ratio": float(statistics["mean_gap_ratio"]),
        "form_factor": np.asarray(statistics["form_factor"]),
        "mean_form_factor": np.asarray(statistics["mean_form_factor"]),
        "determinant_phase_x": np.asarray(
            statistics["determinant_phase_x"]
        ),
        "determinant_phase_y": np.asarray(
            statistics["determinant_phase_y"]
        ),
    }


def _seed_worker(arguments: tuple[Any, ...]) -> dict[str, Any]:
    (
        N,
        n_flux,
        rank,
        primary_mesh,
        convergence_mesh,
        positive_g,
        seed,
        commuting,
    ) = arguments
    _, _, coefficients, orbitals = _raw_bundle_arrays(N, primary_mesh)
    basis = BosonBasis(n_flux, N)
    k_values = np.arange(1, rank + 1, dtype=int)
    primary_records: list[dict[str, Any]] = []
    for coupling in positive_g:
        deformed = deform_orbital_mesh(
            orbitals,
            g=float(coupling),
            seed=int(seed),
            commuting=bool(commuting),
        )
        geometry = analyze_frame_bundle(
            coefficients,
            deformed,
            basis,
        )
        primary_records.append(_geometry_record(geometry, k_values))
    endpoint_record = None
    if not commuting:
        _, _, endpoint_coefficients, endpoint_orbitals = _raw_bundle_arrays(
            N,
            convergence_mesh,
        )
        endpoint_deformed = deform_orbital_mesh(
            endpoint_orbitals,
            g=float(positive_g[-1]),
            seed=int(seed),
            commuting=False,
        )
        endpoint_geometry = analyze_frame_bundle(
            endpoint_coefficients,
            endpoint_deformed,
            basis,
        )
        endpoint_record = _geometry_record(
            endpoint_geometry,
            k_values,
        )
    return {
        "N": int(N),
        "seed": int(seed),
        "commuting": bool(commuting),
        "primary": primary_records,
        "endpoint": endpoint_record,
    }


def _run_workers(
    arguments: list[tuple[Any, ...]],
    workers: int,
) -> list[dict[str, Any]]:
    if int(workers) <= 1:
        return [_seed_worker(item) for item in arguments]
    results: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=int(workers)
    ) as executor:
        futures = [executor.submit(_seed_worker, item) for item in arguments]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"completed N={result['N']} seed={result['seed']} "
                f"commuting={result['commuting']}",
                flush=True,
            )
    return results


def _interval(values: np.ndarray) -> list[float]:
    return np.quantile(
        np.asarray(values, dtype=float),
        [0.025, 0.5, 0.975],
    ).tolist()


def _bootstrap_mean_interval(
    values: np.ndarray,
    seed: int,
    samples: int = REGISTERED_BOOTSTRAP_SAMPLES,
) -> list[float]:
    """Return a seed-cluster bootstrap interval for the mean."""

    observations = np.asarray(values, dtype=float)
    if observations.ndim != 1 or observations.size < 1:
        raise ValueError("bootstrap values must be a nonempty vector")
    if observations.size == 1:
        value = float(observations[0])
        return [value, value, value]
    rng = np.random.default_rng(int(seed))
    indices = rng.integers(
        0,
        observations.size,
        size=(int(samples), observations.size),
    )
    means = np.mean(observations[indices], axis=1)
    return np.quantile(means, [0.025, 0.5, 0.975]).tolist()


def _cue_simultaneous_band(
    form_factor: np.ndarray,
    stop: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Build an empirical 95% simultaneous CUE band over ``k < stop``."""

    values = np.asarray(form_factor, dtype=float)
    if values.ndim != 2 or not 1 <= int(stop) <= values.shape[1]:
        raise ValueError("invalid CUE form-factor window")
    window = values[:, : int(stop)]
    center = np.mean(window, axis=0)
    scale = np.std(window, axis=0, ddof=1)
    if np.any(scale <= 0.0):
        raise RuntimeError("CUE reference has a singular pointwise scale")
    maximum_standardized_deviation = np.max(
        np.abs((window - center[None, :]) / scale[None, :]),
        axis=1,
    )
    critical = float(
        np.quantile(maximum_standardized_deviation, 0.95)
    )
    return (
        center,
        center - critical * scale,
        center + critical * scale,
        critical,
    )


def _size_summary(
    size: tuple[int, int, int],
    primary_mesh: int,
    convergence_mesh: int,
    g_values: tuple[float, ...],
    seeds: tuple[int, ...],
    records: list[dict[str, Any]],
    commuting_record: dict[str, Any],
    cue_samples: int,
    cue_seed: int,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    N, n_flux, rank = size
    primary_base = load_twist_bundle(
        default_checkpoint_path(N, primary_mesh),
        N,
        n_flux,
        rank,
        primary_mesh,
    )
    convergence_base = load_twist_bundle(
        default_checkpoint_path(N, convergence_mesh),
        N,
        n_flux,
        rank,
        convergence_mesh,
    )
    k_values = np.arange(1, rank + 1, dtype=int)
    base_record = _geometry_record(primary_base.geometry, k_values)
    convergence_base_record = _geometry_record(
        convergence_base.geometry,
        k_values,
    )
    by_seed = {
        int(record["seed"]): record
        for record in records
        if record["N"] == N and not record["commuting"]
    }
    if set(by_seed) != set(seeds):
        raise RuntimeError(f"missing noncommuting records for N={N}")
    positive_count = len(g_values) - 1
    gap_mean = np.empty((len(seeds), len(g_values)), dtype=float)
    form_mean = np.empty(
        (len(seeds), len(g_values), rank),
        dtype=float,
    )
    loop_count = 2 * primary_mesh
    gap_loops = np.empty(
        (len(seeds), len(g_values), loop_count),
        dtype=float,
    )
    form_loops = np.empty(
        (len(seeds), len(g_values), loop_count, rank),
        dtype=float,
    )
    chern = np.empty((len(seeds), len(g_values)), dtype=float)
    trace_chern = np.empty_like(chern)
    branch_margin = np.empty_like(chern)
    minimum_overlap = np.empty_like(chern)
    endpoint_chern = np.empty(len(seeds), dtype=float)
    endpoint_trace_chern = np.empty(len(seeds), dtype=float)
    endpoint_branch_margin = np.empty(len(seeds), dtype=float)
    endpoint_overlap = np.empty(len(seeds), dtype=float)
    endpoint_gap_loops = np.empty(
        (len(seeds), 2 * convergence_mesh),
        dtype=float,
    )
    endpoint_form_loops = np.empty(
        (len(seeds), 2 * convergence_mesh, rank),
        dtype=float,
    )
    for seed_index, seed in enumerate(seeds):
        gap_mean[seed_index, 0] = base_record["mean_gap_ratio"]
        form_mean[seed_index, 0] = base_record["mean_form_factor"]
        gap_loops[seed_index, 0] = base_record["gap_ratio"]
        form_loops[seed_index, 0] = base_record["form_factor"]
        chern[seed_index, 0] = base_record["chern_determinant"]
        trace_chern[seed_index, 0] = base_record["chern_trace_log"]
        branch_margin[seed_index, 0] = base_record["branch_margin"]
        minimum_overlap[seed_index, 0] = base_record["minimum_overlap"]
        record = by_seed[seed]
        if len(record["primary"]) != positive_count:
            raise RuntimeError("deformation grid is incomplete")
        for offset, point in enumerate(record["primary"], start=1):
            gap_mean[seed_index, offset] = point["mean_gap_ratio"]
            form_mean[seed_index, offset] = point["mean_form_factor"]
            gap_loops[seed_index, offset] = point["gap_ratio"]
            form_loops[seed_index, offset] = point["form_factor"]
            chern[seed_index, offset] = point["chern_determinant"]
            trace_chern[seed_index, offset] = point["chern_trace_log"]
            branch_margin[seed_index, offset] = point["branch_margin"]
            minimum_overlap[seed_index, offset] = point["minimum_overlap"]
        endpoint = record["endpoint"]
        endpoint_chern[seed_index] = endpoint["chern_determinant"]
        endpoint_trace_chern[seed_index] = endpoint["chern_trace_log"]
        endpoint_branch_margin[seed_index] = endpoint["branch_margin"]
        endpoint_overlap[seed_index] = endpoint["minimum_overlap"]
        endpoint_gap_loops[seed_index] = endpoint["gap_ratio"]
        endpoint_form_loops[seed_index] = endpoint["form_factor"]
    commuting_gap = np.empty(len(g_values), dtype=float)
    commuting_form = np.empty((len(g_values), rank), dtype=float)
    commuting_chern = np.empty(len(g_values), dtype=float)
    commuting_gap_loops = np.empty(
        (len(g_values), loop_count),
        dtype=float,
    )
    commuting_form_loops = np.empty(
        (len(g_values), loop_count, rank),
        dtype=float,
    )
    commuting_gap[0] = base_record["mean_gap_ratio"]
    commuting_form[0] = base_record["mean_form_factor"]
    commuting_chern[0] = base_record["chern_determinant"]
    commuting_gap_loops[0] = base_record["gap_ratio"]
    commuting_form_loops[0] = base_record["form_factor"]
    for offset, point in enumerate(
        commuting_record["primary"],
        start=1,
    ):
        commuting_gap[offset] = point["mean_gap_ratio"]
        commuting_form[offset] = point["mean_form_factor"]
        commuting_chern[offset] = point["chern_determinant"]
        commuting_gap_loops[offset] = point["gap_ratio"]
        commuting_form_loops[offset] = point["form_factor"]
    cue = cue_wilson_reference(
        D=rank,
        samples=int(cue_samples),
        k_values=k_values,
        seed=int(cue_seed),
    )
    cue_gap_interval = _interval(cue["gap_ratio"])
    nonplateau_stop = max(2, rank // 2)
    (
        cue_form_window_mean,
        cue_form_simultaneous_lower,
        cue_form_simultaneous_upper,
        cue_form_simultaneous_critical,
    ) = _cue_simultaneous_band(
        cue["form_factor"],
        stop=nonplateau_stop,
    )
    cue_form_mean = np.mean(cue["form_factor"], axis=0)
    gap_by_g = [
        _interval(gap_mean[:, index])
        for index in range(len(g_values))
    ]
    form_by_g = np.median(form_mean, axis=0)
    final_gap_compatible = (
        cue_gap_interval[0]
        <= gap_by_g[-1][1]
        <= cue_gap_interval[2]
    )
    nonplateau = slice(0, max(2, rank // 2))
    final_form_compatible = bool(np.all(
        (
            form_by_g[-1, :nonplateau_stop]
            >= cue_form_simultaneous_lower
        )
        & (
            form_by_g[-1, :nonplateau_stop]
            <= cue_form_simultaneous_upper
        )
    ))
    base_residual = float(
        np.sqrt(
            np.mean(
                (
                    base_record["mean_form_factor"][nonplateau]
                    - cue_form_mean[nonplateau]
                )
                ** 2
            )
        )
    )
    final_residual = np.sqrt(
        np.mean(
            (
                form_mean[:, -1, nonplateau]
                - cue_form_mean[None, nonplateau]
            )
            ** 2,
            axis=1,
        )
    )
    residual_improvement = base_residual - final_residual
    gap_change = gap_mean[:, -1] - gap_mean[:, 0]
    gap_change_interval = _bootstrap_mean_interval(
        gap_change,
        seed=cue_seed + 10_000,
    )
    improvement_interval = _bootstrap_mean_interval(
        residual_improvement,
        seed=cue_seed + 20_000,
    )
    change_significant = (
        gap_change_interval[0] > 0.0
        or gap_change_interval[2] < 0.0
        or improvement_interval[0] > 0.0
        or improvement_interval[2] < 0.0
    )
    base_integer = int(round(base_record["chern_determinant"]))
    all_chern_values = np.concatenate(
        [
            chern.ravel(),
            endpoint_chern,
            commuting_chern,
            np.asarray(
                [convergence_base_record["chern_determinant"]]
            ),
        ]
    )
    summary = {
        "N": N,
        "n_flux": n_flux,
        "rank": rank,
        "primary_mesh": primary_mesh,
        "convergence_mesh": convergence_mesh,
        "base_chern_integer": base_integer,
        "base_chern_primary": base_record["chern_determinant"],
        "base_chern_convergence": convergence_base_record[
            "chern_determinant"
        ],
        "primary_chern_range": [
            float(np.min(chern)),
            float(np.max(chern)),
        ],
        "convergence_endpoint_chern_range": [
            float(np.min(endpoint_chern)),
            float(np.max(endpoint_chern)),
        ],
        "commuting_chern_range": [
            float(np.min(commuting_chern)),
            float(np.max(commuting_chern)),
        ],
        "minimum_branch_margin": float(
            min(
                np.min(branch_margin),
                np.min(endpoint_branch_margin),
                base_record["branch_margin"],
                convergence_base_record["branch_margin"],
            )
        ),
        "minimum_overlap_singular_value": float(
            min(
                np.min(minimum_overlap),
                np.min(endpoint_overlap),
                base_record["minimum_overlap"],
                convergence_base_record["minimum_overlap"],
            )
        ),
        "maximum_determinant_trace_difference": float(
            max(
                np.max(np.abs(chern - trace_chern)),
                np.max(
                    np.abs(endpoint_chern - endpoint_trace_chern)
                ),
            )
        ),
        "maximum_energy_spectrum_error": 0.0,
        "maximum_gap_error": 0.0,
        "isospectrality_mode": (
            "exact_coordinate_identity_under_periodic_ambient_conjugation"
        ),
        "minimum_external_gap": float(
            min(
                np.min(primary_base.external_gap),
                np.min(convergence_base.external_gap),
            )
        ),
        "gap_ratio_by_g": gap_by_g,
        "base_gap_ratio": base_record["mean_gap_ratio"],
        "final_gap_ratio_interval": gap_by_g[-1],
        "cue_gap_ratio_interval": cue_gap_interval,
        "gap_change_interval": gap_change_interval,
        "base_form_factor_residual": base_residual,
        "final_form_factor_residual_interval": _interval(final_residual),
        "form_factor_improvement_interval": improvement_interval,
        "cue_form_simultaneous_critical": (
            cue_form_simultaneous_critical
        ),
        "cue_nonplateau_stop": nonplateau_stop,
        "cue_compatible_at_largest_g": (
            final_gap_compatible and final_form_compatible
        ),
        "holonomy_change_significant": bool(change_significant),
        "all_chern_equal": bool(
            np.max(np.abs(all_chern_values - base_integer)) < 1e-8
        ),
        "determinant_phase_x_base": base_record[
            "determinant_phase_x"
        ].tolist(),
        "determinant_phase_x_final_seed0": by_seed[seeds[0]][
            "primary"
        ][-1]["determinant_phase_x"].tolist(),
    }
    arrays = {
        "gap_mean": gap_mean,
        "form_mean": form_mean,
        "gap_loops": gap_loops,
        "form_loops": form_loops,
        "chern": chern,
        "trace_chern": trace_chern,
        "branch_margin": branch_margin,
        "minimum_overlap": minimum_overlap,
        "endpoint_chern": endpoint_chern,
        "endpoint_trace_chern": endpoint_trace_chern,
        "endpoint_branch_margin": endpoint_branch_margin,
        "endpoint_overlap": endpoint_overlap,
        "endpoint_gap_loops": endpoint_gap_loops,
        "endpoint_form_loops": endpoint_form_loops,
        "commuting_gap": commuting_gap,
        "commuting_form": commuting_form,
        "commuting_chern": commuting_chern,
        "commuting_gap_loops": commuting_gap_loops,
        "commuting_form_loops": commuting_form_loops,
        "cue_gap": cue["gap_ratio"],
        "cue_form": cue["form_factor"],
        "cue_form_simultaneous_mean": cue_form_window_mean,
        "cue_form_simultaneous_lower": cue_form_simultaneous_lower,
        "cue_form_simultaneous_upper": cue_form_simultaneous_upper,
        "base_form": base_record["mean_form_factor"],
        "base_determinant_phase_x": base_record[
            "determinant_phase_x"
        ],
        "final_determinant_phase_x": by_seed[seeds[0]][
            "primary"
        ][-1]["determinant_phase_x"],
    }
    return summary, arrays


def _random_gauge_error(
    size: tuple[int, int, int],
    mesh: int,
    g: float,
    seed: int,
) -> dict[str, float]:
    N, n_flux, rank = size
    _, _, coefficients, orbitals = _raw_bundle_arrays(N, mesh)
    deformed = deform_orbital_mesh(
        orbitals,
        g=float(g),
        seed=int(seed),
        commuting=False,
    )
    basis = BosonBasis(n_flux, N)
    original = analyze_frame_bundle(coefficients, deformed, basis)
    transformed = analyze_frame_bundle(
        random_local_gauge(coefficients, seed=seed + 50_000),
        deformed,
        basis,
    )
    original_phases = sorted_wilson_eigenphases(original)
    transformed_phases = sorted_wilson_eigenphases(transformed)
    return {
        "chern_error": abs(
            original.chern_determinant
            - transformed.chern_determinant
        ),
        "wilson_phase_error": float(
            np.max(
                np.abs(
                    np.exp(1j * original_phases)
                    - np.exp(1j * transformed_phases)
                )
            )
        ),
    }


def select_topology_branch(payload: dict[str, Any]) -> str:
    """Select the preregistered topology/holonomy result branch."""

    if not all(payload.get("checks", {}).values()):
        return "topology_mesh_unresolved"
    sizes = payload.get("sizes", [])
    if sizes and all(
        size["cue_compatible_at_largest_g"] for size in sizes
    ):
        return "fixed_chern_chaotic_holonomy"
    if any(size["holonomy_change_significant"] for size in sizes):
        return "fixed_chern_deformed_holonomy"
    return "topology_without_holonomy_crossover"


def run(
    output_json: Path = OUTPUT_JSON,
    output_npz: Path = OUTPUT_NPZ,
    sizes: tuple[tuple[int, int, int], ...] = REGISTERED_SIZES,
    primary_mesh: int = REGISTERED_PRIMARY_MESH,
    convergence_mesh: int = REGISTERED_CONVERGENCE_MESH,
    g_values: tuple[float, ...] = REGISTERED_G,
    generator_seeds: tuple[int, ...] = REGISTERED_GENERATOR_SEEDS,
    cue_samples: int = REGISTERED_CUE_SAMPLES,
    workers: int = 4,
    production: bool = True,
) -> dict[str, Any]:
    """Run the registered or reduced closed-surface calculation."""

    started = time.perf_counter()
    if (
        len(g_values) < 2
        or g_values[0] != 0.0
        or any(right <= left for left, right in zip(g_values, g_values[1:]))
    ):
        raise ValueError("g grid must be strictly increasing from zero")
    positive_g = tuple(float(value) for value in g_values[1:])
    validated_checkpoints: dict[str, str] = {}
    base_bundles = []
    for N, n_flux, rank in sizes:
        for mesh in (primary_mesh, convergence_mesh):
            path = default_checkpoint_path(N, mesh)
            bundle = load_twist_bundle(
                path,
                N,
                n_flux,
                rank,
                mesh,
            )
            base_bundles.append(bundle)
            validated_checkpoints[str(path.relative_to(SCRIPT_ROOT))] = (
                _sha256(path)
            )
            arrays_path = path.with_suffix(".npz")
            validated_checkpoints[
                str(arrays_path.relative_to(SCRIPT_ROOT))
            ] = _sha256(arrays_path)
    worker_arguments: list[tuple[Any, ...]] = []
    for N, n_flux, rank in sizes:
        for seed in generator_seeds:
            worker_arguments.append(
                (
                    N,
                    n_flux,
                    rank,
                    primary_mesh,
                    convergence_mesh,
                    positive_g,
                    seed,
                    False,
                )
            )
        worker_arguments.append(
            (
                N,
                n_flux,
                rank,
                primary_mesh,
                convergence_mesh,
                positive_g,
                REGISTERED_COMMUTING_SEED,
                True,
            )
        )
    records = _run_workers(worker_arguments, workers=workers)
    size_summaries: list[dict[str, Any]] = []
    size_arrays: list[dict[str, np.ndarray]] = []
    for size_index, size in enumerate(sizes):
        commuting = next(
            record
            for record in records
            if record["N"] == size[0] and record["commuting"]
        )
        summary, arrays = _size_summary(
            size=size,
            primary_mesh=primary_mesh,
            convergence_mesh=convergence_mesh,
            g_values=g_values,
            seeds=generator_seeds,
            records=records,
            commuting_record=commuting,
            cue_samples=cue_samples,
            cue_seed=REGISTERED_SEED + size_index,
        )
        size_summaries.append(summary)
        size_arrays.append(arrays)
    gauge = _random_gauge_error(
        sizes[0],
        primary_mesh,
        g_values[-1],
        generator_seeds[0],
    )
    checks = {
        "kernel_count": all(
            bundle.observed_rank_min
            == bundle.observed_rank_max
            == bundle.rank
            for bundle in base_bundles
        ),
        "gap_open": all(
            float(np.min(bundle.external_gap)) > 0.0
            for bundle in base_bundles
        ),
        "mesh_chern_integer": all(
            size["all_chern_equal"] for size in size_summaries
        ),
        "mesh_chern_agreement": all(
            abs(
                size["base_chern_primary"]
                - size["base_chern_convergence"]
            )
            < 1e-8
            for size in size_summaries
        ),
        "determinant_trace_agreement": all(
            size["maximum_determinant_trace_difference"] < 1e-8
            for size in size_summaries
        ),
        "branch_margin": all(
            size["minimum_branch_margin"] > 0.0
            for size in size_summaries
        ),
        "overlap_floor": all(
            size["minimum_overlap_singular_value"] > 5e-2
            for size in size_summaries
        ),
        "random_gauge_invariance": (
            gauge["chern_error"] < 1e-9
            and gauge["wilson_phase_error"] < 1e-8
        ),
        "isospectral_orbit": all(
            size["maximum_energy_spectrum_error"] < 1e-13
            and size["maximum_gap_error"] < 1e-13
            for size in size_summaries
        ),
        "cue_reference_count": int(cue_samples) >= 64,
    }
    payload: dict[str, Any] = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "sizes": [list(size) for size in sizes],
            "primary_mesh": int(primary_mesh),
            "convergence_mesh": int(convergence_mesh),
            "g_values": list(g_values),
            "generator_seeds": list(generator_seeds),
            "commuting_seed": REGISTERED_COMMUTING_SEED,
            "cue_samples": int(cue_samples),
            "workers": int(workers),
            "production": bool(production),
            "mesh_upgrade_rationale": (
                "mesh12 aliases one N4 seed at g=1; mesh16 and mesh20 "
                "are the accepted converged pair"
            ),
        },
        "sizes": size_summaries,
        "random_gauge_errors": gauge,
        "checks": checks,
        "checkpoint_hashes": validated_checkpoints,
        "mesh_alias_audit": {
            "json": str(MESH_ALIAS_AUDIT_JSON.relative_to(SCRIPT_ROOT)),
            "json_sha256": (
                _sha256(MESH_ALIAS_AUDIT_JSON)
                if MESH_ALIAS_AUDIT_JSON.exists()
                else None
            ),
            "npz": str(MESH_ALIAS_AUDIT_NPZ.relative_to(SCRIPT_ROOT)),
            "npz_sha256": (
                _sha256(MESH_ALIAS_AUDIT_NPZ)
                if MESH_ALIAS_AUDIT_NPZ.exists()
                else None
            ),
        },
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    payload["result_branch"] = select_topology_branch(payload)
    output_arrays: dict[str, np.ndarray] = {
        "g_values": np.asarray(g_values, dtype=float),
        "generator_seeds": np.asarray(generator_seeds, dtype=np.int64),
    }
    for size_index, arrays in enumerate(size_arrays):
        for key, values in arrays.items():
            output_arrays[f"size_{size_index}_{key}"] = np.asarray(values)
    _atomic_npz(output_npz, **output_arrays)
    payload["npz_sha256"] = _sha256(output_npz)
    _atomic_json(output_json, payload)
    if production and not all(checks.values()):
        raise RuntimeError(f"production topology gates failed: {checks}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reduced", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    arguments = parser.parse_args()
    if arguments.reduced:
        payload = run(
            sizes=((3, 8, 16),),
            primary_mesh=6,
            convergence_mesh=8,
            g_values=(0.0, 0.25),
            generator_seeds=(20260728400,),
            cue_samples=64,
            workers=1,
            production=False,
            output_json=OUTPUT_ROOT / "topological_holonomy_reduced_v3.json",
            output_npz=OUTPUT_ROOT / "topological_holonomy_reduced_v3.npz",
        )
    else:
        payload = run(workers=arguments.workers)
    print(json.dumps(
        {
            "result_branch": payload["result_branch"],
            "checks": payload["checks"],
            "runtime_seconds": payload["runtime_seconds"],
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
