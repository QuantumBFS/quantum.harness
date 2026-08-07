from __future__ import annotations

from typing import Callable

import numpy as np


class OptimizeResult:
    def __init__(
        self,
        best_x: np.ndarray,
        best_noisy: float,
        best_exact: float,
        queries: int,
        queries_to_target: int | None,
    ) -> None:
        self.best_x = best_x
        self.best_noisy = best_noisy
        self.best_exact = best_exact
        self.queries = queries
        self.queries_to_target = queries_to_target


def nelder_mead(
    objective: Callable[[np.ndarray], tuple[float, float]],
    x0: np.ndarray,
    step: float,
    max_queries: int,
    target_exact: float,
) -> OptimizeResult:
    x0 = np.asarray(x0, dtype=float)
    dim = x0.size
    simplex = _initial_simplex(x0, step)
    values: list[tuple[float, float]] = []
    queries = 0
    queries_to_target: int | None = None
    best_x = simplex[0].copy()
    best_noisy = float("inf")
    best_exact = float("inf")

    def evaluate(point: np.ndarray) -> tuple[float, float]:
        nonlocal queries, queries_to_target, best_x, best_noisy, best_exact
        noisy, exact = objective(point)
        queries += 1
        if exact < best_exact:
            best_x = point.copy()
            best_exact = exact
        if noisy < best_noisy:
            best_noisy = noisy
        if queries_to_target is None and exact <= target_exact:
            queries_to_target = queries
        return noisy, exact

    for point in simplex:
        if queries >= max_queries:
            break
        values.append(evaluate(point))

    alpha = 1.0
    gamma = 2.0
    rho = 0.5
    sigma = 0.5

    while queries < max_queries and queries_to_target is None:
        order = np.argsort([value[0] for value in values])
        simplex = simplex[order]
        values = [values[index] for index in order]
        centroid = np.mean(simplex[:-1], axis=0)
        worst = simplex[-1]
        reflected = centroid + alpha * (centroid - worst)
        reflected_value = evaluate(reflected)
        if queries >= max_queries or queries_to_target is not None:
            break

        if reflected_value[0] < values[0][0]:
            expanded = centroid + gamma * (reflected - centroid)
            expanded_value = evaluate(expanded)
            if expanded_value[0] < reflected_value[0]:
                simplex[-1] = expanded
                values[-1] = expanded_value
            else:
                simplex[-1] = reflected
                values[-1] = reflected_value
            continue

        if reflected_value[0] < values[-2][0]:
            simplex[-1] = reflected
            values[-1] = reflected_value
            continue

        contracted = centroid + rho * (worst - centroid)
        contracted_value = evaluate(contracted)
        if contracted_value[0] < values[-1][0]:
            simplex[-1] = contracted
            values[-1] = contracted_value
            continue

        best = simplex[0].copy()
        for index in range(1, dim + 1):
            if queries >= max_queries or queries_to_target is not None:
                break
            simplex[index] = best + sigma * (simplex[index] - best)
            values[index] = evaluate(simplex[index])

    return OptimizeResult(best_x, best_noisy, best_exact, queries, queries_to_target)


def _initial_simplex(x0: np.ndarray, step: float) -> np.ndarray:
    dim = x0.size
    simplex = np.repeat(x0[None, :], dim + 1, axis=0)
    for index in range(dim):
        simplex[index + 1, index] += step
    return simplex
