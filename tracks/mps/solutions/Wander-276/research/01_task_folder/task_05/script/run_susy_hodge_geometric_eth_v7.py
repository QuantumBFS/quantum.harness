#!/usr/bin/env python3
"""Checkpointed and sealed N=2 SYK Hodge-response runner v7."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lgeth.hodge_response import (
    coupling_panels,
    hodge_response,
    hodge_signature,
    scalable_covariance_matched_wick,
)
from lgeth.hodge_response import HodgeSignature
from lgeth.hodge_wick import hodge_gaussian_r4_reference
from lgeth.susy_cohomology import (
    BPSFrame,
    charge_basis,
    charge_hamiltonian,
    cubic_supercharge,
    expected_generic_bps_rank,
    normalized_complex_couplings,
    solve_bps_frame,
)
from lgeth.wick_channels import gaussian_r4_reference


VERSION = "v7"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"
CHECKPOINT_ROOT = OUTPUT_ROOT / "susy_hodge_v7_checkpoints"
REGISTERED_SIZES = (8, 10, 12, 14)
REGISTERED_SECTORS = ("central", "adjacent")
REGISTERED_PANEL_KINDS = ("sparse", "isotropic")
PANEL_SIZE = 8
REALIZATION_COUNTS = {8: 64, 10: 48, 12: 32, 14: 24}
NULL_REPLICATES = 2_000
NULL_DRAWS_PER_REALIZATION = 128
BASE_SEED = 2026080111
FORBIDDEN_SAFE_TOKENS = ("r4", "four_point", "connected")
PILOT_SAFE_JSON = OUTPUT_ROOT / "susy_hodge_v7_covariates_pilot.json"
PILOT_JSON = OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot.json"
PILOT_NPZ = OUTPUT_ROOT / "susy_hodge_v7_outcomes_pilot.npz"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    temporary.replace(path)


def _atomic_text(path: Path, value: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _derived_seed(*parts: object) -> int:
    label = "|".join(str(item) for item in (BASE_SEED, VERSION, *parts))
    return int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")


def _source_hashes() -> dict[str, str]:
    paths = (
        Path(__file__).resolve(),
        SCRIPT_ROOT / "lgeth" / "susy_cohomology.py",
        SCRIPT_ROOT / "lgeth" / "hodge_response.py",
        SCRIPT_ROOT / "lgeth" / "hodge_wick.py",
        SCRIPT_ROOT / "lgeth" / "wick_channels.py",
    )
    return {str(path.relative_to(SCRIPT_ROOT)): sha256(path) for path in paths}


def _sector_charge(N: int, sector: str) -> int:
    modes = int(N)
    label = str(sector)
    if modes % 2:
        raise ValueError("registered SUSY sequence requires even N")
    if label == "central":
        return modes // 2
    if label == "adjacent":
        return modes // 2 - 1
    raise ValueError(f"sector must be one of {REGISTERED_SECTORS}")


def _validate_case(
    N: int,
    sector: str,
    realization: int,
    *,
    reduced: bool,
) -> tuple[int, str, int, int]:
    modes = int(N)
    label = str(sector)
    index = int(realization)
    charge = _sector_charge(modes, label)
    if not reduced:
        if modes not in REGISTERED_SIZES:
            raise ValueError(f"N must be one of {REGISTERED_SIZES}")
        if not 0 <= index < REALIZATION_COUNTS[modes]:
            raise ValueError("realization is outside the registered range")
    elif modes < 6 or index < 0:
        raise ValueError("invalid reduced realization")
    return modes, label, index, charge


def kernel_paths(
    root: Path,
    N: int,
    sector: str,
    realization: int,
) -> tuple[Path, Path]:
    stem = (
        Path(root)
        / "kernels"
        / f"N{int(N)}_{sector}_seed{int(realization):03d}_{VERSION}"
    )
    return stem.with_suffix(".json"), stem.with_suffix(".npz")


def panel_paths(
    root: Path,
    N: int,
    sector: str,
    realization: int,
    panel_kind: str,
) -> tuple[Path, Path, Path]:
    stem = (
        Path(root)
        / "panels"
        / (
            f"N{int(N)}_{sector}_seed{int(realization):03d}_"
            f"{panel_kind}_{VERSION}"
        )
    )
    return (
        stem.with_suffix(".json"),
        stem.with_suffix(".npz"),
        Path(str(stem) + ".outcome.json"),
    )


def prepare_realization(
    N: int,
    sector: str,
    realization: int,
    *,
    root: Path = CHECKPOINT_ROOT,
    reduced: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Solve and checkpoint one coupling realization without any four-point data."""

    modes, label, index, charge = _validate_case(
        N,
        sector,
        realization,
        reduced=reduced,
    )
    coupling_seed = _derived_seed(modes, label, index, "couplings")
    identity = {
        "version": VERSION,
        "N": modes,
        "sector": label,
        "charge": charge,
        "realization": index,
        "coupling_seed": coupling_seed,
        "expected_rank": expected_generic_bps_rank(modes, charge),
        "reduced": bool(reduced),
        "sources": _source_hashes(),
    }
    identity_hash = _json_hash(identity)
    metadata_path, arrays_path = kernel_paths(root, modes, label, index)
    if not force and metadata_path.is_file() and arrays_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            metadata.get("identity") == identity
            and metadata.get("identity_hash") == identity_hash
            and metadata.get("arrays_sha256") == sha256(arrays_path)
            and all(metadata.get("checks", {}).values())
        ):
            return metadata
        raise ValueError("SUSY realization checkpoint identity mismatch")
    couplings = normalized_complex_couplings(modes, coupling_seed)
    frame = solve_bps_frame(modes, charge, couplings, dense_cutoff=4096)
    _atomic_npz(
        arrays_path,
        couplings=couplings,
        projector_frame=frame.projector_frame,
        complement_frame=frame.complement_frame,
        positive_energies=frame.positive_energies,
    )
    checks = {
        "expected_bps_rank": frame.projector_frame.shape[1]
        == identity["expected_rank"],
        "open_external_gap": frame.gap > 1e-10,
        "kernel_residual": frame.kernel_residual < 1e-8,
        "orthonormal_frame": frame.orthogonality_error < 1e-10,
        "unit_coupling_norm": abs(float(np.linalg.norm(couplings)) - 1.0)
        < 1e-13,
    }
    metadata = {
        "identity": identity,
        "identity_hash": identity_hash,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "hilbert_dimension": len(frame.basis),
        "bps_rank": frame.projector_frame.shape[1],
        "complement_rank": frame.complement_frame.shape[1],
        "gap": frame.gap,
        "kernel_residual": frame.kernel_residual,
        "orthogonality_error": frame.orthogonality_error,
        "arrays_sha256": sha256(arrays_path),
        "checks": checks,
        "passed": all(checks.values()),
    }
    if not metadata["passed"]:
        raise RuntimeError(f"SUSY realization audit failed: {checks}")
    _atomic_json(metadata_path, metadata)
    return metadata


def _load_frame(
    root: Path,
    N: int,
    sector: str,
    realization: int,
) -> tuple[dict[str, Any], np.ndarray, BPSFrame]:
    metadata_path, arrays_path = kernel_paths(root, N, sector, realization)
    if not metadata_path.is_file() or not arrays_path.is_file():
        raise FileNotFoundError("missing SUSY realization checkpoint")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("arrays_sha256") != sha256(arrays_path):
        raise ValueError("SUSY realization array hash mismatch")
    with np.load(arrays_path) as arrays:
        couplings = np.asarray(arrays["couplings"], dtype=complex)
        projector = np.asarray(arrays["projector_frame"], dtype=complex)
        complement = np.asarray(arrays["complement_frame"], dtype=complex)
        energies = np.asarray(arrays["positive_energies"], dtype=float)
    charge = int(metadata["identity"]["charge"])
    q_in = cubic_supercharge(N, charge - 3, couplings)
    q_out = cubic_supercharge(N, charge, couplings)
    hamiltonian = charge_hamiltonian(N, charge, couplings)
    frame = BPSFrame(
        N=int(N),
        charge=charge,
        basis=charge_basis(N, charge),
        projector_frame=projector,
        complement_frame=complement,
        positive_energies=energies,
        gap=float(energies[0]),
        kernel_residual=float(metadata["kernel_residual"]),
        orthogonality_error=float(metadata["orthogonality_error"]),
        expected_rank=int(metadata["identity"]["expected_rank"]),
        q_in=q_in,
        q_out=q_out,
        hamiltonian=hamiltonian,
    )
    return metadata, couplings, frame


def _signature_arrays(signature: Any) -> dict[str, np.ndarray]:
    return {
        "minus_channel_covariance": signature.minus_channel_covariance,
        "plus_channel_covariance": signature.plus_channel_covariance,
        "minus_target_eigenvalues": signature.minus_target_eigenvalues,
        "plus_target_eigenvalues": signature.plus_target_eigenvalues,
        "minus_external_eigenvalues": signature.minus_external_eigenvalues,
        "plus_external_eigenvalues": signature.plus_external_eigenvalues,
    }


def _signature_from_safe(
    safe: dict[str, Any],
    arrays: Any,
) -> HodgeSignature:
    scalars = safe["signature"]
    return HodgeSignature(
        channel_count=int(scalars["channel_count"]),
        target_rank=int(scalars["target_rank"]),
        minus_weight=float(scalars["minus_weight"]),
        plus_weight=float(scalars["plus_weight"]),
        hodge_balance=float(scalars["hodge_balance"]),
        minus_channel_covariance=np.asarray(
            arrays["minus_channel_covariance"], dtype=complex
        ),
        plus_channel_covariance=np.asarray(
            arrays["plus_channel_covariance"], dtype=complex
        ),
        minus_target_eigenvalues=np.asarray(
            arrays["minus_target_eigenvalues"], dtype=float
        ),
        plus_target_eigenvalues=np.asarray(
            arrays["plus_target_eigenvalues"], dtype=float
        ),
        minus_external_eigenvalues=np.asarray(
            arrays["minus_external_eigenvalues"], dtype=float
        ),
        plus_external_eigenvalues=np.asarray(
            arrays["plus_external_eigenvalues"], dtype=float
        ),
        minus_target_effective_rank=float(
            scalars["minus_target_effective_rank"]
        ),
        plus_target_effective_rank=float(scalars["plus_target_effective_rank"]),
        minus_external_effective_rank=float(
            scalars["minus_external_effective_rank"]
        ),
        plus_external_effective_rank=float(
            scalars["plus_external_effective_rank"]
        ),
        minus_target_entropy=float(scalars["minus_target_entropy"]),
        plus_target_entropy=float(scalars["plus_target_entropy"]),
        minus_external_entropy=float(scalars["minus_external_entropy"]),
        plus_external_entropy=float(scalars["plus_external_entropy"]),
        orthogonality_relative_error=float(
            scalars["orthogonality_relative_error"]
        ),
    )


def _safe_serialization_check(payload: dict[str, Any]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    return not any(token in serialized for token in FORBIDDEN_SAFE_TOKENS)


def _positive_covariance_spectrum(values: np.ndarray) -> np.ndarray:
    spectrum = np.maximum(np.asarray(values, dtype=float), 0.0)
    largest = float(np.max(spectrum))
    if largest <= 0.0:
        raise ValueError("covariance spectrum has no positive support")
    return spectrum[spectrum > 1e-12 * largest]


def _banked_complete_medians(
    banks: np.ndarray,
    replicates: int,
    seed: int,
) -> np.ndarray:
    """Draw one bank entry per realization and aggregate by the median."""

    values = np.asarray(banks, dtype=float)
    count = int(replicates)
    if values.ndim != 2 or min(values.shape) < 1 or count < 1:
        raise ValueError("null banks and replicate count are invalid")
    rng = np.random.default_rng(int(seed))
    selections = rng.integers(
        0,
        values.shape[1],
        size=(count, values.shape[0]),
    )
    realization_indices = np.arange(values.shape[0])[None, :]
    draws = values[realization_indices, selections]
    return np.median(draws, axis=1)


def run_panel(
    N: int,
    sector: str,
    realization: int,
    panel_kind: str,
    *,
    root: Path = CHECKPOINT_ROOT,
    reduced: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Evaluate one panel while isolating the physical statistic in a sidecar."""

    modes, label, index, _ = _validate_case(
        N,
        sector,
        realization,
        reduced=reduced,
    )
    kind = str(panel_kind)
    if kind not in REGISTERED_PANEL_KINDS:
        raise ValueError(f"panel kind must be one of {REGISTERED_PANEL_KINDS}")
    safe_path, arrays_path, outcome_path = panel_paths(
        root,
        modes,
        label,
        index,
        kind,
    )
    if not force and safe_path.is_file() and arrays_path.is_file() and outcome_path.is_file():
        safe = json.loads(safe_path.read_text(encoding="utf-8"))
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        if (
            safe.get("arrays_sha256") == sha256(arrays_path)
            and outcome.get("safe_identity_hash") == safe.get("identity_hash")
            and all(safe.get("checks", {}).values())
        ):
            return {"safe": safe, "outcome": outcome}
        raise ValueError("SUSY panel checkpoint identity mismatch")
    kernel, couplings, frame = _load_frame(root, modes, label, index)
    panel_seed = _derived_seed(modes, label, index, "panels")
    tangents = coupling_panels(couplings, PANEL_SIZE, panel_seed)[kind]
    response = hodge_response(frame, couplings, tangents)
    signature = hodge_signature(response)
    statistic = scalable_covariance_matched_wick(response.total)
    safe_identity = {
        "version": VERSION,
        "N": modes,
        "sector": label,
        "charge": frame.charge,
        "realization": index,
        "panel_kind": kind,
        "panel_seed": panel_seed,
        "kernel_identity_hash": kernel["identity_hash"],
        "sources": _source_hashes(),
    }
    safe_identity_hash = _json_hash(safe_identity)
    arrays = {
        "tangents": tangents,
        **_signature_arrays(signature),
        "total_target_eigenvalues": statistic.left_eigenvalues,
        "total_external_eigenvalues": statistic.right_eigenvalues,
    }
    _atomic_npz(arrays_path, **arrays)
    signature_scalars = {
        "channel_count": signature.channel_count,
        "target_rank": signature.target_rank,
        "minus_weight": signature.minus_weight,
        "plus_weight": signature.plus_weight,
        "hodge_balance": signature.hodge_balance,
        "minus_target_effective_rank": signature.minus_target_effective_rank,
        "plus_target_effective_rank": signature.plus_target_effective_rank,
        "minus_external_effective_rank": signature.minus_external_effective_rank,
        "plus_external_effective_rank": signature.plus_external_effective_rank,
        "minus_target_entropy": signature.minus_target_entropy,
        "plus_target_entropy": signature.plus_target_entropy,
        "minus_external_entropy": signature.minus_external_entropy,
        "plus_external_entropy": signature.plus_external_entropy,
        "orthogonality_relative_error": signature.orthogonality_relative_error,
    }
    checks = {
        **response.checks,
        "full_channel_support": len(statistic.channel_covariance_eigenvalues)
        == PANEL_SIZE,
        "safe_arrays_exclude_response_matrices": set(arrays)
        == {
            "tangents",
            "minus_channel_covariance",
            "plus_channel_covariance",
            "minus_target_eigenvalues",
            "plus_target_eigenvalues",
            "minus_external_eigenvalues",
            "plus_external_eigenvalues",
            "total_target_eigenvalues",
            "total_external_eigenvalues",
        },
        "finite_hodge_signature": all(
            np.isfinite(value) for value in signature_scalars.values()
        ),
    }
    safe = {
        "identity": safe_identity,
        "identity_hash": safe_identity_hash,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "kernel": {
            "bps_rank": kernel["bps_rank"],
            "complement_rank": kernel["complement_rank"],
            "gap": kernel["gap"],
            "kernel_residual": kernel["kernel_residual"],
        },
        "signature": signature_scalars,
        "spectrum_lengths": {
            key: int(np.asarray(value).size)
            for key, value in _signature_arrays(signature).items()
        },
        "arrays_sha256": sha256(arrays_path),
        "checks": checks,
        "passed": all(checks.values()),
    }
    safe["checks"]["no_outcome_leakage"] = _safe_serialization_check(safe)
    safe["passed"] = all(safe["checks"].values())
    if not safe["passed"]:
        raise RuntimeError(f"safe SUSY panel audit failed: {safe['checks']}")
    _atomic_json(safe_path, safe)
    outcome = {
        "version": VERSION,
        "N": modes,
        "sector": label,
        "realization": index,
        "panel_kind": kind,
        "safe_identity_hash": safe_identity_hash,
        "safe_arrays_sha256": safe["arrays_sha256"],
        "R4": float(statistic.R4),
    }
    if not np.isfinite(outcome["R4"]):
        raise RuntimeError("physical response statistic is not finite")
    _atomic_json(outcome_path, outcome)
    return {"safe": safe, "outcome": outcome}


def write_safe_covariates(
    cases: list[tuple[int, str, int, str]],
    *,
    root: Path = CHECKPOINT_ROOT,
    output_json: Path,
) -> dict[str, Any]:
    """Aggregate safe panel records without opening outcome sidecars."""

    records: list[dict[str, Any]] = []
    for case in cases:
        safe_path, arrays_path, _ = panel_paths(root, *case)
        if not safe_path.is_file() or not arrays_path.is_file():
            raise FileNotFoundError("missing safe SUSY panel checkpoint")
        safe = json.loads(safe_path.read_text(encoding="utf-8"))
        if safe.get("arrays_sha256") != sha256(arrays_path):
            raise ValueError("safe SUSY panel array hash mismatch")
        if not all(safe.get("checks", {}).values()):
            raise ValueError("safe SUSY panel contains a failed check")
        records.append(safe)
    payload = {
        "version": VERSION,
        "records": records,
        "checks": {
            "complete_requested_grid": len(records) == len(cases),
            "all_safe_checks": all(
                all(record["checks"].values()) for record in records
            ),
        },
    }
    payload["checks"]["no_outcome_leakage"] = _safe_serialization_check(payload)
    payload["passed"] = all(payload["checks"].values())
    if not payload["passed"]:
        raise RuntimeError(f"safe covariate audit failed: {payload['checks']}")
    _atomic_json(output_json, payload)
    return payload


def aggregate_pilot(
    cases: list[tuple[int, str, int, str]],
    *,
    root: Path = CHECKPOINT_ROOT,
    null_samples: int = NULL_REPLICATES,
    null_draws_per_realization: int = NULL_DRAWS_PER_REALIZATION,
    seed: int = BASE_SEED,
    safe_output_json: Path = PILOT_SAFE_JSON,
    output_json: Path = PILOT_JSON,
    output_npz: Path = PILOT_NPZ,
) -> dict[str, Any]:
    """Open sequential pilot outcomes after a complete safe-covariate audit."""

    if (
        int(null_samples) < 1
        or int(null_draws_per_realization) < 1
        or not cases
    ):
        raise ValueError("pilot aggregation requires cases and null samples")
    write_safe_covariates(cases, root=root, output_json=safe_output_json)
    grouped: dict[tuple[int, str, str], list[tuple[int, dict, Any, float]]] = {}
    for case in sorted(cases):
        safe_path, arrays_path, outcome_path = panel_paths(root, *case)
        safe = json.loads(safe_path.read_text(encoding="utf-8"))
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        if (
            outcome.get("safe_identity_hash") != safe.get("identity_hash")
            or outcome.get("safe_arrays_sha256") != safe.get("arrays_sha256")
            or safe.get("arrays_sha256") != sha256(arrays_path)
        ):
            raise ValueError("pilot outcome identity mismatch")
        with np.load(arrays_path) as loaded:
            copied = {key: np.asarray(loaded[key]) for key in loaded.files}
        group = (int(case[0]), str(case[1]), str(case[3]))
        grouped.setdefault(group, []).append(
            (int(case[2]), safe, copied, float(outcome["R4"]))
        )
    output_arrays: dict[str, np.ndarray] = {}
    summaries: list[dict[str, Any]] = []
    for (N, sector, panel_kind), records in sorted(grouped.items()):
        records.sort(key=lambda item: item[0])
        physical = np.asarray([item[3] for item in records], dtype=float)
        signatures = [
            _signature_from_safe(item[1], item[2]) for item in records
        ]
        collapsed_draws = []
        hodge_draws = []
        for realization, _, arrays, _ in records:
            collapsed_draws.append(
                gaussian_r4_reference(
                    _positive_covariance_spectrum(
                        arrays["total_target_eigenvalues"]
                    ),
                    _positive_covariance_spectrum(
                        arrays["total_external_eigenvalues"]
                    ),
                    PANEL_SIZE,
                    int(null_draws_per_realization),
                    _derived_seed(seed, N, sector, panel_kind, realization, "collapsed"),
                )
            )
        for realization, signature in zip(
            [item[0] for item in records],
            signatures,
            strict=True,
        ):
            hodge_draws.append(
                hodge_gaussian_r4_reference(
                    signature,
                    PANEL_SIZE,
                    int(null_draws_per_realization),
                    _derived_seed(
                        seed,
                        N,
                        sector,
                        panel_kind,
                        realization,
                        "hodge_bank",
                    ),
                )
            )
        collapsed = _banked_complete_medians(
            np.asarray(collapsed_draws),
            int(null_samples),
            _derived_seed(seed, N, sector, panel_kind, "collapsed_aggregate"),
        )
        hodge = _banked_complete_medians(
            np.asarray(hodge_draws),
            int(null_samples),
            _derived_seed(seed, N, sector, panel_kind, "hodge_aggregate"),
        )
        key = f"N{N}_{sector}_{panel_kind}"
        output_arrays[f"{key}_physical"] = physical
        output_arrays[f"{key}_collapsed_null"] = collapsed
        output_arrays[f"{key}_hodge_null"] = hodge
        summaries.append(
            {
                "N": N,
                "sector": sector,
                "panel_kind": panel_kind,
                "realizations": len(records),
                "physical_quantiles": np.quantile(
                    physical, [0.025, 0.5, 0.975]
                ).tolist(),
                "collapsed_null_quantiles": np.quantile(
                    collapsed, [0.025, 0.5, 0.975]
                ).tolist(),
                "hodge_null_quantiles": np.quantile(
                    hodge, [0.025, 0.5, 0.975]
                ).tolist(),
                "median_hodge_balance": float(
                    np.median([item.hodge_balance for item in signatures])
                ),
            }
        )
    _atomic_npz(output_npz, **output_arrays)
    checks = {
        "complete_group_partition": sum(
            item["realizations"] for item in summaries
        )
        == len(cases),
        "finite_physical_and_nulls": all(
            np.all(np.isfinite(values)) for values in output_arrays.values()
        ),
        "null_sample_counts": all(
            values.shape == (int(null_samples),)
            for key, values in output_arrays.items()
            if key.endswith("_null")
        ),
        "safe_aggregate_preexists": Path(safe_output_json).is_file(),
    }
    payload = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "uncertainty_unit": "complete_disorder_realization",
        "null_samples": int(null_samples),
        "null_draws_per_realization": int(null_draws_per_realization),
        "cases": summaries,
        "safe_covariates_sha256": sha256(safe_output_json),
        "arrays_sha256": sha256(output_npz),
        "checks": checks,
        "passed": all(checks.values()),
    }
    if not payload["passed"]:
        raise RuntimeError(f"SUSY pilot aggregation failed: {checks}")
    _atomic_json(output_json, payload)
    return payload


def registered_case_grid(
    sizes: tuple[int, ...] | list[int],
) -> list[tuple[int, str, int, str]]:
    """Return the frozen complete pilot grid for the requested sizes."""

    cases: list[tuple[int, str, int, str]] = []
    for N in tuple(int(value) for value in sizes):
        if N not in REGISTERED_SIZES:
            raise ValueError(f"N must be one of {REGISTERED_SIZES}")
        for sector in REGISTERED_SECTORS:
            for realization in range(REALIZATION_COUNTS[N]):
                for panel_kind in REGISTERED_PANEL_KINDS:
                    cases.append((N, sector, realization, panel_kind))
    return cases


def run_registered_pilot(
    sizes: tuple[int, ...] | list[int],
    *,
    root: Path = CHECKPOINT_ROOT,
    null_samples: int = NULL_REPLICATES,
    force: bool = False,
) -> dict[str, Any]:
    """Run the complete registered grid and aggregate its sequential outcomes."""

    requested = tuple(int(value) for value in sizes)
    cases = registered_case_grid(requested)
    for N in requested:
        for sector in REGISTERED_SECTORS:
            for realization in range(REALIZATION_COUNTS[N]):
                prepare_realization(
                    N,
                    sector,
                    realization,
                    root=root,
                    force=force,
                )
                for panel_kind in REGISTERED_PANEL_KINDS:
                    run_panel(
                        N,
                        sector,
                        realization,
                        panel_kind,
                        root=root,
                        force=force,
                    )
    return aggregate_pilot(
        cases,
        root=root,
        null_samples=int(null_samples),
        seed=BASE_SEED,
        safe_output_json=PILOT_SAFE_JSON,
        output_json=PILOT_JSON,
        output_npz=PILOT_NPZ,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    realization = subparsers.add_parser("realization")
    realization.add_argument("--N", type=int, required=True)
    realization.add_argument("--sector", choices=REGISTERED_SECTORS, required=True)
    realization.add_argument("--realization", type=int, required=True)
    realization.add_argument("--force", action="store_true")
    panel = subparsers.add_parser("panel")
    panel.add_argument("--N", type=int, required=True)
    panel.add_argument("--sector", choices=REGISTERED_SECTORS, required=True)
    panel.add_argument("--realization", type=int, required=True)
    panel.add_argument("--panel-kind", choices=REGISTERED_PANEL_KINDS, required=True)
    panel.add_argument("--force", action="store_true")
    pilot = subparsers.add_parser("pilot")
    pilot.add_argument("--sizes", type=int, nargs="+", required=True)
    pilot.add_argument("--null-samples", type=int, default=NULL_REPLICATES)
    pilot.add_argument("--force", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "realization":
        payload = prepare_realization(
            args.N,
            args.sector,
            args.realization,
            force=args.force,
        )
    elif args.command == "panel":
        payload = run_panel(
            args.N,
            args.sector,
            args.realization,
            args.panel_kind,
            force=args.force,
        )["safe"]
    else:
        payload = run_registered_pilot(
            args.sizes,
            null_samples=args.null_samples,
            force=args.force,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


def seal_file_hash(source: Path, seal: Path) -> str:
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError("missing prediction file to seal")
    digest = sha256(source)
    _atomic_text(Path(seal), f"{digest}  {source.name}\n")
    return digest


def _validate_file_hash(source: Path, seal: Path) -> str:
    source = Path(source)
    seal = Path(seal)
    if not seal.is_file():
        raise FileNotFoundError("missing prediction hash seal")
    if not source.is_file():
        raise FileNotFoundError("missing sealed prediction file")
    fields = seal.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != source.name:
        raise ValueError("prediction hash seal format mismatch")
    if fields[0] != sha256(source):
        raise ValueError("prediction hash seal mismatch")
    return fields[0]


def unseal_outcomes(
    cases: list[tuple[int, str, int, str]],
    *,
    root: Path = CHECKPOINT_ROOT,
    prediction_json: Path,
    prediction_seal: Path,
    output_json: Path,
    output_npz: Path,
) -> dict[str, Any]:
    """Open physical sidecars only after validating the prediction seal."""

    prediction_hash = _validate_file_hash(prediction_json, prediction_seal)
    records: list[dict[str, Any]] = []
    values: list[float] = []
    for case in cases:
        safe_path, arrays_path, outcome_path = panel_paths(root, *case)
        if not safe_path.is_file() or not arrays_path.is_file() or not outcome_path.is_file():
            raise FileNotFoundError("missing sealed SUSY panel files")
        safe = json.loads(safe_path.read_text(encoding="utf-8"))
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        if (
            outcome.get("safe_identity_hash") != safe.get("identity_hash")
            or outcome.get("safe_arrays_sha256") != safe.get("arrays_sha256")
            or safe.get("arrays_sha256") != sha256(arrays_path)
        ):
            raise ValueError("outcome identity mismatch")
        if tuple(
            outcome[key]
            for key in ("N", "sector", "realization", "panel_kind")
        ) != tuple(case):
            raise ValueError("outcome case identity mismatch")
        value = float(outcome["R4"])
        if not np.isfinite(value):
            raise ValueError("unsealed outcome is not finite")
        values.append(value)
        records.append(outcome)
    physical = np.asarray(values, dtype=float)
    _atomic_npz(output_npz, physical_R4=physical)
    payload = {
        "version": VERSION,
        "prediction_sha256": prediction_hash,
        "unsealed_utc": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "arrays_sha256": sha256(output_npz),
        "checks": {
            "complete_requested_grid": len(records) == len(cases),
            "finite_outcomes": bool(np.all(np.isfinite(physical))),
        },
    }
    payload["passed"] = all(payload["checks"].values())
    _atomic_json(output_json, payload)
    return payload
