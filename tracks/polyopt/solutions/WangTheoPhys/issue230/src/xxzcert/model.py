"""XXZ model convention and finite-dimensional linear-algebra helpers."""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy import sparse

ComplexArray = NDArray[np.complex128]


def pauli() -> dict[str, ComplexArray]:
    """Return freshly allocated I, X, Y, and Z Pauli matrices."""
    return {
        "I": np.eye(2, dtype=np.complex128),
        "X": np.array([[0, 1], [1, 0]], dtype=np.complex128),
        "Y": np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
        "Z": np.array([[1, 0], [0, -1]], dtype=np.complex128),
    }


def local_xxz(delta: float) -> ComplexArray:
    """Return h_delta=(XX+YY+delta*ZZ)/4."""
    p = pauli()
    return (
        np.kron(p["X"], p["X"])
        + np.kron(p["Y"], p["Y"])
        + float(delta) * np.kron(p["Z"], p["Z"])
    ) / 4.0


def _embed_two_site(
    operator: ComplexArray, sites: int, first: int, second: int
) -> ComplexArray:
    """Embed a two-qubit operator on arbitrary sites using basis indexing."""
    dim = 1 << sites
    out = np.zeros((dim, dim), dtype=np.complex128)
    for row in range(dim):
        local_row = (((row >> (sites - 1 - first)) & 1) << 1) | (
            (row >> (sites - 1 - second)) & 1
        )
        for local_col in range(4):
            value = operator[local_row, local_col]
            if value == 0:
                continue
            col = row
            first_bit = (local_col >> 1) & 1
            second_bit = local_col & 1
            first_mask = 1 << (sites - 1 - first)
            second_mask = 1 << (sites - 1 - second)
            col = (col | first_mask) if first_bit else (col & ~first_mask)
            col = (col | second_mask) if second_bit else (col & ~second_mask)
            out[row, col] += value
    return out


def finite_xxz(delta: float, sites: int, periodic: bool = False) -> ComplexArray:
    """Return the finite open or periodic XXZ Hamiltonian.

    For two sites the periodic bond is counted once, avoiding the common
    double-counting ambiguity.
    """
    if sites < 2:
        raise ValueError("sites must be at least 2")
    h = local_xxz(delta)
    result = np.zeros((1 << sites, 1 << sites), dtype=np.complex128)
    for first in range(sites - 1):
        result += _embed_two_site(h, sites, first, first + 1)
    if periodic and sites > 2:
        result += _embed_two_site(h, sites, sites - 1, 0)
    return result


def finite_xxz_sparse(
    delta: float, sites: int, periodic: bool = False
) -> sparse.csr_matrix:
    """Sparse finite XXZ Hamiltonian in the computational basis."""
    if sites < 2:
        raise ValueError("sites must be at least 2")
    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []
    bonds = [(left, left + 1) for left in range(sites - 1)]
    if periodic and sites > 2:
        bonds.append((sites - 1, 0))
    for state in range(1 << sites):
        diagonal = 0.0
        for left, right in bonds:
            bit_l = (state >> (sites - 1 - left)) & 1
            bit_r = (state >> (sites - 1 - right)) & 1
            diagonal += delta / 4 if bit_l == bit_r else -delta / 4
            if bit_l != bit_r:
                flipped = state ^ (1 << (sites - 1 - left))
                flipped ^= 1 << (sites - 1 - right)
                rows.append(state)
                cols.append(flipped)
                values.append(0.5)
        rows.append(state)
        cols.append(state)
        values.append(diagonal)
    dim = 1 << sites
    return sparse.coo_matrix((values, (rows, cols)), shape=(dim, dim)).tocsr()


def partial_trace_edge(
    rho: ComplexArray, edge: Literal["left", "right"]
) -> ComplexArray:
    """Trace the leftmost or rightmost qubit from a square density matrix."""
    if rho.ndim != 2 or rho.shape[0] != rho.shape[1]:
        raise ValueError("rho must be square")
    dim = rho.shape[0]
    sites_float = np.log2(dim)
    sites = int(round(float(sites_float)))
    if (1 << sites) != dim or sites < 1:
        raise ValueError("rho dimension must be a positive power of two")
    tensor = rho.reshape((2,) * (2 * sites))
    axis = 0 if edge == "left" else sites - 1
    reduced = np.trace(tensor, axis1=axis, axis2=axis + sites)
    return reduced.reshape((1 << (sites - 1),) * 2)


def reduced_density(
    state: ComplexArray, keep: tuple[int, ...], sites: int | None = None
) -> ComplexArray:
    """Return a pure-state reduced density matrix on ordered sites in ``keep``."""
    vector = np.asarray(state, dtype=np.complex128).reshape(-1)
    if sites is None:
        sites = int(round(float(np.log2(vector.size))))
    if vector.size != 1 << sites:
        raise ValueError("state dimension does not match sites")
    if len(set(keep)) != len(keep) or any(i < 0 or i >= sites for i in keep):
        raise ValueError("invalid keep sites")
    discard = tuple(i for i in range(sites) if i not in keep)
    tensor = vector.reshape((2,) * sites)
    ordered = np.transpose(tensor, keep + discard)
    matrix = ordered.reshape(1 << len(keep), -1)
    return matrix @ matrix.conj().T
