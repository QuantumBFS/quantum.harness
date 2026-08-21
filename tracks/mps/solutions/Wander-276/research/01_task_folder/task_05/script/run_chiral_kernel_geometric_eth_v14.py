#!/usr/bin/env python3
"""Execute the sealed prospective chiral-index validation grid."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from lgeth.chiral_kernel_parent import (
    make_chiral_base,
    make_tangent_panel,
)


VERSION = "v14"
SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO = SCRIPT_ROOT.parents[2]
OUTPUT_ROOT = SCRIPT_ROOT / "output/geometric_eth_theory_v14"
DEFAULT_PREDICTION = OUTPUT_ROOT / "chiral_prediction_v14.json"
DEFAULT_SIDECAR = OUTPUT_ROOT / "chiral_prediction_v14.sha256"
DEFAULT_OUTCOMES = OUTPUT_ROOT / "chiral_outcomes_v14.json"

DEVELOPMENT_SIZES = ((16, 24), (24, 36), (32, 48))
VALIDATION_SIZES = ((48, 72), (64, 96), (96, 144))
BASES_PER_SIZE = 64
TANGENTS_PER_BASE = 16
TANGENT_CLASSES = ("random", "local", "structured")
CLASS_SEEDS: dict[str, dict[str, int]] = {
    "random": {"base": 14_001_101, "tangent": 14_001_201},
    "local": {"base": 14_002_101, "tangent": 14_002_201},
    "structured": {"base": 14_003_101, "tangent": 14_003_201},
}
BRANCH_PRECEDENCE = (
    "feasibility_failure",
    "random_channel_failure",
    "deformed_locality_class",
    "channel_law_validated",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scientific_payload_hash(payload: Mapping[str, Any]) -> str:
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


def _json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing required sealed artifact: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid sealed JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"sealed artifact is not a JSON object: {path}")
    return payload


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


def _recorded_source(repo_root: Path, recorded: str) -> Path:
    path = Path(recorded)
    return path if path.is_absolute() else repo_root / path


def validate_prediction_seal(
    *,
    repo_root: Path,
    prediction_path: Path,
    sidecar_path: Path,
) -> dict[str, Any]:
    """Validate the prediction file, sidecar, sources, grid, and precedence."""

    prediction_path = Path(prediction_path)
    sidecar_path = Path(sidecar_path)
    if not prediction_path.is_file() or not sidecar_path.is_file():
        raise RuntimeError("prediction seal and SHA-256 sidecar must both exist")
    expected = sidecar_path.read_text(encoding="utf-8").strip()
    observed = _sha256(prediction_path)
    if expected != observed:
        raise RuntimeError("prediction SHA-256 sidecar mismatch")
    payload = _json_object(prediction_path)
    if payload.get("schema") != "chiral_kernel_prediction_v14":
        raise RuntimeError("unexpected chiral prediction schema")
    try:
        datetime.fromisoformat(str(payload["sealed_utc"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as exc:
        raise RuntimeError("prediction seal timestamp is missing or invalid") from exc
    unsigned = dict(payload)
    registered_scientific_hash = unsigned.pop("scientific_payload_sha256", None)
    if (
        not isinstance(registered_scientific_hash, str)
        or _scientific_payload_hash(unsigned) != registered_scientific_hash
    ):
        raise RuntimeError("prediction scientific payload hash mismatch")
    grid = payload.get("registered_grid", {})
    expected_grid = {
        "development_sizes": [list(size) for size in DEVELOPMENT_SIZES],
        "validation_sizes": [list(size) for size in VALIDATION_SIZES],
        "bases_per_size": BASES_PER_SIZE,
        "tangents_per_base": TANGENTS_PER_BASE,
        "tangent_classes": list(TANGENT_CLASSES),
    }
    if grid != expected_grid:
        raise RuntimeError("prediction does not contain the frozen registered grid")
    if payload.get("branch_precedence") != list(BRANCH_PRECEDENCE):
        raise RuntimeError("prediction branch precedence is not frozen")
    serialized = json.dumps(payload, sort_keys=True).lower()
    forbidden = (
        "observed_fourth_cumulant",
        "validation_outcomes",
        "selected_branch",
    )
    if any(token in serialized for token in forbidden):
        raise RuntimeError("prediction contains validation outcome leakage")
    sources = payload.get("source_hashes")
    if not isinstance(sources, dict) or not sources:
        raise RuntimeError("prediction has no registered source hashes")
    for recorded, digest in sources.items():
        source = _recorded_source(Path(repo_root), recorded)
        if not source.is_file() or _sha256(source) != digest:
            raise RuntimeError(f"registered source hash mismatch: {recorded}")
    return payload


def _case_seed(stream_seed: int, n_b: int, n_a: int, base_index: int) -> int:
    return int(stream_seed + 10_000 * n_b + 100 * n_a + base_index)


def _kernel_projector_a(factor: np.ndarray) -> np.ndarray:
    n_b, n_a = factor.shape
    gram = factor @ factor.conj().T
    return np.eye(n_a, dtype=complex) - factor.conj().T @ np.linalg.solve(
        gram, factor
    )


def _projector_derivative_a(factor: np.ndarray, tangent: np.ndarray) -> np.ndarray:
    gram = factor @ factor.conj().T
    inverse_factor = np.linalg.solve(gram, factor)
    gram_derivative = tangent @ factor.conj().T + factor @ tangent.conj().T
    return (
        -tangent.conj().T @ inverse_factor
        - factor.conj().T @ np.linalg.solve(gram, tangent)
        + factor.conj().T
        @ np.linalg.solve(gram, gram_derivative @ inverse_factor)
    )


def _safe_base_audit(
    factor: np.ndarray,
    panel: np.ndarray,
    *,
    base_seed: int,
    singular_system: tuple[np.ndarray, np.ndarray, np.ndarray],
    responses: list[np.ndarray],
) -> tuple[dict[str, Any], list[np.ndarray]]:
    n_b, n_a = factor.shape
    _, singular_values, right_adjoint = singular_system
    kernel = right_adjoint.conj().T[:, n_b:]
    frame = np.zeros((n_a + n_b, n_a - n_b), dtype=complex)
    frame[:n_a] = kernel
    equation_residuals = []
    horizontal_residuals = []
    for tangent, response in zip(panel, responses, strict=True):
        response_a = response[:n_a]
        equation_residuals.append(
            float(np.linalg.norm(factor @ response_a + tangent @ kernel))
            / max(float(np.linalg.norm(tangent @ kernel)), 1e-30)
        )
        horizontal_residuals.append(float(np.linalg.norm(frame.conj().T @ response)))

    epsilon = 2e-6
    first = panel[0]
    derivative = _projector_derivative_a(factor, first)
    finite_difference = (
        _kernel_projector_a(factor + epsilon * first)
        - _kernel_projector_a(factor - epsilon * first)
    ) / (2.0 * epsilon)
    finite_difference_relative = float(np.linalg.norm(derivative - finite_difference)) / max(
        float(np.linalg.norm(derivative)), 1e-30
    )

    generator = np.random.default_rng(base_seed + 77)
    phase_a = np.exp(1j * generator.uniform(-np.pi, np.pi, size=n_a))
    phase_b = np.exp(1j * generator.uniform(-np.pi, np.pi, size=n_b))
    transformed_factor = phase_b[:, None] * factor * phase_a.conj()[None, :]
    transformed_tangent = phase_b[:, None] * first * phase_a.conj()[None, :]
    transformed_derivative = _projector_derivative_a(
        transformed_factor, transformed_tangent
    )
    expected_derivative = phase_a[:, None] * derivative * phase_a.conj()[None, :]
    gauge_relative = float(
        np.linalg.norm(transformed_derivative - expected_derivative)
    ) / max(float(np.linalg.norm(derivative)), 1e-30)

    expected_nullity = n_a - n_b
    checks = {
        "full_row_rank": bool(np.linalg.matrix_rank(factor, tol=1e-12) == n_b),
        "exact_index_nullity": frame.shape[1] == expected_nullity,
        "positive_gap": float(singular_values[-1]) > 1e-10,
        "kernel_residual": float(np.linalg.norm(factor @ kernel)) < 1e-10,
        "orthonormal_frame": float(
            np.linalg.norm(frame.conj().T @ frame - np.eye(expected_nullity))
        )
        < 1e-10,
        "response_equation": max(equation_residuals) < 1e-9,
        "horizontal_response": max(horizontal_residuals) < 1e-9,
        "projector_finite_difference": finite_difference_relative < 1e-6,
        "gauge_covariance": gauge_relative < 1e-10,
    }
    return {
        "base_seed": int(base_seed),
        "nullity": int(frame.shape[1]),
        "external_gap": float(singular_values[-1]),
        "maximum_response_equation_residual": max(equation_residuals),
        "maximum_horizontal_residual": max(horizontal_residuals),
        "projector_finite_difference_relative": finite_difference_relative,
        "gauge_response_relative": gauge_relative,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }, responses


def _batched_responses(
    factor: np.ndarray,
    panel: np.ndarray,
) -> tuple[
    tuple[np.ndarray, np.ndarray, np.ndarray],
    list[np.ndarray],
]:
    """Factor a base once and solve all tangent responses in one block."""

    n_b, n_a = factor.shape
    left, singular_values, right_adjoint = np.linalg.svd(
        factor, full_matrices=True
    )
    kernel = right_adjoint.conj().T[:, n_b:]
    right_hand_sides = np.einsum("cba,ad->cbd", panel, kernel)
    stacked_rhs = right_hand_sides.transpose(1, 0, 2).reshape(n_b, -1)
    stacked_reduced = np.linalg.solve(
        factor @ factor.conj().T, stacked_rhs
    )
    reduced = stacked_reduced.reshape(
        n_b, panel.shape[0], n_a - n_b
    ).transpose(1, 0, 2)
    response_a = -np.einsum("ab,cbd->cad", factor.conj().T, reduced)
    responses: list[np.ndarray] = []
    for values in response_a:
        response = np.zeros((n_a + n_b, n_a - n_b), dtype=complex)
        response[:n_a] = values
        responses.append(response)
    return (left, singular_values, right_adjoint), responses


def _response_observables(
    factor: np.ndarray,
    tangent: np.ndarray,
    response: np.ndarray,
    singular_system: tuple[np.ndarray, np.ndarray, np.ndarray],
    whitened_entries: np.ndarray,
) -> tuple[float, float, float, float, float]:
    n_b, n_a = factor.shape
    left, singular_values, right_adjoint = singular_system
    kernel = right_adjoint.conj().T[:, n_b:]
    reduced = left.conj().T @ tangent @ kernel
    strengths_squared = np.sum(
        np.abs(reduced / singular_values[:, None]) ** 2, axis=1
    )
    denominator = float(np.sum(strengths_squared**2))
    effective = (
        float(np.sum(strengths_squared)) ** 2 / denominator
        if denominator > 1e-30
        else 1.0
    )
    complete_cumulant, variance, normalized_pseudocovariance = (
        _complete_standardized_fourth_cumulant(whitened_entries)
    )
    return (
        effective,
        complete_cumulant,
        effective * complete_cumulant,
        variance,
        normalized_pseudocovariance,
    )


def _complete_standardized_fourth_cumulant(
    entries: np.ndarray,
) -> tuple[float, float, float]:
    """Return kappa_4/v^2, v, and |p|/v for a complex scalar sample.

    The flattened sample is centered before any moment is evaluated.  Both
    complex Gaussian Wick contractions from the ordinary covariance and the
    third contraction from the pseudocovariance are subtracted:

        kappa_4 / v^2 = m_4 / v^2 - 2 - |p|^2 / v^2.
    """

    flattened = np.asarray(entries, dtype=complex).reshape(-1)
    if flattened.size == 0:
        raise ValueError("the fourth-cumulant sample must be nonempty")
    centered = flattened - np.mean(flattened)
    variance = float(np.mean(np.abs(centered) ** 2))
    if variance <= 1e-30:
        return 0.0, variance, 0.0
    pseudocovariance = complex(np.mean(centered**2))
    normalized_pseudocovariance = float(abs(pseudocovariance) / variance)
    fourth_moment = float(np.mean(np.abs(centered) ** 4))
    complete_cumulant = float(
        fourth_moment / variance**2
        - 2.0
        - normalized_pseudocovariance**2
    )
    return complete_cumulant, variance, normalized_pseudocovariance


def _whiten_response_entries(
    responses: list[np.ndarray],
    *,
    n_a: int,
) -> tuple[np.ndarray, dict[str, float | int]]:
    """Apply the registered covariance-whitening rule separately at each base."""

    entries = np.asarray([response[:n_a].reshape(-1) for response in responses])
    entries = entries - np.mean(entries, axis=1, keepdims=True)
    covariance = entries @ entries.conj().T / entries.shape[1]
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    threshold = max(float(eigenvalues[-1]), 1.0) * 1e-12
    if float(eigenvalues[0]) <= threshold:
        raise RuntimeError(
            "tangent-channel covariance is rank deficient before whitening"
        )
    whitener = (
        eigenvectors
        @ np.diag(1.0 / np.sqrt(eigenvalues))
        @ eigenvectors.conj().T
    )
    whitened = whitener @ entries
    whitened_covariance = whitened @ whitened.conj().T / entries.shape[1]
    error = float(
        np.linalg.norm(whitened_covariance - np.eye(entries.shape[0]))
        / np.sqrt(entries.shape[0])
    )
    return whitened, {
        "rank": int(np.count_nonzero(eigenvalues > threshold)),
        "condition_number": float(eigenvalues[-1] / eigenvalues[0]),
        "identity_error": error,
    }


def _run_class_case(
    *,
    n_b: int,
    n_a: int,
    kind: str,
    base_count: int,
    tangent_count: int,
) -> dict[str, Any]:
    safe_covariates: list[dict[str, Any]] = []
    effective_tensor: list[list[float]] = []
    complete_cumulant_tensor: list[list[float]] = []
    scaled_tensor: list[list[float]] = []
    variance_tensor: list[list[float]] = []
    normalized_pseudocovariance_tensor: list[list[float]] = []
    for base_index in range(base_count):
        base_seed = _case_seed(
            CLASS_SEEDS[kind]["base"], n_b, n_a, base_index
        )
        tangent_seed = _case_seed(
            CLASS_SEEDS[kind]["tangent"], n_b, n_a, base_index
        )
        factor = make_chiral_base(n_a=n_a, n_b=n_b, seed=base_seed)
        panel = make_tangent_panel(
            n_a=n_a,
            n_b=n_b,
            count=tangent_count,
            kind=kind,
            seed=tangent_seed,
        )
        singular_system, responses = _batched_responses(factor, panel)
        safe, responses = _safe_base_audit(
            factor,
            panel,
            base_seed=base_seed,
            singular_system=singular_system,
            responses=responses,
        )
        whitened_entries, whitening = _whiten_response_entries(
            responses, n_a=n_a
        )
        safe["channel_whitening"] = whitening
        safe["checks"]["channel_covariance_whitened"] = bool(
            whitening["rank"] == tangent_count
            and whitening["identity_error"] < 1e-9
        )
        safe["all_checks_pass"] = all(safe["checks"].values())
        safe.update(
            {
                "base_index": base_index,
                "tangent_seed": tangent_seed,
                "tangent_frobenius_min": float(
                    np.min(np.linalg.norm(panel, axis=(1, 2)))
                ),
                "tangent_frobenius_max": float(
                    np.max(np.linalg.norm(panel, axis=(1, 2)))
                ),
            }
        )
        safe_covariates.append(safe)
        effective_row: list[float] = []
        complete_cumulant_row: list[float] = []
        scaled_row: list[float] = []
        variance_row: list[float] = []
        normalized_pseudocovariance_row: list[float] = []
        for tangent, response, whitened in zip(
            panel, responses, whitened_entries, strict=True
        ):
            (
                effective,
                complete_cumulant,
                scaled,
                variance,
                normalized_pseudocovariance,
            ) = _response_observables(
                factor,
                tangent,
                response,
                singular_system,
                whitened,
            )
            effective_row.append(effective)
            complete_cumulant_row.append(complete_cumulant)
            scaled_row.append(scaled)
            variance_row.append(variance)
            normalized_pseudocovariance_row.append(
                normalized_pseudocovariance
            )
        effective_tensor.append(effective_row)
        complete_cumulant_tensor.append(complete_cumulant_row)
        scaled_tensor.append(scaled_row)
        variance_tensor.append(variance_row)
        normalized_pseudocovariance_tensor.append(
            normalized_pseudocovariance_row
        )

    if not all(record["all_checks_pass"] for record in safe_covariates):
        raise RuntimeError(
            f"exact-index or response gate failed before aggregation: {kind}, "
            f"(n_b,n_a)=({n_b},{n_a})"
        )
    effective_array = np.asarray(effective_tensor)
    complete_cumulant_array = np.asarray(complete_cumulant_tensor)
    scaled_array = np.asarray(scaled_tensor)
    variance_array = np.asarray(variance_tensor)
    normalized_pseudocovariance_array = np.asarray(
        normalized_pseudocovariance_tensor
    )
    return {
        "safe_covariates": safe_covariates,
        "outcome_tensors": {
            "effective_channel_number": effective_array.tolist(),
            "complete_standardized_fourth_cumulant": (
                complete_cumulant_array.tolist()
            ),
            "effective_scaled_complete_standardized_fourth_cumulant": (
                scaled_array.tolist()
            ),
            "observable_variance": variance_array.tolist(),
            "normalized_pseudocovariance_magnitude": (
                normalized_pseudocovariance_array.tolist()
            ),
        },
        "aggregate_after_safe_gates": {
            "effective_channel_number_mean": float(np.mean(effective_array)),
            "complete_standardized_fourth_cumulant_mean": float(
                np.mean(complete_cumulant_array)
            ),
            "effective_scaled_complete_standardized_fourth_cumulant_mean": (
                float(np.mean(scaled_array))
            ),
            "observable_variance_mean": float(np.mean(variance_array)),
            "normalized_pseudocovariance_magnitude_mean": float(
                np.mean(normalized_pseudocovariance_array)
            ),
            "base_mean_effective_scaled_complete_standardized_fourth_cumulant": (
                np.mean(scaled_array, axis=1).tolist()
            ),
        },
    }


def run_chiral_grid(
    *,
    sizes: Iterable[tuple[int, int]],
    base_count: int,
    tangent_count: int,
) -> dict[str, Any]:
    """Run an exact-gated grid for all three tangent classes."""

    cases: dict[str, Any] = {}
    for n_b, n_a in sizes:
        if n_a <= n_b:
            raise ValueError("every chiral size requires n_a > n_b")
        case_id = f"n_b{n_b}_n_a{n_a}"
        classes = {
            kind: _run_class_case(
                n_b=n_b,
                n_a=n_a,
                kind=kind,
                base_count=base_count,
                tangent_count=tangent_count,
            )
            for kind in TANGENT_CLASSES
        }
        cases[case_id] = {
            "n_b": n_b,
            "n_a": n_a,
            "expected_nullity": n_a - n_b,
            "classes": classes,
        }
    return cases


def run_sealed_validation(
    *,
    repo_root: Path,
    prediction_path: Path,
    sidecar_path: Path,
    output_path: Path,
    validation_sizes: tuple[tuple[int, int], ...] = VALIDATION_SIZES,
    base_count: int = BASES_PER_SIZE,
    tangent_count: int = TANGENTS_PER_BASE,
    strict_grid: bool = True,
    generated_utc: str | None = None,
) -> dict[str, Any]:
    """Run validation only after the exact seal and source hashes pass."""

    prediction = validate_prediction_seal(
        repo_root=Path(repo_root),
        prediction_path=Path(prediction_path),
        sidecar_path=Path(sidecar_path),
    )
    if strict_grid and (
        tuple(validation_sizes) != VALIDATION_SIZES
        or base_count != BASES_PER_SIZE
        or tangent_count != TANGENTS_PER_BASE
    ):
        raise ValueError("production execution must use the sealed validation grid")
    output_path = Path(output_path)
    if output_path.exists():
        raise RuntimeError("chiral outcome file already exists; refusing to overwrite")
    outcome_timestamp = generated_utc or datetime.now(timezone.utc).isoformat()
    sealed_timestamp = datetime.fromisoformat(
        str(prediction["sealed_utc"]).replace("Z", "+00:00")
    )
    parsed_outcome_timestamp = datetime.fromisoformat(
        outcome_timestamp.replace("Z", "+00:00")
    )
    if parsed_outcome_timestamp <= sealed_timestamp:
        raise RuntimeError("outcome timestamp must be later than the prediction seal")
    cases = run_chiral_grid(
        sizes=validation_sizes,
        base_count=base_count,
        tangent_count=tangent_count,
    )
    all_safe = all(
        safe["all_checks_pass"]
        for case in cases.values()
        for record in case["classes"].values()
        for safe in record["safe_covariates"]
    )
    all_norms = all(
        abs(safe["tangent_frobenius_min"] - 1.0) < 1e-12
        and abs(safe["tangent_frobenius_max"] - 1.0) < 1e-12
        for case in cases.values()
        for record in case["classes"].values()
        for safe in record["safe_covariates"]
    )
    seed_values = [
        CLASS_SEEDS[kind][stream]
        for kind in TANGENT_CLASSES
        for stream in ("base", "tangent")
    ]
    checks = {
        "prediction_seal_verified_before_outcomes": True,
        "all_exact_index_gates_pass": all_safe,
        "same_frobenius_normalization_all_classes": all_norms,
        "same_channel_count_all_classes": all(
            len(row) == tangent_count
            for case in cases.values()
            for record in case["classes"].values()
            for row in record["outcome_tensors"]["effective_channel_number"]
        ),
        "class_seed_streams_disjoint": len(seed_values) == len(set(seed_values)),
    }
    payload = {
        "version": VERSION,
        "schema": "chiral_kernel_outcomes_v14",
        "generated_utc": outcome_timestamp,
        "prediction_sha256": _sha256(Path(prediction_path)),
        "sealed_utc": prediction["sealed_utc"],
        "execution": {
            "mode": "production_sealed_validation" if strict_grid else "test_fixture",
            "sizes": [list(size) for size in validation_sizes],
            "bases_per_size": base_count,
            "tangents_per_base": tangent_count,
            "tangent_classes": list(TANGENT_CLASSES),
            "class_seeds": CLASS_SEEDS,
        },
        "cases": cases,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }
    if not payload["all_checks_pass"]:
        raise RuntimeError("sealed chiral outcome gates did not all pass")
    _atomic_json(output_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--prediction", type=Path, default=DEFAULT_PREDICTION)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTCOMES)
    arguments = parser.parse_args()
    payload = run_sealed_validation(
        repo_root=arguments.repo_root,
        prediction_path=arguments.prediction,
        sidecar_path=arguments.sidecar,
        output_path=arguments.output,
    )
    print(json.dumps({"output": str(arguments.output), "checks": payload["checks"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
