#!/usr/bin/env python3
"""Checkpointed continuum Moore--Read Geometric-ETH calculations."""

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
import scipy

from lgeth.combinatorics import clustered_zero_mode_count
from lgeth.continuum_lll_parent import (
    continuum_operator_panels,
    structured_continuum_operator_panel,
)
from lgeth.manybody_response import KernelFrame, ManyBodyCase
from lgeth.matrix_free_response import solve_kernel_frame_factored
from lgeth.moore_read_parent import build_continuum_moore_read_parent
from lgeth.protected_generator_response import (
    analytic_protected_generator_response,
)
from lgeth.wick_channels import covariance_matched_wick


VERSION = "v9"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output" / "moore_read_v9"
OPENED_PILOT_CASES = ((4, 6), (6, 8))
PRODUCTION_CASES = ((4, 6), (6, 8), (8, 10))
PROSPECTIVE_CASES = ((10, 12),)
REGISTERED_PANELS = 24
REGISTERED_PANEL_SIZE = 8
REGISTERED_SEED = 2026081609
OPERATOR_CLASS = "guiding_density"


def _case_pair(N: int) -> tuple[int, int]:
    particles = int(N)
    return particles, particles + 2


def case_for_particle_number(
    N: int,
    *,
    prospective: bool = False,
) -> ManyBodyCase:
    """Return a registered fixed-four-quasihole Moore--Read case."""

    pair = _case_pair(N)
    allowed = PROSPECTIVE_CASES if prospective else PRODUCTION_CASES
    if pair not in allowed:
        label = "prospective" if prospective else "opened/production"
        raise ValueError(f"case {pair} is not in the {label} registration")
    return ManyBodyCase(
        N=pair[0],
        n_flux=pair[1],
        expected_rank=clustered_zero_mode_count(*pair, k=2, r=2),
        theta_x=0.0,
        theta_y=0.0,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


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


def _source_hashes() -> dict[str, str]:
    sources = (
        SCRIPT_ROOT / "lgeth" / "combinatorics.py",
        SCRIPT_ROOT / "lgeth" / "moore_read_parent.py",
        SCRIPT_ROOT / "lgeth" / "moore_read_audit.py",
        SCRIPT_ROOT / "lgeth" / "protected_generator_response.py",
        SCRIPT_ROOT / "lgeth" / "wick_channels.py",
        Path(__file__).resolve(),
    )
    return {
        str(path.relative_to(SCRIPT_ROOT)): _sha256(path)
        for path in sources
    }


def _case_label(N: int, n_flux: int) -> str:
    return f"N{int(N)}_flux{int(n_flux)}"


def _kernel_paths(root: Path, case: ManyBodyCase) -> tuple[Path, Path]:
    stem = root / "kernels" / f"{_case_label(case.N, case.n_flux)}_{VERSION}"
    return stem.with_suffix(".json"), stem.with_suffix(".npz")


def _panel_paths(
    root: Path,
    case: ManyBodyCase,
    panel: int,
) -> tuple[Path, Path]:
    label = "structured" if int(panel) < 0 else f"panel{int(panel):02d}"
    stem = (
        root
        / "panels"
        / f"{_case_label(case.N, case.n_flux)}_{label}_{VERSION}"
    )
    return stem.with_suffix(".json"), stem.with_suffix(".npz")


def _kernel_identity(case: ManyBodyCase, seed: int) -> dict[str, Any]:
    return {
        "version": VERSION,
        "case": asdict(case),
        "seed": int(seed),
        "parent": "continuum_lll_coherent_three_body",
        "coherent_grid": [case.n_flux, case.n_flux],
        "sources": _source_hashes(),
    }


def prepare_kernel(
    case: ManyBodyCase,
    root: Path,
    *,
    seed: int,
    force: bool = False,
) -> dict[str, Any]:
    """Build and atomically checkpoint one complete Moore--Read kernel."""

    metadata_path, arrays_path = _kernel_paths(root, case)
    identity = _kernel_identity(case, seed)
    identity_hash = _json_hash(identity)
    if not force and metadata_path.exists() and arrays_path.exists():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            payload.get("identity") == identity
            and payload.get("identity_hash") == identity_hash
            and payload.get("arrays_sha256") == _sha256(arrays_path)
            and all(payload.get("checks", {}).values())
        ):
            payload["checkpoint_reused"] = True
            return payload

    started = time.perf_counter()
    system = build_continuum_moore_read_parent(case.N, case.n_flux)
    kernel = solve_kernel_frame_factored(
        system,
        case,
        seed=int(seed) + case.N,
        tolerance=1e-8,
        maxiter=1_500,
    )
    internal_bandwidth = float(np.ptp(kernel.zero_eigenvalues))
    checks = {
        "kernel_count": kernel.observed_rank == case.expected_rank,
        "internal_bandwidth": internal_bandwidth < 1e-8,
        "open_external_gap": kernel.external_gap > 1e-8,
        "kernel_residual": kernel.residual_norm < 5e-6,
        "kernel_orthonormality": kernel.orthonormality_error < 1e-9,
        "factor_is_nonempty": system.constraints.nnz > 0,
    }
    if not all(checks.values()):
        raise RuntimeError(
            f"Moore--Read kernel {case.N, case.n_flux} failed: {checks}"
        )
    _atomic_npz(
        arrays_path,
        frame=kernel.frame,
        zero_eigenvalues=kernel.zero_eigenvalues,
    )
    payload = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "identity": identity,
        "identity_hash": identity_hash,
        "case": asdict(case),
        "basis_dimension": system.basis.dimension,
        "constraint_shape": list(system.constraints.shape),
        "constraint_nnz": int(system.constraints.nnz),
        "kernel_method": kernel.method,
        "observed_rank": kernel.observed_rank,
        "internal_bandwidth": internal_bandwidth,
        "external_gap": kernel.external_gap,
        "kernel_residual_norm": kernel.residual_norm,
        "kernel_orthonormality_error": kernel.orthonormality_error,
        "arrays_sha256": _sha256(arrays_path),
        "checks": checks,
        "runtime_seconds": time.perf_counter() - started,
        "checkpoint_reused": False,
    }
    _atomic_json(metadata_path, payload)
    return payload


def _load_kernel(
    case: ManyBodyCase,
    root: Path,
    *,
    seed: int,
) -> tuple[KernelFrame, dict[str, Any]]:
    metadata_path, arrays_path = _kernel_paths(root, case)
    if not metadata_path.exists() or not arrays_path.exists():
        raise FileNotFoundError(f"missing kernel for {case.N, case.n_flux}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    identity = _kernel_identity(case, seed)
    if (
        metadata.get("identity") != identity
        or metadata.get("identity_hash") != _json_hash(identity)
        or metadata.get("arrays_sha256") != _sha256(arrays_path)
        or not all(metadata.get("checks", {}).values())
    ):
        raise ValueError(f"invalid kernel checkpoint for {case.N, case.n_flux}")
    with np.load(arrays_path, allow_pickle=False) as arrays:
        frame = np.asarray(arrays["frame"], dtype=complex)
        zero = np.asarray(arrays["zero_eigenvalues"], dtype=float)
    return (
        KernelFrame(
            frame=frame,
            zero_eigenvalues=zero,
            external_gap=float(metadata["external_gap"]),
            residual_norm=float(metadata["kernel_residual_norm"]),
            orthonormality_error=float(metadata["kernel_orthonormality_error"]),
            method=str(metadata["kernel_method"]),
            observed_rank=int(metadata["observed_rank"]),
        ),
        metadata,
    )


def run_panel(
    case: ManyBodyCase,
    panel: int,
    root: Path,
    *,
    panels: int,
    panel_size: int,
    seed: int,
    save_channels: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Evaluate one local or structured protected-response panel."""

    index = int(panel)
    if index < -1 or index >= int(panels):
        raise ValueError("panel index is outside the configured range")
    metadata_path, arrays_path = _panel_paths(root, case, index)
    if not force and metadata_path.exists() and arrays_path.exists():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            payload.get("arrays_sha256") == _sha256(arrays_path)
            and all(payload.get("checks", {}).values())
        ):
            payload["checkpoint_reused"] = True
            return payload

    started = time.perf_counter()
    kernel, kernel_metadata = _load_kernel(case, root, seed=seed)
    system = build_continuum_moore_read_parent(case.N, case.n_flux)
    panel_seed = int(seed) + 1_000 * case.N
    if index == -1:
        anchors, generators = structured_continuum_operator_panel(
            case.n_flux,
            OPERATOR_CLASS,
            panel_size=int(panel_size),
        )
        kind = "structured_line"
    else:
        all_anchors, all_generators = continuum_operator_panels(
            case.n_flux,
            OPERATOR_CLASS,
            panels=int(panels),
            panel_size=int(panel_size),
            seed=panel_seed,
        )
        anchors = all_anchors[index]
        generators = all_generators[index]
        kind = "local_guiding_density"
    response = analytic_protected_generator_response(
        system,
        kernel,
        generators,
    )
    result = covariance_matched_wick(response.channels)
    support = result.channel_covariance_eigenvalues
    checks = {
        "kernel_checkpoint": all(kernel_metadata["checks"].values()),
        "response_identity": response.maximum_relative_residual < 1e-9,
        "kernel_leakage": response.maximum_kernel_leakage < 1e-9,
        "fiber_tangent_zero": response.tangent_fiber_norm < 1e-8,
        "finite_wick_statistic": bool(np.isfinite(result.R4)),
        "full_channel_support": bool(
            support[0] > 1e-12 * support[-1]
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(
            f"Moore--Read panel {case.N, index} failed: {checks}"
        )
    arrays: dict[str, np.ndarray] = {
        "anchors": np.asarray(anchors, dtype=int),
        "generators": np.asarray(generators, dtype=complex),
        "left_eigenvalues": result.left_eigenvalues,
        "right_eigenvalues": result.right_eigenvalues,
        "channel_covariance_eigenvalues": support,
        "four_channel_tensor": result.tensor,
        "wick_tensor": result.wick_tensor,
        "connected_tensor": result.connected,
    }
    if save_channels:
        arrays["response_channels"] = response.channels
    _atomic_npz(arrays_path, **arrays)
    payload = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "case": asdict(case),
        "panel": index,
        "panel_kind": kind,
        "operator_class": OPERATOR_CLASS,
        "panel_seed": panel_seed,
        "panel_size": int(panel_size),
        "basis_dimension": system.basis.dimension,
        "rank": case.expected_rank,
        "R4": result.R4,
        "A_left": result.A_left,
        "B_right": result.B_right,
        "maximum_relative_residual": response.maximum_relative_residual,
        "maximum_kernel_leakage": response.maximum_kernel_leakage,
        "tangent_fiber_norm": response.tangent_fiber_norm,
        "channels_saved": bool(save_channels),
        "kernel_identity_hash": kernel_metadata["identity_hash"],
        "arrays_sha256": _sha256(arrays_path),
        "checks": checks,
        "runtime_seconds": time.perf_counter() - started,
        "checkpoint_reused": False,
    }
    _atomic_json(metadata_path, payload)
    return payload


def scientific_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove timestamps, paths, hashes, and runtimes from a pilot payload."""

    return {
        "version": payload["version"],
        "configuration": payload["configuration"],
        "cases": [
            {
                "case": item["case"],
                "basis_dimension": item["basis_dimension"],
                "constraint_shape": item["constraint_shape"],
                "constraint_nnz": item["constraint_nnz"],
                "observed_rank": item["observed_rank"],
                "internal_bandwidth": item["internal_bandwidth"],
                "external_gap": item["external_gap"],
                "kernel_residual_norm": item["kernel_residual_norm"],
                "kernel_checks": item["kernel_checks"],
                "panels": [
                    {
                        key: panel[key]
                        for key in (
                            "panel",
                            "panel_kind",
                            "operator_class",
                            "panel_size",
                            "rank",
                            "R4",
                            "A_left",
                            "B_right",
                            "maximum_relative_residual",
                            "maximum_kernel_leakage",
                            "tangent_fiber_norm",
                            "checks",
                        )
                    }
                    for panel in item["panels"]
                ],
            }
            for item in payload["cases"]
        ],
        "all_checks_pass": payload["all_checks_pass"],
    }


def run_pilot(
    root: Path,
    *,
    cases: tuple[tuple[int, int], ...] = OPENED_PILOT_CASES,
    panels: int = 2,
    panel_size: int = REGISTERED_PANEL_SIZE,
    seed: int = REGISTERED_SEED,
) -> dict[str, Any]:
    """Run opened kernels plus local and structured response panels."""

    started = time.perf_counter()
    summaries: list[dict[str, Any]] = []
    for N, n_flux in cases:
        if (int(N), int(n_flux)) not in OPENED_PILOT_CASES:
            raise ValueError("pilot case is outside the opened registration")
        case = case_for_particle_number(int(N), prospective=False)
        if case.n_flux != int(n_flux):
            raise ValueError("pilot flux does not match the registered sequence")
        kernel = prepare_kernel(case, root, seed=int(seed))
        panel_summaries = [
            run_panel(
                case,
                panel,
                root,
                panels=int(panels),
                panel_size=int(panel_size),
                seed=int(seed),
                save_channels=True,
            )
            for panel in range(int(panels))
        ]
        panel_summaries.append(
            run_panel(
                case,
                -1,
                root,
                panels=int(panels),
                panel_size=int(panel_size),
                seed=int(seed),
                save_channels=True,
            )
        )
        summaries.append(
            {
                "case": kernel["case"],
                "basis_dimension": kernel["basis_dimension"],
                "constraint_shape": kernel["constraint_shape"],
                "constraint_nnz": kernel["constraint_nnz"],
                "observed_rank": kernel["observed_rank"],
                "internal_bandwidth": kernel["internal_bandwidth"],
                "external_gap": kernel["external_gap"],
                "kernel_residual_norm": kernel["kernel_residual_norm"],
                "kernel_checks": kernel["checks"],
                "panels": panel_summaries,
            }
        )
    all_checks = all(
        all(case["kernel_checks"].values())
        and all(all(panel["checks"].values()) for panel in case["panels"])
        for case in summaries
    )
    payload = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "cases": [list(case) for case in cases],
            "panels": int(panels),
            "panel_size": int(panel_size),
            "seed": int(seed),
            "operator_class": OPERATOR_CLASS,
        },
        "cases": summaries,
        "all_checks_pass": all_checks,
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
    }
    _atomic_json(root / f"moore_read_pilot_{VERSION}.json", payload)
    if not all_checks:
        raise RuntimeError("Moore--Read opened pilot failed")
    return payload


def aggregate(
    root: Path,
    *,
    cases: tuple[tuple[int, int], ...],
    panels: int,
) -> dict[str, Any]:
    """Aggregate an exactly complete grid of local panel summaries."""

    case_summaries: list[dict[str, Any]] = []
    for N, n_flux in cases:
        case = case_for_particle_number(
            int(N),
            prospective=(int(N), int(n_flux)) in PROSPECTIVE_CASES,
        )
        values = []
        for panel in range(int(panels)):
            metadata_path, arrays_path = _panel_paths(root, case, panel)
            if not metadata_path.exists() or not arrays_path.exists():
                raise RuntimeError("aggregate requires a complete panel grid")
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if payload.get("arrays_sha256") != _sha256(arrays_path):
                raise RuntimeError("panel array hash mismatch")
            if not all(payload.get("checks", {}).values()):
                raise RuntimeError("aggregate includes a failed panel")
            values.append(float(payload["R4"]))
        case_summaries.append(
            {
                "N": case.N,
                "n_flux": case.n_flux,
                "rank": case.expected_rank,
                "R4": values,
                "R4_median": float(np.median(values)),
            }
        )
    result = {
        "version": VERSION,
        "configuration": {
            "cases": [list(case) for case in cases],
            "panels": int(panels),
        },
        "cases": case_summaries,
        "complete_panel_grid": True,
    }
    _atomic_json(root / f"moore_read_aggregate_{VERSION}.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--prepare-kernel", type=int)
    parser.add_argument("--panel", nargs=2, type=int, metavar=("N", "PANEL"))
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    selected = sum(
        (
            bool(arguments.preflight),
            arguments.prepare_kernel is not None,
            arguments.panel is not None,
            bool(arguments.aggregate),
        )
    )
    if selected != 1:
        parser.error("select exactly one execution mode")
    if arguments.preflight:
        result = run_pilot(arguments.root)
    elif arguments.prepare_kernel is not None:
        case = case_for_particle_number(arguments.prepare_kernel)
        result = prepare_kernel(
            case,
            arguments.root,
            seed=REGISTERED_SEED,
            force=arguments.force,
        )
    elif arguments.panel is not None:
        N, panel = arguments.panel
        case = case_for_particle_number(N)
        result = run_panel(
            case,
            panel,
            arguments.root,
            panels=REGISTERED_PANELS,
            panel_size=REGISTERED_PANEL_SIZE,
            seed=REGISTERED_SEED,
            save_channels=N <= 6,
            force=arguments.force,
        )
    else:
        result = aggregate(
            arguments.root,
            cases=PRODUCTION_CASES,
            panels=REGISTERED_PANELS,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
