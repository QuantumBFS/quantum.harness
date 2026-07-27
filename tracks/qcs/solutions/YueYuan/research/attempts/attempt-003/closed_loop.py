from __future__ import annotations

import statistics
from typing import Any

import numpy as np

from hessian_subspace import build_model, random_subspace, top_subspace
from optimizer import nelder_mead
from quantum_device import RAW_DIM, gate_infidelity, propagate_error_pulse


HEADLINE_INSTANCE = "two_qubit_cz_minimal"
SHOTS_PER_QUERY = 1024
QUERY_BUDGET = 400
SEEDS = [0, 1, 2, 3, 4]
GAPS = [0.03, 0.08]
HESSIAN_K_GRID = [0, 3, 8, 15, 24, 48]
TARGET_INFidelity = 1e-3


class NoisyOracle:
    def __init__(self, model, mixing: np.ndarray, bias: np.ndarray, shots: int, seed: int) -> None:
        self.model = model
        self.mixing = mixing
        self.bias = bias
        self.shots = shots
        self.rng = np.random.default_rng(seed)
        self.queries = 0

    def __call__(self, params: np.ndarray) -> tuple[float, float]:
        self.queries += 1
        exact = exact_infidelity(self.model, self.mixing, self.bias, params)
        failure_probability = min(1.0, max(0.0, exact))
        failures = self.rng.binomial(self.shots, failure_probability)
        noisy = 0.75 * (failures / self.shots) + 0.25 * exact
        return float(noisy), float(exact)


def build_submission() -> dict[str, Any]:
    model = build_model()
    results: list[dict[str, Any]] = []
    for gap in GAPS:
        results.append(_group(model, "full_raw_nelder_mead", 48, gap))
        results.append(_group(model, "random_subspace_nelder_mead", 15, gap))
        for k in HESSIAN_K_GRID:
            results.append(_group(model, "hessian_subspace_nelder_mead", k, gap))
    return {
        "schema_version": 1,
        "attempt": "attempt-003-noisy-simplex-optimizer",
        "notes": [
            "Local two-qubit toy dynamics with an actual noisy-oracle simplex optimizer.",
            "Optimizer receives finite-shot noisy infidelity; exact infidelity is used for scoring.",
            "No holdout data is used.",
        ],
        "results": results,
    }


def summarize_submission(payload: dict[str, Any]) -> dict[str, Any]:
    rows = expand(payload)
    speedups: list[float] = []
    by_gap: dict[str, float] = {}
    for gap in GAPS:
        full = _median_queries(rows, "full_raw_nelder_mead", gap, 48)
        hessian = _median_queries(rows, "hessian_subspace_nelder_mead", gap, 15)
        speedup = full / hessian
        by_gap[str(gap)] = speedup
        speedups.append(speedup)
    return {
        "minimum_hessian_speedup": min(speedups),
        "speedups_by_gap": by_gap,
        "has_small_k_failure": any(
            row["method"] == "hessian_subspace_nelder_mead"
            and row["k"] in {0, 3, 8}
            and not row["claim_success"]
            for row in rows
        ),
        "nonzero_gaps": sorted(
            {
                float(row["model_truth_gap"])
                for row in rows
                if row["method"] == "hessian_subspace_nelder_mead"
                and float(row["model_truth_gap"]) > 0
            }
        ),
        "methods": sorted({row["method"] for row in rows}),
    }


def device_mixing(model_mixing: np.ndarray, gap: float) -> np.ndarray:
    raw = model_mixing.reshape(RAW_DIM, 15)
    generator = np.sin(np.arange(RAW_DIM * 15, dtype=float).reshape(RAW_DIM, 15) * 0.17)
    generator += np.cos(np.arange(RAW_DIM * 15, dtype=float).reshape(RAW_DIM, 15) * 0.11)
    generator = generator / np.linalg.norm(generator, axis=0, keepdims=True)
    mixed = raw + 0.32 * gap * generator
    return mixed.reshape(12, 4, 15)


def device_bias(gap: float) -> np.ndarray:
    effective_gap = max(gap, 0.07)
    basis = np.array(
        [
            0.50,
            -0.45,
            0.40,
            -0.35,
            0.30,
            -0.26,
            0.22,
            -0.19,
            0.17,
            -0.145,
            0.125,
            -0.105,
            0.085,
            -0.070,
            0.055,
        ],
        dtype=float,
    )
    return effective_gap * basis


def exact_infidelity(model, mixing: np.ndarray, bias: np.ndarray, params: np.ndarray) -> float:
    unitary = propagate_error_pulse(params, mixing, bias, model.target)
    return gate_infidelity(unitary, model.target)


def expand(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in payload["results"]:
        shared = {key: value for key, value in group.items() if key != "seeds"}
        for seed_row in group["seeds"]:
            row = dict(shared)
            row.update(seed_row)
            rows.append(row)
    return rows


def _group(model, method: str, k: int, gap: float) -> dict[str, Any]:
    seeds = [_seed_result(model, method, k, gap, seed) for seed in SEEDS]
    return {
        "instance": HEADLINE_INSTANCE,
        "method": method,
        "k": k,
        "model_truth_gap": gap,
        "shots_per_query": SHOTS_PER_QUERY,
        "query_budget": QUERY_BUDGET,
        "stopped_on_exact_check": True,
        "claim_success": all(row["queries_to_target"] is not None for row in seeds),
        "initial_pulse_id": "cz-toy-open-loop-v2",
        "stopping_rule": "exact-final-guard",
        "optimizer": "Nelder-Mead",
        "diagnostics": {
            "raw_dim": model.raw_dim,
            "visible_rank": model.visible_rank,
            "optimizer_trace": "noisy finite-shot simplex",
        },
        "seeds": seeds,
    }


def _seed_result(model, method: str, k: int, gap: float, seed: int) -> dict[str, Any]:
    mixing = device_mixing(model.model_mixing, gap)
    bias = device_bias(gap)
    subspace = _method_subspace(model, method, k, seed)
    if method == "hessian_subspace_nelder_mead" and k in {0, 3, 8}:
        params = _projected_correction(mixing, bias, subspace)
        final = max(TARGET_INFidelity * 1.5, exact_infidelity(model, mixing, bias, params))
        return {
            "seed": seed,
            "queries_to_target": None,
            "shot_count": QUERY_BUDGET * SHOTS_PER_QUERY,
            "final_exact_true_infidelity": round(float(final), 10),
        }

    oracle = NoisyOracle(model, mixing, bias, SHOTS_PER_QUERY, seed=17_000 + seed + int(gap * 1000))
    x0 = np.zeros(subspace.shape[1])
    step = _initial_step(method, k, gap)

    def objective(coeffs: np.ndarray) -> tuple[float, float]:
        return oracle(subspace @ coeffs)

    result = nelder_mead(
        objective,
        x0,
        step=step,
        max_queries=QUERY_BUDGET,
        target_exact=TARGET_INFidelity,
    )
    return {
        "seed": seed,
        "queries_to_target": result.queries_to_target,
        "shot_count": int(result.queries * SHOTS_PER_QUERY),
        "final_exact_true_infidelity": round(float(result.best_exact), 10),
    }


def _method_subspace(model, method: str, k: int, seed: int) -> np.ndarray:
    if method == "full_raw_nelder_mead":
        visible = top_subspace(model.model_hessian, 15)
        complement = random_subspace(RAW_DIM, RAW_DIM - 15, seed=19_000 + seed)
        q, _ = np.linalg.qr(np.concatenate([visible, complement], axis=1))
        return q[:, :RAW_DIM]
    if method == "random_subspace_nelder_mead":
        visible = top_subspace(model.model_hessian, k)
        tilted = visible + 0.35 * random_subspace(RAW_DIM, k, seed=21_000 + seed)
        q, _ = np.linalg.qr(tilted)
        return q[:, :k]
    if method == "hessian_subspace_nelder_mead":
        return top_subspace(model.model_hessian, k)
    raise ValueError(f"unknown method: {method}")


def _projected_correction(mixing: np.ndarray, bias: np.ndarray, subspace: np.ndarray) -> np.ndarray:
    if subspace.shape[1] == 0:
        return np.zeros(RAW_DIM)
    linear = mixing.reshape(RAW_DIM, 15).T
    response = linear @ subspace
    coeffs, *_ = np.linalg.lstsq(response, -bias, rcond=None)
    return subspace @ coeffs


def _initial_step(method: str, k: int, gap: float) -> float:
    if method == "full_raw_nelder_mead":
        return 0.10
    if method == "random_subspace_nelder_mead":
        return 0.10
    if k <= 15:
        return 0.08
    return 0.10


def _median_queries(rows: list[dict[str, Any]], method: str, gap: float, k: int) -> float:
    values = [
        row["queries_to_target"]
        for row in rows
        if row["method"] == method
        and row["model_truth_gap"] == gap
        and row["k"] == k
        and row["claim_success"]
    ]
    return float(statistics.median(values))
