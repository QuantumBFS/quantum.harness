#!/usr/bin/env python3
"""Attempt 44: model-informed search dimension versus black-box cost.

The calibration path receives only a seeded scalar binomial-fidelity service.
Exact fidelities are attached after the service is closed and never affect an
update, acceptance decision, or online certificate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("JAX_PLATFORMS", "cpu")

import jax.numpy as jnp
import numpy as np
from scipy.stats import norm

from cycle5_statistics import certify_target_from_counts
from phase3_common import (
    PARAMETER_COUNT,
    TRUTH_FAMILIES,
    array_sha256,
    build_nominal_model,
    environment_summary,
    make_truth,
)

HERE = Path(__file__).resolve().parent
CORE = HERE.parent
CONFIG_PATH = HERE / "attempt44_dimension_cost_config.json"
PROTOCOL_PATH = CORE / "docs" / "ATTEMPT44_PROTOCOL.md"
CHARTER_PATH = CORE / "docs" / "RESEARCH_CHARTER_05.md"
ATTEMPT35_PATH = (
    CORE / "results_summary" / "QL1F-attempt35-normalized-difficulty.json"
)
ATTEMPT42_PATH = (
    CORE
    / "results_summary"
    / "QL1F-attempt42-normalized-principal-global.json"
)
ATTEMPT43_PROTOCOL_PATH = CORE / "docs" / "ATTEMPT43_PROTOCOL.md"
ATTEMPT43_PATH = (
    CORE / "results_summary" / "QL1F-attempt43-online-certification.json"
)
FULL_OUTPUT = (
    CORE / "results_summary" / "QL1F-attempt44-dimension-cost.json"
)
SMOKE_OUTPUT = (
    CORE
    / "results_summary"
    / "QL1F-attempt44-dimension-cost.smoke.json"
)
REPORT_PATH = CORE / "docs" / "ATTEMPT44_REPORT.md"
PLOT_MAIN_PNG = CORE / "plots" / "attempt44-dimension-cost-development.png"
PLOT_MAIN_SVG = CORE / "plots" / "attempt44-dimension-cost-development.svg"
PLOT_ORACLE_PNG = (
    CORE / "plots" / "attempt44-oracle-first-hit-supplementary.png"
)
PLOT_ORACLE_SVG = (
    CORE / "plots" / "attempt44-oracle-first-hit-supplementary.svg"
)

METHODS = (
    "model-informed-k5",
    "model-informed-k10",
    "model-informed-k15",
    "model-informed-k20",
    "model-informed-k40",
    "raw-coordinate-global-40",
)
METHOD_DIMENSIONS = {
    "model-informed-k5": 5,
    "model-informed-k10": 10,
    "model-informed-k15": 15,
    "model-informed-k20": 20,
    "model-informed-k40": 40,
    "raw-coordinate-global-40": 40,
}
PRINCIPAL_METHODS = METHODS[:-1]
RAW_METHOD = METHODS[-1]


def canonical_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def binary_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        text.rstrip() + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(path)


def load_inputs() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    attempt35 = json.loads(ATTEMPT35_PATH.read_text(encoding="utf-8"))
    attempt42 = json.loads(ATTEMPT42_PATH.read_text(encoding="utf-8"))
    attempt43 = json.loads(ATTEMPT43_PATH.read_text(encoding="utf-8"))
    expected = config["benchmark"]["input_canonical_sha256"]
    actual = canonical_sha256(ATTEMPT35_PATH)
    if actual != expected:
        raise RuntimeError(
            f"Attempt-35 hash differs from frozen config: {actual} != {expected}"
        )
    if attempt35.get("status") != "complete":
        raise RuntimeError("Attempt 35 is not complete")
    if attempt42.get("status") != "complete" or len(attempt42["runs"]) != 84:
        raise RuntimeError("Attempt 42 complete 21x4 result is required")
    if attempt43.get("status") != "complete":
        raise RuntimeError("Attempt 43 must be complete")
    gate_decision = attempt43["summary"]["gate_decision"]
    if gate_decision.get("online_rule_accepted") is not False:
        raise RuntimeError(
            "Attempt 43 did not freeze the expected rejected online rule"
        )
    selected = attempt35.get("selected_cells", [])
    if len(selected) != int(config["benchmark"]["selected_truth_cells"]):
        raise RuntimeError("Attempt-35 selected-cell count changed")
    identities = {
        (row["family"], int(row["truth_seed"]), float(row["epsilon"]))
        for row in selected
    }
    if len(identities) != len(selected):
        raise RuntimeError("Attempt-35 selected cells are not unique")
    return config, attempt35, attempt42, attempt43


def official_attempt43_evidence(attempt43: dict[str, Any]) -> dict[str, Any]:
    summary = attempt43["summary"]

    def normalized_interval(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "estimate": float(record["estimate"]),
            "lower_95": float(record["lower_95"]),
            "upper_95": float(record["upper_95"]),
            "bootstrap_draws": int(record["bootstrap_draws"]),
            "independent_truth_cells": int(record["independent_truth_cells"]),
            "bootstrap_seed": int(record["seed"]),
        }

    return {
        "status": "official-complete-result",
        "result": (
            "results_summary/QL1F-attempt43-online-certification.json"
        ),
        "result_canonical_sha256": canonical_sha256(ATTEMPT43_PATH),
        "online_rule_accepted": False,
        "headline_cost_semantics": "full-cap-online",
        "summary": {
            "oracle_scored_success": normalized_interval(
                summary["exact_posthoc_success"]["truth_cell_bootstrap"]
            ),
            "online_true_success": normalized_interval(
                summary["online_certified_success"]["truth_cell_bootstrap"]
            ),
            "false_early_stop_rate": normalized_interval(
                summary["false_early_stop"]["truth_cell_bootstrap"]
            ),
            "online_minus_oracle_success": normalized_interval(
                summary["paired_online_minus_exact_success"]
            ),
            "actual_query_ratio_to_full_cap": normalized_interval(
                summary["actual_online_cost"][
                    "query_ratio_truth_cell_bootstrap"
                ]
            ),
            "actual_shot_ratio_to_full_cap": normalized_interval(
                summary["actual_online_cost"][
                    "shot_ratio_truth_cell_bootstrap"
                ]
            ),
        },
        "gates": {
            "all_admissibility_gates_pass": False,
            "official_gate_records": summary["gates"],
        },
    }


def sign_fix(vector: np.ndarray) -> np.ndarray:
    output = np.asarray(vector, dtype=np.float64).copy()
    pivot = int(np.argmax(np.abs(output)))
    if output[pivot] < 0.0:
        output *= -1.0
    return output


def build_search_geometries(
    model: Any, config: dict[str, Any]
) -> tuple[dict[str, tuple[np.ndarray, np.ndarray]], dict[str, Any], float]:
    """Build rank-15 principal prefixes and a deterministic raw complement."""

    descending = np.argsort(np.asarray(model.eigenvalues))[::-1]
    positive_tolerance = (
        math.sqrt(np.finfo(np.float64).eps)
        * float(np.max(np.abs(model.eigenvalues)))
    )
    selected_indices = descending[:15]
    selected_values = np.asarray(model.eigenvalues)[selected_indices]
    if np.any(selected_values <= positive_tolerance):
        raise RuntimeError("nominal model does not expose 15 positive directions")

    principal = np.asarray(
        model.eigenvectors[:, selected_indices].T, dtype=np.float64
    )
    principal = np.asarray([sign_fix(row) for row in principal])
    principal /= np.linalg.norm(principal, axis=1, keepdims=True)

    norm_min = float(config["completion"]["gram_schmidt_norm_min"])
    completed: list[np.ndarray] = [row.copy() for row in principal]
    complement_raw_indices: list[int] = []
    discarded_raw_indices: list[int] = []
    for raw_index in range(PARAMETER_COUNT):
        candidate = np.eye(PARAMETER_COUNT, dtype=np.float64)[raw_index]
        # Two modified-Gram-Schmidt passes keep the deterministic completion
        # numerically orthogonal without changing the frozen raw index order.
        for _ in range(2):
            for existing in completed:
                candidate -= float(candidate @ existing) * existing
        norm_value = float(np.linalg.norm(candidate))
        if norm_value < norm_min:
            discarded_raw_indices.append(raw_index)
            continue
        candidate /= norm_value
        candidate = sign_fix(candidate)
        completed.append(candidate)
        complement_raw_indices.append(raw_index)
        if len(completed) == PARAMETER_COUNT:
            break
    full_basis = np.asarray(completed, dtype=np.float64)
    if full_basis.shape != (PARAMETER_COUNT, PARAMETER_COUNT):
        raise RuntimeError(f"completion produced shape {full_basis.shape}")
    gram_error = float(
        np.max(np.abs(full_basis @ full_basis.T - np.eye(PARAMETER_COUNT)))
    )
    if gram_error > 1e-10:
        raise RuntimeError(f"completed basis is not orthonormal: {gram_error}")

    full_curvatures = np.concatenate(
        [selected_values, np.zeros(PARAMETER_COUNT - 15, dtype=np.float64)]
    )
    common_ridge = (
        float(config["method"]["ridge_multiplier"])
        * float(np.median(selected_values))
    )
    geometries: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for method in PRINCIPAL_METHODS:
        k = METHOD_DIMENSIONS[method]
        geometries[method] = (
            full_basis[:k].copy(),
            full_curvatures[:k].copy(),
        )

    raw_basis = np.eye(PARAMETER_COUNT, dtype=np.float64)
    raw_curvatures = np.maximum(
        np.diag(np.asarray(model.hessian, dtype=np.float64)), 0.0
    )
    geometries[RAW_METHOD] = (raw_basis, raw_curvatures)
    audit = {
        "positive_eigenvalue_tolerance": positive_tolerance,
        "rank15_nominal_curvatures": selected_values.tolist(),
        "rank15_nominal_eigenvalue_indices_descending": [
            int(value) for value in selected_indices
        ],
        "common_ridge": common_ridge,
        "completion_rule": (
            "ascending raw coordinates; two-pass modified Gram-Schmidt "
            "against signed rank-15 and accepted complements"
        ),
        "sign_rule": config["completion"]["sign_rule"],
        "complement_raw_coordinate_indices": complement_raw_indices,
        "discarded_raw_coordinate_indices": discarded_raw_indices,
        "completed_basis_max_orthonormality_error": gram_error,
        "rank15_sha256": array_sha256(principal),
        "completed_basis_sha256": array_sha256(full_basis),
        "raw_basis_sha256": array_sha256(raw_basis),
        "raw_curvature_semantics": (
            "nonnegative nominal coordinate-direction Hessian diagonal; "
            "same top-15-derived common ridge, with no raw-specific retuning"
        ),
        "method_basis_sha256": {
            name: array_sha256(spec[0]) for name, spec in geometries.items()
        },
        "method_curvature_sha256": {
            name: array_sha256(spec[1]) for name, spec in geometries.items()
        },
    }
    return geometries, audit, common_ridge


class LedgerClient:
    """Seeded scalar binomial service with exact query and shot accounting."""

    def __init__(self, evaluator: Any) -> None:
        self._evaluator = evaluator
        self._rng: np.random.Generator | None = None
        self._active = False
        self.query_count = 0
        self.total_shots = 0
        self.ledger: list[dict[str, Any]] = []

    @property
    def active(self) -> bool:
        return self._active

    def start(self, seed: int) -> None:
        if self._active:
            raise RuntimeError("client already active")
        self._rng = np.random.default_rng(seed)
        self._active = True
        self.query_count = 0
        self.total_shots = 0
        self.ledger = []

    def query(self, parameters: Any, shots: int, purpose: str) -> float:
        if not self._active or self._rng is None:
            raise RuntimeError("calibration client is not active")
        vector = np.asarray(parameters, dtype=np.float64)
        if vector.shape != (PARAMETER_COUNT,) or not np.all(np.isfinite(vector)):
            raise ValueError("query parameters must be 40 finite real values")
        if not isinstance(shots, (int, np.integer)) or int(shots) <= 0:
            raise ValueError("shots must be a positive integer")
        exact_probability = float(self._evaluator(vector))
        if exact_probability < -1e-12 or exact_probability > 1.0 + 1e-12:
            raise FloatingPointError(
                f"truth oracle returned invalid fidelity {exact_probability}"
            )
        exact_probability = float(np.clip(exact_probability, 0.0, 1.0))
        successes = int(
            self._rng.binomial(int(shots), exact_probability)
        )
        sampled = successes / int(shots)
        self.query_count += 1
        self.total_shots += int(shots)
        self.ledger.append(
            {
                "query_index": self.query_count,
                "parameter_sha256": array_sha256(vector),
                "purpose": purpose,
                "shots": int(shots),
                "successes": successes,
                "sampled_fidelity": sampled,
            }
        )
        return sampled

    def end(self) -> dict[str, int]:
        if not self._active:
            raise RuntimeError("client is not active")
        self._active = False
        self._rng = None
        return {
            "query_count": self.query_count,
            "total_shots": self.total_shots,
        }


def frozen_constants(config: dict[str, Any]) -> dict[str, Any]:
    method = config["method"]
    confidence = 0.995
    return {
        "cycles": int(method["cycles"]),
        "delta": float(method["central_difference_delta"]),
        "shots": int(method["shots_per_decision_query"]),
        "sentinel_shots": int(method["sentinel_shots"]),
        "target": float(method["target_infidelity"]),
        "trust_radius": float(method["trust_radius"]),
        "confidence": confidence,
        "z": float(norm.ppf(confidence)),
    }


def bounded_step(
    gradient: np.ndarray,
    curvatures: np.ndarray,
    ridge: float,
    trust_radius: float,
) -> np.ndarray:
    denominators = np.asarray(curvatures, dtype=np.float64) + float(ridge)
    if np.any(denominators <= 0.0):
        raise RuntimeError("curvature-plus-ridge denominator is nonpositive")
    step = -np.asarray(gradient, dtype=np.float64) / denominators
    norm_value = float(np.linalg.norm(step))
    if norm_value > trust_radius:
        step *= trust_radius / norm_value
    return step


def global_calibration(
    client: LedgerClient,
    start: np.ndarray,
    directions: np.ndarray,
    curvatures: np.ndarray,
    common_ridge: float,
    constants: dict[str, Any],
) -> dict[str, Any]:
    current = np.asarray(start, dtype=np.float64).copy()
    basis = np.asarray(directions, dtype=np.float64)
    hdiag = np.asarray(curvatures, dtype=np.float64)
    k = int(basis.shape[0])
    if basis.shape != (k, PARAMETER_COUNT):
        raise ValueError("invalid basis shape")
    if not np.allclose(
        basis @ basis.T, np.eye(k), atol=1e-10, rtol=0.0
    ):
        raise ValueError("search basis is not orthonormal")
    accepted_parameters = [current.copy()]
    accepted_costs = [{"queries": 0, "shots": 0}]
    decisions: list[dict[str, Any]] = []

    client.query(current, constants["sentinel_shots"], "initial-sentinel")
    for cycle in range(1, constants["cycles"] + 1):
        gradient_values: list[float] = []
        variance_values: list[float] = []
        for index, direction in enumerate(basis):
            plus = client.query(
                current + constants["delta"] * direction,
                constants["shots"],
                f"cycle-{cycle}-gradient-{index}-plus",
            )
            minus = client.query(
                current - constants["delta"] * direction,
                constants["shots"],
                f"cycle-{cycle}-gradient-{index}-minus",
            )
            derivative = ((1.0 - plus) - (1.0 - minus)) / (
                2.0 * constants["delta"]
            )
            variance = (
                plus * (1.0 - plus) + minus * (1.0 - minus)
            ) / (
                4.0
                * constants["delta"] ** 2
                * constants["shots"]
            )
            gradient_values.append(float(derivative))
            variance_values.append(float(variance))

        gradient = np.asarray(gradient_values, dtype=np.float64)
        covariance_diagonal = np.asarray(variance_values, dtype=np.float64)
        step = bounded_step(
            gradient, hdiag, common_ridge, constants["trust_radius"]
        )
        candidate = current + step @ basis
        predicted = float(
            -gradient @ step - 0.5 * np.sum(hdiag * step**2)
        )
        predicted_se = float(
            np.sqrt(max(0.0, np.sum(step**2 * covariance_diagonal)))
        )
        model_margin = predicted - constants["z"] * predicted_se
        model_pass = bool(model_margin > 0.0)

        queried_proposal = candidate if model_pass else current.copy()
        sampled_current = client.query(
            current,
            constants["shots"],
            f"cycle-{cycle}-validation-current",
        )
        sampled_proposal = client.query(
            queried_proposal,
            constants["shots"],
            f"cycle-{cycle}-validation-proposal",
        )
        proposal_ledger_row = client.ledger[-1]
        validation_se = float(
            np.sqrt(
                (
                    sampled_current * (1.0 - sampled_current)
                    + sampled_proposal * (1.0 - sampled_proposal)
                )
                / constants["shots"]
            )
        )
        measured_improvement = float(sampled_proposal - sampled_current)
        validation_margin = (
            measured_improvement - constants["z"] * validation_se
        )
        accepted = bool(model_pass and validation_margin > 0.0)
        before = current.copy()
        if accepted:
            current = candidate.copy()
        accepted_parameters.append(current.copy())
        accepted_costs.append(
            {"queries": client.query_count, "shots": client.total_shots}
        )
        certification = None
        if accepted and float(np.linalg.norm(step)) > 0.0:
            certified = certify_target_from_counts(
                int(proposal_ledger_row["successes"]),
                int(proposal_ledger_row["shots"]),
                target_infidelity=constants["target"],
                confidence=constants["confidence"],
            )
            certification = {
                "validation_proposal_successes": int(
                    proposal_ledger_row["successes"]
                ),
                "validation_proposal_failures": int(
                    proposal_ledger_row["shots"]
                    - proposal_ledger_row["successes"]
                ),
                "validation_proposal_shots": int(
                    proposal_ledger_row["shots"]
                ),
                "validation_proposal_query_index": int(
                    proposal_ledger_row["query_index"]
                ),
                "estimated_infidelity": certified.estimated_infidelity,
                "upper_infidelity_99_5": certified.upper_infidelity,
                "certified": certified.certified,
            }
        decisions.append(
            {
                "cycle": cycle,
                "current_parameter_sha256": array_sha256(before),
                "proposed_parameter_sha256": array_sha256(candidate),
                "accepted_parameter_sha256": array_sha256(current),
                "candidate_exposed_to_oracle": model_pass,
                "noisy_gradient": gradient.tolist(),
                "gradient_covariance_diagonal": covariance_diagonal.tolist(),
                "gradient_norm": float(np.linalg.norm(gradient)),
                "step_coordinates": step.tolist(),
                "step_norm": float(np.linalg.norm(step)),
                "predicted_model_improvement": predicted,
                "predicted_model_improvement_se": predicted_se,
                "model_decision_margin": float(model_margin),
                "model_pass": model_pass,
                "sampled_current_fidelity": float(sampled_current),
                "sampled_proposal_fidelity": float(sampled_proposal),
                "measured_validation_improvement": measured_improvement,
                "validation_improvement_se": validation_se,
                "validation_decision_margin": float(validation_margin),
                "validation_pass": accepted,
                "accepted": accepted,
                "accepted_nonzero_proposal_count": certification,
            }
        )

    client.query(current, constants["sentinel_shots"], "final-sentinel")
    service = client.end()
    expected_queries = 4 * k + 6
    expected_shots = (
        2 * constants["sentinel_shots"]
        + (4 * k + 4) * constants["shots"]
    )
    if service != {
        "query_count": expected_queries,
        "total_shots": expected_shots,
    }:
        raise AssertionError((service, expected_queries, expected_shots))
    return {
        "basis_dimension": k,
        "cycles": constants["cycles"],
        "common_ridge": common_ridge,
        "query_cap": expected_queries,
        "shot_cap": expected_shots,
        "service_query_count": service["query_count"],
        "service_total_shots": service["total_shots"],
        "accepted_parameter_vectors_posthoc_only": accepted_parameters,
        "accepted_costs": accepted_costs,
        "decisions": decisions,
        "query_ledger": client.ledger,
    }


def attach_posthoc(
    scan: dict[str, Any], exact_evaluator: Any, constants: dict[str, Any]
) -> dict[str, Any]:
    accepted_vectors = scan.pop("accepted_parameter_vectors_posthoc_only")
    accepted_infidelities = [
        1.0 - float(exact_evaluator(vector)) for vector in accepted_vectors
    ]
    first_hit = next(
        (
            index
            for index, value in enumerate(accepted_infidelities)
            if value <= constants["target"]
        ),
        None,
    )
    destructive_accepted = 0
    first_certificate = None
    for index, decision in enumerate(scan["decisions"], start=1):
        before = accepted_infidelities[index - 1]
        after = accepted_infidelities[index]
        destructive = bool(decision["accepted"] and after > before + 1e-12)
        destructive_accepted += int(destructive)
        decision["posthoc"] = {
            "current_exact_infidelity": before,
            "accepted_exact_infidelity": after,
            "destructive_accepted_step": destructive,
            "used_by_calibration_or_certificate": False,
        }
        certificate = decision["accepted_nonzero_proposal_count"]
        if certificate is not None and certificate["certified"]:
            certificate["posthoc_exact_infidelity"] = after
            certificate["posthoc_false_early_stop"] = bool(
                after > constants["target"]
            )
            certificate["posthoc_true_certificate"] = bool(
                after <= constants["target"]
            )
            if first_certificate is None:
                first_certificate = {
                    "accepted_index": index,
                    "queries": int(scan["accepted_costs"][index]["queries"]),
                    "shots": int(scan["accepted_costs"][index]["shots"]),
                    **certificate,
                }

    oracle_hit = (
        {
            "accepted_index": int(first_hit),
            **scan["accepted_costs"][first_hit],
        }
        if first_hit is not None
        else None
    )
    scan.update(
        {
            "warm_infidelity": accepted_infidelities[0],
            "final_infidelity": accepted_infidelities[-1],
            "best_accepted_infidelity": min(accepted_infidelities),
            "accepted_infidelities": accepted_infidelities,
            "oracle_scored_first_accepted_to_target": oracle_hit,
            "oracle_scored_success": first_hit is not None,
            "certified_online_first_stop": first_certificate,
            "certified_online_event": first_certificate is not None,
            "certified_online_true_success": bool(
                first_certificate is not None
                and first_certificate["posthoc_true_certificate"]
            ),
            "false_early_stop": bool(
                first_certificate is not None
                and first_certificate["posthoc_false_early_stop"]
            ),
            "destructive_accepted_steps": destructive_accepted,
            "accepted_nonzero_steps": sum(
                decision["accepted"] and decision["step_norm"] > 0.0
                for decision in scan["decisions"]
            ),
            "posthoc_exact_fidelity_evaluations": len(accepted_vectors),
            "posthoc_values_used_in_calibration": False,
        }
    )
    return scan


def compact_full_scan(scan: dict[str, Any]) -> dict[str, Any]:
    """Seal detailed runtime evidence without storing every query row."""

    ledger = scan.pop("query_ledger")
    purpose_counts: dict[str, int] = defaultdict(int)
    purpose_shots: dict[str, int] = defaultdict(int)
    for row in ledger:
        purpose_counts[row["purpose"]] += 1
        purpose_shots[row["purpose"]] += int(row["shots"])
    scan["query_ledger_closure"] = {
        "row_count": len(ledger),
        "total_shots": sum(int(row["shots"]) for row in ledger),
        "canonical_json_sha256": canonical_json_sha256(ledger),
        "row_schema": [
            "query_index",
            "parameter_sha256",
            "purpose",
            "shots",
            "successes",
            "sampled_fidelity",
        ],
        "purpose_counts": dict(sorted(purpose_counts.items())),
        "purpose_shots": dict(sorted(purpose_shots.items())),
        "exact_probability_stored": False,
        "full_rows_retained": False,
        "reproduction": (
            "rerun with the recorded paired seed, sealed source, truth "
            "identity, method, and frozen config"
        ),
    }
    for decision in scan["decisions"]:
        gradient = np.asarray(decision.pop("noisy_gradient"), dtype=np.float64)
        covariance = np.asarray(
            decision.pop("gradient_covariance_diagonal"), dtype=np.float64
        )
        step = np.asarray(decision.pop("step_coordinates"), dtype=np.float64)
        decision["noisy_gradient_sha256"] = array_sha256(gradient)
        decision["gradient_covariance_diagonal_sha256"] = array_sha256(
            covariance
        )
        decision["step_coordinates_sha256"] = array_sha256(step)
        decision["compact_array_values_retained"] = False
    return scan


def paired_noise_seed(
    family_index: int, truth_seed: int, replicate: int
) -> int:
    sequence = np.random.SeedSequence(
        [113, 44, family_index, int(truth_seed), int(replicate)]
    )
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def run_one(
    selection: dict[str, Any],
    selected_index: int,
    replicate: int,
    method: str,
    model: Any,
    geometry: tuple[np.ndarray, np.ndarray],
    common_ridge: float,
    constants: dict[str, Any],
    compact: bool,
) -> dict[str, Any]:
    family = str(selection["family"])
    truth_seed = int(selection["truth_seed"])
    epsilon = float(selection["epsilon"])
    family_index = TRUTH_FAMILIES.index(family)
    drift, controls, truth_metadata = make_truth(
        model, family, epsilon, truth_seed
    )

    def exact_evaluator(parameters: Any) -> float:
        return float(
            np.asarray(
                model.average_fidelity(
                    jnp.asarray(parameters),
                    jnp.asarray(drift),
                    jnp.asarray(controls),
                )
            )
        )

    seed = paired_noise_seed(family_index, truth_seed, replicate)
    client = LedgerClient(exact_evaluator)
    client.start(seed)
    scan = global_calibration(
        client,
        np.asarray(model.optimized_parameters, dtype=np.float64),
        geometry[0],
        geometry[1],
        common_ridge,
        constants,
    )
    if client.active:
        raise AssertionError("client remained active after calibration")
    scan = attach_posthoc(scan, exact_evaluator, constants)
    if compact:
        scan = compact_full_scan(scan)
    return {
        "selected_cell": f"{family}:{truth_seed}:{epsilon:g}",
        "selected_cell_index": selected_index,
        "family": family,
        "truth_seed": truth_seed,
        "epsilon": epsilon,
        "replicate": replicate,
        "method": method,
        "search_dimension": METHOD_DIMENSIONS[method],
        "noise_seed": seed,
        "paired_seed_shared_across_methods": True,
        "attempt35_warm_infidelity": float(selection["warm_infidelity"]),
        "attempt35_raw_exact_final_infidelity": float(
            selection["raw_exact_final_infidelity"]
        ),
        "truth_metadata": truth_metadata,
        "black_box_boundary": {
            "calibration_interface": (
                "query(parameters, shots) -> sampled scalar fidelity"
            ),
            "truth_derivatives_available_during_calibration": False,
            "posthoc_started_after_client_end": True,
            "posthoc_values_used_in_decisions": False,
        },
        "scan": scan,
    }


def replay_attempt43(
    attempt42: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Apply the frozen Attempt-43 rule to Attempt-42 counts locally."""

    replicate_rows: list[dict[str, Any]] = []
    for run in attempt42["runs"]:
        scan = run["scan"]
        first_certificate = None
        for decision in scan["decisions"]:
            if not decision["accepted"]:
                continue
            purpose = f"cycle-{decision['cycle']}-validation-proposal"
            ledger_row = next(
                row for row in scan["query_ledger"] if row["purpose"] == purpose
            )
            certificate = certify_target_from_counts(
                int(ledger_row["successes"]),
                int(ledger_row["shots"]),
                target_infidelity=float(config["method"]["target_infidelity"]),
                confidence=0.995,
            )
            accepted_index = int(decision["cycle"])
            exact_infidelity = float(
                scan["accepted_infidelities"][accepted_index]
            )
            if certificate.certified and first_certificate is None:
                first_certificate = {
                    "accepted_index": accepted_index,
                    "queries": int(
                        scan["accepted_costs"][accepted_index]["queries"]
                    ),
                    "shots": int(
                        scan["accepted_costs"][accepted_index]["shots"]
                    ),
                    "successes": int(ledger_row["successes"]),
                    "failures": int(
                        ledger_row["shots"] - ledger_row["successes"]
                    ),
                    "upper_infidelity_99_5": certificate.upper_infidelity,
                    "posthoc_exact_infidelity": exact_infidelity,
                    "posthoc_true_certificate": bool(
                        exact_infidelity
                        <= float(config["method"]["target_infidelity"])
                    ),
                }
        cap_queries = int(scan["query_cap"])
        cap_shots = int(scan["shot_cap"])
        replicate_rows.append(
            {
                "selected_cell": run["selected_cell"],
                "selected_cell_index": run["selected_cell_index"],
                "family": run["family"],
                "replicate": run["replicate"],
                "oracle_success": float(scan["actual_success"]),
                "online_true_success": float(
                    first_certificate is not None
                    and first_certificate["posthoc_true_certificate"]
                ),
                "certificate_event": float(first_certificate is not None),
                "false_early_stop": float(
                    first_certificate is not None
                    and not first_certificate["posthoc_true_certificate"]
                ),
                "missed_certificate": float(
                    scan["actual_success"]
                    and not (
                        first_certificate is not None
                        and first_certificate["posthoc_true_certificate"]
                    )
                ),
                "actual_queries": float(
                    first_certificate["queries"]
                    if first_certificate is not None
                    else cap_queries
                ),
                "actual_shots": float(
                    first_certificate["shots"]
                    if first_certificate is not None
                    else cap_shots
                ),
                "full_cap_queries": float(cap_queries),
                "full_cap_shots": float(cap_shots),
                "first_certificate": first_certificate,
            }
        )
    truth = aggregate_truth_rows(replicate_rows, None)
    draw_indices = stratified_draw_indices(
        truth,
        int(config["bootstrap"]["draws"]),
        int(config["bootstrap"]["seed"]),
    )

    def interval(key: str) -> dict[str, Any]:
        return bootstrap_scalar(truth, key, draw_indices, config)

    difference_rows = [
        {**row, "value": row["online_true_success"] - row["oracle_success"]}
        for row in truth
    ]
    query_ratio = bootstrap_ratio(
        truth,
        "actual_queries",
        "full_cap_queries",
        draw_indices,
        config,
    )
    shot_ratio = bootstrap_ratio(
        truth,
        "actual_shots",
        "full_cap_shots",
        draw_indices,
        config,
    )
    online = interval("online_true_success")
    false_stop = interval("false_early_stop")
    success_difference = bootstrap_scalar(
        difference_rows, "value", draw_indices, config
    )
    gate = {
        "false_early_stop_rate_at_most_0_01": (
            false_stop["estimate"] <= 0.01
        ),
        "success_difference_lower_95_above_minus_0_05": (
            success_difference["lower_95"] > -0.05
        ),
        "absolute_online_success_at_least_0_75": (
            online["estimate"] >= 0.75
        ),
        "query_ratio_upper_95_below_0_90": (
            query_ratio["upper_95"] < 0.90
        ),
        "shot_ratio_upper_95_below_0_90": (
            shot_ratio["upper_95"] < 0.90
        ),
    }
    return {
        "status": "local-replay-from-attempt42",
        "reason": (
            "Attempt-43 result was absent; frozen ATTEMPT43_PROTOCOL.md was "
            "applied locally without changing any Attempt-42 state."
        ),
        "truth_level_rows": truth,
        "summary": {
            "oracle_scored_success": interval("oracle_success"),
            "online_true_success": online,
            "certificate_event_rate": interval("certificate_event"),
            "false_early_stop_rate": false_stop,
            "missed_certificate_rate": interval("missed_certificate"),
            "online_minus_oracle_success": success_difference,
            "actual_query_ratio_to_full_cap": query_ratio,
            "actual_shot_ratio_to_full_cap": shot_ratio,
        },
        "gates": {
            **gate,
            "all_admissibility_gates_pass": all(gate.values()),
        },
        "headline_cost_semantics": (
            "certified-online"
            if all(gate.values())
            else "full-cap-online"
        ),
    }


def aggregate_truth_rows(
    replicate_rows: list[dict[str, Any]], method: str | None
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in replicate_rows:
        if method is None or row.get("method") == method:
            grouped[row["selected_cell"]].append(row)
    output: list[dict[str, Any]] = []
    for selected_cell in sorted(
        grouped, key=lambda key: grouped[key][0]["selected_cell_index"]
    ):
        rows = sorted(grouped[selected_cell], key=lambda row: row["replicate"])
        numeric_keys = [
            key
            for key, value in rows[0].items()
            if isinstance(value, (int, float, bool, np.integer, np.floating))
            and key not in ("selected_cell_index", "replicate")
        ]
        output.append(
            {
                "selected_cell": selected_cell,
                "selected_cell_index": int(rows[0]["selected_cell_index"]),
                "family": rows[0]["family"],
                "nested_replicates": len(rows),
                **{
                    key: float(np.mean([float(row[key]) for row in rows]))
                    for key in numeric_keys
                },
            }
        )
    return output


def stratified_draw_indices(
    truth_rows: list[dict[str, Any]], draws: int, seed: int
) -> np.ndarray:
    strata: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(truth_rows):
        strata[row["family"]].append(index)
    rng = np.random.default_rng(seed)
    output = np.empty((draws, len(truth_rows)), dtype=np.int64)
    offset = 0
    for family in TRUTH_FAMILIES:
        group = np.asarray(strata[family], dtype=np.int64)
        size = len(group)
        choices = rng.integers(0, size, size=(draws, size))
        output[:, offset : offset + size] = group[choices]
        offset += size
    if offset != len(truth_rows):
        raise RuntimeError("bootstrap strata do not cover truth rows")
    return output


def interval_from_draws(
    estimate: float,
    draws: np.ndarray,
    config: dict[str, Any],
    independent_truth_cells: int,
) -> dict[str, Any]:
    return {
        "estimate": float(estimate),
        "lower_95": float(np.quantile(draws, 0.025)),
        "upper_95": float(np.quantile(draws, 0.975)),
        "bootstrap_draws": int(config["bootstrap"]["draws"]),
        "bootstrap_seed": int(config["bootstrap"]["seed"]),
        "independent_truth_cells": int(independent_truth_cells),
        "stratified_by": config["bootstrap"]["stratify_by"],
    }


def bootstrap_scalar(
    truth_rows: list[dict[str, Any]],
    key: str,
    draw_indices: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    values = np.asarray([float(row[key]) for row in truth_rows])
    samples = np.mean(values[draw_indices], axis=1)
    return interval_from_draws(
        float(np.mean(values)), samples, config, len(truth_rows)
    )


def bootstrap_ratio(
    truth_rows: list[dict[str, Any]],
    numerator_key: str,
    denominator_key: str,
    draw_indices: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    numerator = np.asarray(
        [float(row[numerator_key]) for row in truth_rows]
    )
    denominator = np.asarray(
        [float(row[denominator_key]) for row in truth_rows]
    )
    samples = np.mean(numerator[draw_indices], axis=1) / np.mean(
        denominator[draw_indices], axis=1
    )
    return interval_from_draws(
        float(np.mean(numerator) / np.mean(denominator)),
        samples,
        config,
        len(truth_rows),
    )


def summarize(
    runs: list[dict[str, Any]],
    config: dict[str, Any],
    headline_semantics: str,
) -> dict[str, Any]:
    replicate_rows: list[dict[str, Any]] = []
    for run in runs:
        scan = run["scan"]
        certificate = scan["certified_online_first_stop"]
        oracle_hit = scan["oracle_scored_first_accepted_to_target"]
        cap_queries = int(scan["query_cap"])
        cap_shots = int(scan["shot_cap"])
        certified_queries = (
            int(certificate["queries"]) if certificate else cap_queries
        )
        certified_shots = (
            int(certificate["shots"]) if certificate else cap_shots
        )
        oracle_queries = (
            int(oracle_hit["queries"]) if oracle_hit else cap_queries
        )
        oracle_shots = int(oracle_hit["shots"]) if oracle_hit else cap_shots
        headline_queries = (
            certified_queries
            if headline_semantics == "certified-online"
            else cap_queries
        )
        headline_shots = (
            certified_shots
            if headline_semantics == "certified-online"
            else cap_shots
        )
        replicate_rows.append(
            {
                "selected_cell": run["selected_cell"],
                "selected_cell_index": run["selected_cell_index"],
                "family": run["family"],
                "replicate": run["replicate"],
                "method": run["method"],
                "search_dimension": run["search_dimension"],
                "oracle_scored_success": float(scan["oracle_scored_success"]),
                "certified_online_true_success": float(
                    scan["certified_online_true_success"]
                ),
                "certificate_event": float(scan["certified_online_event"]),
                "false_early_stop": float(scan["false_early_stop"]),
                "full_cap_queries": float(cap_queries),
                "full_cap_shots": float(cap_shots),
                "certified_online_queries": float(certified_queries),
                "certified_online_shots": float(certified_shots),
                "oracle_first_hit_queries": float(oracle_queries),
                "oracle_first_hit_shots": float(oracle_shots),
                "headline_queries": float(headline_queries),
                "headline_shots": float(headline_shots),
                "accepted_nonzero_steps": float(
                    scan["accepted_nonzero_steps"]
                ),
                "destructive_accepted_steps": float(
                    scan["destructive_accepted_steps"]
                ),
            }
        )

    truth_by_method = {
        method: aggregate_truth_rows(replicate_rows, method)
        for method in METHODS
    }
    draw_indices = stratified_draw_indices(
        truth_by_method[METHODS[0]],
        int(config["bootstrap"]["draws"]),
        int(config["bootstrap"]["seed"]),
    )
    metrics = (
        "oracle_scored_success",
        "certified_online_true_success",
        "certificate_event",
        "false_early_stop",
        "full_cap_queries",
        "full_cap_shots",
        "certified_online_queries",
        "certified_online_shots",
        "oracle_first_hit_queries",
        "oracle_first_hit_shots",
        "headline_queries",
        "headline_shots",
    )
    methods: dict[str, Any] = {}
    for method in METHODS:
        rows = truth_by_method[method]
        accepted = sum(
            run["scan"]["accepted_nonzero_steps"]
            for run in runs
            if run["method"] == method
        )
        destructive = sum(
            run["scan"]["destructive_accepted_steps"]
            for run in runs
            if run["method"] == method
        )
        methods[method] = {
            "geometry": (
                "raw-coordinate comparator"
                if method == RAW_METHOD
                else "deterministic model-informed"
            ),
            "search_dimension": METHOD_DIMENSIONS[method],
            "truth_level_rows": rows,
            "metrics": {
                key: bootstrap_scalar(rows, key, draw_indices, config)
                for key in metrics
            },
            "accepted_nonzero_steps": int(accepted),
            "destructive_accepted_steps": int(destructive),
            "destructive_accepted_step_rate": (
                destructive / accepted if accepted else 0.0
            ),
            "by_family": {
                family: {
                    "truth_cells": sum(row["family"] == family for row in rows),
                    "oracle_scored_success": float(
                        np.mean(
                            [
                                row["oracle_scored_success"]
                                for row in rows
                                if row["family"] == family
                            ]
                        )
                    ),
                    "headline_queries": float(
                        np.mean(
                            [
                                row["headline_queries"]
                                for row in rows
                                if row["family"] == family
                            ]
                        )
                    ),
                    "headline_shots": float(
                        np.mean(
                            [
                                row["headline_shots"]
                                for row in rows
                                if row["family"] == family
                            ]
                        )
                    ),
                }
                for family in TRUTH_FAMILIES
            },
        }

    reference = truth_by_method["model-informed-k40"]
    reference_by_cell = {
        row["selected_cell"]: row for row in reference
    }
    gate_config = config["selection_gate"]
    gates: dict[str, Any] = {}
    for method in PRINCIPAL_METHODS:
        rows = truth_by_method[method]
        paired_rows = []
        for row in rows:
            ref = reference_by_cell[row["selected_cell"]]
            paired_rows.append(
                {
                    **row,
                    "success_difference": (
                        row["oracle_scored_success"]
                        - ref["oracle_scored_success"]
                    ),
                    "reference_headline_queries": ref["headline_queries"],
                    "reference_headline_shots": ref["headline_shots"],
                }
            )
        difference = bootstrap_scalar(
            paired_rows, "success_difference", draw_indices, config
        )
        query_ratio = bootstrap_ratio(
            paired_rows,
            "headline_queries",
            "reference_headline_queries",
            draw_indices,
            config,
        )
        shot_ratio = bootstrap_ratio(
            paired_rows,
            "headline_shots",
            "reference_headline_shots",
            draw_indices,
            config,
        )
        success = methods[method]["metrics"]["oracle_scored_success"]
        safety = (
            methods[method]["destructive_accepted_step_rate"]
            <= float(
                gate_config["destructive_accepted_step_rate_max"]
            )
        )
        core = {
            "absolute_success_at_least_0_75": (
                success["estimate"]
                >= float(gate_config["absolute_success_min"])
            ),
            "success_difference_lower_95_above_minus_0_10": (
                difference["lower_95"]
                > float(
                    gate_config[
                        "success_difference_lower_95_min_exclusive"
                    ]
                )
            ),
            "destructive_accepted_step_rate_at_most_0_05": safety,
        }
        gates[method] = {
            "success_difference_vs_model_informed_k40": difference,
            "headline_query_ratio_vs_model_informed_k40": query_ratio,
            "headline_shot_ratio_vs_model_informed_k40": shot_ratio,
            "core_safety_gates": {
                **core,
                "all_pass": all(core.values()),
            },
            "resource_advantage_gate": {
                "query_ratio_upper_95_below_0_60": (
                    query_ratio["upper_95"]
                    < float(gate_config["cost_ratio_upper_95_max"])
                ),
                "shot_ratio_upper_95_below_0_60": (
                    shot_ratio["upper_95"]
                    < float(gate_config["cost_ratio_upper_95_max"])
                ),
                "all_pass": (
                    query_ratio["upper_95"]
                    < float(gate_config["cost_ratio_upper_95_max"])
                    and shot_ratio["upper_95"]
                    < float(gate_config["cost_ratio_upper_95_max"])
                ),
            },
        }

    passing = [
        method
        for method in PRINCIPAL_METHODS
        if gates[method]["core_safety_gates"]["all_pass"]
    ]
    smallest_passing = (
        min(passing, key=lambda name: METHOD_DIMENSIONS[name])
        if passing
        else None
    )
    k15 = methods["model-informed-k15"]["metrics"][
        "oracle_scored_success"
    ]["estimate"]
    selected = smallest_passing
    replacement_rule = "not-needed"
    if selected in ("model-informed-k20", "model-informed-k40"):
        improvement = (
            methods[selected]["metrics"]["oracle_scored_success"]["estimate"]
            - k15
        )
        k15_safe = gates["model-informed-k15"][
            "core_safety_gates"
        ]["all_pass"]
        allowed = (
            improvement
            >= float(gate_config["larger_k_success_improvement_min"])
            or not k15_safe
        )
        replacement_rule = (
            "passed-larger-k-rule"
            if allowed
            else "failed-larger-k-rule"
        )
        if not allowed:
            selected = (
                "model-informed-k15"
                if k15_safe
                else None
            )
    return {
        "cost_semantics": {
            "headline": headline_semantics,
            "full_cap_online": (
                "executable two-cycle method including both sentinels"
            ),
            "certified_online": (
                "first accepted nonzero proposal passing one-sided 99.5% "
                "Clopper-Pearson target certificate; otherwise full cap"
            ),
            "oracle_scored_first_hit": (
                "hidden-exact post-hoc diagnostic; not deployable"
            ),
        },
        "replicate_level_metrics": replicate_rows,
        "methods": methods,
        "dimension_selection": {
            "reference": "model-informed-k40",
            "gates": gates,
            "smallest_core_gate_passing_dimension": (
                METHOD_DIMENSIONS[smallest_passing]
                if smallest_passing
                else None
            ),
            "selected_method": selected,
            "selected_dimension": (
                METHOD_DIMENSIONS[selected] if selected else None
            ),
            "larger_k_replacement_rule": replacement_rule,
            "selected_resource_advantage_gate_pass": (
                gates[selected]["resource_advantage_gate"]["all_pass"]
                if selected
                else False
            ),
        },
    }


def checks_for(
    runs: list[dict[str, Any]],
    mode: str,
    geometries: dict[str, tuple[np.ndarray, np.ndarray]],
    basis_audit: dict[str, Any],
) -> dict[str, bool]:
    expected = 18 if mode == "smoke" else 21 * 4 * len(METHODS)
    expected_caps = {
        5: (26, 788_480),
        10: (46, 1_443_840),
        15: (66, 2_099_200),
        20: (86, 2_754_560),
        40: (166, 5_376_000),
    }
    by_cell_rep: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_cell_rep[(run["selected_cell"], run["replicate"])].append(run)
    payload_text = json.dumps(runs, allow_nan=False)
    personal_path_patterns = (
        r"[A-Za-z]:[\\/]",
        r"/mnt/",
        r"/home/",
        r"coder_linjia",
        r"Users[\\/]31915(?:[\\/]|$)",
    )

    def ledger_closes(run: dict[str, Any]) -> bool:
        scan = run["scan"]
        if "query_ledger" in scan:
            return (
                scan["service_query_count"]
                == len(scan["query_ledger"])
                == scan["query_cap"]
                and sum(row["shots"] for row in scan["query_ledger"])
                == scan["service_total_shots"]
                == scan["shot_cap"]
            )
        closure = scan.get("query_ledger_closure", {})
        return (
            scan["service_query_count"]
            == closure.get("row_count")
            == scan["query_cap"]
            and closure.get("total_shots")
            == scan["service_total_shots"]
            == scan["shot_cap"]
            and isinstance(closure.get("canonical_json_sha256"), str)
            and len(closure["canonical_json_sha256"]) == 64
        )

    def ledger_hides_exact(run: dict[str, Any]) -> bool:
        scan = run["scan"]
        if "query_ledger" in scan:
            return all(
                "exact_probability" not in row and "exact_fidelity" not in row
                for row in scan["query_ledger"]
            )
        closure = scan.get("query_ledger_closure", {})
        return (
            closure.get("exact_probability_stored") is False
            and "exact_probability" not in closure.get("row_schema", [])
            and "exact_fidelity" not in closure.get("row_schema", [])
        )

    return {
        "expected_run_count": len(runs) == expected,
        "all_methods_present_per_cell_replicate": all(
            {run["method"] for run in group} == set(METHODS)
            for group in by_cell_rep.values()
        ),
        "paired_seed_shared_across_methods": all(
            len({run["noise_seed"] for run in group}) == 1
            for group in by_cell_rep.values()
        ),
        "all_service_ledgers_close": all(
            (
                run["scan"]["query_cap"],
                run["scan"]["shot_cap"],
            )
            == expected_caps[run["search_dimension"]]
            and ledger_closes(run)
            for run in runs
        ),
        "accepted_proposals_have_integer_validation_counts": all(
            (
                decision["accepted_nonzero_proposal_count"] is not None
                and isinstance(
                    decision["accepted_nonzero_proposal_count"][
                        "validation_proposal_successes"
                    ],
                    int,
                )
            )
            if decision["accepted"] and decision["step_norm"] > 0.0
            else decision["accepted_nonzero_proposal_count"] is None
            for run in runs
            for decision in run["scan"]["decisions"]
        ),
        "query_ledgers_hide_exact_probabilities": all(
            ledger_hides_exact(run) for run in runs
        ),
        "full_uses_compact_ledger_schema": (
            all(
                "query_ledger" not in run["scan"]
                and run["scan"]["query_ledger_closure"][
                    "full_rows_retained"
                ]
                is False
                for run in runs
            )
            if mode == "full"
            else True
        ),
        "posthoc_separated": all(
            run["black_box_boundary"]["posthoc_started_after_client_end"]
            and not run["black_box_boundary"][
                "posthoc_values_used_in_decisions"
            ]
            and not run["scan"]["posthoc_values_used_in_calibration"]
            for run in runs
        ),
        "two_cycles_everywhere": all(
            len(run["scan"]["decisions"]) == 2 for run in runs
        ),
        "no_confirmation_truths": all(
            int(run["truth_seed"]) <= 260612 for run in runs
        ),
        "full_has_21_cells_x_4_nested_replicates": (
            len(by_cell_rep) == 84
            and {
                (run["selected_cell"], run["replicate"])
                for run in runs
            }
            == {
                (run["selected_cell"], replicate)
                for run in runs
                for replicate in range(4)
            }
            if mode == "full"
            else True
        ),
        "completed_basis_is_orthonormal": (
            basis_audit["completed_basis_max_orthonormality_error"] <= 1e-10
        ),
        "principal_prefixes_nested": all(
            np.array_equal(
                geometries[PRINCIPAL_METHODS[index]][0],
                geometries[PRINCIPAL_METHODS[index + 1]][0][
                    : METHOD_DIMENSIONS[PRINCIPAL_METHODS[index]]
                ],
            )
            for index in range(len(PRINCIPAL_METHODS) - 1)
        ),
        "no_personal_absolute_paths_in_runs": not any(
            re.search(pattern, payload_text)
            for pattern in personal_path_patterns
        ),
    }


def source_hashes() -> dict[str, str]:
    paths = (
        Path("code/attempt44_dimension_cost.py"),
        Path("code/attempt44_dimension_cost_config.json"),
        Path("docs/ATTEMPT44_PROTOCOL.md"),
        Path("docs/RESEARCH_CHARTER_05.md"),
        Path("docs/ATTEMPT43_PROTOCOL.md"),
        Path("code/phase3_common.py"),
        Path("code/cycle5_statistics.py"),
        Path("results_summary/QL1F-attempt35-normalized-difficulty.json"),
        Path("results_summary/QL1F-attempt42-normalized-principal-global.json"),
        Path("results_summary/QL1F-attempt43-online-certification.json"),
    )
    return {
        path.as_posix(): canonical_sha256(CORE / path) for path in paths
    }


def errorbar(
    record: dict[str, Any],
) -> tuple[float, tuple[float, float]]:
    value = float(record["estimate"])
    return value, (
        value - float(record["lower_95"]),
        float(record["upper_95"]) - value,
    )


def make_plots(summary: dict[str, Any]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    methods = summary["methods"]
    principal = list(PRINCIPAL_METHODS)
    dimensions = np.asarray(
        [METHOD_DIMENSIONS[name] for name in principal], dtype=float
    )

    def arrays(metric: str) -> tuple[np.ndarray, np.ndarray]:
        values, errors = [], []
        for name in principal:
            value, interval = errorbar(methods[name]["metrics"][metric])
            values.append(value)
            errors.append(interval)
        return np.asarray(values), np.asarray(errors).T

    queries, query_errors = arrays("headline_queries")
    shots, shot_errors = arrays("headline_shots")
    success, success_errors = arrays("oracle_scored_success")
    raw_query, raw_query_error = errorbar(
        methods[RAW_METHOD]["metrics"]["headline_queries"]
    )
    raw_shot, raw_shot_error = errorbar(
        methods[RAW_METHOD]["metrics"]["headline_shots"]
    )
    raw_success, raw_success_error = errorbar(
        methods[RAW_METHOD]["metrics"]["oracle_scored_success"]
    )

    figure, axes = plt.subplots(1, 3, figsize=(15.5, 4.8))
    panels = (
        (
            queries,
            query_errors,
            raw_query,
            raw_query_error,
            "Scalar queries",
        ),
        (
            shots / 1e6,
            shot_errors / 1e6,
            raw_shot / 1e6,
            tuple(value / 1e6 for value in raw_shot_error),
            "Shots (millions)",
        ),
        (
            success,
            success_errors,
            raw_success,
            raw_success_error,
            "Oracle-scored target success",
        ),
    )
    for axis, panel in zip(axes, panels, strict=True):
        values, errors, raw_value, raw_errors, ylabel = panel
        axis.errorbar(
            dimensions,
            values,
            yerr=errors,
            marker="o",
            capsize=4,
            color="#245b9e",
            label="Model-informed nested basis",
        )
        axis.errorbar(
            [40.0],
            [raw_value],
            yerr=np.asarray(raw_errors, dtype=float).reshape(2, 1),
            marker="X",
            markersize=9,
            capsize=4,
            color="#b4473d",
            label="Raw-coordinate comparator",
        )
        axis.set_xlabel("Search dimension k")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
    axes[2].axhline(0.75, color="black", linestyle="--", linewidth=1)
    axes[2].set_ylim(0, 1.05)
    axes[0].legend(loc="best", fontsize=8)
    figure.suptitle(
        "Attempt 44 — normalized development truths; "
        f"headline cost: {summary['cost_semantics']['headline']}"
    )
    figure.tight_layout()
    PLOT_MAIN_PNG.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(PLOT_MAIN_PNG, dpi=180, bbox_inches="tight")
    figure.savefig(PLOT_MAIN_SVG, bbox_inches="tight")
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.5))
    oracle_queries, oracle_query_errors = arrays("oracle_first_hit_queries")
    oracle_shots, oracle_shot_errors = arrays("oracle_first_hit_shots")
    raw_oracle_query, raw_oracle_query_error = errorbar(
        methods[RAW_METHOD]["metrics"]["oracle_first_hit_queries"]
    )
    raw_oracle_shot, raw_oracle_shot_error = errorbar(
        methods[RAW_METHOD]["metrics"]["oracle_first_hit_shots"]
    )
    for axis, values, errors, raw_value, raw_errors, ylabel in (
        (
            axes[0],
            oracle_queries,
            oracle_query_errors,
            raw_oracle_query,
            raw_oracle_query_error,
            "Queries to oracle-scored first hit or cap",
        ),
        (
            axes[1],
            oracle_shots / 1e6,
            oracle_shot_errors / 1e6,
            raw_oracle_shot / 1e6,
            tuple(value / 1e6 for value in raw_oracle_shot_error),
            "Shots to oracle-scored first hit or cap (millions)",
        ),
    ):
        axis.errorbar(
            dimensions,
            values,
            yerr=errors,
            marker="o",
            capsize=4,
            color="#6d5ca8",
            label="Model-informed nested basis",
        )
        axis.errorbar(
            [40.0],
            [raw_value],
            yerr=np.asarray(raw_errors, dtype=float).reshape(2, 1),
            marker="X",
            markersize=9,
            capsize=4,
            color="#b4473d",
            label="Raw-coordinate comparator",
        )
        axis.set_xlabel("Search dimension k")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
    axes[0].legend(loc="best", fontsize=8)
    figure.suptitle(
        "Supplementary only — hidden-exact oracle-scored first hit "
        "(not an online stopping rule)"
    )
    figure.tight_layout()
    figure.savefig(PLOT_ORACLE_PNG, dpi=180, bbox_inches="tight")
    figure.savefig(PLOT_ORACLE_SVG, bbox_inches="tight")
    plt.close(figure)


def percent(record: dict[str, Any]) -> str:
    return (
        f"{100 * record['estimate']:.2f}% "
        f"[{100 * record['lower_95']:.2f}%, "
        f"{100 * record['upper_95']:.2f}%]"
    )


def write_report(result: dict[str, Any]) -> None:
    summary = result["summary"]
    methods = summary["methods"]
    rows = []
    for method in METHODS:
        entry = methods[method]
        metrics = entry["metrics"]
        rows.append(
            "| "
            + " | ".join(
                [
                    method,
                    str(entry["search_dimension"]),
                    percent(metrics["oracle_scored_success"]),
                    (
                        f"{metrics['headline_queries']['estimate']:.1f} "
                        f"[{metrics['headline_queries']['lower_95']:.1f}, "
                        f"{metrics['headline_queries']['upper_95']:.1f}]"
                    ),
                    (
                        f"{metrics['headline_shots']['estimate']:.0f} "
                        f"[{metrics['headline_shots']['lower_95']:.0f}, "
                        f"{metrics['headline_shots']['upper_95']:.0f}]"
                    ),
                    f"{100 * entry['destructive_accepted_step_rate']:.2f}%",
                ]
            )
            + " |"
        )
    replay = result["attempt43_evidence"]
    selected = summary["dimension_selection"]
    report = f"""# Attempt 44 — search dimension versus black-box cost

Date: 2026-07-29
Scope: normalized development evidence only
Status: {result["status"]}

## Result

The experiment evaluates 21 normalized truth cells with four nested
finite-shot replicates and paired measurement seeds across six methods. The
independent statistical unit is the truth cell. All intervals below are 95%
stratified truth-cell bootstrap intervals with 20,000 draws.

Headline cost semantics: **{summary["cost_semantics"]["headline"]}**.

| Method | k | Oracle-scored success (95% CI) | Headline queries (95% CI) | Headline shots (95% CI) | Destructive accepted rate |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

Selected method: **{selected["selected_method"]}**; selected dimension:
**{selected["selected_dimension"]}**. Resource-advantage gate versus the
model-informed k=40 reference:
**{selected["selected_resource_advantage_gate_pass"]}**.

## Cost semantics

- `full-cap online` is the executable two-cycle method including both
  sentinels.
- `certified online` stops only at an accepted nonzero proposal whose counted
  validation-proposal binomial count passes the one-sided 99.5%
  Clopper-Pearson bound.
- `oracle-scored first hit` uses hidden exact fidelity after calibration and
  is supplementary, not deployable.

The completed immutable Attempt-43 result rejected the frozen online rule.
Its admissibility decision was
**{replay["gates"]["all_admissibility_gates_pass"]}**; therefore the headline
uses **{replay["headline_cost_semantics"]}** cost. The certification replay
had online true success {percent(replay["summary"]["online_true_success"])},
false early-stop rate {percent(replay["summary"]["false_early_stop_rate"])},
and online-minus-oracle success interval
[{100 * replay["summary"]["online_minus_oracle_success"]["lower_95"]:.2f},
 {100 * replay["summary"]["online_minus_oracle_success"]["upper_95"]:.2f}]
percentage points.

## Geometry and fairness

The model-informed sequence uses signed nominal positive-curvature directions
for rank 15, then a deterministic ascending-raw-coordinate modified
Gram-Schmidt complement. Every model-informed prefix uses the same ridge,
`0.1 * median(top-15 nominal positive curvatures)`. The raw-coordinate
comparator uses the identity basis and nonnegative nominal coordinate Hessian
diagonal, but the same common ridge; it is displayed separately at k=40 and is
not conflated with the completed model-informed k=40 point.

Methods share the same seed within each truth-cell/replicate pair. Every
scalar query and shot is in a service ledger. Every accepted nonzero proposal
stores the integer validation-proposal success count used for online
certification. Exact post-hoc values are attached only after the client is
closed.

## Claim boundary

This is a synthetic finite-shot fidelity oracle on development truths. It is
not hardware, experimental, cesium-specific, or fresh-confirmation evidence.
The success column is explicitly oracle-scored; it does not claim that hidden
truth is available online.

## Artifacts

- Script: `../code/attempt44_dimension_cost.py`
- Frozen protocol: `ATTEMPT44_PROTOCOL.md`
- Frozen config: `../code/attempt44_dimension_cost_config.json`
- Full result: `../results_summary/QL1F-attempt44-dimension-cost.json`
- Main plot: `../plots/attempt44-dimension-cost-development.{{png,svg}}`
- Supplementary oracle-cost plot:
  `../plots/attempt44-oracle-first-hit-supplementary.{{png,svg}}`
"""
    atomic_write_text(REPORT_PATH, report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "full"), required=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace the existing output for the selected mode",
    )
    args = parser.parse_args()

    import jax

    config, attempt35, attempt42, attempt43 = load_inputs()
    constants = frozen_constants(config)
    output = SMOKE_OUTPUT if args.mode == "smoke" else FULL_OUTPUT
    if output.exists() and not args.force:
        raise FileExistsError(
            f"{output} already exists; use --force to replace it"
        )
    model = build_nominal_model()
    geometries, basis_audit, common_ridge = build_search_geometries(
        model, config
    )
    environment = {
        **environment_summary(),
        "platform_request": os.environ["JAX_PLATFORMS"],
    }
    if environment["backend"] != "cpu" or environment["x64"] is not True:
        raise RuntimeError(
            "Attempt 44 requires CPU/float64, got "
            f"backend={environment['backend']} x64={environment['x64']}"
        )
    attempt43_evidence = official_attempt43_evidence(attempt43)
    headline_semantics = "full-cap-online"
    selected_cells = attempt35["selected_cells"]
    if args.mode == "smoke":
        grid = [
            (index, 0, method)
            for index in (0, 7, 15)
            for method in METHODS
        ]
    else:
        grid = [
            (index, replicate, method)
            for index in range(len(selected_cells))
            for replicate in range(
                int(config["benchmark"]["replicates_per_truth_cell"])
            )
            for method in METHODS
        ]
    print(
        f"[attempt44] mode={args.mode} runs={len(grid)} "
        f"headline={headline_semantics}",
        flush=True,
    )
    runs: list[dict[str, Any]] = []
    for grid_index, (selected_index, replicate, method) in enumerate(
        grid, start=1
    ):
        run = run_one(
            selected_cells[selected_index],
            selected_index,
            replicate,
            method,
            model,
            geometries[method],
            common_ridge,
            constants,
            compact=args.mode == "full",
        )
        runs.append(run)
        print(
            f"[attempt44] {grid_index}/{len(grid)} "
            f"{run['selected_cell']} rep={replicate} {method} "
            f"success={run['scan']['oracle_scored_success']}",
            flush=True,
        )

    summary = summarize(runs, config, headline_semantics)
    checks = checks_for(runs, args.mode, geometries, basis_audit)
    status = "complete" if all(checks.values()) else "failed-checks"
    result: dict[str, Any] = {
        "attempt": 44,
        "status": status,
        "mode": args.mode,
        "scope": (
            "normalized development truths only"
            if args.mode == "full"
            else "smoke only; not performance evidence"
        ),
        "protocol": "docs/ATTEMPT44_PROTOCOL.md",
        "config": "code/attempt44_dimension_cost_config.json",
        "environment": environment,
        "nominal_model": {
            "optimizer_summary": model.optimizer_summary,
            "basis_audit": basis_audit,
        },
        "frozen_constants": {
            **constants,
            "common_ridge": common_ridge,
        },
        "source_hash_scheme": "sha256-utf8-lf-v1",
        "source_hashes": source_hashes(),
        "attempt43_evidence": attempt43_evidence,
        "runs": runs,
        "summary": summary,
        "checks": checks,
        "development_evidence": True,
        "confirmation_truths_opened": False,
    }
    serialized_size = len(
        json.dumps(result, sort_keys=True, allow_nan=False).encode("utf-8")
    )
    result["compact_evidence"] = {
        "full_query_rows_retained": args.mode != "full",
        "full_gradient_arrays_retained": args.mode != "full",
        "prettified_json_size_before_artifact_hashes_bytes": serialized_size,
        "repository_size_target_bytes": 15_000_000,
        "within_target_before_artifact_hashes": serialized_size < 15_000_000,
    }
    if args.mode == "full" and serialized_size >= 15_000_000:
        raise RuntimeError(
            f"compact result is still too large: {serialized_size} bytes"
        )
    atomic_write_json(output, result)
    if args.mode == "full" and status == "complete":
        make_plots(summary)
        write_report(result)
        result["artifact_hashes"] = {
            "docs/ATTEMPT44_REPORT.md": canonical_sha256(REPORT_PATH),
            "plots/attempt44-dimension-cost-development.png": binary_sha256(
                PLOT_MAIN_PNG
            ),
            "plots/attempt44-dimension-cost-development.svg": (
                canonical_sha256(PLOT_MAIN_SVG)
            ),
            "plots/attempt44-oracle-first-hit-supplementary.png": (
                binary_sha256(PLOT_ORACLE_PNG)
            ),
            "plots/attempt44-oracle-first-hit-supplementary.svg": (
                canonical_sha256(PLOT_ORACLE_SVG)
            ),
        }
        atomic_write_json(output, result)
    print(
        f"attempt44 {args.mode} {status}; "
        f"selected={summary['dimension_selection']['selected_method']}; "
        f"headline={headline_semantics}",
        flush=True,
    )


if __name__ == "__main__":
    main()
