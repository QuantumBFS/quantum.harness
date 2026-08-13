"""Numerical locality screening for odd-cycle word-pair cones."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import sympy as sp
from scipy import optimize

from oracle.oddcycle_word_operator import NormalOrderedLabel, WordPairColumn

if TYPE_CHECKING:
    from oracle.oddcycle_local_targets import TargetPoint


_ACTIVE_TOLERANCE = 1.0e-10
_RESIDUAL_TOLERANCE = 1.0e-9


@dataclass(frozen=True)
class LocalitySpec:
    """Explicit supports allowed for a bounded-body normal-ordered operator."""

    name: str
    max_body_order: int
    allowed_supports: tuple[frozenset[int], ...]

    def allows_support(self, support: frozenset[int]) -> bool:
        """Whether ``support`` is contained in one permitted local support."""

        return any(support <= allowed for allowed in self.allowed_supports)


def locality_specs() -> dict[str, LocalitySpec]:
    """Return the fixed five-site path, ring, and cluster locality ladders."""

    path_edges = tuple(frozenset((index, index + 1)) for index in range(4))
    ring_edges = (*path_edges, frozenset((4, 0)))
    path_arcs = tuple(frozenset((index, index + 1, index + 2)) for index in range(3))
    ring_arcs = tuple(
        frozenset((index, (index + 1) % 5, (index + 2) % 5))
        for index in range(5)
    )
    return {
        "path-edge": LocalitySpec("path-edge", 2, path_edges),
        "ring-edge": LocalitySpec("ring-edge", 2, ring_edges),
        "path-arc3": LocalitySpec("path-arc3", 2, path_arcs),
        "ring-arc3": LocalitySpec("ring-arc3", 2, ring_arcs),
        "cluster-two-body": LocalitySpec(
            "cluster-two-body", 2, (frozenset(range(5)),)
        ),
    }


def forbidden_label_indices(
    labels: Sequence[NormalOrderedLabel], spec: LocalitySpec
) -> tuple[int, ...]:
    """Return coordinates disallowed by ``spec``; the scalar is always allowed."""

    return tuple(
        index
        for index, label in enumerate(labels)
        if label.body_order
        and (
            label.body_order > spec.max_body_order
            or not spec.allows_support(label.support)
        )
    )


@dataclass(frozen=True)
class NumericalConeResult:
    """One deterministic HiGHS feasibility or target-objective screen."""

    status: str
    weights: np.ndarray | None
    residual: float | None
    minimum_retained_weight: float | None
    active_indices: tuple[int, ...]
    objective: float | None
    solver_message: str
    iteration_count: int | None
    objective_index: int | None = None
    objective_sign: int | None = None


@dataclass(frozen=True)
class TargetConeResult:
    """One numerical membership screen for an exact named target."""

    status: str
    target_id: str
    target_parameters: tuple[tuple[str, sp.Rational], ...]
    weights: np.ndarray | None
    residual: float | None
    minimum_retained_weight: float | None
    active_indices: tuple[int, ...]
    target_diagonal_gauge_frustrated: bool
    solver_message: str
    iteration_count: int | None


def _solver_message(result: optimize.OptimizeResult | None) -> str:
    if result is None:
        return "linprog did not return a result"
    message = getattr(result, "message", None)
    return message if isinstance(message, str) else "linprog result has no message"


def _iteration_count(result: optimize.OptimizeResult | None) -> int | None:
    count = getattr(result, "nit", None) if result is not None else None
    return int(count) if isinstance(count, (int, np.integer)) else None


def _inconclusive_result(
    result: optimize.OptimizeResult | None,
) -> NumericalConeResult:
    return NumericalConeResult(
        status="solver-inconclusive",
        weights=None,
        residual=None,
        minimum_retained_weight=None,
        active_indices=(),
        objective=None,
        solver_message=_solver_message(result),
        iteration_count=_iteration_count(result),
    )


def _has_finite_infeasibility_certificate(forbidden_columns: np.ndarray) -> bool:
    """Find a finite strict separator certifying that zero is outside the hull."""

    ray_count = forbidden_columns.shape[1]
    try:
        certificate = optimize.linprog(
            np.zeros(forbidden_columns.shape[0]),
            A_ub=-forbidden_columns.T,
            b_ub=-np.ones(ray_count),
            bounds=(None, None),
            method="highs",
        )
    except (ArithmeticError, ValueError):
        return False
    vector = getattr(certificate, "x", None)
    return bool(
        getattr(certificate, "status", None) == 0
        and vector is not None
        and np.all(np.isfinite(vector))
    )


def _has_finite_target_infeasibility_certificate(
    columns: np.ndarray,
    target: np.ndarray,
) -> bool:
    """Find a finite Farkas separator for ``columns @ q = target, q >= 0``."""

    constraints = np.vstack((-columns.T, target[np.newaxis, :]))
    bounds = np.concatenate((np.zeros(columns.shape[1]), [-1.0]))
    try:
        certificate = optimize.linprog(
            np.zeros(columns.shape[0]),
            A_ub=constraints,
            b_ub=bounds,
            bounds=(None, None),
            method="highs",
        )
    except (ArithmeticError, ValueError):
        return False
    vector = getattr(certificate, "x", None)
    return bool(
        getattr(certificate, "status", None) == 0
        and vector is not None
        and np.all(np.isfinite(vector))
    )


def _scan_positive_matrix_equality(
    columns: np.ndarray,
    target: np.ndarray,
) -> NumericalConeResult:
    """Screen one nonnegative matrix-cone equality."""

    matrix = np.asarray(columns, dtype=np.float64)
    right_hand_side = np.asarray(target, dtype=np.float64)
    if (
        matrix.ndim != 2
        or right_hand_side.shape != (matrix.shape[0],)
        or not np.all(np.isfinite(matrix))
        or not np.all(np.isfinite(right_hand_side))
    ):
        return _inconclusive_result(None)

    ray_count = matrix.shape[1]
    try:
        result = optimize.linprog(
            np.zeros(ray_count),
            A_eq=matrix,
            b_eq=right_hand_side,
            bounds=(0.0, None),
            method="highs",
        )
    except (ArithmeticError, ValueError):
        return _inconclusive_result(None)

    if getattr(result, "status", None) == 2:
        if _has_finite_target_infeasibility_certificate(
            matrix,
            right_hand_side,
        ):
            return NumericalConeResult(
                status="numerically-infeasible",
                weights=None,
                residual=None,
                minimum_retained_weight=None,
                active_indices=(),
                objective=None,
                solver_message=_solver_message(result),
                iteration_count=_iteration_count(result),
            )
        return _inconclusive_result(result)

    weights = getattr(result, "x", None)
    if getattr(result, "status", None) != 0 or weights is None:
        return _inconclusive_result(result)
    normalized_weights = np.asarray(weights, dtype=np.float64)
    if (
        normalized_weights.shape != (ray_count,)
        or not np.all(np.isfinite(normalized_weights))
    ):
        return _inconclusive_result(result)

    residual = float(
        np.max(
            np.abs(matrix @ normalized_weights - right_hand_side),
            initial=0.0,
        )
    )
    if not np.isfinite(residual) or residual > _RESIDUAL_TOLERANCE:
        return _inconclusive_result(result)
    active_indices = tuple(
        int(index)
        for index in np.flatnonzero(
            normalized_weights > _ACTIVE_TOLERANCE
        )
    )
    retained = normalized_weights[list(active_indices)]
    return NumericalConeResult(
        status="numerical-survivor",
        weights=normalized_weights,
        residual=residual,
        minimum_retained_weight=(
            float(np.min(retained)) if retained.size else None
        ),
        active_indices=active_indices,
        objective=0.0,
        solver_message=_solver_message(result),
        iteration_count=_iteration_count(result),
    )


def scan_positive_matrix_kernel(
    forbidden_columns: np.ndarray,
    objective: np.ndarray | None = None,
) -> NumericalConeResult:
    """Screen the normalized positive kernel of a floating-point row matrix."""

    matrix = np.asarray(forbidden_columns, dtype=np.float64)
    if matrix.ndim != 2 or not np.all(np.isfinite(matrix)):
        return _inconclusive_result(None)
    ray_count = matrix.shape[1]
    cost = np.zeros(ray_count) if objective is None else np.asarray(objective)
    if cost.shape != (ray_count,) or not np.all(np.isfinite(cost)):
        return _inconclusive_result(None)

    a_eq = np.vstack((matrix, np.ones((1, ray_count))))
    b_eq = np.concatenate((np.zeros(matrix.shape[0]), [1.0]))
    try:
        result = optimize.linprog(
            cost, A_eq=a_eq, b_eq=b_eq, bounds=(0.0, None), method="highs"
        )
    except (ArithmeticError, ValueError):
        return _inconclusive_result(None)

    if getattr(result, "status", None) == 2:
        if _has_finite_infeasibility_certificate(matrix):
            return NumericalConeResult(
                status="numerically-infeasible",
                weights=None,
                residual=None,
                minimum_retained_weight=None,
                active_indices=(),
                objective=None,
                solver_message=_solver_message(result),
                iteration_count=_iteration_count(result),
            )
        return _inconclusive_result(result)

    weights = getattr(result, "x", None)
    if getattr(result, "status", None) != 0 or weights is None:
        return _inconclusive_result(result)
    weights = np.asarray(weights, dtype=np.float64)
    if weights.shape != (ray_count,) or not np.all(np.isfinite(weights)):
        return _inconclusive_result(result)

    residual = float(np.max(np.abs(a_eq @ weights - b_eq)))
    if not np.isfinite(residual) or residual > _RESIDUAL_TOLERANCE:
        return _inconclusive_result(result)
    active_indices = tuple(
        int(index) for index in np.flatnonzero(weights > _ACTIVE_TOLERANCE)
    )
    retained = weights[list(active_indices)]
    return NumericalConeResult(
        status="numerical-survivor",
        weights=weights,
        residual=residual,
        minimum_retained_weight=float(np.min(retained)),
        active_indices=active_indices,
        objective=float(cost @ weights),
        solver_message=_solver_message(result),
        iteration_count=_iteration_count(result),
    )


def scan_positive_local_kernel(
    columns: Sequence[WordPairColumn],
    spec: LocalitySpec,
    objective_index: int | None = None,
) -> tuple[NumericalConeResult, ...]:
    """Run feasibility and signed permitted two-body objective screens."""

    if not columns:
        return ()
    labels = tuple(columns[0].coordinates)
    forbidden = forbidden_label_indices(labels, spec)
    coordinates = np.asarray(
        [[column.coordinates[label] for column in columns] for label in labels],
        dtype=np.float64,
    )
    forbidden_columns = coordinates[list(forbidden), :]
    permitted_two_body = tuple(
        index
        for index, label in enumerate(labels)
        if label.body_order == 2 and index not in set(forbidden)
    )
    if objective_index is not None:
        if objective_index not in permitted_two_body:
            raise ValueError("objective_index must select a permitted two-body label")
        permitted_two_body = (objective_index,)

    base = scan_positive_matrix_kernel(forbidden_columns)
    results = [base]
    for index in permitted_two_body:
        for sign in (1, -1):
            result = scan_positive_matrix_kernel(
                forbidden_columns, sign * coordinates[index]
            )
            results.append(
                NumericalConeResult(
                    status=result.status,
                    weights=result.weights,
                    residual=result.residual,
                    minimum_retained_weight=result.minimum_retained_weight,
                    active_indices=result.active_indices,
                    objective=result.objective,
                    solver_message=result.solver_message,
                    iteration_count=result.iteration_count,
                    objective_index=index,
                    objective_sign=sign,
                )
            )
    return tuple(results)


def scan_target_cone(
    columns: Sequence[WordPairColumn],
    target: TargetPoint,
) -> TargetConeResult:
    """Test whether ``-H_target`` is in the word cone modulo a scalar."""

    from oracle.oddcycle_local_hs_exact import diagonal_sign_gauge_audit
    from oracle.oddcycle_local_targets import TargetPoint
    from oracle.oddcycle_word_operator import normal_ordered_coordinates

    if not isinstance(target, TargetPoint):
        raise TypeError("target must be a TargetPoint")
    normalized_columns = tuple(columns)
    if not normalized_columns:
        numerical = _inconclusive_result(None)
    else:
        labels = tuple(normalized_columns[0].coordinates)
        if any(
            set(column.coordinates) != set(labels)
            for column in normalized_columns
        ):
            raise ValueError("columns must use one common coordinate basis")
        scalar_indices = tuple(
            index
            for index, label in enumerate(labels)
            if label.body_order == 0
        )
        if len(scalar_indices) != 1:
            raise ValueError("coordinate basis must contain one scalar label")
        non_scalar = tuple(
            index
            for index in range(len(labels))
            if index != scalar_indices[0]
        )
        target_coordinates = normal_ordered_coordinates(
            -target.hamiltonian,
            5,
        )
        if set(target_coordinates) != set(labels):
            raise ValueError(
                "target and columns must use one common coordinate basis"
            )
        coordinate_matrix = np.asarray(
            [
                [
                    column.coordinates[labels[index]]
                    for column in normalized_columns
                ]
                for index in non_scalar
            ],
            dtype=np.float64,
        )
        right_hand_side = np.asarray(
            [target_coordinates[labels[index]] for index in non_scalar],
            dtype=np.float64,
        )
        numerical = _scan_positive_matrix_equality(
            coordinate_matrix,
            right_hand_side,
        )

    dimension = target.hamiltonian.rows
    particle_number_blocks = tuple(
        tuple(
            state
            for state in range(dimension)
            if state.bit_count() == particles
        )
        for particles in range(6)
    )
    gauge_audit = diagonal_sign_gauge_audit(
        target.hamiltonian,
        particle_number_blocks,
    )
    return TargetConeResult(
        status=numerical.status,
        target_id=target.target_id,
        target_parameters=target.parameters,
        weights=numerical.weights,
        residual=numerical.residual,
        minimum_retained_weight=numerical.minimum_retained_weight,
        active_indices=numerical.active_indices,
        target_diagonal_gauge_frustrated=(
            gauge_audit["status"] == "exact-gauge-frustrated"
        ),
        solver_message=numerical.solver_message,
        iteration_count=numerical.iteration_count,
    )


__all__ = [
    "LocalitySpec",
    "NumericalConeResult",
    "TargetConeResult",
    "forbidden_label_indices",
    "locality_specs",
    "scan_positive_local_kernel",
    "scan_positive_matrix_kernel",
    "scan_target_cone",
]
