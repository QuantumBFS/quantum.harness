"""Small state-polynomial SDP hierarchy for pairwise ±-commuting observables.

This implements the reduced hierarchy in Eqs. (17)-(19) of
arXiv:2310.00612.  A basis element is indexed by a square-free subset S and
represents prod(i in S) <A_i> A_S.  Moment entries are identified using
A_i^2=I, A_i A_j=zeta_ij A_j A_i, and <A_i>=x_i.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Iterable

import cvxpy as cp
import numpy as np


def _edge_set(edges: Iterable[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    return frozenset(tuple(sorted(edge)) for edge in edges)


def basis_subsets(n: int, order: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        subset
        for size in range(order + 1)
        for subset in combinations(range(n), size)
    )


def _canonical_word(
    word: tuple[int, ...], edges: frozenset[tuple[int, int]]
) -> tuple[int, int]:
    """Reduce a word to sign * increasing square-free word, returned as mask."""
    items = list(word)
    sign = 1
    # Stable insertion sort; swapping an anti-commuting pair changes the sign.
    for pos in range(1, len(items)):
        cursor = pos
        while cursor and items[cursor - 1] > items[cursor]:
            left, right = items[cursor - 1], items[cursor]
            if tuple(sorted((left, right))) in edges:
                sign = -sign
            items[cursor - 1], items[cursor] = right, left
            cursor -= 1
    reduced: list[int] = []
    for item in items:
        if reduced and reduced[-1] == item:
            reduced.pop()
        else:
            reduced.append(item)
    mask = sum(1 << item for item in reduced)
    return sign, mask


def _adjoint_sign(mask: int, edges: frozenset[tuple[int, int]]) -> int:
    vertices = tuple(index for index in range(mask.bit_length()) if mask & (1 << index))
    sign, _ = _canonical_word(tuple(reversed(vertices)), edges)
    return sign


def _entry_label(
    left: tuple[int, ...],
    right: tuple[int, ...],
    n: int,
    edges: frozenset[tuple[int, int]],
) -> tuple[int, tuple[tuple[int, ...], int] | None]:
    counts = [0] * n
    for index in left + right:
        counts[index] += 1
    sign, mask = _canonical_word(tuple(reversed(left)) + right, edges)
    if _adjoint_sign(mask, edges) < 0:
        return sign, None
    if mask and mask & (mask - 1) == 0:
        # The remaining state symbol is <A_i>=x_i.
        counts[mask.bit_length() - 1] += 1
        mask = 0
    return sign, (tuple(counts), mask)


def solve_theta_basis(
    n: int,
    edges: Iterable[tuple[int, int]],
    basis: Iterable[tuple[int, ...]],
    *,
    subset_cuts: Iterable[tuple[tuple[int, ...], float]] = (),
    solver: str = "CLARABEL",
) -> dict[str, object]:
    """Solve the relaxation for an independently supplied square-free basis."""
    graph_edges = _edge_set(edges)
    basis = tuple(sorted(set(tuple(sorted(item)) for item in basis), key=lambda item: (len(item), item)))
    if not basis or basis[0] != ():
        raise ValueError("basis must include the empty word")
    if any(len(set(item)) != len(item) or any(index < 0 or index >= n for index in item) for item in basis):
        raise ValueError("basis entries must be square-free subsets of graph vertices")
    missing_singletons = [vertex for vertex in range(n) if (vertex,) not in basis]
    if missing_singletons:
        raise ValueError(f"basis is missing singleton vertices {missing_singletons}")
    index = {subset: position for position, subset in enumerate(basis)}
    matrix = cp.Variable((len(basis), len(basis)), symmetric=True)
    constraints: list[cp.Constraint] = [matrix >> 0, matrix[0, 0] == 1.0]

    groups: dict[tuple[tuple[int, ...], int], list[tuple[int, int, int]]] = defaultdict(list)
    zero_entries: list[tuple[int, int]] = []
    for row, left in enumerate(basis):
        for col in range(row, len(basis)):
            sign, label = _entry_label(left, basis[col], n, graph_edges)
            if label is None:
                zero_entries.append((row, col))
            else:
                groups[label].append((row, col, sign))
    for row, col in zero_entries:
        constraints.append(matrix[row, col] == 0.0)
    for members in groups.values():
        anchor_row, anchor_col, anchor_sign = members[0]
        for row, col, sign in members[1:]:
            constraints.append(sign * matrix[row, col] == anchor_sign * matrix[anchor_row, anchor_col])

    singleton_diagonal = {
        vertex: matrix[index[(vertex,)], index[(vertex,)]] for vertex in range(n)
    }
    for vertices, bound in subset_cuts:
        constraints.append(cp.sum([singleton_diagonal[vertex] for vertex in vertices]) <= bound)
    objective = cp.Maximize(cp.sum(list(singleton_diagonal.values())))
    problem = cp.Problem(objective, constraints)
    value = problem.solve(
        solver=solver,
        tol_gap_abs=1e-9,
        tol_gap_rel=1e-9,
        tol_feas=1e-9,
        max_iter=500,
        verbose=False,
    )
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
        raise RuntimeError(f"SDP failed with status {problem.status}")
    eigenvalues = np.linalg.eigvalsh(np.asarray(matrix.value, dtype=float))
    return {
        "value": float(value),
        "status": problem.status,
        "max_degree": max(map(len, basis)),
        "matrix_size": len(basis),
        "constraint_count": len(constraints),
        "min_eigenvalue": float(eigenvalues[0]),
    }


def solve_theta(
    n: int,
    edges: Iterable[tuple[int, int]],
    order: int,
    *,
    subset_cuts: Iterable[tuple[tuple[int, ...], float]] = (),
    solver: str = "CLARABEL",
) -> dict[str, object]:
    """Solve the complete square-free basis through ``order``."""
    if not 1 <= order <= n:
        raise ValueError(f"order must lie in [1, {n}]")
    result = solve_theta_basis(
        n,
        edges,
        basis_subsets(n, order),
        subset_cuts=subset_cuts,
        solver=solver,
    )
    result["order"] = order
    return result


if __name__ == "__main__":
    from problem import EDGES, VERTICES

    for relaxation_order in (1, 2, 3):
        print(solve_theta(len(VERTICES), EDGES, relaxation_order), flush=True)
