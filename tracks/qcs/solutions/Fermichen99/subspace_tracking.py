"""Rank-preserving device-side tracking of an active control subspace.

The optimizer always searches in exactly ``k`` coordinates.  A small set of
orthogonal scout directions is used only to estimate how the local curvature
has rotated; after the estimate, the candidate space is compressed back to
rank ``k``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from optimizers import (
    ClosedLoopResult,
    _closed_loop_summary,
    optimize_black_box_scipy,
)
from sim_to_real import BlackBoxDevice


@dataclass(frozen=True)
class SubspaceUpdate:
    basis: np.ndarray
    curvatures: np.ndarray
    restricted_hessian: np.ndarray
    scouts: np.ndarray
    queries: int
    rotation_frobenius: float


@dataclass(frozen=True)
class TrackingStage:
    stage: int
    optimization_queries: int
    confirmation_queries: int
    reported_infidelity: float
    reported_upper_bound: float
    confirmed: bool
    update_queries: int
    rotation_frobenius: float | None


@dataclass(frozen=True)
class RankPreservingResult:
    summary: ClosedLoopResult
    final_origin: np.ndarray
    final_basis: np.ndarray
    final_curvatures: np.ndarray
    stages: tuple[TrackingStage, ...]
    message: str


def _orthonormal_scouts(
    basis: np.ndarray,
    count: int,
    *,
    seed: int,
) -> np.ndarray:
    ambient, rank = basis.shape
    if count <= 0 or count > ambient - rank:
        raise ValueError("invalid scout count")
    rng = np.random.default_rng(seed)
    candidates = rng.normal(size=(ambient, count + rank))
    coefficients = np.einsum(
        "ik,ij->kj", basis, candidates, optimize=False
    )
    candidates -= np.einsum(
        "ik,kj->ij", basis, coefficients, optimize=False
    )
    scouts, _ = np.linalg.qr(candidates)
    return scouts[:, :count]


def _subspace_projector_distance(
    left: np.ndarray,
    right: np.ndarray,
) -> float:
    left_projector = np.einsum(
        "ik,jk->ij", left, left, optimize=False
    )
    right_projector = np.einsum(
        "ik,jk->ij", right, right, optimize=False
    )
    return float(np.linalg.norm(left_projector - right_projector))


def cross_block_query_cost(
    rank: int,
    scout_count: int,
    *,
    center_repeats: int,
) -> int:
    """Return the exact query cost of one cross-block curvature update."""

    if rank <= 0 or scout_count <= 0 or center_repeats <= 0:
        raise ValueError("rank, scout_count, and center_repeats must be positive")
    return center_repeats + 2 * (rank + scout_count) + 4 * rank * scout_count


def estimate_cross_block_rotation(
    device: BlackBoxDevice,
    origin: np.ndarray,
    basis: np.ndarray,
    prior_curvatures: np.ndarray,
    *,
    scout_count: int = 3,
    finite_difference_step: float = 0.4,
    center_repeats: int = 4,
    diagonal_blend: float = 0.5,
    cross_shrink: float = 0.2,
    seed: int = 0,
) -> SubspaceUpdate:
    """Rotate a rank-k basis from targeted current/scout cross curvatures.

    The model basis supplies a strong structural prior: its restricted Hessian
    is approximately diagonal. Device queries therefore estimate only the
    diagonal curvatures and the k-by-r coupling block to temporary scouts,
    instead of fitting all O((k+r)^2) Hessian entries from an underdetermined
    random sketch. The returned basis is compressed back to exactly rank k.
    """

    origin = np.asarray(origin, dtype=np.float64)
    basis = np.asarray(basis, dtype=np.float64)
    prior_curvatures = np.asarray(prior_curvatures, dtype=np.float64)
    if basis.ndim != 2 or basis.shape[0] != origin.size:
        raise ValueError("basis shape does not match origin")
    rank = basis.shape[1]
    if prior_curvatures.shape != (rank,):
        raise ValueError("prior_curvatures must have one value per basis column")
    if finite_difference_step <= 0.0 or center_repeats <= 0:
        raise ValueError("finite-difference step and repeats must be positive")
    if not 0.0 <= diagonal_blend <= 1.0:
        raise ValueError("diagonal_blend must lie in [0, 1]")
    if not 0.0 <= cross_shrink <= 1.0:
        raise ValueError("cross_shrink must lie in [0, 1]")

    query_start = device.query_count
    scouts = _orthonormal_scouts(basis, scout_count, seed=seed)
    center_loss = float(
        np.mean([device.query(origin) for _ in range(center_repeats)])
    )
    step = finite_difference_step

    diagonal = np.empty(rank + scout_count, dtype=np.float64)
    candidate = np.column_stack([basis, scouts])
    for index in range(rank + scout_count):
        direction = candidate[:, index]
        plus = device.query(origin + step * direction)
        minus = device.query(origin - step * direction)
        diagonal[index] = (plus + minus - 2.0 * center_loss) / step**2

    positive_prior = np.maximum(prior_curvatures, 1e-12)
    active_diagonal = (
        (1.0 - diagonal_blend) * positive_prior
        + diagonal_blend * np.maximum(diagonal[:rank], 0.0)
    )
    scout_floor = max(
        float(np.min(active_diagonal)) * 0.02,
        float(np.max(active_diagonal)) * 1e-8,
    )
    scout_diagonal = np.maximum(diagonal[rank:], scout_floor)

    cross = np.empty((scout_count, rank), dtype=np.float64)
    scale = 4.0 * step**2
    for scout_index in range(scout_count):
        scout = scouts[:, scout_index]
        for active_index in range(rank):
            active = basis[:, active_index]
            plus_plus = device.query(origin + step * (active + scout))
            plus_minus = device.query(origin + step * (active - scout))
            minus_plus = device.query(origin + step * (-active + scout))
            minus_minus = device.query(origin - step * (active + scout))
            cross[scout_index, active_index] = (
                plus_plus - plus_minus - minus_plus + minus_minus
            ) / scale

    restricted_hessian = np.zeros(
        (rank + scout_count, rank + scout_count), dtype=np.float64
    )
    restricted_hessian[:rank, :rank] = np.diag(active_diagonal)
    restricted_hessian[rank:, rank:] = np.diag(scout_diagonal)
    restricted_hessian[rank:, :rank] = cross_shrink * cross
    restricted_hessian[:rank, rank:] = cross_shrink * cross.T

    eigenvalues, eigenvectors = np.linalg.eigh(restricted_hessian)
    order = np.argsort(eigenvalues)[::-1]
    selected = order[:rank]
    rotated_basis = candidate @ eigenvectors[:, selected]
    rotated_basis, _ = np.linalg.qr(rotated_basis)
    curvatures = np.maximum(eigenvalues[selected], 1e-12)
    return SubspaceUpdate(
        basis=rotated_basis[:, :rank],
        curvatures=curvatures,
        restricted_hessian=restricted_hessian,
        scouts=scouts,
        queries=device.query_count - query_start,
        rotation_frobenius=_subspace_projector_distance(
            basis, rotated_basis[:, :rank]
        ),
    )


def _wilson_upper_bound(
    infidelity: float,
    trials: int,
    *,
    z_score: float,
) -> float:
    if trials <= 0:
        return infidelity
    probability = float(np.clip(infidelity, 0.0, 1.0))
    denominator = 1.0 + z_score**2 / trials
    center = (
        probability + z_score**2 / (2.0 * trials)
    ) / denominator
    margin = (
        z_score
        * np.sqrt(
            probability * (1.0 - probability) / trials
            + z_score**2 / (4.0 * trials**2)
        )
        / denominator
    )
    return float(center + margin)


def optimize_rank_preserving(
    device: BlackBoxDevice,
    origin: np.ndarray,
    basis: np.ndarray,
    prior_curvatures: np.ndarray,
    *,
    stage_query_budgets: Sequence[int] = (200, 200, 272),
    max_total_queries: int = 1000,
    target_infidelity: float = 1e-3,
    scout_count: int = 2,
    finite_difference_step: float = 0.4,
    center_repeats: int = 4,
    confirmation_queries: int = 4,
    confirmation_z_score: float = 1.64,
    diagonal_blend: float = 0.5,
    cross_shrink: float = 0.2,
    seed: int = 0,
) -> RankPreservingResult:
    """Closed-loop calibration with a fixed-rank, rotating search basis."""

    if device.query_count:
        raise ValueError("device history must be empty at optimizer start")
    if not stage_query_budgets or any(
        budget <= 0 for budget in stage_query_budgets
    ):
        raise ValueError("stage query budgets must be positive")
    if max_total_queries <= 0 or confirmation_queries <= 0:
        raise ValueError("query budgets must be positive")

    current_origin = np.asarray(origin, dtype=np.float64)
    current_basis = np.asarray(basis, dtype=np.float64)
    current_curvatures = np.asarray(
        prior_curvatures, dtype=np.float64
    )
    stages: list[TrackingStage] = []
    message = "all rank-preserving stages completed"

    for stage_index, requested_budget in enumerate(stage_query_budgets):
        remaining = max_total_queries - device.query_count
        if remaining <= confirmation_queries:
            message = "total query budget exhausted before optimization"
            break
        stage_budget = min(
            requested_budget,
            remaining - confirmation_queries,
        )
        evaluation_repeats = (
            2 if stage_index == len(stage_query_budgets) - 1 else 1
        )
        optimization_start = device.query_count
        stage_result = optimize_black_box_scipy(
            device,
            current_origin,
            basis=current_basis,
            method="COBYQA",
            max_queries=stage_budget,
            target_infidelity=target_infidelity,
            optimizer_options={
                "initial_tr_radius": 0.25,
                "final_tr_radius": 1e-6,
            },
            allow_existing_history=True,
            evaluation_repeats=evaluation_repeats,
        )
        optimization_queries = device.query_count - optimization_start
        current_origin = stage_result.params

        confirmation_count = min(
            confirmation_queries,
            max_total_queries - device.query_count,
        )
        reported_losses = [
            device.query(current_origin)
            for _ in range(confirmation_count)
        ]
        reported_infidelity = float(np.mean(reported_losses))
        if device.shots is None:
            reported_upper_bound = reported_infidelity
        else:
            reported_upper_bound = _wilson_upper_bound(
                reported_infidelity,
                device.shots * confirmation_count,
                z_score=confirmation_z_score,
            )
        confirmed = reported_upper_bound <= target_infidelity
        update_queries = 0
        rotation = None

        if confirmed:
            message = "reported target confirmed"
        elif stage_index < len(stage_query_budgets) - 1:
            update_cost = cross_block_query_cost(
                current_basis.shape[1],
                scout_count,
                center_repeats=center_repeats,
            )
            if device.query_count + update_cost > max_total_queries:
                message = "insufficient budget for another subspace update"
            else:
                update = estimate_cross_block_rotation(
                    device,
                    current_origin,
                    current_basis,
                    current_curvatures,
                    scout_count=scout_count,
                    finite_difference_step=finite_difference_step,
                    center_repeats=center_repeats,
                    diagonal_blend=diagonal_blend,
                    cross_shrink=cross_shrink,
                    seed=seed + 1000 * stage_index,
                )
                current_basis = update.basis
                current_curvatures = update.curvatures
                update_queries = update.queries
                rotation = update.rotation_frobenius

        stages.append(
            TrackingStage(
                stage=stage_index + 1,
                optimization_queries=optimization_queries,
                confirmation_queries=confirmation_count,
                reported_infidelity=reported_infidelity,
                reported_upper_bound=reported_upper_bound,
                confirmed=confirmed,
                update_queries=update_queries,
                rotation_frobenius=rotation,
            )
        )
        if confirmed or (
            not confirmed
            and stage_index < len(stage_query_budgets) - 1
            and update_queries == 0
        ):
            break

    summary = _closed_loop_summary(
        device,
        target_infidelity=target_infidelity,
        optimizer_success=any(stage.confirmed for stage in stages),
        message=message,
    )
    return RankPreservingResult(
        summary=summary,
        final_origin=current_origin,
        final_basis=current_basis,
        final_curvatures=current_curvatures,
        stages=tuple(stages),
        message=message,
    )
