from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


class OrderingError(ValueError):
    """An orbital ordering is not a strict permutation."""


@dataclass(frozen=True)
class OrderingCandidate:
    seed: int
    ordering: tuple[int, ...]
    cost: float


@dataclass(frozen=True)
class OrderingSelection:
    ordering: tuple[int, ...]
    cost: float
    candidates: tuple[OrderingCandidate, ...]


def validate_ordering(ordering: Any, n_orbitals: int) -> tuple[int, ...]:
    try:
        result = tuple(int(index) for index in ordering)
    except (TypeError, ValueError) as exc:
        raise OrderingError("ordering must be a permutation of integer orbitals") from exc
    if len(result) != n_orbitals or sorted(result) != list(range(n_orbitals)):
        raise OrderingError(
            f"ordering must be a permutation of 0..{n_orbitals - 1}; got {result}"
        )
    return result


def exchange_interaction_matrix(h1e: Any, g2e: Any) -> np.ndarray:
    one_body = np.asarray(h1e)
    two_body = np.asarray(g2e)
    if one_body.ndim == 3:
        one_body = one_body[0] + one_body[1]
    if two_body.ndim == 5:
        two_body = two_body[0] + two_body[1] * 2 + two_body[2]
    if one_body.ndim != 2 or two_body.ndim != 4:
        raise OrderingError("expected rank-2 h1e and rank-4 g2e arrays")
    exchange = np.abs(np.einsum("ijji->ij", two_body, optimize=True))
    return np.abs(one_body) * 1.0e-7 + exchange


def corrected_block2_ga_ordering(
    driver: Any,
    h1e: Any,
    g2e: Any,
    *,
    n_tasks: int = 64,
    base_seed: int = 1234,
    n_generations: int = 10_000,
    n_configs: int | None = None,
    n_elite: int = 8,
    clone_rate: float = 0.1,
    mutate_rate: float = 0.1,
) -> OrderingSelection:
    """Run block2 GA starts and select by evaluated cost, not tuple order.

    block2 0.5.3 computes every candidate cost in ``orbital_reordering`` but
    returns the lexicographically first unique tuple. This wrapper uses the same
    C++ optimizer and cost function while selecting the actual minimum.
    """

    if n_tasks < 1:
        raise OrderingError("n_tasks must be positive")
    interaction = exchange_interaction_matrix(h1e, g2e)
    n_orbitals = int(interaction.shape[0])
    backend = driver.bw.b
    kmat = backend.VectorDouble(interaction.ravel())
    options = {
        "n_generations": n_generations,
        "n_configs": n_configs or n_orbitals * 2,
        "n_elite": n_elite,
        "clone_rate": clone_rate,
        "mutate_rate": mutate_rate,
    }
    candidates: list[OrderingCandidate] = []
    for offset in range(n_tasks):
        seed = base_seed + offset
        backend.Random.rand_seed(seed)
        raw = backend.OrbitalOrdering.ga_opt(n_orbitals, kmat, **options)
        cost = float(
            backend.OrbitalOrdering.evaluate(n_orbitals, kmat, raw)
        )
        ordering = validate_ordering(raw, n_orbitals)
        candidates.append(
            OrderingCandidate(seed=seed, ordering=ordering, cost=cost)
        )
    best = min(candidates, key=lambda candidate: (candidate.cost, candidate.ordering))
    return OrderingSelection(
        ordering=best.ordering,
        cost=best.cost,
        candidates=tuple(candidates),
    )
