#!/usr/bin/env python3
"""Opened lattice-SUSY cohomology calculation with shared geometric statistics."""

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
import scipy

from lgeth.lattice_susy_parent import (
    lattice_susy_response,
    linear_supercharge,
    normalized_cycle_couplings,
    project_component_tangents,
    solve_cycle_union_frame,
)
from lgeth.wick_channels import covariance_matched_wick


VERSION = "v10"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output" / "lattice_susy_v10"
OPENED_CYCLES = (1, 2, 3)
PROSPECTIVE_CYCLES = (4,)
PANEL_KINDS = ("local", "isotropic")
REGISTERED_SEED = 2026081610


def panel_size_for_cycles(cycles: int) -> int:
    """Return the registered tangent-label count."""

    count = int(cycles)
    if count < 1:
        raise ValueError("cycles must be positive")
    return min(8, 5 * count - 1)


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


def _local_candidates(cycles: int, size: int, seed: int) -> np.ndarray:
    """Return balanced single-site candidates across cycle components."""

    count = int(cycles)
    requested = int(size)
    rng = np.random.default_rng(int(seed))
    orders = [rng.permutation(6).tolist() for _ in range(count)]
    used = [0] * count
    coordinates: list[int] = []
    while len(coordinates) < requested:
        progress = False
        for component in range(count):
            if len(coordinates) >= requested:
                break
            if used[component] >= 5:
                continue
            coordinates.append(6 * component + orders[component][used[component]])
            used[component] += 1
            progress = True
        if not progress:
            raise ValueError("local panel exceeds nontrivial tangent dimension")
    return np.eye(6 * count, dtype=complex)[coordinates]


def tangent_panel(
    cycles: int,
    couplings: np.ndarray,
    kind: str,
    *,
    seed: int,
) -> np.ndarray:
    """Construct one registered local or isotropic tangent frame."""

    count = int(cycles)
    size = panel_size_for_cycles(count)
    label = str(kind)
    if label == "local":
        candidates = _local_candidates(count, size, int(seed))
    elif label == "isotropic":
        rng = np.random.default_rng(int(seed))
        candidates = rng.normal(size=(size, 6 * count)) + 1j * rng.normal(
            size=(size, 6 * count)
        )
    else:
        raise ValueError("unknown lattice-SUSY panel kind")
    return project_component_tangents(couplings, candidates, count)


def _run_case(
    cycles: int,
    root: Path,
    panel_kinds: tuple[str, ...],
    seed: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    count = int(cycles)
    if count not in OPENED_CYCLES:
        raise ValueError("case is outside the opened lattice-SUSY registration")
    couplings = normalized_cycle_couplings(count, int(seed) + count)
    frame = solve_cycle_union_frame(count, couplings)
    nilpotency = float(np.linalg.norm((frame.q_out @ frame.q_in).toarray()))
    kernel_checks = {
        "complete_harmonic_rank": frame.projector_frame.shape[1] == 2**count,
        "zero_internal_bandwidth": float(np.ptp(frame.zero_energies)) < 1e-9,
        "open_external_gap": frame.gap > 1e-8,
        "kernel_residual": frame.kernel_residual < 2e-9,
        "orthonormal_frame": frame.orthogonality_error < 2e-10,
        "nilpotent_supercharge": nilpotency < 5e-11,
        "two_nonempty_hodge_maps": frame.q_in.nnz > 0 and frame.q_out.nnz > 0,
    }
    if not all(kernel_checks.values()):
        raise RuntimeError(f"lattice-SUSY kernel failed: {kernel_checks}")

    panels: dict[str, dict[str, Any]] = {}
    projector_motion = 0.0
    for offset, kind in enumerate(panel_kinds):
        tangents = tangent_panel(
            count,
            couplings,
            kind,
            seed=int(seed) + 1_000 * count + offset,
        )
        response = lattice_susy_response(frame, couplings, tangents)
        statistic = covariance_matched_wick(response.total)
        minus_weight = float(np.sum(np.abs(response.minus) ** 2))
        plus_weight = float(np.sum(np.abs(response.plus) ** 2))
        total_weight = minus_weight + plus_weight
        hodge_balance = float(
            4.0 * minus_weight * plus_weight / total_weight**2
        )
        motion = float(np.linalg.norm(response.total))
        projector_motion = max(projector_motion, motion)
        checks = {
            **response.checks,
            "nontrivial_projector_motion": motion > 1e-8,
            "two_nonzero_hodge_branches": min(minus_weight, plus_weight) > 1e-12,
            "finite_wick_statistic": bool(np.isfinite(statistic.R4)),
            "full_channel_support": bool(
                statistic.channel_covariance_eigenvalues[0]
                > 1e-12 * statistic.channel_covariance_eigenvalues[-1]
            ),
        }
        if not all(checks.values()):
            raise RuntimeError(
                f"lattice-SUSY panel m={count} {kind} failed: {checks}"
            )
        arrays_name = f"cycle_union_m{count}_{kind}_{VERSION}.npz"
        arrays_path = root / arrays_name
        _atomic_npz(
            arrays_path,
            couplings=couplings,
            tangents=tangents,
            projector_frame=frame.projector_frame,
            minus=response.minus,
            plus=response.plus,
            total=response.total,
            four_channel_tensor=statistic.tensor,
            wick_tensor=statistic.wick_tensor,
            connected_tensor=statistic.connected,
            channel_covariance_eigenvalues=(
                statistic.channel_covariance_eigenvalues
            ),
        )
        panels[str(kind)] = {
            "kind": str(kind),
            "panel_size": int(tangents.shape[0]),
            "R4": statistic.R4,
            "A_left": statistic.A_left,
            "B_right": statistic.B_right,
            "minus_weight": minus_weight,
            "plus_weight": plus_weight,
            "hodge_balance": hodge_balance,
            "response_norm": motion,
            "branch_sum_relative_error": response.branch_sum_relative_error,
            "direct_relative_error": response.direct_relative_error,
            "orthogonality_relative_error": (
                response.orthogonality_relative_error
            ),
            "target_leakage": response.target_leakage,
            "arrays_file": arrays_name,
            "arrays_sha256": _sha256(arrays_path),
            "checks": checks,
        }
    return {
        "cycles": count,
        "vertices": frame.n_vertices,
        "charge": frame.charge,
        "basis_dimension": len(frame.basis),
        "observed_rank": int(frame.projector_frame.shape[1]),
        "zero_internal_bandwidth": float(np.ptp(frame.zero_energies)),
        "external_gap": frame.gap,
        "kernel_residual": frame.kernel_residual,
        "orthogonality_error": frame.orthogonality_error,
        "nilpotency_residual": nilpotency,
        "projector_motion_norm": projector_motion,
        "kernel_checks": kernel_checks,
        "panels": panels,
        "runtime_seconds": time.perf_counter() - started,
    }


def scientific_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove timestamps, runtimes, paths, and hashes from a result."""

    return {
        "version": payload["version"],
        "configuration": payload["configuration"],
        "cases": [
            {
                key: value
                for key, value in case.items()
                if key != "runtime_seconds"
            }
            | {
                "panels": {
                    name: {
                        key: value
                        for key, value in panel.items()
                        if key not in {"arrays_file", "arrays_sha256"}
                    }
                    for name, panel in case["panels"].items()
                }
            }
            for case in payload["cases"]
        ],
        "all_checks_pass": payload["all_checks_pass"],
    }


def run_pilot(
    root: Path,
    *,
    cycles: tuple[int, ...] = OPENED_CYCLES,
    panel_kinds: tuple[str, ...] = PANEL_KINDS,
    seed: int = REGISTERED_SEED,
) -> dict[str, Any]:
    """Run every opened graph-cohomology case deterministically."""

    started = time.perf_counter()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cases = [
        _run_case(value, root, tuple(panel_kinds), int(seed))
        for value in cycles
    ]
    passed = all(
        all(case["kernel_checks"].values())
        and all(
            all(panel["checks"].values())
            for panel in case["panels"].values()
        )
        for case in cases
    )
    payload = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "cycles": [int(value) for value in cycles],
            "panel_kinds": [str(value) for value in panel_kinds],
            "seed": int(seed),
            "graph_family": "disjoint_union_C6",
            "zero_mode_origin": "independence_complex_cohomology",
        },
        "cases": cases,
        "all_checks_pass": passed,
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
    }
    _atomic_json(root / f"lattice_susy_pilot_{VERSION}.json", payload)
    if not passed:
        raise RuntimeError("lattice-SUSY opened pilot failed")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--preflight", action="store_true")
    arguments = parser.parse_args()
    if not arguments.preflight:
        parser.error("select --preflight")
    result = run_pilot(arguments.root)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
