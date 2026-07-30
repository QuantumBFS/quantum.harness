"""Fail closed before allocating shots to the cost-sensitivity experiment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .discovery import ANALYSIS_SCHEMA
from .sensitivity_analysis import _sha256


class SensitivityGateError(RuntimeError):
    """Raised when the discovery evidence does not authorize cost simulation."""


def require_final_discovery(analysis_root: Path, matrix_path: Path) -> dict:
    if not os.environ.get("SLURM_JOB_ID"):
        raise SensitivityGateError("cost gate must execute inside Slurm")
    analysis_root = analysis_root.resolve(strict=True)
    matrix_path = matrix_path.resolve(strict=True)
    summary = json.loads(
        (analysis_root / "analysis-summary.json").read_text(encoding="ascii")
    )
    expected_artifacts = {
        "analysis-checksums.sha256",
        "analysis-summary.json",
        "continuation-plan.json",
        "discovery-cells.parquet",
        "discovery-comparisons.parquet",
        "logical-failures.packbits.npy",
        "logical-failure-shots.npy",
    }
    if (
        not isinstance(summary, dict)
        or summary.get("schema_version") != ANALYSIS_SCHEMA
        or summary.get("status") != "final-discovery"
        or summary.get("next_phase_groups") != 0
        or summary.get("initial_matrix_sha256") != _sha256(matrix_path)
        or set(summary.get("artifacts", [])) != expected_artifacts
    ):
        raise SensitivityGateError("discovery is not final for cost sensitivity")
    return {
        "status": "cost-sensitivity-authorized",
        "discovery_analysis": str(analysis_root),
        "discovery_matrix_sha256": _sha256(matrix_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery-analysis", type=Path, required=True)
    parser.add_argument("--discovery-matrix", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            require_final_discovery(
                args.discovery_analysis, args.discovery_matrix
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
