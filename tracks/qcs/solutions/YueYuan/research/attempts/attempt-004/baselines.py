from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

import device_subspace
from device import AuditEvaluator, QueryOnlyDevice
from hessian import leading_eigenspace
from optimizers import nelder_mead
from pulses import clip_pulse


@dataclass(frozen=True)
class RunRecord:
    method: str
    system: str
    target: str
    hilbert_dim: int
    pulse_dim: int
    k: int
    mismatch: str
    shots_per_query: int
    query_budget: int
    seed: int
    query_count: int
    total_shots: int
    queries_to_target: int | None
    total_shots_to_target: int | None
    final_fidelity: float
    final_infidelity: float
    success: bool
    adaptive_initial_k: int | None = None
    adaptive_final_k: int | None = None
    adaptive_widened: bool | None = None
    device_probe_attempted: bool | None = None
    device_probe_directions_tested: int | None = None
    device_probe_directions_selected: int | None = None
    device_probe_query_count: int | None = None
    device_probe_shot_count: int | None = None

    def to_json(self) -> dict:
        return asdict(self)


def random_subspace(raw_dim: int, k: int, seed: int) -> np.ndarray:
    if k == 0:
        return np.zeros((raw_dim, 0), dtype=float)
    rng = np.random.default_rng(seed)
    q, _ = np.linalg.qr(rng.normal(size=(raw_dim, k)))
    return q[:, :k]


def run_model_only(system, true_system, start_theta, shots: int, seed: int) -> RunRecord:
    oracle = QueryOnlyDevice(true_system, seed=seed)
    oracle.query(start_theta, shots=shots, seed=seed)
    audit = AuditEvaluator(true_system)
    fidelity = audit.exact_fidelity(start_theta)
    infidelity = 1.0 - fidelity
    target = 1e-3
    success = infidelity <= target
    return RunRecord(
        method="model_only",
        system=system.config.name,
        target=system.config.target,
        hilbert_dim=system.config.hilbert_dim,
        pulse_dim=system.config.raw_dim,
        k=0,
        mismatch="recorded_by_runner",
        shots_per_query=shots,
        query_budget=1,
        seed=seed,
        query_count=oracle.query_count,
        total_shots=oracle.shot_count,
        queries_to_target=1 if success else None,
        total_shots_to_target=shots if success else None,
        final_fidelity=fidelity,
        final_infidelity=infidelity,
        success=success,
    )


def run_subspace_method(
    method,
    system,
    true_system,
    start_theta,
    hessian_matrix,
    k: int,
    shots: int,
    seed: int,
    cfg,
) -> RunRecord:
    if method == "full_space_nelder_mead":
        basis = np.eye(system.config.raw_dim)
    elif method == "random_subspace_nelder_mead":
        basis = random_subspace(system.config.raw_dim, k, seed=10_000 + seed)
    elif method == "hessian_subspace_nelder_mead":
        basis = leading_eigenspace(hessian_matrix, k).vectors
    else:
        raise ValueError(f"unknown method: {method}")

    oracle = QueryOnlyDevice(true_system, seed=seed)
    audit = AuditEvaluator(true_system)
    queries_to_target = None
    total_shots_to_target = None

    def objective(coeffs):
        nonlocal queries_to_target, total_shots_to_target
        theta = clip_pulse(start_theta + basis @ coeffs, system.config)
        noisy_infidelity = oracle.query(theta, shots=shots)
        exact_infidelity = audit.exact_infidelity(theta)
        if queries_to_target is None and exact_infidelity <= cfg.target_infidelity:
            queries_to_target = oracle.query_count
            total_shots_to_target = oracle.shot_count
        return noisy_infidelity

    x0 = np.zeros(basis.shape[1], dtype=float)
    result = nelder_mead(
        objective,
        x0,
        step=cfg.initial_step,
        max_queries=cfg.query_budget,
        bounds=(-1.0, 1.0),
    )
    final_theta = clip_pulse(start_theta + basis @ result.best_x, system.config)
    fidelity = audit.exact_fidelity(final_theta)
    infidelity = 1.0 - fidelity
    success = queries_to_target is not None or infidelity <= cfg.target_infidelity
    return RunRecord(
        method=method,
        system=system.config.name,
        target=system.config.target,
        hilbert_dim=system.config.hilbert_dim,
        pulse_dim=system.config.raw_dim,
        k=k,
        mismatch="recorded_by_runner",
        shots_per_query=shots,
        query_budget=cfg.query_budget,
        seed=seed,
        query_count=oracle.query_count,
        total_shots=oracle.shot_count,
        queries_to_target=queries_to_target,
        total_shots_to_target=total_shots_to_target,
        final_fidelity=fidelity,
        final_infidelity=infidelity,
        success=success,
    )


def run_adaptive_hessian_method(
    system,
    true_system,
    start_theta,
    hessian_matrix,
    initial_k: int,
    max_k: int,
    shots: int,
    seed: int,
    cfg,
) -> RunRecord:
    initial_k = min(max(0, int(initial_k)), system.config.raw_dim)
    max_k = min(max(initial_k, int(max_k)), system.config.raw_dim)
    initial_basis = leading_eigenspace(hessian_matrix, initial_k).vectors
    max_basis = leading_eigenspace(hessian_matrix, max_k).vectors
    oracle = QueryOnlyDevice(true_system, seed=seed)
    audit = AuditEvaluator(true_system)
    queries_to_target = None
    total_shots_to_target = None

    def make_objective(basis):
        def objective(coeffs):
            nonlocal queries_to_target, total_shots_to_target
            theta = clip_pulse(start_theta + basis @ coeffs, system.config)
            noisy_infidelity = oracle.query(theta, shots=shots)
            exact_infidelity = audit.exact_infidelity(theta)
            if queries_to_target is None and exact_infidelity <= cfg.target_infidelity:
                queries_to_target = oracle.query_count
                total_shots_to_target = oracle.shot_count
            return noisy_infidelity

        return objective

    first_budget = max(1, cfg.query_budget // 2)
    first = nelder_mead(
        make_objective(initial_basis),
        np.zeros(initial_k, dtype=float),
        step=cfg.initial_step,
        max_queries=first_budget,
        bounds=(-1.0, 1.0),
    )
    widened = (
        max_k > initial_k
        and first.best_value > 0.0
        and oracle.query_count < cfg.query_budget
    )
    final_basis = initial_basis
    final_x = first.best_x
    final_k = initial_k

    if widened:
        final_basis = max_basis
        final_k = max_k
        padded = np.zeros(max_k, dtype=float)
        padded[: initial_k] = first.best_x
        second = nelder_mead(
            make_objective(max_basis),
            padded,
            step=cfg.initial_step,
            max_queries=cfg.query_budget - oracle.query_count,
            bounds=(-1.0, 1.0),
        )
        final_x = second.best_x

    final_theta = clip_pulse(start_theta + final_basis @ final_x, system.config)
    fidelity = audit.exact_fidelity(final_theta)
    infidelity = 1.0 - fidelity
    success = queries_to_target is not None or infidelity <= cfg.target_infidelity
    return RunRecord(
        method="adaptive_hessian_subspace_nelder_mead",
        system=system.config.name,
        target=system.config.target,
        hilbert_dim=system.config.hilbert_dim,
        pulse_dim=system.config.raw_dim,
        k=max_k,
        mismatch="recorded_by_runner",
        shots_per_query=shots,
        query_budget=cfg.query_budget,
        seed=seed,
        query_count=oracle.query_count,
        total_shots=oracle.shot_count,
        queries_to_target=queries_to_target,
        total_shots_to_target=total_shots_to_target,
        final_fidelity=fidelity,
        final_infidelity=infidelity,
        success=success,
        adaptive_initial_k=initial_k,
        adaptive_final_k=final_k,
        adaptive_widened=widened,
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


def run_device_informed_adaptive_hessian_method(
    system,
    true_system,
    start_theta,
    hessian_matrix,
    initial_k: int,
    max_k: int,
    shots: int,
    seed: int,
    cfg,
    probe_cfg=None,
) -> RunRecord:
    initial_k = min(max(0, int(initial_k)), system.config.raw_dim)
    max_k = min(max(initial_k, int(max_k)), system.config.raw_dim)
    initial_basis = leading_eigenspace(hessian_matrix, initial_k).vectors
    oracle = QueryOnlyDevice(true_system, seed=seed)
    audit = AuditEvaluator(true_system)
    queries_to_target = None
    total_shots_to_target = None

    def note_query(theta):
        nonlocal queries_to_target, total_shots_to_target
        exact_infidelity = audit.exact_infidelity(theta)
        if queries_to_target is None and exact_infidelity <= cfg.target_infidelity:
            queries_to_target = oracle.query_count
            total_shots_to_target = oracle.shot_count

    def make_objective(basis):
        def objective(coeffs):
            theta = clip_pulse(start_theta + basis @ coeffs, system.config)
            noisy_infidelity = oracle.query(theta, shots=shots)
            note_query(theta)
            return noisy_infidelity

        return objective

    pilot_budget = min(cfg.query_budget, max(initial_k + 2, cfg.query_budget // 3))
    first = nelder_mead(
        make_objective(initial_basis),
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
        system,
        initial_k,
        max_k,
        remaining,
        cfg,
        probe_cfg,
    )
    if (
        first.best_value > 0.0
        and affordable_probe is not None
        and oracle.query_count < cfg.query_budget
    ):
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
            on_query=note_query,
        )
        if probe_result.selected_count:
            final_basis = np.column_stack([initial_basis, probe_result.basis])
            final_x = np.zeros(final_basis.shape[1], dtype=float)
            final_x[: first.best_x.size] = first.best_x

    if oracle.query_count < cfg.query_budget and final_basis.shape[1]:
        second = nelder_mead(
            make_objective(final_basis),
            final_x,
            step=cfg.initial_step,
            max_queries=cfg.query_budget - oracle.query_count,
            bounds=(-1.0, 1.0),
        )
        final_x = second.best_x

    final_theta = clip_pulse(start_theta + final_basis @ final_x, system.config)
    fidelity = audit.exact_fidelity(final_theta)
    infidelity = 1.0 - fidelity
    success = queries_to_target is not None or infidelity <= cfg.target_infidelity
    return RunRecord(
        method="device_informed_adaptive_hessian_nelder_mead",
        system=system.config.name,
        target=system.config.target,
        hilbert_dim=system.config.hilbert_dim,
        pulse_dim=system.config.raw_dim,
        k=final_basis.shape[1],
        mismatch="recorded_by_runner",
        shots_per_query=shots,
        query_budget=cfg.query_budget,
        seed=seed,
        query_count=oracle.query_count,
        total_shots=oracle.shot_count,
        queries_to_target=queries_to_target,
        total_shots_to_target=total_shots_to_target,
        final_fidelity=fidelity,
        final_infidelity=infidelity,
        success=success,
        adaptive_initial_k=initial_k,
        adaptive_final_k=final_basis.shape[1],
        adaptive_widened=bool(final_basis.shape[1] > initial_k),
        device_probe_attempted=probe_attempted,
        device_probe_directions_tested=(
            int(probe_result.metadata["direction_count"]) if probe_result else 0
        ),
        device_probe_directions_selected=(
            int(probe_result.selected_count) if probe_result else 0
        ),
        device_probe_query_count=int(probe_result.query_count) if probe_result else 0,
        device_probe_shot_count=int(probe_result.shot_count) if probe_result else 0,
    )
