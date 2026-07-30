#!/usr/bin/env python3
"""Fit and test a held-out covariance-deformed Geometric-ETH model."""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.grassmann import (
    coordinate_participation,
    covariance_deformed_rows,
    frame_overlap,
    haar_frame_overlap_mean,
    polarization_imbalance,
    principal_angles,
    regularize_covariance,
)
from lgeth.jacobi import (
    canonical_channel_form,
    normalized_curvature,
    sample_jacobi_compression,
)
from lgeth.statistics import bulk_gap_ratio_per_spectrum, histogram_l1


VERSION = "v1"
REGISTERED_DIAGNOSTIC_ROWS = 1_024
REGISTERED_MODEL_SAMPLES = 10_000
CANDIDATE_FLOORS = (0.002, 0.005, 0.01, 0.02, 0.05)
HISTOGRAM_EDGES = np.linspace(-1.0, 1.0, 161)


def _channel(
    coefficients: np.ndarray,
    channel_basis: np.ndarray,
    tangent_gram: np.ndarray,
) -> np.ndarray:
    norm_squared = float(coefficients @ tangent_gram @ coefficients)
    if norm_squared <= 0.0:
        raise RuntimeError("cached tangent has zero many-body norm")
    return (
        np.tensordot(coefficients, channel_basis, axes=(0, 0))
        / np.sqrt(norm_squared)
    )


def _physical_rows(
    arrays: Any,
    indices: np.ndarray,
):
    channel_basis = arrays["channel_basis"]
    tangent_gram = arrays["tangent_gram"]
    coefficients_v = arrays["tangent_coefficients_v"]
    coefficients_w = arrays["tangent_coefficients_w"]
    for raw_index in indices:
        index = int(raw_index)
        channel_v = _channel(
            coefficients_v[index], channel_basis, tangent_gram
        )
        channel_w = _channel(
            coefficients_w[index], channel_basis, tangent_gram
        )
        yield normalized_curvature(
            channel_v,
            channel_w,
            rtol=1e-10,
        ).Y


def _training_geometry(
    arrays: Any,
    indices: np.ndarray,
) -> tuple[np.ndarray, dict[str, np.ndarray | float]]:
    dimension = int(arrays["channel_basis"].shape[2] * 2)
    rank = int(arrays["normalized_spectra"].shape[1])
    mean_projector = np.zeros((dimension, dimension), dtype=complex)
    per_block = np.zeros((8, dimension, dimension), dtype=complex)
    block_count = np.zeros(8, dtype=int)
    participation = np.empty(indices.size, dtype=float)
    polarization = np.empty(indices.size, dtype=float)
    frame_overlaps = np.empty(indices.size // 2, dtype=float)
    angles: list[np.ndarray] = []
    previous = None
    pair = 0
    second_sum = 0.0
    fourth_sum = 0.0
    entry_count = 0
    for position, (index, rows) in enumerate(
        zip(indices, _physical_rows(arrays, indices), strict=True)
    ):
        projector = rows.conj().T @ rows
        mean_projector += projector
        block = int(arrays["seed_block"][int(index)])
        per_block[block] += projector
        block_count[block] += 1
        participation[position] = coordinate_participation(rows)["fraction"]
        polarization[position] = polarization_imbalance(rows)
        squared = np.abs(rows).ravel() ** 2
        second_sum += float(np.sum(squared))
        fourth_sum += float(np.sum(squared * squared))
        entry_count += squared.size
        if position % 2 == 0:
            previous = rows
        elif previous is not None:
            frame_overlaps[pair] = frame_overlap(previous, rows)
            angles.append(principal_angles(previous, rows))
            previous = None
            pair += 1
    mean_projector /= indices.size
    for block in range(8):
        if block_count[block]:
            per_block[block] /= block_count[block]
    isotropic = (rank / dimension) * np.eye(dimension)
    anisotropy = float(
        np.linalg.norm(mean_projector - isotropic)
        / np.linalg.norm(isotropic)
    )
    principal = np.concatenate(angles) if angles else np.empty(0)
    second = second_sum / entry_count
    fourth_ratio = (fourth_sum / entry_count) / (second * second)
    diagnostics: dict[str, np.ndarray | float] = {
        "mean_projector_by_seed_block": per_block,
        "seed_block_counts": block_count,
        "participation": participation,
        "polarization": polarization,
        "frame_overlaps": frame_overlaps,
        "principal_angles": principal,
        "relative_frobenius_anisotropy": anisotropy,
        "entry_fourth_ratio": fourth_ratio,
    }
    return mean_projector, diagnostics


def _spectra_from_deformed(
    rank: int,
    covariance: np.ndarray,
    floor: float,
    samples: int,
    seed: int,
    progress_label: str | None = None,
) -> np.ndarray:
    dimension = covariance.shape[0]
    form = canonical_channel_form(dimension // 2)
    spectra = np.empty((samples, rank), dtype=np.float32)
    rng = np.random.default_rng(seed)
    for index, rows in enumerate(
        covariance_deformed_rows(
            rank,
            covariance,
            samples,
            rng,
            floor_fraction=floor,
        )
    ):
        omega = rows @ form @ rows.conj().T
        spectra[index] = np.linalg.eigvalsh(
            0.5 * (omega + omega.conj().T)
        )
        if (
            progress_label is not None
            and (index + 1) % max(1, samples // 4) == 0
        ):
            print(
                f"{progress_label}: {index + 1}/{samples}",
                flush=True,
            )
    return spectra


def _comparison(
    physical: np.ndarray,
    haar: np.ndarray,
    deformed: np.ndarray,
) -> dict[str, Any]:
    haar_l1 = histogram_l1(physical, haar, HISTOGRAM_EDGES)
    deformed_l1 = histogram_l1(physical, deformed, HISTOGRAM_EDGES)
    physical_gap = bulk_gap_ratio_per_spectrum(physical)
    haar_gap = bulk_gap_ratio_per_spectrum(haar)
    deformed_gap = bulk_gap_ratio_per_spectrum(deformed)
    moments = {}
    for order in (2, 4, 6, 8):
        moments[str(order)] = {
            "physical": float(np.mean(physical.astype(float) ** order)),
            "haar": float(np.mean(haar.astype(float) ** order)),
            "deformed": float(np.mean(deformed.astype(float) ** order)),
        }
    improvement = (haar_l1 - deformed_l1) / haar_l1
    gap_difference = abs(
        float(np.mean(physical_gap)) - float(np.mean(deformed_gap))
    )
    if improvement >= 0.25 and gap_difference < 0.025:
        branch = "leading_covariance_capture"
    elif improvement > 0.05:
        branch = "partial_capture"
    else:
        branch = "no_held_out_improvement"
    return {
        "density_l1": {
            "physical_vs_haar": haar_l1,
            "physical_vs_deformed": deformed_l1,
            "relative_improvement": improvement,
        },
        "mean_gap_ratio": {
            "physical": float(np.mean(physical_gap)),
            "haar": float(np.mean(haar_gap)),
            "deformed": float(np.mean(deformed_gap)),
            "physical_deformed_absolute_difference": gap_difference,
        },
        "moments": moments,
        "result_branch": branch,
    }


def run(
    physical_npz: Path,
    output_json: Path,
    output_npz: Path,
    diagnostic_rows: int = REGISTERED_DIAGNOSTIC_ROWS,
    model_samples: int = REGISTERED_MODEL_SAMPLES,
) -> dict[str, Any]:
    """Fit on train, choose the floor on validation, and report only test."""

    started = time.perf_counter()
    row_count = int(diagnostic_rows)
    sample_count = int(model_samples)
    if row_count < 16 or sample_count < 16:
        raise ValueError("require at least 16 diagnostic rows and spectra")
    with np.load(physical_npz) as arrays:
        train_all = arrays["train_indices"]
        validation_indices = arrays["validation_indices"]
        test_indices = arrays["test_indices"]
        if row_count > train_all.size:
            raise ValueError("diagnostic_rows exceeds the training split")
        diagnostic_indices = train_all[:row_count]
        mean_projector, geometry = _training_geometry(
            arrays,
            diagnostic_indices,
        )
        rank = int(arrays["normalized_spectra"].shape[1])
        dimension = int(mean_projector.shape[0])
        physical_validation = arrays["normalized_spectra"][
            validation_indices
        ].astype(float)
        physical_test = arrays["normalized_spectra"][test_indices].astype(
            float
        )
    validation_samples = min(max(32, sample_count // 20), 512)
    validation_scores: dict[str, dict[str, float]] = {}
    validation_spectra = np.empty(
        (len(CANDIDATE_FLOORS), validation_samples, rank),
        dtype=np.float32,
    )
    for floor_index, floor in enumerate(CANDIDATE_FLOORS):
        candidate = _spectra_from_deformed(
            rank,
            mean_projector,
            floor,
            validation_samples,
            seed=20260728200,
        )
        validation_spectra[floor_index] = candidate
        density_l1 = histogram_l1(
            physical_validation,
            candidate,
            HISTOGRAM_EDGES,
        )
        physical_gap = float(
            np.mean(bulk_gap_ratio_per_spectrum(physical_validation))
        )
        candidate_gap = float(
            np.mean(bulk_gap_ratio_per_spectrum(candidate))
        )
        gap_difference = abs(physical_gap - candidate_gap)
        validation_scores[str(floor)] = {
            "density_l1": density_l1,
            "gap_ratio_difference": gap_difference,
            "selection_score": density_l1 + 0.5 * gap_difference,
        }
    selected_floor = min(
        CANDIDATE_FLOORS,
        key=lambda floor: validation_scores[str(floor)][
            "selection_score"
        ],
    )
    haar_spectra = sample_jacobi_compression(
        rank,
        dimension // 2,
        sample_count,
        seed=20260728210,
    ).astype(np.float32)
    print(f"Haar reference: {sample_count}/{sample_count}", flush=True)
    deformed_spectra = _spectra_from_deformed(
        rank,
        mean_projector,
        selected_floor,
        sample_count,
        seed=20260728220,
        progress_label="deformed model",
    )
    comparison = _comparison(
        physical_test,
        haar_spectra,
        deformed_spectra,
    )
    regularized = regularize_covariance(
        mean_projector,
        floor_fraction=selected_floor,
    )
    covariance_eigenvalues = np.linalg.eigvalsh(regularized)
    frame_baseline = haar_frame_overlap_mean(rank, dimension)
    geometry_summary = {
        "relative_frobenius_anisotropy": float(
            geometry["relative_frobenius_anisotropy"]
        ),
        "mean_participation_fraction": float(
            np.mean(geometry["participation"])
        ),
        "mean_absolute_polarization": float(
            np.mean(np.abs(geometry["polarization"]))
        ),
        "mean_frame_overlap": float(np.mean(geometry["frame_overlaps"])),
        "haar_frame_overlap": frame_baseline,
        "mean_principal_angle": float(
            np.mean(geometry["principal_angles"])
        ),
        "entry_fourth_ratio": float(geometry["entry_fourth_ratio"]),
    }
    checks = {
        "train_validation_test_disjoint": bool(
            np.intersect1d(diagnostic_indices, validation_indices).size == 0
            and np.intersect1d(diagnostic_indices, test_indices).size == 0
            and np.intersect1d(validation_indices, test_indices).size == 0
        ),
        "covariance_fit_uses_requested_training_rows": (
            diagnostic_indices.size == row_count
        ),
        "all_candidate_floors_scored": (
            len(validation_scores) == len(CANDIDATE_FLOORS)
        ),
        "selected_floor_is_registered": selected_floor in CANDIDATE_FLOORS,
        "model_shapes_match": bool(
            haar_spectra.shape == (sample_count, rank)
            and deformed_spectra.shape == (sample_count, rank)
        ),
        "all_spectra_bounded": bool(
            np.max(np.abs(haar_spectra)) <= 1.0 + 2e-7
            and np.max(np.abs(deformed_spectra)) <= 1.0 + 2e-7
        ),
        "branch_registered": comparison["result_branch"]
        in {
            "leading_covariance_capture",
            "partial_capture",
            "no_held_out_improvement",
        },
    }
    result = {
        "schema_version": 1,
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "physical_source": str(physical_npz),
        "rank": rank,
        "ambient_channel_dimension": dimension,
        "diagnostic_training_rows": row_count,
        "validation_model_samples_per_floor": validation_samples,
        "haar_samples": sample_count,
        "deformed_samples": sample_count,
        "candidate_floors": list(CANDIDATE_FLOORS),
        "validation_scores": validation_scores,
        "selected_floor": selected_floor,
        "training_geometry": geometry_summary,
        "held_out_test": comparison,
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
        mean_projector=mean_projector,
        covariance_eigenvalues=covariance_eigenvalues,
        diagnostic_indices=diagnostic_indices,
        validation_indices=validation_indices,
        test_indices=test_indices,
        validation_spectra=validation_spectra,
        candidate_floors=np.asarray(CANDIDATE_FLOORS),
        haar_spectra=haar_spectra,
        deformed_spectra=deformed_spectra,
        mean_projector_by_seed_block=geometry[
            "mean_projector_by_seed_block"
        ],
        seed_block_counts=geometry["seed_block_counts"],
        physical_participation=geometry["participation"],
        physical_polarization=geometry["polarization"],
        physical_frame_overlaps=geometry["frame_overlaps"],
        physical_principal_angles=geometry["principal_angles"],
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--physical-npz",
        type=Path,
        default=Path("output/physical_ensemble_v1.npz"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("output/covariance_model_v1.json"),
    )
    parser.add_argument(
        "--output-npz",
        type=Path,
        default=Path("output/covariance_model_v1.npz"),
    )
    parser.add_argument(
        "--diagnostic-rows",
        type=int,
        default=REGISTERED_DIAGNOSTIC_ROWS,
    )
    parser.add_argument(
        "--model-samples",
        type=int,
        default=REGISTERED_MODEL_SAMPLES,
    )
    args = parser.parse_args()
    result = run(
        args.physical_npz,
        args.output_json,
        args.output_npz,
        diagnostic_rows=args.diagnostic_rows,
        model_samples=args.model_samples,
    )
    print(json.dumps(result, indent=2))
    if not result["all_checks_pass"]:
        raise SystemExit("covariance-model audit failed")


if __name__ == "__main__":
    main()
