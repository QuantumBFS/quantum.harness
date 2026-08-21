#!/usr/bin/env python3
"""Generate the spectral-silence and independent-chaos control artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.channels import (
    build_physical_channel_cache,
    cached_channel,
)
from lgeth.controls import (
    fixed_projector_spectral_ensemble,
    fourier_tangent_pairs,
    scrambled_tangent_pair,
)
from lgeth.form_factors import (
    atom_raw_decomposition,
    degenerate_energy_form_factor,
    finite_jacobi_form_factor,
    form_factor_parts,
)
from lgeth.jacobi import normalized_curvature
from lgeth.statistics import unfold_spectra


VERSION = "v2"
REGISTERED_SEED = 20260728210
G_VALUES = np.asarray(
    [0.0, 0.02, 0.05, 0.10, 0.20, 0.40, 0.70, 1.0],
    dtype=float,
)
ALPHA_VALUES = np.asarray(
    [0.0, 0.10, 0.20, 0.35, 0.50, 0.70, 0.85, 1.0],
    dtype=float,
)
TIMES = np.linspace(0.0, 3.0, 121)
REGISTERED_SAMPLES_PER_G = 4000
REGISTERED_SPECTRAL_SAMPLES = 4000
REGISTERED_QUADRATURE_ORDER = 512
REGISTERED_RANK_FORM_FACTOR_SAMPLES = 500
RANK_LABELS = ("n8", "n10", "n12", "n14", "n16", "n18", "n20")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _default_output(name: str) -> Path:
    return Path(__file__).resolve().parent / "output" / name


def _connected_parts(spectra: np.ndarray) -> tuple[np.ndarray, ...]:
    unfolded = unfold_spectra(spectra, "ensemble_cdf")
    parts = form_factor_parts(unfolded, TIMES)
    return parts.raw, parts.disconnected, parts.connected


def _structured_control(
    cache,
) -> dict[str, np.ndarray]:
    pairs = fourier_tangent_pairs(5)
    spectra = np.empty((len(pairs), cache.rank), dtype=np.float32)
    active_ranks = np.empty(len(pairs), dtype=np.int16)
    unique_counts = np.empty(len(pairs), dtype=np.int16)
    momenta = np.empty((len(pairs), 2), dtype=np.int16)
    orbit_keys = np.empty((len(pairs), 2), dtype=np.int16)
    orbit_lookup = {
        key: index
        for index, key in enumerate(
            sorted({pair.orbit_key for pair in pairs})
        )
    }
    orbit_id = np.empty(len(pairs), dtype=np.int16)
    for index, pair in enumerate(pairs):
        channel_v = cached_channel(pair.v, cache)
        channel_w = cached_channel(pair.w, cache)
        normalized = normalized_curvature(
            channel_v,
            channel_w,
            rtol=1e-10,
        )
        spectrum = np.linalg.eigvalsh(normalized.omega)
        spectra[index] = spectrum
        active_ranks[index] = normalized.rank
        unique_counts[index] = np.unique(
            np.round(spectrum, 10)
        ).size
        momenta[index] = (pair.kx, pair.ky)
        orbit_keys[index] = pair.orbit_key
        orbit_id[index] = orbit_lookup[pair.orbit_key]
    raw, disconnected, connected = _connected_parts(spectra)
    return {
        "spectra": spectra,
        "active_ranks": active_ranks,
        "unique_counts": unique_counts,
        "momenta": momenta,
        "orbit_keys": orbit_keys,
        "orbit_id": orbit_id,
        "raw": raw,
        "disconnected": disconnected,
        "connected": connected,
    }


def _geometry_axis(
    cache,
    samples_per_g: int,
    seed: int,
) -> dict[str, np.ndarray]:
    count = int(samples_per_g)
    if count < 24:
        raise ValueError("samples_per_g must be at least 24")
    positive_g = G_VALUES[1:]
    pairs = fourier_tangent_pairs(5)
    spectra = np.empty(
        (positive_g.size, count, cache.rank),
        dtype=np.float32,
    )
    active_ranks = np.empty(
        (positive_g.size, count),
        dtype=np.int16,
    )
    unique_counts = np.empty_like(active_ranks)
    momentum_index = np.empty_like(active_ranks)
    seed_block = np.empty_like(active_ranks)
    child_sequences = np.random.SeedSequence(seed).spawn(
        positive_g.size
    )
    for g_index, (g, child) in enumerate(
        zip(positive_g, child_sequences, strict=True)
    ):
        rng = np.random.default_rng(child)
        blocks = np.array_split(np.arange(count), 8)
        for block, indices in enumerate(blocks):
            for sample in indices:
                pair_index = int(sample % len(pairs))
                pair = pairs[pair_index]
                random_v = rng.normal(size=pair.v.size)
                random_w = rng.normal(size=pair.w.size)
                coefficients_v, coefficients_w = scrambled_tangent_pair(
                    pair,
                    random_v,
                    random_w,
                    float(g),
                    cache.tangent_gram,
                )
                channel_v = cached_channel(coefficients_v, cache)
                channel_w = cached_channel(coefficients_w, cache)
                normalized = normalized_curvature(
                    channel_v,
                    channel_w,
                    rtol=1e-10,
                )
                spectrum = np.linalg.eigvalsh(normalized.omega)
                spectra[g_index, sample] = spectrum
                active_ranks[g_index, sample] = normalized.rank
                unique_counts[g_index, sample] = np.unique(
                    np.round(spectrum, 10)
                ).size
                momentum_index[g_index, sample] = pair_index
                seed_block[g_index, sample] = block
        print(
            f"geometry axis g={g:.2f}: {count} spectra",
            flush=True,
        )
    raw = np.empty((positive_g.size, TIMES.size), dtype=float)
    disconnected = np.empty_like(raw)
    connected = np.empty_like(raw)
    for index in range(positive_g.size):
        raw[index], disconnected[index], connected[index] = (
            _connected_parts(spectra[index])
        )
    return {
        "g_values": positive_g,
        "spectra": spectra,
        "active_ranks": active_ranks,
        "unique_counts": unique_counts,
        "momentum_index": momentum_index,
        "seed_block": seed_block,
        "raw": raw,
        "disconnected": disconnected,
        "connected": connected,
    }


def _rank_form_factors(
    scaling: np.lib.npyio.NpzFile,
    scaling_metadata: dict[str, Any],
    requested_samples: int,
) -> dict[str, np.ndarray]:
    cases = scaling_metadata["cases"]
    rank_count = len(cases)
    physical_continuous = np.empty(
        (rank_count, TIMES.size),
        dtype=float,
    )
    physical_full = np.empty_like(physical_continuous)
    reference_continuous = np.empty_like(physical_continuous)
    reference_full = np.empty_like(physical_continuous)
    raw_full = np.empty_like(physical_continuous)
    raw_atom_atom = np.empty_like(physical_continuous)
    raw_atom_continuum = np.empty_like(physical_continuous)
    raw_continuum_continuum = np.empty_like(physical_continuous)
    dimensions = np.empty(rank_count, dtype=np.int16)
    channels = np.empty(rank_count, dtype=np.int16)
    interiors = np.empty(rank_count, dtype=np.int16)
    atoms = np.empty(rank_count, dtype=np.int16)
    sample_counts = np.empty(rank_count, dtype=np.int32)
    for index, (label, case) in enumerate(
        zip(RANK_LABELS, cases, strict=True)
    ):
        physical = scaling[f"{label}_interior_spectra"]
        reference = scaling[f"{label}_reference_interior_spectra"]
        count = min(
            int(requested_samples),
            int(physical.shape[0]),
        )
        indices = np.linspace(
            0,
            physical.shape[0] - 1,
            count,
            dtype=int,
        )
        physical_sample = np.asarray(physical[indices], dtype=float)
        reference_sample = np.asarray(reference[indices], dtype=float)
        physical_parts = form_factor_parts(
            unfold_spectra(physical_sample, "ensemble_cdf"),
            TIMES,
        )
        reference_parts = form_factor_parts(
            unfold_spectra(reference_sample, "ensemble_cdf"),
            TIMES,
        )
        D = int(case["D"])
        M = int(case["M"])
        k = int(case["interior_dimension"])
        atom_each = int(case["plus_atoms_per_matrix"])
        physical_continuous[index] = physical_parts.connected
        reference_continuous[index] = reference_parts.connected
        physical_full[index] = (k / D) * physical_parts.connected
        reference_full[index] = (k / D) * reference_parts.connected
        decomposition = atom_raw_decomposition(
            reference_sample,
            minus_atoms=atom_each,
            plus_atoms=atom_each,
            times=TIMES,
        )
        raw_full[index] = decomposition["full"]
        raw_atom_atom[index] = decomposition["atom_atom"]
        raw_atom_continuum[index] = decomposition["atom_continuum"]
        raw_continuum_continuum[index] = decomposition[
            "continuum_continuum"
        ]
        dimensions[index] = D
        channels[index] = M
        interiors[index] = k
        atoms[index] = atom_each
        sample_counts[index] = count
    return {
        "D": dimensions,
        "M": channels,
        "interior": interiors,
        "atom_each": atoms,
        "sample_count": sample_counts,
        "physical_connected_continuous": physical_continuous,
        "physical_connected_full": physical_full,
        "reference_connected_continuous": reference_continuous,
        "reference_connected_full": reference_full,
        "reference_raw_full": raw_full,
        "reference_raw_atom_atom": raw_atom_atom,
        "reference_raw_atom_continuum": raw_atom_continuum,
        "reference_raw_continuum_continuum": (
            raw_continuum_continuum
        ),
    }


def run(
    output_json: Path,
    output_npz: Path,
    samples_per_g: int = REGISTERED_SAMPLES_PER_G,
    spectral_samples: int = REGISTERED_SPECTRAL_SAMPLES,
    quadrature_order: int = REGISTERED_QUADRATURE_ORDER,
    rank_form_factor_samples: int = (
        REGISTERED_RANK_FORM_FACTOR_SAMPLES
    ),
) -> dict[str, Any]:
    """Generate all A+B control and finite-Jacobi data."""

    started = time.perf_counter()
    script_dir = Path(__file__).resolve().parent
    physical_path = script_dir / "output" / "physical_ensemble_v1.npz"
    physical_json_path = (
        script_dir / "output" / "physical_ensemble_v1.json"
    )
    covariance_path = script_dir / "output" / "covariance_model_v1.npz"
    covariance_json_path = (
        script_dir / "output" / "covariance_model_v1.json"
    )
    scaling_path = script_dir / "output" / "rank_scaling_v1.npz"
    scaling_json_path = script_dir / "output" / "rank_scaling_v1.json"
    input_paths = (
        physical_path,
        physical_json_path,
        covariance_path,
        covariance_json_path,
        scaling_path,
        scaling_json_path,
    )
    for path in input_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    physical_metadata = json.loads(
        physical_json_path.read_text(encoding="utf-8")
    )
    covariance_metadata = json.loads(
        covariance_json_path.read_text(encoding="utf-8")
    )
    scaling_metadata = json.loads(
        scaling_json_path.read_text(encoding="utf-8")
    )
    physical = np.load(physical_path, allow_pickle=False)
    covariance = np.load(covariance_path, allow_pickle=False)
    scaling = np.load(scaling_path, allow_pickle=False)
    cache = build_physical_channel_cache()
    structured = _structured_control(cache)
    geometry = _geometry_axis(
        cache,
        samples_per_g=int(samples_per_g),
        seed=REGISTERED_SEED,
    )
    test_indices = physical["test_indices"]
    physical_test_spectra = np.asarray(
        physical["normalized_spectra"][test_indices],
        dtype=np.float32,
    )
    physical_raw, physical_disconnected, physical_connected = (
        _connected_parts(physical_test_spectra)
    )
    haar_spectra = np.asarray(
        covariance["haar_spectra"],
        dtype=np.float32,
    )
    haar_raw, haar_disconnected, haar_connected = _connected_parts(
        haar_spectra
    )
    exact_energy = degenerate_energy_form_factor(cache.rank, TIMES)
    analytic_jacobi = finite_jacobi_form_factor(
        cache.rank,
        cache.external_dimension,
        TIMES,
        quadrature_order=int(quadrature_order),
    )
    fixed = fixed_projector_spectral_ensemble(
        dimension=cache.rank,
        samples=int(spectral_samples),
        alphas=ALPHA_VALUES,
        seed=REGISTERED_SEED + 1,
        reference_curvature_spectrum=physical_test_spectra[0],
        times=TIMES,
    )
    rank = _rank_form_factors(
        scaling,
        scaling_metadata,
        requested_samples=int(rank_form_factor_samples),
    )
    atom_relation_error = float(
        np.max(
            np.abs(
                rank["reference_connected_full"]
                - (
                    rank["interior"] / rank["D"]
                )[:, None]
                * rank["reference_connected_continuous"]
            )
        )
    )
    raw_closure_error = float(
        np.max(
            np.abs(
                rank["reference_raw_full"]
                - rank["reference_raw_atom_atom"]
                - rank["reference_raw_atom_continuum"]
                - rank["reference_raw_continuum_continuum"]
            )
        )
    )
    checks = {
        "input_v1_artifacts_pass": bool(
            physical_metadata["all_checks_pass"]
            and covariance_metadata["all_checks_pass"]
            and scaling_metadata["all_checks_pass"]
        ),
        "exact_energy_silence": bool(
            np.max(
                np.abs(exact_energy.raw - cache.rank)
            )
            < 1e-12
            and np.max(np.abs(exact_energy.connected)) < 1e-12
        ),
        "structured_control_full_rank": bool(
            np.all(structured["active_ranks"] == cache.rank)
        ),
        "structured_control_multiplets": bool(
            np.max(structured["unique_counts"]) <= 10
        ),
        "geometry_axis_full_rank": bool(
            np.all(geometry["active_ranks"] == cache.rank)
        ),
        "geometry_axis_exact_parent": bool(
            cache.kernel_bandwidth < 1e-10
            and cache.external_gap > 1e-3
            and abs(
                cache.kernel_bandwidth
                - physical_metadata["parent"]["kernel_bandwidth"]
            )
            < 1e-12
            and abs(
                cache.external_gap
                - physical_metadata["parent"]["external_gap"]
            )
            < 1e-12
        ),
        "fixed_projector_invariance": bool(
            np.max(fixed.projector_distance) < 1e-12
            and np.max(fixed.curvature_spectrum_error) < 1e-12
        ),
        "spectral_axis_resolved": bool(
            fixed.mean_gap_ratio[-1]
            > fixed.mean_gap_ratio[0] + 0.12
        ),
        "finite_jacobi_mass_and_basis": bool(
            analytic_jacobi.mass_error < 2e-8
            and analytic_jacobi.orthogonality_error < 2e-8
            and abs(analytic_jacobi.connected_continuous[0]) < 1e-9
        ),
        "atom_plateau_theorem": bool(
            atom_relation_error < 1e-12
            and raw_closure_error < 1e-12
        ),
    }
    result = {
        "schema_version": 2,
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "registered_seed": REGISTERED_SEED,
        "sample_counts": {
            "structured_momenta": int(
                structured["spectra"].shape[0]
            ),
            "structured_orbits": int(
                np.unique(structured["orbit_id"]).size
            ),
            "per_positive_g": int(samples_per_g),
            "fixed_projector_per_alpha": int(spectral_samples),
            "rank_form_factor_requested": int(
                rank_form_factor_samples
            ),
            "rank_form_factor_actual": (
                rank["sample_count"].astype(int).tolist()
            ),
            "physical_test": int(physical_test_spectra.shape[0]),
            "haar_reference": int(haar_spectra.shape[0]),
        },
        "grids": {
            "g": G_VALUES.tolist(),
            "alpha": ALPHA_VALUES.tolist(),
            "times": {
                "minimum": float(TIMES[0]),
                "maximum": float(TIMES[-1]),
                "points": int(TIMES.size),
            },
        },
        "physical_case": {
            "N": cache.N,
            "n": cache.n_flux,
            "D": cache.rank,
            "M": cache.external_dimension,
            "kernel_bandwidth": cache.kernel_bandwidth,
            "external_gap": cache.external_gap,
        },
        "structured_control": {
            "minimum_active_rank": int(
                np.min(structured["active_ranks"])
            ),
            "maximum_distinct_eigenvalues": int(
                np.max(structured["unique_counts"])
            ),
        },
        "fixed_projector_control": {
            "poisson_endpoint_gap_ratio": float(
                fixed.mean_gap_ratio[0]
            ),
            "gue_endpoint_gap_ratio": float(
                fixed.mean_gap_ratio[-1]
            ),
            "maximum_projector_distance": float(
                np.max(fixed.projector_distance)
            ),
            "maximum_curvature_spectrum_error": float(
                np.max(fixed.curvature_spectrum_error)
            ),
        },
        "finite_jacobi": {
            "quadrature_order": int(quadrature_order),
            "mass_error": analytic_jacobi.mass_error,
            "orthogonality_error": (
                analytic_jacobi.orthogonality_error
            ),
            "atom_relation_error": atom_relation_error,
            "raw_atom_closure_error": raw_closure_error,
        },
        "inputs": {
            str(path.relative_to(script_dir)): _sha256(path)
            for path in input_paths
        },
        "checks": checks,
        "all_checks_pass": bool(all(checks.values())),
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_npz.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(
        output_npz,
        times=TIMES.astype(np.float32),
        energy_raw=exact_energy.raw.astype(np.float32),
        energy_disconnected=exact_energy.disconnected.astype(np.float32),
        energy_connected=exact_energy.connected.astype(np.float32),
        jacobi_connected_D50=(
            analytic_jacobi.connected_continuous.astype(np.float32)
        ),
        structured_spectra=structured["spectra"],
        structured_active_ranks=structured["active_ranks"],
        structured_unique_counts=structured["unique_counts"],
        structured_momenta=structured["momenta"],
        structured_orbit_keys=structured["orbit_keys"],
        structured_orbit_id=structured["orbit_id"],
        structured_raw=structured["raw"].astype(np.float32),
        structured_disconnected=(
            structured["disconnected"].astype(np.float32)
        ),
        structured_connected=structured["connected"].astype(
            np.float32
        ),
        physical_test_spectra=physical_test_spectra,
        physical_raw=physical_raw.astype(np.float32),
        physical_disconnected=physical_disconnected.astype(np.float32),
        physical_connected=physical_connected.astype(np.float32),
        physical_seed_block=physical["seed_block"][test_indices],
        haar_spectra=haar_spectra,
        haar_raw=haar_raw.astype(np.float32),
        haar_disconnected=haar_disconnected.astype(np.float32),
        haar_connected=haar_connected.astype(np.float32),
        g_values=geometry["g_values"].astype(np.float32),
        g_spectra=geometry["spectra"],
        g_active_ranks=geometry["active_ranks"],
        g_unique_counts=geometry["unique_counts"],
        g_momentum_index=geometry["momentum_index"],
        g_seed_block=geometry["seed_block"],
        g_raw=geometry["raw"].astype(np.float32),
        g_disconnected=geometry["disconnected"].astype(np.float32),
        g_connected=geometry["connected"].astype(np.float32),
        alpha_values=fixed.alphas.astype(np.float32),
        energy_spectra_alpha=fixed.energy_spectra,
        energy_gap_ratio_alpha=fixed.mean_gap_ratio.astype(np.float32),
        energy_raw_alpha=fixed.energy_raw.astype(np.float32),
        energy_disconnected_alpha=(
            fixed.energy_disconnected.astype(np.float32)
        ),
        energy_connected_alpha=fixed.energy_connected.astype(
            np.float32
        ),
        projector_distance_alpha=fixed.projector_distance.astype(
            np.float64
        ),
        curvature_error_alpha=(
            fixed.curvature_spectrum_error.astype(np.float64)
        ),
        rank_D=rank["D"],
        rank_M=rank["M"],
        rank_interior=rank["interior"],
        rank_atom_each=rank["atom_each"],
        rank_form_factor_sample_count=rank["sample_count"],
        rank_physical_connected_continuous=(
            rank["physical_connected_continuous"].astype(np.float32)
        ),
        rank_physical_connected_full=(
            rank["physical_connected_full"].astype(np.float32)
        ),
        rank_reference_connected_continuous=(
            rank["reference_connected_continuous"].astype(np.float32)
        ),
        rank_reference_connected_full=(
            rank["reference_connected_full"].astype(np.float32)
        ),
        rank_reference_raw_full=(
            rank["reference_raw_full"].astype(np.float32)
        ),
        rank_reference_raw_atom_atom=(
            rank["reference_raw_atom_atom"].astype(np.float32)
        ),
        rank_reference_raw_atom_continuum=(
            rank["reference_raw_atom_continuum"].astype(np.float32)
        ),
        rank_reference_raw_continuum_continuum=(
            rank["reference_raw_continuum_continuum"].astype(
                np.float32
            )
        ),
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-json",
        type=Path,
        default=_default_output("spectral_silence_v2.json"),
    )
    parser.add_argument(
        "--output-npz",
        type=Path,
        default=_default_output("spectral_silence_v2.npz"),
    )
    parser.add_argument(
        "--samples-per-g",
        type=int,
        default=REGISTERED_SAMPLES_PER_G,
    )
    parser.add_argument(
        "--spectral-samples",
        type=int,
        default=REGISTERED_SPECTRAL_SAMPLES,
    )
    parser.add_argument(
        "--quadrature-order",
        type=int,
        default=REGISTERED_QUADRATURE_ORDER,
    )
    parser.add_argument(
        "--rank-form-factor-samples",
        type=int,
        default=REGISTERED_RANK_FORM_FACTOR_SAMPLES,
    )
    args = parser.parse_args()
    result = run(
        args.output_json,
        args.output_npz,
        samples_per_g=args.samples_per_g,
        spectral_samples=args.spectral_samples,
        quadrature_order=args.quadrature_order,
        rank_form_factor_samples=args.rank_form_factor_samples,
    )
    print(json.dumps(result, indent=2))
    if not result["all_checks_pass"]:
        raise SystemExit("spectral-silence production audit failed")


if __name__ == "__main__":
    main()
