"""A first genuine thermodynamic rooted-window state-polynomial SDP.

This module assembles a deliberately weak but valid outer relaxation on a
radius-one Hamiltonian window.  Excitations are supported only at the root;
all terms of the infinite nearest-neighbor Hamiltonian that fail to commute
with them are present in the window.  Consequently, infeasibility excludes an
infinite-volume U(1)-invariant state with the assumed gap.  Feasibility proves
nothing, and this subset of constraints is not assigned an (L,d) label from the
complete hierarchy.

The operator positivity block uses identity plus all one-site matrix units on
the rooted patch.  A second moment matrix lifts products of diagonal root-state
symbols, which is exactly where |omega(a)|^2 survives U(1) invariance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import TypeAlias

import cvxpy as cp
import networkx as nx
import numpy as np

from .atomic_sdp import FEASIBLE_STATUSES, INFEASIBLE_STATUSES
from .local_algebra import atomic_energies

LocalUnit: TypeAlias = tuple[int, int] | None
Monomial: TypeAlias = tuple[LocalUnit, ...]
Operator: TypeAlias = dict[Monomial, complex]


def _identity(sites: int) -> Monomial:
    return (None,) * sites


def _unit(sites: int, site: int, row: int, column: int) -> Monomial:
    result: list[LocalUnit] = [None] * sites
    result[site] = (row, column)
    return tuple(result)


def _adjoint_monomial(monomial: Monomial) -> Monomial:
    return tuple(None if unit is None else (unit[1], unit[0]) for unit in monomial)


def _charge(monomial: Monomial) -> int:
    return sum(0 if unit is None else unit[0] - unit[1] for unit in monomial)


def _monomial_sort_key(monomial: Monomial) -> tuple[tuple[int, int], ...]:
    return tuple((-1, -1) if unit is None else unit for unit in monomial)


def _multiply_monomials(left: Monomial, right: Monomial) -> Monomial | None:
    product: list[LocalUnit] = []
    for first, second in zip(left, right):
        if first is None:
            product.append(second)
        elif second is None:
            product.append(first)
        elif first[1] != second[0]:
            return None
        else:
            product.append((first[0], second[1]))
    return tuple(product)


def _clean(operator: Operator, tolerance: float = 1e-14) -> Operator:
    return {monomial: coefficient for monomial, coefficient in operator.items() if abs(coefficient) > tolerance}


def _add(*operators: Operator) -> Operator:
    result: Operator = {}
    for operator in operators:
        for monomial, coefficient in operator.items():
            result[monomial] = result.get(monomial, 0.0) + coefficient
    return _clean(result)


def _scale(coefficient: complex, operator: Operator) -> Operator:
    return _clean({monomial: coefficient * value for monomial, value in operator.items()})


def _multiply(left: Operator, right: Operator) -> Operator:
    result: Operator = {}
    for left_monomial, left_coefficient in left.items():
        for right_monomial, right_coefficient in right.items():
            product = _multiply_monomials(left_monomial, right_monomial)
            if product is not None:
                result[product] = result.get(product, 0.0) + left_coefficient * right_coefficient
    return _clean(result)


def _adjoint(operator: Operator) -> Operator:
    return {
        _adjoint_monomial(monomial): np.conjugate(coefficient)
        for monomial, coefficient in operator.items()
    }


def _commutator(left: Operator, right: Operator) -> Operator:
    return _add(_multiply(left, right), _scale(-1.0, _multiply(right, left)))


def _matrix_operator(matrix: np.ndarray, sites: int, site: int) -> Operator:
    result: Operator = {}
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            if abs(matrix[row, column]) > 1e-14:
                result[_unit(sites, site, row, column)] = complex(matrix[row, column])
    return result


def _incident_hamiltonian(
    graph: nx.Graph,
    nmax: int,
    hopping: float,
    interaction: float,
    mu: float,
) -> Operator:
    sites = graph.number_of_nodes()
    dim = nmax + 1
    annihilation = np.zeros((dim, dim), dtype=complex)
    for occupation in range(1, dim):
        annihilation[occupation - 1, occupation] = np.sqrt(occupation)
    creation = annihilation.conj().T
    energies = np.diag(atomic_energies(nmax, interaction=interaction, mu=mu))
    hamiltonian = _matrix_operator(energies, sites, 0)
    root_creation = _matrix_operator(creation, sites, 0)
    root_annihilation = _matrix_operator(annihilation, sites, 0)
    for neighbor in graph.neighbors(0):
        neighbor_creation = _matrix_operator(creation, sites, neighbor)
        neighbor_annihilation = _matrix_operator(annihilation, sites, neighbor)
        edge = _add(
            _multiply(root_creation, neighbor_annihilation),
            _multiply(neighbor_creation, root_annihilation),
        )
        hamiltonian = _add(hamiltonian, _scale(-hopping, edge))
    return hamiltonian


class _U1Expectation:
    """Affine pseudo-expectation with exact adjoint and U(1) relations."""

    def __init__(self, sites: int):
        self.sites = sites
        self.identity = _identity(sites)
        self.variables: dict[Monomial, cp.Variable] = {}

    def monomial(self, monomial: Monomial) -> cp.Expression | complex:
        if monomial == self.identity:
            return 1.0
        if _charge(monomial) != 0:
            return 0.0
        adjoint = _adjoint_monomial(monomial)
        representative = min((monomial, adjoint), key=_monomial_sort_key)
        if representative not in self.variables:
            self.variables[representative] = cp.Variable(
                complex=representative != _adjoint_monomial(representative),
                name=f"y{len(self.variables)}",
            )
        variable = self.variables[representative]
        return variable if monomial == representative else cp.conj(variable)

    def operator(self, operator: Operator) -> cp.Expression:
        expression: cp.Expression | complex = 0.0
        for monomial, coefficient in operator.items():
            expression = expression + coefficient * self.monomial(monomial)
        return cp.Expression.cast_to_const(expression) if not isinstance(expression, cp.Expression) else expression


@dataclass
class RootedSDPResult:
    claim_type: str
    symmetry: str
    geometry: str
    nmax: int
    hopping: float
    interaction: float
    mu: float
    gamma: float
    solver: str
    status: str
    classification: str
    objective: float | None
    sense: str
    observable: str | None
    operator_moment_size: int
    state_moment_size: int
    scalar_variables: int
    scalar_equalities: int
    scalar_inequalities: int
    solve_time_s: float
    num_iters: int | None
    operator_moment_min_eigenvalue: float | None
    state_moment_min_eigenvalue: float | None
    covariance_min_eigenvalue: float | None
    gap_min_eigenvalue: float | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _classification(status: str) -> str:
    if status in FEASIBLE_STATUSES:
        return "FEASIBLE"
    if status in INFEASIBLE_STATUSES:
        return "INFEASIBLE"
    return "UNKNOWN"


def solve_rooted_gap(
    graph: nx.Graph,
    nmax: int,
    gamma: float,
    *,
    hopping: float,
    interaction: float = 1.0,
    mu: float = 0.5,
    solver: str = "CLARABEL",
    observable: str | None = None,
    sense: str = "feasibility",
) -> RootedSDPResult:
    """Solve the U(1)-restricted root-excitation outer SDP at fixed gamma."""
    if gamma < 0:
        raise ValueError("gamma must be nonnegative")
    sites = graph.number_of_nodes()
    dim = nmax + 1
    expectation = _U1Expectation(sites)
    identity_operator = {_identity(sites): 1.0}
    units: list[Operator] = [identity_operator]
    for site in range(sites):
        for row in range(dim):
            for column in range(dim):
                units.append({_unit(sites, site, row, column): 1.0})

    moment_entries: list[list[cp.Expression]] = []
    for row, left in enumerate(units):
        entries: list[cp.Expression] = []
        for column, right in enumerate(units):
            if column < row:
                entries.append(cp.conj(moment_entries[column][row]))
            else:
                entries.append(expectation.operator(_multiply(_adjoint(left), right)))
        moment_entries.append(entries)
    operator_moment = cp.bmat(moment_entries)

    constraints: list[cp.Constraint] = [operator_moment >> 0]
    for site in range(sites):
        normalization = sum(
            expectation.monomial(_unit(sites, site, level, level)) for level in range(dim)
        )
        constraints.append(normalization == 1)

    root_units = [
        {_unit(sites, 0, row, column): 1.0}
        for row in range(dim)
        for column in range(dim)
    ]
    diagonal_indices = [level * dim + level for level in range(dim)]
    probabilities = cp.hstack(
        [expectation.operator(root_units[index]) for index in diagonal_indices]
    )
    lifted_products = cp.Variable((dim, dim), symmetric=True, name="P")
    state_moment = cp.bmat(
        [
            [np.ones((1, 1)), cp.reshape(probabilities, (1, dim), order="C")],
            [cp.reshape(probabilities, (dim, 1), order="C"), lifted_products],
        ]
    )
    constraints.extend(
        [
            probabilities >= 0,
            cp.sum(probabilities) == 1,
            state_moment >> 0,
            lifted_products @ np.ones(dim) == probabilities,
            cp.diag(lifted_products) <= probabilities,
        ]
    )

    hamiltonian = _incident_hamiltonian(graph, nmax, hopping, interaction, mu)
    for root_operator in root_units:
        constraints.append(expectation.operator(_commutator(hamiltonian, root_operator)) == 0)

    covariance_entries: list[list[cp.Expression]] = []
    gap_entries: list[list[cp.Expression]] = []
    for row, left in enumerate(root_units):
        covariance_row: list[cp.Expression] = []
        entries: list[cp.Expression] = []
        for column, right in enumerate(root_units):
            if column < row:
                covariance_row.append(cp.conj(covariance_entries[column][row]))
                entries.append(cp.conj(gap_entries[column][row]))
                continue
            first = _multiply(_adjoint(left), _commutator(hamiltonian, right))
            second = _multiply(_commutator(hamiltonian, _adjoint(left)), right)
            energy_form = expectation.operator(_scale(0.5, _add(first, _scale(-1.0, second))))
            covariance = expectation.operator(_multiply(_adjoint(left), right))
            left_row, left_column = divmod(row, dim)
            right_row, right_column = divmod(column, dim)
            if left_row == left_column and right_row == right_column:
                covariance = covariance - lifted_products[left_row, right_row]
            covariance = cp.real(covariance) if row == column else covariance
            covariance_row.append(covariance)
            entry = energy_form - gamma * covariance
            entries.append(cp.real(entry) if row == column else entry)
        covariance_entries.append(covariance_row)
        gap_entries.append(entries)
    covariance_matrix = cp.bmat(covariance_entries)
    gap_matrix = cp.bmat(gap_entries)
    constraints.extend([covariance_matrix >> 0, gap_matrix >> 0])

    observable_operator: Operator | None = None
    if observable in {"rho0", "F0"}:
        diagonal = np.arange(dim, dtype=float)
        if observable == "F0":
            diagonal = (diagonal - 1.0) ** 2
        observable_operator = _matrix_operator(np.diag(diagonal), sites, 0)
    elif observable == "K0":
        hopping_operator = _scale(-1.0 / graph.graph["infinite_coordination"], _incident_hamiltonian(graph, nmax, 1.0, 0.0, 0.0))
        observable_operator = hopping_operator
    elif observable is not None:
        raise ValueError("observable must be rho0, F0, K0, or None")

    if sense == "feasibility":
        objective = cp.Minimize(0)
    elif sense in {"min", "max"} and observable_operator is not None:
        expression = cp.real(expectation.operator(observable_operator))
        objective = cp.Minimize(expression) if sense == "min" else cp.Maximize(expression)
    else:
        raise ValueError("optimization requires sense min/max and an observable")

    problem = cp.Problem(objective, constraints)
    start = perf_counter()
    try:
        value = problem.solve(solver=solver, verbose=False)
        status = str(problem.status)
    except cp.error.SolverError:
        value = None
        status = "solver_error"
    elapsed = perf_counter() - start
    classification = _classification(status)

    def minimum_eigenvalue(expression: cp.Expression) -> float | None:
        if classification != "FEASIBLE" or expression.value is None:
            return None
        matrix = np.asarray(expression.value, dtype=complex)
        return float(np.linalg.eigvalsh(0.5 * (matrix + matrix.conj().T))[0])

    metrics = problem.size_metrics
    stats = problem.solver_stats
    return RootedSDPResult(
        claim_type="THERMODYNAMIC_U1_ROOT_EXCITATION_OUTER_SDP",
        symmetry="U1_INVARIANT_STATES_ONLY",
        geometry=str(graph.graph["geometry"]),
        nmax=nmax,
        hopping=hopping,
        interaction=interaction,
        mu=mu,
        gamma=gamma,
        solver=solver,
        status=status,
        classification=classification,
        objective=None if value is None or not np.isfinite(value) else float(value),
        sense=sense,
        observable=observable,
        operator_moment_size=len(units),
        state_moment_size=dim + 1,
        scalar_variables=metrics.num_scalar_variables,
        scalar_equalities=metrics.num_scalar_eq_constr,
        scalar_inequalities=metrics.num_scalar_leq_constr,
        solve_time_s=float(
            stats.solve_time
            if stats is not None and stats.solve_time is not None
            else elapsed
        ),
        num_iters=None if stats is None else stats.num_iters,
        operator_moment_min_eigenvalue=minimum_eigenvalue(operator_moment),
        state_moment_min_eigenvalue=minimum_eigenvalue(state_moment),
        covariance_min_eigenvalue=minimum_eigenvalue(covariance_matrix),
        gap_min_eigenvalue=minimum_eigenvalue(gap_matrix),
    )


def bisect_rooted_gap(
    graph: nx.Graph,
    nmax: int,
    *,
    hopping: float,
    interaction: float = 1.0,
    mu: float = 0.5,
    lower: float = 0.0,
    upper: float = 1.0,
    tolerance: float = 2e-3,
    max_steps: int = 30,
    solver: str = "CLARABEL",
) -> tuple[float, float, list[RootedSDPResult]]:
    history: list[RootedSDPResult] = []

    def evaluate(value: float) -> RootedSDPResult:
        result = solve_rooted_gap(
            graph,
            nmax,
            value,
            hopping=hopping,
            interaction=interaction,
            mu=mu,
            solver=solver,
        )
        history.append(result)
        return result

    low = evaluate(lower)
    high = evaluate(upper)
    if low.classification != "FEASIBLE":
        raise RuntimeError(f"lower bracket is {low.classification}: {low.status}")
    if high.classification != "INFEASIBLE":
        raise RuntimeError(f"upper bracket is {high.classification}: {high.status}")
    for _ in range(max_steps):
        if upper - lower <= tolerance:
            break
        middle = 0.5 * (lower + upper)
        result = evaluate(middle)
        if result.classification == "FEASIBLE":
            lower = middle
        elif result.classification == "INFEASIBLE":
            upper = middle
        else:
            break
    return lower, upper, history
