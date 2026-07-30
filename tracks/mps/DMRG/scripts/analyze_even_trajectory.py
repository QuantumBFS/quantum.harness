from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def _optional_vector(values: np.ndarray) -> list[float | None]:
    return [float(value) if np.isfinite(value) else None for value in values]


def analyze_directory(input_directory: Path) -> dict[str, object]:
    summary = json.loads(
        (input_directory / "summary.json").read_text(encoding="utf-8")
    )
    trajectory = np.load(input_directory / "trajectory.npz")
    running = trajectory["running_bias"]
    means = trajectory["mean_operators"]
    covariances = trajectory["covariance"]
    if len(running) == 0:
        raise ValueError("trajectory contains no variational steps")
    block_sites = (int(summary["length"]) // 3) ** 2
    start = int(0.8 * len(running))
    late = means[start:] / block_sites
    mean = late.mean(axis=0)
    if len(late) >= 2:
        chunk_count = min(12, len(late))
        chunk_means = np.stack(
            [chunk.mean(axis=0) for chunk in np.array_split(late, chunk_count)]
        )
        standard_error = chunk_means.std(axis=0, ddof=1) / np.sqrt(chunk_count)
        z_scores = np.divide(
            mean,
            standard_error,
            out=np.full_like(mean, np.nan),
            where=standard_error > 0.0,
        )
        finite_z = np.abs(z_scores[np.isfinite(z_scores)])
        max_abs_late_z = float(finite_z.max()) if finite_z.size else None
        late_statistics_status = "ESTIMATED_FROM_LATE_WINDOW_CHUNKS"
    else:
        chunk_count = 0
        standard_error = np.full_like(mean, np.nan)
        z_scores = np.full_like(mean, np.nan)
        max_abs_late_z = None
        late_statistics_status = "INSUFFICIENT_LATE_WINDOW_FOR_STANDARD_ERROR"
    checkpoints = [
        max(0, int(len(running) * fraction) - 1)
        for fraction in (0.6, 0.8, 0.9, 1.0)
    ]
    renormalized = -running[checkpoints]
    coupling_drift = renormalized[-1] - renormalized[-2]
    average_covariance = covariances[start:].mean(axis=0)
    eigenvalues = np.linalg.eigvalsh(average_covariance)
    largest_eigenvalue = float(eigenvalues[-1])
    tolerance = (
        np.finfo(float).eps
        * average_covariance.shape[0]
        * max(1.0, abs(largest_eigenvalue))
    )
    if eigenvalues[0] > tolerance:
        covariance_condition_number: float | None = float(
            eigenvalues[-1] / eigenvalues[0]
        )
        covariance_status = "POSITIVE_DEFINITE"
    else:
        covariance_condition_number = None
        covariance_status = "SINGULAR_OR_NOT_POSITIVE_DEFINITE"
    report = {
        "late_statistics_status": late_statistics_status,
        "late_window_samples": int(len(late)),
        "late_window_chunks": chunk_count,
        "late_window_first_step": start + 1,
        "late_window_last_step": len(running),
        "late_mean_per_block_site": _optional_vector(mean),
        "late_chunk_standard_errors": _optional_vector(standard_error),
        "late_z_scores": _optional_vector(z_scores),
        "max_abs_late_z": max_abs_late_z,
        "nearest_neighbor_at_60_80_90_100_percent": renormalized[:, 0].tolist(),
        "coupling_drift_90_to_100_percent": coupling_drift.tolist(),
        "max_abs_coupling_drift_90_to_100_percent": float(
            np.max(np.abs(coupling_drift))
        ),
        "covariance_status": covariance_status,
        "mean_covariance_min_eigenvalue": float(eigenvalues[0]),
        "mean_covariance_max_eigenvalue": largest_eigenvalue,
        "mean_covariance_condition_number": covariance_condition_number,
    }
    (input_directory / "convergence.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the final 20% of a VMCRG run")
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    report = analyze_directory(args.input)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
