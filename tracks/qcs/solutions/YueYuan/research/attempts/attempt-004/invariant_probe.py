from __future__ import annotations

import numpy as np

import config
import hessian
import open_loop
import pulses
import systems


CURVATURE_FRACTION_TARGET = 0.95
PHYSICAL_SMOKE_OPEN_LOOP = config.OpenLoopConfig(
    steps=18,
    learning_rate=config.default_smoke_sweep().open_loop.learning_rate,
    target_infidelity=5e-2,
    seed_scale=0.0,
)


def su_dimension(d: int) -> int:
    if d <= 1:
        raise ValueError("d must be greater than 1")
    return int(d * d - 1)


def local_chart_hessian(d: int, flat_extra: int = 0) -> np.ndarray:
    if flat_extra < 0:
        raise ValueError("flat_extra must be non-negative")
    curved = su_dimension(d)
    values = np.concatenate(
        [
            np.ones(curved, dtype=float),
            np.zeros(1 + int(flat_extra), dtype=float),
        ]
    )
    return np.diag(values)


def physical_hessian_rank_row(system_config: config.SystemConfig, seed: int = 0) -> dict:
    system = systems.build_system(system_config)
    start = pulses.initial_pulse(system_config, seed=seed)
    optimized = open_loop.optimize_model_pulse(system, start, PHYSICAL_SMOKE_OPEN_LOOP)
    hess = hessian.dense_hessian(system, optimized.theta)
    eigenvalues = np.linalg.eigvalsh(hess)
    benchmark = su_dimension(system_config.hilbert_dim)
    return {
        "system": system_config.name,
        "hilbert_dim": system_config.hilbert_dim,
        "benchmark_rank": benchmark,
        "observed_curved_rank": hessian.min_k_for_curvature(
            eigenvalues, CURVATURE_FRACTION_TARGET
        ),
        "pulse_dim_or_chart_dim": system_config.raw_dim,
        "evidence_type": "attempt_004_model_hessian_smoke",
        "rank_metric": "k_for_95pct_curvature",
        "curvature_at_benchmark_rank": hessian.curvature_fraction(eigenvalues, benchmark),
        "formal_effective_rank": hessian.effective_rank(eigenvalues),
        "source_seed": seed,
        "open_loop_infidelity": optimized.final_infidelity,
        "caveat": (
            "formal numerical rank can include small curvature tails; "
            "reported rank is the dimension needed for 95 percent model-Hessian curvature"
        ),
    }


def local_chart_rank_row(d: int, flat_extra: int = 32) -> dict:
    hess = local_chart_hessian(d, flat_extra=flat_extra)
    eigenvalues = np.linalg.eigvalsh(hess)
    benchmark = su_dimension(d)
    system_name = {2: "one_qubit_chart", 4: "two_qubit_chart", 8: "three_qubit_chart"}.get(
        d, f"hilbert_{d}_chart"
    )
    return {
        "system": system_name,
        "hilbert_dim": d,
        "benchmark_rank": benchmark,
        "observed_curved_rank": int(np.sum(np.abs(eigenvalues) > 1e-10)),
        "pulse_dim_or_chart_dim": int(hess.shape[0]),
        "evidence_type": "local_unitary_chart",
        "rank_metric": "exact_chart_curved_rank",
        "curvature_at_benchmark_rank": 1.0,
        "formal_effective_rank": int(np.sum(np.abs(eigenvalues) > 1e-10)),
        "source_seed": "",
        "open_loop_infidelity": "",
        "caveat": (
            "sanity probe for the phase-blind local unitary chart, "
            "not a full closed-loop calibration"
        ),
    }


def rank_probe_rows() -> list[dict]:
    return [
        physical_hessian_rank_row(config.ONE_QUBIT_X, seed=0),
        physical_hessian_rank_row(config.TWO_QUBIT_CZ, seed=0),
        local_chart_rank_row(8, flat_extra=32),
    ]
