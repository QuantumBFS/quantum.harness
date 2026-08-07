from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import device_subspace
from baselines import RunRecord, random_subspace
from device import AuditEvaluator
from hessian import leading_eigenspace
from optimizers import nelder_mead
from pulses import clip_pulse


@dataclass(frozen=True)
class QueryTranscriptEntry:
    query_index: int
    shots: int
    total_shots: int
    pulse_parameters: np.ndarray
    noisy_infidelity: float


@dataclass(frozen=True)
class SealedRunResult:
    method: str
    final_theta: np.ndarray
    k: int
    query_count: int
    shot_count: int
    transcript: tuple[QueryTranscriptEntry, ...]
    metadata: dict


class RecordingQueryOracle:
    def __init__(self, oracle) -> None:
        self._oracle = oracle
        self._transcript: list[QueryTranscriptEntry] = []

    @property
    def query_count(self) -> int:
        return int(self._oracle.query_count)

    @property
    def shot_count(self) -> int:
        return int(self._oracle.shot_count)

    @property
    def transcript(self) -> tuple[QueryTranscriptEntry, ...]:
        return tuple(self._transcript)

    def query(self, pulse_parameters, shots: int, seed: int | None = None) -> float:
        value = float(self._oracle.query(pulse_parameters, shots=shots, seed=seed))
        self._transcript.append(
            QueryTranscriptEntry(
                query_index=self.query_count,
                shots=int(shots),
                total_shots=self.shot_count,
                pulse_parameters=np.asarray(pulse_parameters, dtype=float).copy(),
                noisy_infidelity=value,
            )
        )
        return value


def _basis_for_method(method: str, system, hessian_matrix, k: int, seed: int) -> np.ndarray:
    if method == "full_space_nelder_mead":
        return np.eye(system.config.raw_dim)
    if method == "random_subspace_nelder_mead":
        return random_subspace(system.config.raw_dim, k, seed=10_000 + seed)
    if method == "hessian_subspace_nelder_mead":
        return leading_eigenspace(hessian_matrix, k).vectors
    raise ValueError(f"unknown sealed method: {method}")


def run_sealed_subspace_method(
    method: str,
    system,
    oracle,
    start_theta,
    hessian_matrix,
    k: int,
    shots: int,
    seed: int,
    cfg,
) -> SealedRunResult:
    basis = _basis_for_method(method, system, hessian_matrix, k, seed)

    def objective(coeffs):
        theta = clip_pulse(start_theta + basis @ coeffs, system.config)
        return oracle.query(theta, shots=shots)

    result = nelder_mead(
        objective,
        np.zeros(basis.shape[1], dtype=float),
        step=cfg.initial_step,
        max_queries=cfg.query_budget,
        bounds=(-1.0, 1.0),
    )
    final_theta = clip_pulse(start_theta + basis @ result.best_x, system.config)
    return SealedRunResult(
        method=method,
        final_theta=final_theta,
        k=basis.shape[1],
        query_count=int(oracle.query_count),
        shot_count=int(oracle.shot_count),
        transcript=tuple(oracle.transcript),
        metadata={},
    )


def _affordable_probe_config(
    system,
    initial_k: int,
    max_k: int,
    remaining_queries: int,
    cfg,
    probe_cfg,
):
    default = probe_cfg or device_subspace.ProbeConfig(
        direction_count=min(8, max(0, system.config.raw_dim - initial_k)),
        append_count=min(4, max(0, max_k - initial_k)),
        step=max(0.02, 0.5 * cfg.initial_step),
        repeats=1,
        min_positive_curvature=0.0,
    )
    if default.append_count <= 0 or remaining_queries <= 4:
        return None
    max_directions = max(0, (remaining_queries - 3) // (2 * default.repeats))
    direction_count = min(default.direction_count, max_directions)
    if direction_count <= 0:
        return None
    return device_subspace.ProbeConfig(
        direction_count=direction_count,
        append_count=min(default.append_count, max_k - initial_k, direction_count),
        step=default.step,
        repeats=default.repeats,
        min_positive_curvature=default.min_positive_curvature,
    )


def run_sealed_adaptive_hessian_method(
    system,
    oracle,
    start_theta,
    hessian_matrix,
    initial_k: int,
    max_k: int,
    shots: int,
    seed: int,
    cfg,
) -> SealedRunResult:
    initial_k = min(max(0, int(initial_k)), system.config.raw_dim)
    max_k = min(max(initial_k, int(max_k)), system.config.raw_dim)
    initial_basis = leading_eigenspace(hessian_matrix, initial_k).vectors
    max_basis = leading_eigenspace(hessian_matrix, max_k).vectors

    def objective_for(basis):
        def objective(coeffs):
            theta = clip_pulse(start_theta + basis @ coeffs, system.config)
            return oracle.query(theta, shots=shots)

        return objective

    first_budget = max(1, cfg.query_budget // 2)
    first = nelder_mead(
        objective_for(initial_basis),
        np.zeros(initial_k, dtype=float),
        step=cfg.initial_step,
        max_queries=first_budget,
        bounds=(-1.0, 1.0),
    )
    widened = max_k > initial_k and first.best_value > 0.0 and oracle.query_count < cfg.query_budget
    final_basis = initial_basis
    final_x = first.best_x
    final_k = initial_k
    if widened:
        final_basis = max_basis
        final_k = max_k
        padded = np.zeros(max_k, dtype=float)
        padded[: initial_k] = first.best_x
        second = nelder_mead(
            objective_for(max_basis),
            padded,
            step=cfg.initial_step,
            max_queries=cfg.query_budget - oracle.query_count,
            bounds=(-1.0, 1.0),
        )
        final_x = second.best_x
    final_theta = clip_pulse(start_theta + final_basis @ final_x, system.config)
    return SealedRunResult(
        method="adaptive_hessian_subspace_nelder_mead",
        final_theta=final_theta,
        k=final_k,
        query_count=int(oracle.query_count),
        shot_count=int(oracle.shot_count),
        transcript=tuple(oracle.transcript),
        metadata={
            "adaptive_initial_k": initial_k,
            "adaptive_final_k": final_k,
            "adaptive_widened": widened,
        },
    )


def run_sealed_device_informed_adaptive_hessian_method(
    system,
    oracle,
    start_theta,
    hessian_matrix,
    initial_k: int,
    max_k: int,
    shots: int,
    seed: int,
    cfg,
    probe_cfg=None,
) -> SealedRunResult:
    initial_k = min(max(0, int(initial_k)), system.config.raw_dim)
    max_k = min(max(initial_k, int(max_k)), system.config.raw_dim)
    initial_basis = leading_eigenspace(hessian_matrix, initial_k).vectors

    def objective_for(basis):
        def objective(coeffs):
            theta = clip_pulse(start_theta + basis @ coeffs, system.config)
            return oracle.query(theta, shots=shots)

        return objective

    pilot_budget = min(cfg.query_budget, max(initial_k + 2, cfg.query_budget // 3))
    first = nelder_mead(
        objective_for(initial_basis),
        np.zeros(initial_k, dtype=float),
        step=cfg.initial_step,
        max_queries=pilot_budget,
        bounds=(-1.0, 1.0),
    )
    probe_attempted = False
    probe_result = None
    final_basis = initial_basis
    final_x = first.best_x
    remaining = cfg.query_budget - oracle.query_count
    affordable_probe = _affordable_probe_config(
        system, initial_k, max_k, remaining, cfg, probe_cfg
    )
    if first.best_value > 0.0 and affordable_probe is not None and oracle.query_count < cfg.query_budget:
        probe_attempted = True
        center_theta = clip_pulse(start_theta + initial_basis @ first.best_x, system.config)
        probe_result = device_subspace.estimate_device_subspace(
            oracle,
            system.config,
            center_theta,
            initial_basis,
            shots=shots,
            seed=50_000 + seed,
            cfg=affordable_probe,
        )
        if probe_result.selected_count:
            final_basis = np.column_stack([initial_basis, probe_result.basis])
            final_x = np.zeros(final_basis.shape[1], dtype=float)
            final_x[: first.best_x.size] = first.best_x
    if oracle.query_count < cfg.query_budget and final_basis.shape[1]:
        second = nelder_mead(
            objective_for(final_basis),
            final_x,
            step=cfg.initial_step,
            max_queries=cfg.query_budget - oracle.query_count,
            bounds=(-1.0, 1.0),
        )
        final_x = second.best_x
    final_theta = clip_pulse(start_theta + final_basis @ final_x, system.config)
    return SealedRunResult(
        method="device_informed_adaptive_hessian_nelder_mead",
        final_theta=final_theta,
        k=final_basis.shape[1],
        query_count=int(oracle.query_count),
        shot_count=int(oracle.shot_count),
        transcript=tuple(oracle.transcript),
        metadata={
            "adaptive_initial_k": initial_k,
            "adaptive_final_k": final_basis.shape[1],
            "adaptive_widened": bool(final_basis.shape[1] > initial_k),
            "device_probe_attempted": probe_attempted,
            "device_probe_directions_tested": (
                int(probe_result.metadata["direction_count"]) if probe_result else 0
            ),
            "device_probe_directions_selected": (
                int(probe_result.selected_count) if probe_result else 0
            ),
            "device_probe_query_count": int(probe_result.query_count) if probe_result else 0,
            "device_probe_shot_count": int(probe_result.shot_count) if probe_result else 0,
        },
    )


def score_sealed_run(
    system,
    sealed_result: SealedRunResult,
    true_system,
    shots: int,
    query_budget: int,
    seed: int,
    target_infidelity: float,
    mismatch: str,
    pulse_transform=None,
) -> RunRecord:
    audit = AuditEvaluator(true_system)

    def scored_pulse(theta):
        if pulse_transform is None:
            return theta
        return pulse_transform(theta)

    queries_to_target = None
    total_shots_to_target = None
    for entry in sealed_result.transcript:
        exact_infidelity = audit.exact_infidelity(scored_pulse(entry.pulse_parameters))
        if queries_to_target is None and exact_infidelity <= target_infidelity:
            queries_to_target = entry.query_index
            total_shots_to_target = entry.total_shots
            break
    final_fidelity = audit.exact_fidelity(scored_pulse(sealed_result.final_theta))
    final_infidelity = 1.0 - final_fidelity
    success = queries_to_target is not None or final_infidelity <= target_infidelity
    metadata = dict(sealed_result.metadata)
    return RunRecord(
        method=sealed_result.method,
        system=system.config.name,
        target=system.config.target,
        hilbert_dim=system.config.hilbert_dim,
        pulse_dim=system.config.raw_dim,
        k=sealed_result.k,
        mismatch=mismatch,
        shots_per_query=shots,
        query_budget=query_budget,
        seed=seed,
        query_count=sealed_result.query_count,
        total_shots=sealed_result.shot_count,
        queries_to_target=queries_to_target,
        total_shots_to_target=total_shots_to_target,
        final_fidelity=final_fidelity,
        final_infidelity=final_infidelity,
        success=success,
        adaptive_initial_k=metadata.get("adaptive_initial_k"),
        adaptive_final_k=metadata.get("adaptive_final_k"),
        adaptive_widened=metadata.get("adaptive_widened"),
        device_probe_attempted=metadata.get("device_probe_attempted"),
        device_probe_directions_tested=metadata.get("device_probe_directions_tested"),
        device_probe_directions_selected=metadata.get("device_probe_directions_selected"),
        device_probe_query_count=metadata.get("device_probe_query_count"),
        device_probe_shot_count=metadata.get("device_probe_shot_count"),
    )
