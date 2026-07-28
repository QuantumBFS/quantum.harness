from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class OptimizeResult:
    best_x: np.ndarray
    best_value: float
    queries: int
    history: list[dict[str, float]]


def _clip(x: np.ndarray, bounds):
    if bounds is None:
        return x
    low, high = bounds
    return np.clip(x, low, high)


def nelder_mead(objective, x0: np.ndarray, step: float, max_queries: int, bounds=None) -> OptimizeResult:
    x0 = np.asarray(x0, dtype=float)
    dim = x0.size
    simplex = np.repeat(x0[None, :], dim + 1, axis=0)
    for index in range(dim):
        simplex[index + 1, index] += step
    simplex = _clip(simplex, bounds)
    values = []
    history: list[dict[str, float]] = []
    queries = 0
    best_x = simplex[0].copy()
    best_value = float("inf")

    def evaluate(point: np.ndarray) -> float:
        nonlocal queries, best_x, best_value
        value = float(objective(point))
        queries += 1
        if value < best_value:
            best_value = value
            best_x = point.copy()
        history.append({"query": float(queries), "value": value, "best_value": best_value})
        return value

    for point in simplex:
        if queries >= max_queries:
            break
        values.append(evaluate(point))

    alpha, gamma, rho, sigma = 1.0, 2.0, 0.5, 0.5
    while queries < max_queries:
        order = np.argsort(values)
        simplex = simplex[order]
        values = [values[index] for index in order]
        centroid = np.mean(simplex[:-1], axis=0)
        worst = simplex[-1]
        reflected = _clip(centroid + alpha * (centroid - worst), bounds)
        reflected_value = evaluate(reflected)
        if queries >= max_queries:
            break
        if reflected_value < values[0]:
            expanded = _clip(centroid + gamma * (reflected - centroid), bounds)
            expanded_value = evaluate(expanded)
            if expanded_value < reflected_value:
                simplex[-1] = expanded
                values[-1] = expanded_value
            else:
                simplex[-1] = reflected
                values[-1] = reflected_value
            continue
        if reflected_value < values[-2]:
            simplex[-1] = reflected
            values[-1] = reflected_value
            continue
        contracted = _clip(centroid + rho * (worst - centroid), bounds)
        contracted_value = evaluate(contracted)
        if contracted_value < values[-1]:
            simplex[-1] = contracted
            values[-1] = contracted_value
            continue
        best = simplex[0].copy()
        for index in range(1, dim + 1):
            if queries >= max_queries:
                break
            simplex[index] = _clip(best + sigma * (simplex[index] - best), bounds)
            values[index] = evaluate(simplex[index])
    return OptimizeResult(best_x=best_x, best_value=best_value, queries=queries, history=history)
