#!/usr/bin/env python3
"""Run the binary-symplectic X-cube geometric negative control."""

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

from lgeth.xcube_stabilizer import (
    coefficient_reweighting_control,
    structured_transport_control,
    verify_dense_transport_toy,
    xcube_stabilizer_table,
)


VERSION = "v11"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output" / "xcube_v11"
OPENED_LENGTHS = (2, 3, 4, 5)
PROSPECTIVE_LENGTHS = (6,)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def scientific_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove timestamps, runtimes, and file hashes from a result."""

    projection = {
        "version": payload["version"],
        "configuration": payload["configuration"],
        "dense_toy_audit": payload["dense_toy_audit"],
        "cases": [
            {key: value for key, value in case.items() if key != "runtime_seconds"}
            for case in payload["cases"]
        ],
        "all_checks_pass": payload["all_checks_pass"],
    }
    return json.loads(json.dumps(projection, sort_keys=True))


def run_control(
    root: Path,
    *,
    lengths: tuple[int, ...] = OPENED_LENGTHS,
) -> dict[str, Any]:
    """Audit every opened X-cube size without dense Hilbert allocation."""

    started = time.perf_counter()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    dense_toy = verify_dense_transport_toy()
    cases: list[dict[str, Any]] = []
    for length in lengths:
        case_started = time.perf_counter()
        size = int(length)
        if size not in OPENED_LENGTHS:
            raise ValueError("case is outside the opened X-cube registration")
        table = xcube_stabilizer_table(size)
        coefficient = coefficient_reweighting_control(size)
        transport = structured_transport_control(size)
        expected_logical = 6 * size - 3
        checks = {
            "stabilizer_rank_formula": (
                table.stabilizer_rank == table.n_qubits - expected_logical
            ),
            "degeneracy_formula": table.ground_dimension == 2**expected_logical,
            "coefficient_geometry_zero": all(coefficient["checks"].values()),
            "transport_geometry_structured": all(transport.checks.values()),
            "transport_curvature_scalar": (
                transport.curvature_distinct_eigenvalues == 1
                and transport.connected_curvature_variance == 0.0
            ),
            "dense_transport_identity": all(dense_toy["checks"].values()),
        }
        if not all(checks.values()):
            raise RuntimeError(f"X-cube L={size} control failed: {checks}")
        cases.append(
            {
                "length": size,
                "n_qubits": table.n_qubits,
                "stabilizer_count": int(table.rows.shape[0]),
                "stabilizer_rank": table.stabilizer_rank,
                "logical_qubits": table.logical_qubits,
                "ground_dimension": table.ground_dimension,
                "coefficient_control": coefficient,
                "transport_control": asdict(transport),
                "checks": checks,
                "runtime_seconds": time.perf_counter() - case_started,
            }
        )
    arrays_path = root / f"xcube_geometric_control_{VERSION}.npz"
    _atomic_npz(
        arrays_path,
        lengths=np.asarray([case["length"] for case in cases], dtype=int),
        n_qubits=np.asarray([case["n_qubits"] for case in cases], dtype=int),
        stabilizer_ranks=np.asarray(
            [case["stabilizer_rank"] for case in cases], dtype=int
        ),
        logical_qubits=np.asarray(
            [case["logical_qubits"] for case in cases], dtype=int
        ),
        ground_dimensions=np.asarray(
            [case["ground_dimension"] for case in cases], dtype=np.int64
        ),
        coefficient_curvature=np.zeros(len(cases), dtype=float),
        transport_curvature=np.full(len(cases), -0.5, dtype=float),
        connected_curvature_variance=np.zeros(len(cases), dtype=float),
    )
    passed = all(all(case["checks"].values()) for case in cases)
    payload = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "lengths": [int(value) for value in lengths],
            "boundary_conditions": "periodic",
            "model": "X-cube stabilizer code",
            "deformations": [
                "positive_stabilizer_reweighting",
                "local_isospectral_unitary_transport",
            ],
        },
        "dense_toy_audit": dense_toy,
        "cases": cases,
        "arrays_file": arrays_path.name,
        "arrays_sha256": _sha256(arrays_path),
        "all_checks_pass": passed,
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
    }
    _atomic_json(root / f"xcube_geometric_control_{VERSION}.json", payload)
    if not passed:
        raise RuntimeError("X-cube opened control failed")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--run", action="store_true")
    arguments = parser.parse_args()
    if not arguments.run:
        parser.error("select --run")
    result = run_control(arguments.root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
