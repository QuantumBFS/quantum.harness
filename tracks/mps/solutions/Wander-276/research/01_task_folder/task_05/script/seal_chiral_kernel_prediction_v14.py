#!/usr/bin/env python3
"""Freeze the chiral-index prediction before sealed validation outcomes exist."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any, Mapping

import numpy as np

from run_chiral_kernel_geometric_eth_v14 import (
    BASES_PER_SIZE,
    BRANCH_PRECEDENCE,
    CLASS_SEEDS,
    DEVELOPMENT_SIZES,
    TANGENT_CLASSES,
    TANGENTS_PER_BASE,
    VALIDATION_SIZES,
    run_chiral_grid,
)


BASE_BOOTSTRAP_SEED = 20_260_821
BASE_BOOTSTRAP_REPLICATES = 10_000
BASE_BOOTSTRAP_FAMILY_ALPHA = 0.05


VERSION = "v14"
SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO = SCRIPT_ROOT.parents[2]
OUTPUT_ROOT = SCRIPT_ROOT / "output/geometric_eth_theory_v14"
DEFAULT_THEORY = OUTPUT_ROOT / "channel_theory_v14.json"
DEFAULT_PREDICTION = OUTPUT_ROOT / "chiral_prediction_v14.json"
DEFAULT_SIDECAR = OUTPUT_ROOT / "chiral_prediction_v14.sha256"
DEFAULT_OUTCOMES = OUTPUT_ROOT / "chiral_outcomes_v14.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_scientific_hash(payload: Mapping[str, Any]) -> str:
    encoded = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing channel-theory dependency: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid channel-theory dependency: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("channel-theory dependency must be a JSON object")
    return payload


def _nested_value(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    for value in payload.values():
        if isinstance(value, dict):
            nested = _nested_value(value, keys)
            if nested is not None:
                return nested
    return None


def validate_channel_theory(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Consume the concurrent theory audit through a strict minimal schema."""

    if payload.get("version") != VERSION:
        raise RuntimeError("channel theory has the wrong version")
    if payload.get("schema") != "geometric_eth_channel_theory_v14":
        raise RuntimeError("channel theory has an unexpected schema")
    checks = payload.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or not all(value is True for value in checks.values())
        or payload.get("all_checks_pass") is not True
    ):
        raise RuntimeError("channel theory has not passed all registered checks")
    counts = _nested_value(
        payload, ("registered_channel_counts", "channel_counts")
    )
    if counts != [4, 8, 16, 32, 64]:
        raise RuntimeError("channel theory has an incomplete channel-count grid")
    maximum_error = _nested_value(
        payload, ("maximum_relative_error", "max_relative_error")
    )
    if (
        not isinstance(maximum_error, (int, float))
        or not np.isfinite(maximum_error)
        or maximum_error > 0.08
        or maximum_error < 0.0
    ):
        raise RuntimeError("channel theory exceeds the frozen relative-error gate")
    registered_hash = payload.get("scientific_payload_sha256")
    if not isinstance(registered_hash, str) or len(registered_hash) != 64:
        raise RuntimeError("channel theory lacks a scientific payload hash")
    unsigned = deepcopy(dict(payload))
    unsigned.pop("scientific_payload_sha256")
    if _canonical_scientific_hash(unsigned) != registered_hash:
        raise RuntimeError("channel theory scientific payload hash mismatch")
    source_hashes = payload.get("source_hashes")
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise RuntimeError("channel theory has no source-hash contract")
    if repo_root is not None:
        for recorded, digest in source_hashes.items():
            source = Path(recorded)
            if not source.is_absolute():
                source = Path(repo_root) / source
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or not source.is_file()
                or _sha256(source) != digest
            ):
                raise RuntimeError(
                    f"channel theory registered source hash mismatch: {recorded}"
                )
    return dict(payload)


def _record_path(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _atomic_sidecar(path: Path, digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(digest + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _development_band(
    development_cases: Mapping[str, Any],
    *,
    family_alpha: float = 0.05,
) -> dict[str, Any]:
    means: list[float] = []
    errors: list[float] = []
    case_summaries: dict[str, Any] = {}
    case_count = len(development_cases)
    quantile = NormalDist().inv_cdf(1.0 - family_alpha / (2.0 * case_count))
    for case_id, case in development_cases.items():
        values = np.asarray(
            case["classes"]["random"]["aggregate_after_safe_gates"][
                "base_mean_effective_scaled_complete_standardized_fourth_cumulant"
            ],
            dtype=float,
        )
        mean = float(np.mean(values))
        error = float(np.std(values, ddof=1) / np.sqrt(values.size)) if values.size > 1 else 0.0
        means.append(mean)
        errors.append(error)
        case_summaries[case_id] = {
            "base_count": int(values.size),
            "mean_used_only_for_band_construction": mean,
            "standard_error_used_only_for_band_construction": error,
        }
    lower = min(mean - quantile * error for mean, error in zip(means, errors, strict=True))
    upper = max(mean + quantile * error for mean, error in zip(means, errors, strict=True))
    if not lower < upper:
        padding = max(abs(lower), 1.0) * 1e-12
        lower -= padding
        upper += padding
    return {
        "lower": float(lower),
        "upper": float(upper),
        "family_alpha": family_alpha,
        "normal_quantile": float(quantile),
        "development_case_count": case_count,
        "construction": "envelope_of_Bonferroni_normal_intervals_over_base_means",
        "development_safe_summary": case_summaries,
    }


def seal_prediction(
    *,
    repo_root: Path,
    channel_theory_path: Path,
    prediction_path: Path,
    sidecar_path: Path,
    outcomes_path: Path,
    development_sizes: tuple[tuple[int, int], ...] = DEVELOPMENT_SIZES,
    development_base_count: int = BASES_PER_SIZE,
    tangent_count: int = TANGENTS_PER_BASE,
    strict_grid: bool = True,
    sealed_utc: str | None = None,
) -> dict[str, Any]:
    """Calibrate on development sizes and atomically freeze validation rules."""

    repo_root = Path(repo_root)
    channel_theory_path = Path(channel_theory_path)
    prediction_path = Path(prediction_path)
    sidecar_path = Path(sidecar_path)
    outcomes_path = Path(outcomes_path)
    if outcomes_path.exists():
        raise RuntimeError("outcome leakage: outcomes exist before prediction sealing")
    if prediction_path.exists() or sidecar_path.exists():
        raise RuntimeError("prediction seal already exists; refusing to rewrite")
    if strict_grid and (
        tuple(development_sizes) != DEVELOPMENT_SIZES
        or development_base_count != BASES_PER_SIZE
        or tangent_count != TANGENTS_PER_BASE
    ):
        raise ValueError("production seal must use the frozen development grid")
    theory = validate_channel_theory(
        _load_json(channel_theory_path), repo_root=repo_root
    )

    development = run_chiral_grid(
        sizes=development_sizes,
        base_count=development_base_count,
        tangent_count=tangent_count,
    )
    if not all(
        safe["all_checks_pass"]
        for case in development.values()
        for record in case["classes"].values()
        for safe in record["safe_covariates"]
    ):
        raise RuntimeError("development exact-index gates failed before sealing")
    band = _development_band(development)

    source_paths = [
        channel_theory_path,
        repo_root / "01_task_folder/task_05/script/lgeth/chiral_kernel_parent.py",
        repo_root / "01_task_folder/task_05/script/run_chiral_kernel_geometric_eth_v14.py",
        repo_root / "01_task_folder/task_05/script/seal_chiral_kernel_prediction_v14.py",
    ]
    if not all(path.is_file() for path in source_paths):
        missing = [str(path) for path in source_paths if not path.is_file()]
        raise RuntimeError(f"prediction source is missing: {missing}")
    sources = {
        _record_path(repo_root, path): _sha256(path) for path in source_paths
    }
    payload: dict[str, Any] = {
        "version": VERSION,
        "schema": "chiral_kernel_prediction_v14",
        "sealed_utc": sealed_utc or datetime.now(timezone.utc).isoformat(),
        "registered_grid": {
            "development_sizes": [list(size) for size in DEVELOPMENT_SIZES],
            "validation_sizes": [list(size) for size in VALIDATION_SIZES],
            "bases_per_size": BASES_PER_SIZE,
            "tangents_per_base": TANGENTS_PER_BASE,
            "tangent_classes": list(TANGENT_CLASSES),
        },
        "execution_provenance": {
            "calibration_mode": "production_development"
            if strict_grid
            else "test_fixture",
            "executed_development_sizes": [list(size) for size in development_sizes],
            "executed_base_count": development_base_count,
            "executed_tangent_count": tangent_count,
            "class_seeds": CLASS_SEEDS,
        },
        "primary_prediction": {
            "statistic": (
                "N_eff_times_covariance_whitened_complete_standardized_"
                "fourth_cumulant"
            ),
            "complete_complex_wick_subtraction": (
                "kappa4_over_v_squared_equals_m4_over_v_squared_minus_2_"
                "minus_normalized_pseudocovariance_magnitude_squared"
            ),
            "rule": (
                "the random tangent class must remain inside the frozen "
                "simultaneous band at all three validation sizes"
            ),
            "estimator": (
                "at each size, average the 16 registered tangent statistics "
                "within each of 64 bases, then average those 64 base means"
            ),
            "decision": (
                "all three random-class validation point estimates must lie "
                "inside the closed development-derived simultaneous band"
            ),
            "bootstrap_intervals_are_reporting_only": True,
            "bootstrap_intervals_do_not_expand_primary_band": True,
            "simultaneous_band": band,
            "controls": (
                "local and repeated-cell classes are not required to enter "
                "the random-channel band"
            ),
            "observable_side_self_normalization": (
                "at each base, apply the registered covariance-whitening "
                "rule and center each flattened observation before computing "
                "its variance and pseudocovariance"
            ),
            "no_validation_refit_of_development_band_or_thresholds": True,
        },
        "registered_analysis": {
            "base_bootstrap": {
                "master_seed": BASE_BOOTSTRAP_SEED,
                "replicates": BASE_BOOTSTRAP_REPLICATES,
                "family_alpha": BASE_BOOTSTRAP_FAMILY_ALPHA,
                "resampling_unit": "base_mean_over_16_registered_tangents",
                "draws_per_replicate": BASES_PER_SIZE,
                "interval": (
                    "two-sided Bonferroni percentile simultaneous interval "
                    "within each class across the three validation sizes"
                ),
                "lower_quantile": (
                    BASE_BOOTSTRAP_FAMILY_ALPHA
                    / (2.0 * len(VALIDATION_SIZES))
                ),
                "upper_quantile": (
                    1.0
                    - BASE_BOOTSTRAP_FAMILY_ALPHA
                    / (2.0 * len(VALIDATION_SIZES))
                ),
                "seed_derivation": (
                    "numpy SeedSequence(master_seed).spawn(9), consumed in "
                    "class-major then validation-size-major order"
                ),
                "class_order": list(TANGENT_CLASSES),
                "size_order": [list(size) for size in VALIDATION_SIZES],
            },
            "structured_control_separation": {
                "eligible_classes": ["local", "structured"],
                "criterion": (
                    "there exists one eligible class whose registered 95% "
                    "base-bootstrap interval is disjoint from the frozen "
                    "random development band at at least two of three "
                    "validation sizes, including (96,144)"
                ),
                "minimum_disjoint_sizes": 2,
                "must_include_size": [96, 144],
                "strict_disjointness": (
                    "interval_upper < band_lower or interval_lower > band_upper"
                ),
                "required_for_title_gate": True,
            },
            "branch_rules": {
                "feasibility_failure": "any exact-index or seal gate fails",
                "random_channel_failure": (
                    "exact and seal gates pass but the random primary "
                    "prediction fails"
                ),
                "deformed_locality_class": (
                    "the random primary prediction and structured-control "
                    "separation criterion both pass"
                ),
                "channel_law_validated": (
                    "the random primary prediction passes but the "
                    "structured-control separation criterion fails"
                ),
            },
        },
        "branch_precedence": list(BRANCH_PRECEDENCE),
        "channel_theory_contract": {
            "schema": theory["schema"],
            "scientific_payload_sha256": theory["scientific_payload_sha256"],
            "maximum_relative_error": _nested_value(
                theory, ("maximum_relative_error", "max_relative_error")
            ),
        },
        "source_hashes": sources,
    }
    payload["scientific_payload_sha256"] = _canonical_scientific_hash(payload)
    _atomic_json(prediction_path, payload)
    _atomic_sidecar(sidecar_path, _sha256(prediction_path))
    if stat.S_IMODE(prediction_path.stat().st_mode) != 0o644 or stat.S_IMODE(
        sidecar_path.stat().st_mode
    ) != 0o644:
        raise RuntimeError("prediction outputs must have mode 0644")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--channel-theory", type=Path, default=DEFAULT_THEORY)
    parser.add_argument("--prediction", type=Path, default=DEFAULT_PREDICTION)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--outcomes", type=Path, default=DEFAULT_OUTCOMES)
    arguments = parser.parse_args()
    payload = seal_prediction(
        repo_root=arguments.repo_root,
        channel_theory_path=arguments.channel_theory,
        prediction_path=arguments.prediction,
        sidecar_path=arguments.sidecar,
        outcomes_path=arguments.outcomes,
    )
    print(
        json.dumps(
            {
                "prediction": str(arguments.prediction),
                "scientific_payload_sha256": payload["scientific_payload_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
