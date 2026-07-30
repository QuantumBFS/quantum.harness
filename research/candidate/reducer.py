#!/usr/bin/env python3
"""Finite-abelian symmetry reduction for invariant Hermitian matrices."""

from __future__ import annotations

import itertools
import math
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


def _validate_hermitian(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.complex128)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Hamiltonian must be a square matrix")
    scale = max(1.0, np.linalg.norm(matrix))
    if np.linalg.norm(matrix - matrix.conj().T) / scale > 1e-10:
        raise ValueError("Hamiltonian must be Hermitian")
    return matrix


def _perfect_power_candidates(dimension: int, local_dim=None, sites=None) -> list[tuple[int, int]]:
    if local_dim is not None and local_dim < 2:
        raise ValueError("local dimension must be at least two")
    if sites is not None and sites < 1:
        raise ValueError("site count must be positive")
    candidates = []
    dimensions = [int(local_dim)] if local_dim is not None else range(2, min(dimension, 9) + 1)
    for d in dimensions:
        if sites is not None:
            lengths = [int(sites)]
        else:
            minimum_sites = 1 if local_dim is not None else 2
            lengths = range(minimum_sites, int(math.log(dimension, d)) + 2)
        for length in lengths:
            if d**length == dimension:
                candidates.append((d, length))
    return sorted(set(candidates), key=lambda item: (item[0], item[1]))


def _local_spin_operators(local_dim: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    spin = (local_dim - 1) / 2
    magnetic = np.arange(spin, -spin - 1, -1, dtype=float)
    raising = np.zeros((local_dim, local_dim), dtype=np.complex128)
    for column in range(1, local_dim):
        m = magnetic[column]
        raising[column - 1, column] = np.sqrt(spin * (spin + 1) - m * (m + 1))
    lowering = raising.conj().T
    return (raising + lowering) / 2, (raising - lowering) / (2j), np.diag(magnetic)


def _embed_local(operator: np.ndarray, site: int, local_dim: int, sites: int) -> np.ndarray:
    result = np.ones((1, 1), dtype=np.complex128)
    identity = np.eye(local_dim, dtype=np.complex128)
    for index in range(sites):
        result = np.kron(result, operator if index == site else identity)
    return result


def spin_generators(local_dim: int, sites: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    local = _local_spin_operators(local_dim)
    total = []
    for operator in local:
        embedded = sum(
            (_embed_local(operator, site, local_dim, sites) for site in range(sites)),
            np.zeros((local_dim**sites, local_dim**sites), dtype=np.complex128),
        )
        total.append(embedded)
    return tuple(total)


def _normalized_commutator(matrix: np.ndarray, operator: np.ndarray) -> float:
    denominator = max(1.0, np.linalg.norm(matrix) * np.linalg.norm(operator))
    return float(np.linalg.norm(matrix @ operator - operator @ matrix) / denominator)


def _global_spin_flip(local_dim: int, sites: int) -> np.ndarray:
    if local_dim != 2:
        raise ValueError("the built-in Z2 spin-flip template currently requires local_dim=2")
    flip = np.array([[0, 1], [1, 0]], dtype=np.complex128)
    result = np.ones((1, 1), dtype=np.complex128)
    for _ in range(sites):
        result = np.kron(result, flip)
    return result


def _translation_operator(local_dim: int, sites: int) -> np.ndarray:
    shape = (local_dim,) * sites
    linear = np.arange(local_dim**sites).reshape(shape)
    operator = np.zeros((local_dim**sites, local_dim**sites), dtype=np.complex128)
    for state in np.ndindex(shape):
        shifted = state[1:] + state[:1]
        operator[linear[shifted], linear[state]] = 1
    return operator


def _template_operators(symmetry: str, local_dim: int, sites: int) -> tuple[list[np.ndarray], list[int] | None]:
    if symmetry == "su2":
        return list(spin_generators(local_dim, sites)), None
    if symmetry == "u1":
        return [spin_generators(local_dim, sites)[2]], None
    if symmetry == "z2":
        return [_global_spin_flip(local_dim, sites)], [2]
    if symmetry == "translation":
        return [_translation_operator(local_dim, sites)], [sites]
    raise ValueError(f"unsupported symmetry: {symmetry}")


def match_symmetry_template(matrix: np.ndarray, symmetry: str, *, local_dim=None, sites=None,
                            tolerance: float = 1e-10) -> dict:
    matrix = _validate_hermitian(matrix)
    requested = symmetry.lower()
    names = ("su2", "u1", "z2", "translation") if requested == "auto" else (requested,)
    matches = []
    attempted = []
    for d, length in _perfect_power_candidates(matrix.shape[0], local_dim, sites):
        for name in names:
            try:
                operators, moduli = _template_operators(name, d, length)
            except ValueError:
                continue
            residuals = [_normalized_commutator(matrix, operator) for operator in operators]
            candidate = {
                "symmetry": name,
                "local_dim": d,
                "sites": length,
                "residual": max(residuals, default=0.0),
                "generator_residuals": residuals,
                "operators": operators,
                "moduli": moduli,
            }
            attempted.append(candidate)
            if candidate["residual"] <= tolerance:
                matches.append(candidate)
    if not matches:
        best = min(attempted, key=lambda item: item["residual"], default=None)
        detail = "no dimension-compatible template"
        if best is not None:
            detail = (f'best candidate was {best["symmetry"]} on {best["sites"]} sites '
                      f'with local_dim={best["local_dim"]}, residual={best["residual"]:.3e}')
        raise ValueError(f"no symmetry template matched: {detail}")
    if len(matches) > 1:
        descriptions = ", ".join(
            f'{item["symmetry"]}:{item["sites"]}x{item["local_dim"]}' for item in matches
        )
        raise ValueError(
            f"ambiguous symmetry representation ({descriptions}); specify --local-dim and/or --sites"
        )
    return matches[0]


def _reduce_generator_sectors(matrix: np.ndarray, generator: np.ndarray, label: str,
                              tolerance: float) -> list[dict]:
    values, vectors = np.linalg.eigh((generator + generator.conj().T) / 2)
    sectors = []
    used = np.zeros(len(values), dtype=bool)
    for index, value in enumerate(values):
        if used[index]:
            continue
        selected = np.abs(values - value) <= tolerance
        used |= selected
        basis = vectors[:, selected]
        block = basis.conj().T @ matrix @ basis
        sectors.append({
            "label": {label: float(value)},
            "basis": basis,
            "block": (block + block.conj().T) / 2,
            "irrep_dimension": 1,
            "multiplicity": basis.shape[1],
        })
    return sectors


def _reduce_su2(matrix: np.ndarray, match: dict, tolerance: float) -> list[dict]:
    jx, jy, jz = match["operators"]
    j2 = jx @ jx + jy @ jy + jz @ jz
    diagonal = np.real(np.diag(jz))
    maximum_spin = match["sites"] * (match["local_dim"] - 1) / 2
    sectors = []
    twice_spin = int(round(2 * maximum_spin))
    for twice_j in range(twice_spin % 2, twice_spin + 1, 2):
        spin = twice_j / 2
        indices = np.flatnonzero(np.abs(diagonal - spin) <= tolerance)
        if len(indices) == 0:
            continue
        restricted = j2[np.ix_(indices, indices)]
        values, vectors = np.linalg.eigh((restricted + restricted.conj().T) / 2)
        selected = np.abs(values - spin * (spin + 1)) <= max(tolerance, 1e-8)
        basis = np.eye(matrix.shape[0], dtype=np.complex128)[:, indices] @ vectors[:, selected]
        if basis.shape[1] == 0:
            continue
        block = basis.conj().T @ matrix @ basis
        sectors.append({
            "label": {"spin": spin},
            "basis": basis,
            "block": (block + block.conj().T) / 2,
            "irrep_dimension": twice_j + 1,
            "multiplicity": basis.shape[1],
        })
    return sectors


def decompose_by_template(matrix: np.ndarray, symmetry: str, *, local_dim=None, sites=None,
                          tolerance: float = 1e-10) -> dict:
    matrix = _validate_hermitian(matrix)
    match = match_symmetry_template(matrix, symmetry, local_dim=local_dim, sites=sites,
                                    tolerance=tolerance)
    if match["symmetry"] == "su2":
        sectors = _reduce_su2(matrix, match, tolerance)
    elif match["symmetry"] == "u1":
        sectors = _reduce_generator_sectors(matrix, match["operators"][0], "charge", tolerance)
    else:
        abelian = reduce_invariant_hermitian(matrix, np.asarray(match["operators"]),
                                             np.asarray(match["moduli"]))
        sectors = [
            {
                "label": {"character": sector["character"]},
                "basis": sector["basis"],
                "block": sector["block"],
                "irrep_dimension": 1,
                "multiplicity": sector["block"].shape[0],
            }
            for sector in abelian["sectors"]
        ]
    dense_spectrum = np.linalg.eigvalsh(matrix)
    reconstructed_spectrum = np.sort(np.concatenate([
        np.repeat(np.linalg.eigvalsh(sector["block"]), sector["irrep_dimension"])
        for sector in sectors
    ]))
    completeness = sum(sector["multiplicity"] * sector["irrep_dimension"] for sector in sectors)
    if completeness != matrix.shape[0] or len(reconstructed_spectrum) != matrix.shape[0]:
        raise ValueError("symmetry sectors do not reconstruct the full Hilbert space")
    return {
        "symmetry": match["symmetry"],
        "dimension": matrix.shape[0],
        "local_dim": match["local_dim"],
        "sites": match["sites"],
        "commutator_residual": match["residual"],
        "spectrum_reconstruction_error": float(np.max(np.abs(dense_spectrum - reconstructed_spectrum))),
        "sectors": sectors,
    }
