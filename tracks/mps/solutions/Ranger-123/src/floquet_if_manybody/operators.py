"""Spin-half operators with a documented computational-basis convention."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

ComplexMatrix = NDArray[np.complex128]

_PAULI: dict[str, ComplexMatrix] = {
    "i": np.eye(2, dtype=np.complex128),
    "x": np.array([[0, 1], [1, 0]], dtype=np.complex128),
    "y": np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
    "z": np.array([[1, 0], [0, -1]], dtype=np.complex128),
}


def pauli(name: str) -> ComplexMatrix:
    try:
        return _PAULI[name.lower()].copy()
    except KeyError as exc:
        raise ValueError(f"unknown Pauli operator {name!r}") from exc


def tensor_product(operators: list[ComplexMatrix]) -> ComplexMatrix:
    if not operators:
        raise ValueError("operators must not be empty")
    result = np.array([[1.0 + 0.0j]])
    for operator in operators:
        result = np.kron(result, operator)
    return result


def site_operator(name: str, site: int, n: int) -> ComplexMatrix:
    if n < 1 or not 0 <= site < n:
        raise ValueError("site must satisfy 0 <= site < n")
    factors = [pauli("i") for _ in range(n)]
    factors[site] = pauli(name)
    return tensor_product(factors)


def product_operator(terms: dict[int, str], n: int) -> ComplexMatrix:
    factors = [pauli("i") for _ in range(n)]
    for site, name in terms.items():
        if not 0 <= site < n:
            raise ValueError("site must satisfy 0 <= site < n")
        factors[site] = pauli(name)
    return tensor_product(factors)


def collective_operator(name: str, n: int, eta: float = 1.0) -> ComplexMatrix:
    if n < 1:
        raise ValueError("n must be positive")
    result = np.zeros((2**n, 2**n), dtype=np.complex128)
    for site in range(n):
        result += site_operator(name, site, n)
    return np.asarray(eta * result, dtype=np.complex128)


def swap_operator(first: int, second: int, n: int) -> ComplexMatrix:
    """Permutation matrix that swaps two spin sites."""
    if first == second or not (0 <= first < n and 0 <= second < n):
        raise ValueError("swap sites must be distinct valid indices")
    out = np.zeros((2**n, 2**n), dtype=np.complex128)
    for column in range(2**n):
        bits = list(format(column, f"0{n}b"))
        bits[first], bits[second] = bits[second], bits[first]
        row = int("".join(bits), 2)
        out[row, column] = 1
    return out
