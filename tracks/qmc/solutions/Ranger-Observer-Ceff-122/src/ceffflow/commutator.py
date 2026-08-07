"""Small-system statistical deficiency for measurement--RG commutators."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import linprog, minimize

from .self_dual import SELF_DUAL_BETA, SelfDualBornCylinder


@dataclass(frozen=True, slots=True)
class DeficiencyResult:
    """Optimal finite classical post-processing in worst-case total variation."""

    deficiency: float
    stochastic_map: NDArray[np.float64]
    optimizer_status: str


@dataclass(frozen=True, slots=True)
class RelativeEntropyDeficiencyResult:
    """Optimal worst-case target-to-simulated relative entropy."""

    deficiency: float
    stochastic_map: NDArray[np.float64]
    optimizer_status: str


@dataclass(frozen=True, slots=True)
class SelfDualBlockDeficiency:
    """Local self-dual weak-measurement obstruction for a 2-to-1 block."""

    beta: float
    record_range: int
    tv: DeficiencyResult
    kl: RelativeEntropyDeficiencyResult

    @property
    def diamond_distance(self) -> float:
        r"""Return \(\frac12\|\mathcal Q-\mathcal K\mathcal P\|_\diamond\).

        Both optimized measurement channels have two classical outputs and
        commuting effects diagonal in the two-site X basis.  Their half
        diamond norm is therefore the largest absolute plus-effect
        eigenvalue difference, exactly the TV optimum over the four X
        eigenstates used here.
        """

        return self.tv.deficiency

    @property
    def diamond_norm(self) -> float:
        """Return the unhalved diamond norm under the same convention."""

        return 2.0 * self.diamond_distance


@dataclass(frozen=True, slots=True)
class SelfDualTrajectoryBlockDeficiency:
    """Block obstruction evaluated on critical conditional trajectories."""

    length: int
    beta: float
    record_range: int
    trajectories: int
    rows: int
    state_count: int
    tv: DeficiencyResult
    kl: RelativeEntropyDeficiencyResult


def statistical_deficiency(
    fine_distributions: ArrayLike,
    quantum_first_distributions: ArrayLike,
) -> DeficiencyResult:
    r"""Minimize \(\sup_\lambda TV(Q_\lambda,P_\lambda K)\) over K."""

    fine = np.asarray(fine_distributions, dtype=float)
    target = np.asarray(quantum_first_distributions, dtype=float)
    if fine.ndim != 2 or target.ndim != 2 or fine.shape[0] != target.shape[0]:
        raise ValueError("distribution families must be aligned matrices")
    if np.any(fine < 0.0) or np.any(target < 0.0):
        raise ValueError("probabilities must be nonnegative")
    if not np.allclose(np.sum(fine, axis=1), 1.0):
        raise ValueError("fine distributions must be normalized")
    if not np.allclose(np.sum(target, axis=1), 1.0):
        raise ValueError("target distributions must be normalized")
    states, fine_outcomes = fine.shape
    coarse_outcomes = target.shape[1]
    map_count = fine_outcomes * coarse_outcomes
    absolute_count = states * coarse_outcomes
    total_variables = map_count + absolute_count + 1
    objective = np.zeros(total_variables)
    objective[-1] = 1.0

    def map_index(fine_index: int, coarse_index: int) -> int:
        return fine_index * coarse_outcomes + coarse_index

    def absolute_index(state: int, coarse_index: int) -> int:
        return map_count + state * coarse_outcomes + coarse_index

    inequalities: list[NDArray[np.float64]] = []
    bounds: list[float] = []
    for state in range(states):
        for coarse in range(coarse_outcomes):
            # P K - Q <= u
            row = np.zeros(total_variables)
            for fine_index in range(fine_outcomes):
                row[map_index(fine_index, coarse)] = fine[state, fine_index]
            row[absolute_index(state, coarse)] = -1.0
            inequalities.append(row)
            bounds.append(float(target[state, coarse]))
            # Q - P K <= u
            row = np.zeros(total_variables)
            for fine_index in range(fine_outcomes):
                row[map_index(fine_index, coarse)] = -fine[state, fine_index]
            row[absolute_index(state, coarse)] = -1.0
            inequalities.append(row)
            bounds.append(float(-target[state, coarse]))
        # sum_c u_lambda,c / 2 <= t
        row = np.zeros(total_variables)
        for coarse in range(coarse_outcomes):
            row[absolute_index(state, coarse)] = 0.5
        row[-1] = -1.0
        inequalities.append(row)
        bounds.append(0.0)

    equalities = np.zeros((fine_outcomes, total_variables))
    equality_values = np.ones(fine_outcomes)
    for fine_index in range(fine_outcomes):
        for coarse in range(coarse_outcomes):
            equalities[
                fine_index, map_index(fine_index, coarse)
            ] = 1.0
    result = linprog(
        objective,
        A_ub=np.asarray(inequalities),
        b_ub=np.asarray(bounds),
        A_eq=equalities,
        b_eq=equality_values,
        bounds=[(0.0, None)] * total_variables,
        method="highs",
    )
    if not result.success:
        raise RuntimeError(f"deficiency optimization failed: {result.message}")
    stochastic_map = result.x[:map_count].reshape(
        fine_outcomes, coarse_outcomes
    )
    return DeficiencyResult(
        deficiency=float(result.x[-1]),
        stochastic_map=stochastic_map,
        optimizer_status=str(result.message),
    )


def relative_entropy_deficiency(
    fine_distributions: ArrayLike,
    quantum_first_distributions: ArrayLike,
) -> RelativeEntropyDeficiencyResult:
    r"""Minimize \(\sup_\lambda D(Q_\lambda\Vert P_\lambda K)\) over K."""

    fine = np.asarray(fine_distributions, dtype=float)
    target = np.asarray(quantum_first_distributions, dtype=float)
    if fine.ndim != 2 or target.ndim != 2 or fine.shape[0] != target.shape[0]:
        raise ValueError("distribution families must be aligned matrices")
    if np.any(fine < 0.0) or np.any(target < 0.0):
        raise ValueError("probabilities must be nonnegative")
    if not np.allclose(np.sum(fine, axis=1), 1.0):
        raise ValueError("fine distributions must be normalized")
    if not np.allclose(np.sum(target, axis=1), 1.0):
        raise ValueError("target distributions must be normalized")

    _, fine_outcomes = fine.shape
    coarse_outcomes = target.shape[1]
    map_count = fine_outcomes * coarse_outcomes
    tv_solution = statistical_deficiency(fine, target)
    initial_map = np.clip(tv_solution.stochastic_map, 1e-8, 1.0)
    initial_map /= np.sum(initial_map, axis=1, keepdims=True)

    def divergences(flat_map: NDArray[np.float64]) -> NDArray[np.float64]:
        kernel = flat_map[:map_count].reshape(
            fine_outcomes, coarse_outcomes
        )
        simulated = np.clip(fine @ kernel, 1e-15, None)
        terms = np.where(
            target > 0.0,
            target * np.log(np.clip(target, 1e-15, None) / simulated),
            0.0,
        )
        return np.sum(terms, axis=1)

    initial_divergences = divergences(initial_map.ravel())
    initial = np.concatenate(
        [initial_map.ravel(), [float(np.max(initial_divergences))]]
    )
    equality_matrix = np.zeros((fine_outcomes, map_count + 1))
    for fine_index in range(fine_outcomes):
        start = fine_index * coarse_outcomes
        equality_matrix[fine_index, start : start + coarse_outcomes] = 1.0

    constraints = [
        {
            "type": "eq",
            "fun": lambda variables: equality_matrix @ variables
            - np.ones(fine_outcomes),
        },
        {
            "type": "ineq",
            "fun": lambda variables: variables[-1]
            - divergences(variables),
        },
    ]
    result = minimize(
        lambda variables: float(variables[-1]),
        initial,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * map_count + [(0.0, None)],
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    if not result.success:
        raise RuntimeError(
            f"relative-entropy deficiency optimization failed: "
            f"{result.message}"
        )
    stochastic_map = result.x[:map_count].reshape(
        fine_outcomes, coarse_outcomes
    )
    return RelativeEntropyDeficiencyResult(
        deficiency=float(max(result.x[-1], 0.0)),
        stochastic_map=stochastic_map,
        optimizer_status=str(result.message),
    )


def _block_distributions_from_expectations(
    expectations: NDArray[np.float64],
    beta: float,
    record_range: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return physical-record and logical-X distributions for a state family."""

    if beta <= 0.0:
        raise ValueError("beta must be positive")
    if record_range not in (1, 2):
        raise ValueError("record_range must be 1 or 2")
    values = np.asarray(expectations, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("expectations must have columns <X1>, <X2>, <X1 X2>")
    if np.any(np.abs(values) > 1.0 + 1e-10):
        raise ValueError("Pauli expectations must lie in [-1, 1]")
    tanh_beta = float(np.tanh(beta))
    if record_range == 1:
        fine = np.asarray(
            [
                [
                    0.5 * (1.0 + tanh_beta * first),
                    0.5 * (1.0 - tanh_beta * first),
                ]
                for first, _, _ in values
            ]
        )
    else:
        outcome_pairs = ((1, 1), (1, -1), (-1, 1), (-1, -1))
        fine = np.asarray(
            [
                [
                    0.25
                    * (
                        1.0
                        + first_outcome * tanh_beta * first
                        + second_outcome * tanh_beta * second
                        + first_outcome
                        * second_outcome
                        * tanh_beta**2
                        * pair
                    )
                    for first_outcome, second_outcome in outcome_pairs
                ]
                for first, second, pair in values
            ]
        )
    target = np.asarray(
        [
            [
                0.5 * (1.0 + tanh_beta * pair),
                0.5 * (1.0 - tanh_beta * pair),
            ]
            for _, _, pair in values
        ]
    )
    return fine, target


def _self_dual_block_distributions(
    beta: float,
    record_range: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return the channel-level witness on all two-site X eigenstates."""

    expectations = np.asarray(
        [
            [first, second, first * second]
            for first, second in ((-1, -1), (-1, 1), (1, -1), (1, 1))
        ],
        dtype=float,
    )
    return _block_distributions_from_expectations(
        expectations, beta, record_range
    )


def self_dual_block_deficiency(
    beta: float = SELF_DUAL_BETA,
    record_range: int = 2,
) -> SelfDualBlockDeficiency:
    r"""Compare logical weak \(X\) with physical weak-\(X\) records.

    The declared 2-to-1 block channel is CNOT followed by tracing out the
    syndrome qubit.  Its Heisenberg pullback maps logical \(X\) to
    \(X_1X_2\).  The record-first observer sees one or both physical weak-X
    outcomes and may apply any row-stochastic classical post-processing.
    """

    fine, target = _self_dual_block_distributions(beta, record_range)
    return SelfDualBlockDeficiency(
        beta=float(beta),
        record_range=record_range,
        tv=statistical_deficiency(fine, target),
        kl=relative_entropy_deficiency(fine, target),
    )


def self_dual_trajectory_block_deficiency(
    length: int,
    *,
    beta: float = SELF_DUAL_BETA,
    record_range: int = 2,
    trajectories: int = 12,
    rows: int = 4,
    seed: int = 122,
) -> SelfDualTrajectoryBlockDeficiency:
    """Evaluate the block witness on sampled critical conditional states.

    The family contains the plus state and the state after every sampled row
    of each independently restarted Born trajectory.  A single classical
    map must approximate logical-X statistics for the whole family.
    """

    if trajectories < 1 or rows < 1:
        raise ValueError("trajectories and rows must be positive")
    cylinder = SelfDualBornCylinder(length, beta)
    generator = np.random.default_rng(seed + length)
    expectations = [
        cylinder.x_pair_expectations(cylinder.plus_state(), 0, 1)
    ]
    for _ in range(trajectories):
        state = cylinder.plus_state()
        for _ in range(rows):
            state, _ = cylinder.sample_row(
                state,
                generator.random(length),
                generator.random(length),
            )
            expectations.append(cylinder.x_pair_expectations(state, 0, 1))
    fine, target = _block_distributions_from_expectations(
        np.asarray(expectations), beta, record_range
    )
    return SelfDualTrajectoryBlockDeficiency(
        length=length,
        beta=float(beta),
        record_range=record_range,
        trajectories=trajectories,
        rows=rows,
        state_count=len(expectations),
        tv=statistical_deficiency(fine, target),
        kl=relative_entropy_deficiency(fine, target),
    )


def hadamard_z_commutator_example() -> DeficiencyResult:
    """State-family obstruction for Z-measure then classical map vs H then Z."""

    # State order: |0>, |1>, |+>, |->.  The fine observer measures Z.
    fine = np.asarray(
        [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5], [0.5, 0.5]]
    )
    # Quantum-first applies H (a one-site RG/basis rotation) then measures Z,
    # which is equivalent to measuring X on the input family.
    quantum_first = np.asarray(
        [[0.5, 0.5], [0.5, 0.5], [1.0, 0.0], [0.0, 1.0]]
    )
    return statistical_deficiency(fine, quantum_first)
