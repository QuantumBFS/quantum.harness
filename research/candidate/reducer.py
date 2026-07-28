#!/usr/bin/env python3
"""Finite-abelian symmetry reduction for invariant Hermitian matrices."""

from __future__ import annotations

import itertools
from typing import Iterable

import numpy as np


def _elements(moduli: Iterable[int]):
    return itertools.product(*(range(int(n)) for n in moduli))


def _representation_element(generators: np.ndarray, element: tuple[int, ...]) -> np.ndarray:
    result = np.eye(generators.shape[1], dtype=np.complex128)
    for generator, power in zip(generators, element):
        result = result @ np.linalg.matrix_power(generator, power)
    return result


def character_projector(
    generators: np.ndarray, moduli: np.ndarray, character: tuple[int, ...]
) -> np.ndarray:
    """Return P_k = |G|^-1 sum_g conjugate(chi_k(g)) rho(g)."""
    dimension = generators.shape[1]
    projector = np.zeros((dimension, dimension), dtype=np.complex128)
    group_order = int(np.prod(moduli))
    for element in _elements(moduli):
        phase = sum(k * g / int(n) for k, g, n in zip(character, element, moduli))
        chi = np.exp(2j * np.pi * phase)
        projector += np.conjugate(chi) * _representation_element(generators, element)
    return (projector / group_order + (projector / group_order).conj().T) / 2


def reduce_invariant_hermitian(
    matrix: np.ndarray,
    generators: np.ndarray,
    moduli: np.ndarray,
    rank_tolerance: float = 1e-8,
) -> dict:
    """Project an invariant Hermitian matrix into all populated character sectors."""
    matrix = np.asarray(matrix, dtype=np.complex128)
    generators = np.asarray(generators, dtype=np.complex128)
    moduli = np.asarray(moduli, dtype=np.int64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("matrix must be square")
    if generators.shape != (len(moduli), matrix.shape[0], matrix.shape[1]):
        raise ValueError("generators must have shape (len(moduli), n, n)")
    if np.linalg.norm(matrix - matrix.conj().T) > 1e-9:
        raise ValueError("matrix must be Hermitian")

    sectors = []
    for character in _elements(moduli):
        projector = character_projector(generators, moduli, character)
        values, vectors = np.linalg.eigh(projector)
        basis = vectors[:, values > 1.0 - rank_tolerance]
        if basis.shape[1] == 0:
            continue
        block = basis.conj().T @ matrix @ basis
        block = (block + block.conj().T) / 2
        sectors.append(
            {
                "character": list(character),
                "basis": basis,
                "block": block,
                "eigenvalues": np.linalg.eigvalsh(block),
            }
        )

    if not sectors or sum(item["basis"].shape[1] for item in sectors) != matrix.shape[0]:
        raise ValueError("character projectors do not resolve the full representation")
    return {"dimension": matrix.shape[0], "moduli": moduli.tolist(), "sectors": sectors}
