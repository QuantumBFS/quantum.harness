"""Efficient stoquastic gauge for the fixed-partition C3 block-TN factory.

Let ``B=P diag(X_0,X_1,X_2)`` with TN blocks on a fixed partition.
``Gamma(diag(X_r))`` is entrywise nonnegative and preserves the three
block particle counts.  ``Gamma(P)`` is a signed permutation whose sign
depends only on those counts.  Since ``P**3=I``, the sign product on every
count orbit is positive, so one diagonal ``+/-1`` gauge removes all signs.
The same gauge works for every choice of TN blocks and both C3 directions.

Consequently every Hermitian factory Hamiltonian

``H=-sum_a q_a [Gamma(B_a)+Gamma(B_a).T]``

is stoquastic after an efficiently computable diagonal basis change.  This
closes fixed-partition odd block-TN as a QNC candidate even though its
determinant positivity and interacting Hamiltonians remain valid.
"""

from __future__ import annotations

from itertools import product

import numpy as np


def _forward_counts(counts: tuple[int, int, int]) -> tuple[int, int, int]:
    """Counts after the forward block permutation used by the C3 factory."""

    n0, n1, n2 = counts
    return n1, n2, n0


def _forward_fock_sign(counts: tuple[int, int, int]) -> int:
    """Fermionic reordering sign of the forward cyclic block permutation."""

    n0, n1, n2 = counts
    return -1 if (n0 * (n1 + n2)) % 2 else 1


def c3_count_gauge(block_size: int) -> dict[tuple[int, int, int], int]:
    """Return the common sign gauge on all block-count triples.

    The returned phase ``s[n]`` obeys

    ``s[rotate(n)] * sign(P,n) * s[n] = +1``.

    It is constructed orbit by orbit, so the cost is only
    ``O((block_size+1)^3)``.
    """

    if block_size < 1:
        raise ValueError("block_size must be positive")
    phases: dict[tuple[int, int, int], int] = {}
    for counts in product(range(block_size + 1), repeat=3):
        if counts in phases:
            continue
        phases[counts] = 1
        current = counts
        for _ in range(3):
            following = _forward_counts(current)
            expected = phases[current] * _forward_fock_sign(current)
            previous = phases.setdefault(following, expected)
            if previous != expected:
                raise AssertionError("C3 Fock signs have inconsistent holonomy")
            current = following
    return phases


def c3_fock_sign_gauge(block_size: int) -> np.ndarray:
    """Return the diagonal ``+/-1`` gauge in the occupation basis."""

    phases = c3_count_gauge(block_size)
    dimension = 1 << (3 * block_size)
    gauge = np.ones(dimension, dtype=np.int8)
    block_mask = (1 << block_size) - 1
    for state in range(dimension):
        counts = tuple(
            ((state >> (route * block_size)) & block_mask).bit_count()
            for route in range(3)
        )
        gauge[state] = phases[counts]  # type: ignore[index]
    return gauge


def diagonal_sign_transform(matrix: np.ndarray, gauge: np.ndarray) -> np.ndarray:
    """Return ``S matrix S`` without materializing diagonal ``S``."""

    candidate = np.asarray(matrix)
    signs = np.asarray(gauge)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise ValueError("matrix must be square")
    if signs.shape != (candidate.shape[0],):
        raise ValueError("gauge dimension must match matrix")
    if not np.all(np.isin(signs, (-1, 1))):
        raise ValueError("gauge entries must be +/-1")
    return signs[:, None] * candidate * signs[None, :]


def maximum_offdiagonal(matrix: np.ndarray) -> float:
    """Return the largest real off-diagonal entry."""

    candidate = np.asarray(matrix, dtype=float)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise ValueError("matrix must be square")
    offdiagonal = candidate.copy()
    np.fill_diagonal(offdiagonal, -np.inf)
    return float(np.max(offdiagonal))
