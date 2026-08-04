#!/usr/bin/env python3
"""Generate analytic decomposable and one-sided control audit v7."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.hodge_response import (
    HodgeSignature,
    decomposable_curvature,
    hodge_response,
)
from lgeth.hodge_wick import hodge_gaussian_r4_reference
from lgeth.susy_cohomology import (
    analytic_decomposable_curvature_multiplicities,
    decomposable_bps_rank,
    decomposable_couplings,
    decomposable_tangent,
    solve_bps_frame,
)
from lgeth.wick_channels import gaussian_r4_reference


SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_JSON = SCRIPT_ROOT / "output" / "susy_hodge_v7_controls.json"
VERSION = "v7"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _source_hashes() -> dict[str, str]:
    paths = (
        Path(__file__).resolve(),
        SCRIPT_ROOT / "lgeth" / "susy_cohomology.py",
        SCRIPT_ROOT / "lgeth" / "hodge_response.py",
        SCRIPT_ROOT / "lgeth" / "hodge_wick.py",
        SCRIPT_ROOT / "lgeth" / "wick_channels.py",
    )
    return {str(path.relative_to(SCRIPT_ROOT)): sha256(path) for path in paths}


def _atomic_summary(
    matrix: np.ndarray,
    alpha: float,
) -> tuple[dict[str, int], float, list[float]]:
    eigenvalues = np.linalg.eigvalsh(0.5 * (matrix + matrix.conj().T))
    target = 1.0 / float(alpha) ** 2
    tolerance = 2e-11
    counts = {
        "negative": int(np.count_nonzero(np.isclose(eigenvalues, -target, atol=tolerance))),
        "zero": int(np.count_nonzero(np.isclose(eigenvalues, 0.0, atol=tolerance))),
        "positive": int(np.count_nonzero(np.isclose(eigenvalues, target, atol=tolerance))),
    }
    atoms = np.asarray([-target, 0.0, target])
    error = float(np.max(np.min(np.abs(eigenvalues[:, None] - atoms[None, :]), axis=1)))
    return counts, error, eigenvalues.tolist()


def _one_sided_signature() -> HodgeSignature:
    target = np.asarray([0.42, 0.27, 0.18, 0.09, 0.04])
    external = np.asarray([0.51, 0.31, 0.18])
    zero_target = np.zeros_like(target)
    return HodgeSignature(
        channel_count=8,
        target_rank=5,
        minus_weight=1.0,
        plus_weight=0.0,
        hodge_balance=0.0,
        minus_channel_covariance=np.eye(8),
        plus_channel_covariance=np.zeros((8, 8)),
        minus_target_eigenvalues=target,
        plus_target_eigenvalues=zero_target,
        minus_external_eigenvalues=external,
        plus_external_eigenvalues=np.empty(0),
        minus_target_effective_rank=3.5,
        plus_target_effective_rank=0.0,
        minus_external_effective_rank=2.5,
        plus_external_effective_rank=0.0,
        minus_target_entropy=0.8,
        plus_target_entropy=0.0,
        minus_external_entropy=0.8,
        plus_external_entropy=0.0,
        orthogonality_relative_error=0.0,
    )


def generate_controls(output_json: Path = OUTPUT_JSON) -> dict[str, Any]:
    """Write exact curvature atoms and immutable one-sided null regression."""

    alpha = 1.7
    couplings6 = decomposable_couplings(6, alpha)
    frame6 = solve_bps_frame(6, 3, couplings6, dense_cutoff=64)
    tangents6 = np.stack(
        [
            decomposable_tangent(6, "12", 3),
            decomposable_tangent(6, "13", 4),
        ]
    )
    response6 = hodge_response(frame6, couplings6, tangents6)
    diagonal_counts, diagonal_error, diagonal_eigenvalues = _atomic_summary(
        decomposable_curvature(response6, 0), alpha
    )
    off_counts, off_error, off_eigenvalues = _atomic_summary(
        decomposable_curvature(response6, 0, 1), alpha
    )
    expected_diagonal = analytic_decomposable_curvature_multiplicities(
        6, 3, "diagonal"
    )
    expected_off = analytic_decomposable_curvature_multiplicities(
        6, 3, "off_diagonal"
    )

    couplings8 = decomposable_couplings(8, alpha)
    rank8 = decomposable_bps_rank(8, 4)
    frame8 = solve_bps_frame(
        8,
        4,
        couplings8,
        dense_cutoff=128,
        expected_rank_override=rank8,
    )

    signature = _one_sided_signature()
    hodge_reference = hodge_gaussian_r4_reference(signature, 8, 32, 211)
    immutable_reference = gaussian_r4_reference(
        signature.minus_target_eigenvalues,
        signature.minus_external_eigenvalues,
        8,
        32,
        211,
    )
    one_sided_difference = float(
        np.max(np.abs(hodge_reference - immutable_reference))
    )
    checks = {
        "N6_diagonal_multiplicities": diagonal_counts == expected_diagonal,
        "N6_off_diagonal_multiplicities": off_counts == expected_off,
        "N6_curvature_atoms": max(diagonal_error, off_error) < 2e-11,
        "N8_decomposable_rank": frame8.projector_frame.shape[1] == rank8 == 60,
        "N8_open_gap": frame8.gap > 1e-10,
        "one_sided_exact_regression": one_sided_difference == 0.0,
    }
    payload = {
        "version": VERSION,
        "sources": _source_hashes(),
        "decomposable_N6": {
            "alpha": alpha,
            "bps_rank": int(frame6.projector_frame.shape[1]),
            "gap": float(frame6.gap),
            "diagonal_multiplicities": diagonal_counts,
            "off_diagonal_multiplicities": off_counts,
            "diagonal_max_atom_error": diagonal_error,
            "off_diagonal_max_atom_error": off_error,
            "diagonal_eigenvalues": diagonal_eigenvalues,
            "off_diagonal_eigenvalues": off_eigenvalues,
        },
        "decomposable_N8": {
            "bps_rank": int(frame8.projector_frame.shape[1]),
            "expected_rank": rank8,
            "gap": float(frame8.gap),
            "kernel_residual": float(frame8.kernel_residual),
        },
        "one_sided_regression": {
            "samples": 32,
            "seed": 211,
            "max_absolute_difference": one_sided_difference,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    if not payload["passed"]:
        raise RuntimeError(f"SUSY/Hodge control audit failed: {checks}")
    _atomic_json(output_json, payload)
    return payload


def main() -> None:
    payload = generate_controls()
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
