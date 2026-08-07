#!/usr/bin/env python3
"""Run gauge-invariant four-channel tests on a genuine many-body sequence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.lattice import build_kapit_laughlin_parent
from lgeth.manybody_response import (
    SiteResponseCache,
    audit_unregistered_small_case,
    build_site_response_cache,
    registered_fixed_two_qh_cases,
    solve_kernel_frame,
)
from lgeth.wick_channels import (
    assemble_channels,
    covariance_matched_wick,
    fourier_density_panel,
    gaussian_r4_reference,
    local_density_panels,
)


VERSION = "v3"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"
OUTPUT_JSON = OUTPUT_ROOT / "matrix_element_geometric_eth_v3.json"
OUTPUT_NPZ = OUTPUT_ROOT / "matrix_element_geometric_eth_v3.npz"
CHECKPOINT_ROOT = OUTPUT_ROOT / "matrix_element_v3_checkpoints"
REGISTERED_PANELS = 24
REGISTERED_PANEL_SIZE = 8
REGISTERED_GAUSSIAN_SAMPLES = 2_000
REGISTERED_SEED = 20260728320
RELATIVE_SHIFTS = (1e-3, 5e-4)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _checkpoint_identity(case) -> dict[str, Any]:
    sources = (
        SCRIPT_ROOT / "lgeth" / "manybody_response.py",
        SCRIPT_ROOT / "lgeth" / "lattice.py",
        SCRIPT_ROOT / "lgeth" / "combinatorics.py",
    )
    return {
        "version": VERSION,
        "case": asdict(case),
        "relative_shifts": list(RELATIVE_SHIFTS),
        "sources": {
            str(path.relative_to(SCRIPT_ROOT)): _sha256_file(path)
            for path in sources
        },
        "numpy": np.__version__,
    }


def _checkpoint_paths(
    checkpoint_dir: Path,
    N: int,
) -> tuple[Path, Path]:
    stem = checkpoint_dir / f"N{int(N)}_site_response_v3"
    return stem.with_suffix(".json"), stem.with_suffix(".npz")


def _load_checkpoint(
    checkpoint_dir: Path,
    case,
) -> tuple[SiteResponseCache, dict[str, Any]] | None:
    metadata_path, arrays_path = _checkpoint_paths(checkpoint_dir, case.N)
    if not metadata_path.exists() or not arrays_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    identity = _checkpoint_identity(case)
    if metadata.get("identity_hash") != _json_hash(identity):
        return None
    if metadata.get("identity") != identity:
        return None
    if not all(metadata.get("checks", {}).values()):
        return None
    with np.load(arrays_path, allow_pickle=False) as arrays:
        cache = SiteResponseCache(
            case=case,
            site_indices=tuple(
                int(value) for value in arrays["site_indices"]
            ),
            solutions=np.asarray(arrays["solutions"], dtype=complex),
            tangent_gram=np.asarray(arrays["tangent_gram"]),
            external_gap=float(metadata["external_gap"]),
            shift_values=tuple(
                float(value) for value in metadata["shift_values"]
            ),
            maximum_relative_residual=float(
                metadata["maximum_relative_residual"]
            ),
            maximum_shift_difference=float(
                metadata["maximum_shift_difference"]
            ),
            maximum_kernel_leakage=float(
                metadata["maximum_kernel_leakage"]
            ),
        )
    return cache, metadata


def _build_checkpoint(
    checkpoint_dir: Path,
    case,
    seed: int,
) -> tuple[SiteResponseCache, dict[str, Any]]:
    started = time.perf_counter()
    system = build_kapit_laughlin_parent(
        case.N,
        case.n_flux,
        case.theta_x,
        case.theta_y,
    )
    kernel = solve_kernel_frame(system, case, seed=seed)
    cache = build_site_response_cache(
        system,
        kernel,
        relative_shifts=RELATIVE_SHIFTS,
    )
    checks = {
        "kernel_count": kernel.observed_rank == case.expected_rank,
        "external_gap": kernel.external_gap > 1e-8,
        "kernel_residual": kernel.residual_norm
        < (1e-8 if kernel.method == "dense" else 5e-7),
        "kernel_orthonormality": kernel.orthonormality_error < 1e-9,
        "resolvent_residual": cache.maximum_relative_residual < 2e-3,
        "resolvent_shift_stability": cache.maximum_shift_difference < 5e-2,
        "kernel_leakage": cache.maximum_kernel_leakage < 1e-7,
    }
    identity = _checkpoint_identity(case)
    metadata = {
        "identity": identity,
        "identity_hash": _json_hash(identity),
        "case": asdict(case),
        "basis_dimension": system.basis.dimension,
        "physical_sites": system.orbitals.shape[0],
        "lattice_length": system.length,
        "kernel_method": kernel.method,
        "observed_rank": kernel.observed_rank,
        "external_gap": kernel.external_gap,
        "kernel_residual_norm": kernel.residual_norm,
        "kernel_orthonormality_error": kernel.orthonormality_error,
        "shift_values": list(cache.shift_values),
        "maximum_relative_residual": cache.maximum_relative_residual,
        "maximum_shift_difference": cache.maximum_shift_difference,
        "maximum_kernel_leakage": cache.maximum_kernel_leakage,
        "runtime_seconds": time.perf_counter() - started,
        "checks": checks,
    }
    if not all(checks.values()):
        raise RuntimeError(
            f"many-body response checkpoint failed for N={case.N}: {checks}"
        )
    metadata_path, arrays_path = _checkpoint_paths(
        checkpoint_dir,
        case.N,
    )
    _atomic_npz(
        arrays_path,
        site_indices=np.asarray(cache.site_indices, dtype=np.int16),
        solutions=cache.solutions,
        tangent_gram=cache.tangent_gram,
    )
    metadata["arrays_sha256"] = _sha256_file(arrays_path)
    _atomic_json(metadata_path, metadata)
    return cache, metadata


def _seeded_unitary(dimension: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(int(seed))
    matrix = rng.normal(size=(dimension, dimension))
    matrix = matrix + 1j * rng.normal(size=matrix.shape)
    unitary, _ = np.linalg.qr(matrix)
    return unitary


def _gauge_invariance_error(
    channels: np.ndarray,
    seed: int,
) -> float:
    values = np.asarray(channels, dtype=complex)
    reference = covariance_matched_wick(values).R4
    label = _seeded_unitary(values.shape[0], seed)
    target = _seeded_unitary(values.shape[2], seed + 1)
    rng = np.random.default_rng(seed + 2)
    external_phases = np.exp(
        2j * np.pi * rng.random(values.shape[1])
    )
    transformed = np.einsum(
        "mn,a,naj,jk->mak",
        label,
        external_phases,
        values,
        target,
        optimize=True,
    )
    observed = covariance_matched_wick(transformed).R4
    return abs(observed - reference)


def _pooled_spectrum(spectra: list[np.ndarray]) -> np.ndarray:
    if not spectra:
        raise ValueError("cannot pool an empty covariance spectrum")
    maximum = max(values.size for values in spectra)
    padded = np.zeros((len(spectra), maximum), dtype=float)
    for index, values in enumerate(spectra):
        normalized = np.asarray(values, dtype=float)
        normalized = normalized / np.sum(normalized)
        padded[index, -normalized.size :] = normalized
    pooled = np.mean(padded, axis=0)
    return pooled[pooled > 1e-14 * np.max(pooled)]


def _case_statistics(
    cache: SiteResponseCache,
    metadata: dict[str, Any],
    panels: int,
    gaussian_samples: int,
    seed: int,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    length = int(metadata["lattice_length"])
    panel_coefficients = local_density_panels(
        length=length,
        panel_size=REGISTERED_PANEL_SIZE,
        panels=panels,
        seed=seed,
    )
    physical_R4 = np.empty(panels, dtype=float)
    A_left = np.empty(panels, dtype=float)
    B_right = np.empty(panels, dtype=float)
    condition = np.empty(panels, dtype=float)
    left_spectra: list[np.ndarray] = []
    right_spectra: list[np.ndarray] = []
    first_channels: np.ndarray | None = None
    for panel in range(panels):
        channels = assemble_channels(cache, panel_coefficients[panel])
        if first_channels is None:
            first_channels = channels
        result = covariance_matched_wick(channels)
        physical_R4[panel] = result.R4
        A_left[panel] = result.A_left
        B_right[panel] = result.B_right
        condition[panel] = (
            result.channel_covariance_eigenvalues[-1]
            / result.channel_covariance_eigenvalues[0]
        )
        left_spectra.append(result.left_eigenvalues)
        right_spectra.append(result.right_eigenvalues)
    if first_channels is None:
        raise RuntimeError("no physical operator panels were evaluated")
    structured_channels = assemble_channels(
        cache,
        fourier_density_panel(length, REGISTERED_PANEL_SIZE),
    )
    structured = covariance_matched_wick(structured_channels)
    pooled_left = _pooled_spectrum(left_spectra)
    pooled_right = _pooled_spectrum(right_spectra)
    reproducibility_first = gaussian_r4_reference(
        pooled_left,
        pooled_right,
        REGISTERED_PANEL_SIZE,
        samples=min(16, gaussian_samples),
        seed=seed + 100,
    )
    reproducibility_second = gaussian_r4_reference(
        pooled_left,
        pooled_right,
        REGISTERED_PANEL_SIZE,
        samples=min(16, gaussian_samples),
        seed=seed + 100,
    )
    reference = gaussian_r4_reference(
        pooled_left,
        pooled_right,
        REGISTERED_PANEL_SIZE,
        samples=gaussian_samples,
        seed=seed + 200,
    )
    quantiles = np.quantile(reference, [0.025, 0.5, 0.975])
    case_checks = dict(metadata["checks"])
    case_checks.update(
        {
            "channel_support": bool(np.all(np.isfinite(condition))),
            "gauge_invariance": _gauge_invariance_error(
                first_channels,
                seed + 300,
            )
            < 2e-9,
            "reference_reproducibility": bool(
                np.array_equal(
                    reproducibility_first,
                    reproducibility_second,
                )
            ),
        }
    )
    summary = {
        "N": cache.case.N,
        "n_flux": cache.case.n_flux,
        "rank": cache.case.expected_rank,
        "basis_dimension": metadata["basis_dimension"],
        "physical_sites": metadata["physical_sites"],
        "lattice_length": length,
        "kernel_method": metadata["kernel_method"],
        "external_gap": metadata["external_gap"],
        "kernel_residual_norm": metadata["kernel_residual_norm"],
        "kernel_orthonormality_error": metadata[
            "kernel_orthonormality_error"
        ],
        "maximum_relative_residual": metadata[
            "maximum_relative_residual"
        ],
        "maximum_shift_difference": metadata[
            "maximum_shift_difference"
        ],
        "maximum_kernel_leakage": metadata[
            "maximum_kernel_leakage"
        ],
        "physical_R4": physical_R4.tolist(),
        "physical_R4_median": float(np.median(physical_R4)),
        "physical_R4_interval": np.quantile(
            physical_R4,
            [0.025, 0.975],
        ).tolist(),
        "structured_R4": structured.R4,
        "gaussian_R4_interval": quantiles.tolist(),
        "physical_excess": float(np.median(physical_R4) - quantiles[1]),
        "A_left_median": float(np.median(A_left)),
        "B_right_median": float(np.median(B_right)),
        "channel_condition_maximum": float(np.max(condition)),
        "gauge_invariance_error": _gauge_invariance_error(
            first_channels,
            seed + 300,
        ),
        "checks": case_checks,
    }
    arrays = {
        "physical_R4": physical_R4,
        "A_left": A_left,
        "B_right": B_right,
        "channel_condition": condition,
        "gaussian_R4": reference,
        "pooled_left_eigenvalues": pooled_left,
        "pooled_right_eigenvalues": pooled_right,
        "structured_R4": np.asarray(structured.R4),
    }
    return summary, arrays


def select_result_branch(payload: dict[str, Any]) -> str:
    """Select the preregistered matrix-element result branch."""

    cases = payload.get("cases", [])
    checks = payload.get("checks", {})
    if len(cases) != 3 or not all(checks.values()):
        return "manybody_sequence_incomplete"
    medians = np.asarray(
        [case["physical_R4_median"] for case in cases],
        dtype=float,
    )
    upper = np.asarray(
        [case["gaussian_R4_interval"][2] for case in cases],
        dtype=float,
    )
    slope = float(np.polyfit([3.0, 4.0, 5.0], medians, 1)[0])
    if medians[-1] <= upper[-1] and slope < 0.0:
        return "wick_compatible_trend"
    if medians[-1] > upper[-1] and np.count_nonzero(medians > upper) >= 2:
        return "deformed_geometric_eth"
    return "no_matrix_element_eth_trend"


def run(
    output_json: Path = OUTPUT_JSON,
    output_npz: Path = OUTPUT_NPZ,
    checkpoint_dir: Path = CHECKPOINT_ROOT,
    case_indices: tuple[int, ...] = (0, 1, 2),
    panels: int = REGISTERED_PANELS,
    gaussian_samples: int = REGISTERED_GAUSSIAN_SAMPLES,
    production: bool = True,
    seed: int = REGISTERED_SEED,
) -> dict[str, Any]:
    """Run the registered or reduced matrix-element calculation."""

    started = time.perf_counter()
    panel_count = int(panels)
    reference_count = int(gaussian_samples)
    if panel_count < 2 or reference_count < 8:
        raise ValueError("require at least two panels and eight references")
    registered = registered_fixed_two_qh_cases()
    selected = tuple(registered[int(index)] for index in case_indices)
    if not selected:
        raise ValueError("at least one many-body case is required")
    excluded = audit_unregistered_small_case(2, 6, 0.17, 0.29)
    case_summaries: list[dict[str, Any]] = []
    case_arrays: list[dict[str, np.ndarray]] = []
    for offset, case in enumerate(selected):
        loaded = _load_checkpoint(checkpoint_dir, case)
        reused = loaded is not None
        if loaded is None:
            cache, metadata = _build_checkpoint(
                checkpoint_dir,
                case,
                seed=seed + 10 * offset,
            )
        else:
            cache, metadata = loaded
        summary, arrays = _case_statistics(
            cache,
            metadata,
            panels=panel_count,
            gaussian_samples=reference_count,
            seed=seed + 1_000 * offset,
        )
        summary["checkpoint_reused"] = reused
        summary["checkpoint_identity_hash"] = metadata["identity_hash"]
        case_summaries.append(summary)
        case_arrays.append(arrays)
    all_case_checks = {
        key: all(case["checks"].get(key, False) for case in case_summaries)
        for key in {
            key
            for case in case_summaries
            for key in case["checks"]
        }
    }
    checks = {
        "kernel_count": all_case_checks.get("kernel_count", False),
        "external_gap": all_case_checks.get("external_gap", False),
        "resolvent_residual": all_case_checks.get(
            "resolvent_residual",
            False,
        ),
        "channel_support": all_case_checks.get("channel_support", False),
        "gauge_invariance": all_case_checks.get("gauge_invariance", False),
        "reference_reproducibility": all_case_checks.get(
            "reference_reproducibility",
            False,
        ),
        "n2_excluded_before_production": (
            excluded.expected_rank == 9
            and excluded.observed_rank == 12
            and not excluded.accepted
        ),
    }
    payload: dict[str, Any] = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "case_indices": list(case_indices),
            "panel_size": REGISTERED_PANEL_SIZE,
            "panels": panel_count,
            "gaussian_samples": reference_count,
            "seed": int(seed),
            "relative_shifts": list(RELATIVE_SHIFTS),
            "production": bool(production),
        },
        "excluded_small_case": asdict(excluded),
        "cases": case_summaries,
        "checks": checks,
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    if len(case_summaries) == 3:
        medians = np.asarray(
            [case["physical_R4_median"] for case in case_summaries]
        )
        payload["descriptive_slope_per_particle"] = float(
            np.polyfit([3.0, 4.0, 5.0], medians, 1)[0]
        )
    else:
        payload["descriptive_slope_per_particle"] = None
    payload["result_branch"] = select_result_branch(payload)
    output_arrays: dict[str, np.ndarray] = {
        "N": np.asarray([case["N"] for case in case_summaries]),
        "rank": np.asarray([case["rank"] for case in case_summaries]),
        "external_gap": np.asarray(
            [case["external_gap"] for case in case_summaries]
        ),
    }
    for index, arrays in enumerate(case_arrays):
        for key, values in arrays.items():
            output_arrays[f"case_{index}_{key}"] = np.asarray(values)
    _atomic_npz(output_npz, **output_arrays)
    payload["npz_sha256"] = _sha256_file(output_npz)
    _atomic_json(output_json, payload)
    if production and (
        len(case_summaries) != 3
        or not all(checks.values())
    ):
        raise RuntimeError("production matrix-element gates failed")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reduced",
        action="store_true",
        help="run the N=3 smoke configuration",
    )
    arguments = parser.parse_args()
    if arguments.reduced:
        payload = run(
            case_indices=(0,),
            panels=3,
            gaussian_samples=32,
            production=False,
        )
    else:
        payload = run()
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
