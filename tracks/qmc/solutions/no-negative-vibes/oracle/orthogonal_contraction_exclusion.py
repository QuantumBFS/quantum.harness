"""Conventional-method exclusion audits for the orthogonal candidate."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class CommonCommutantAudit:
    """Common one-particle reduction and Lie-closure diagnostics."""

    rank: int
    nullity: int
    smallest_nonzero_singular_value: float
    lie_closure_dimension: int


@dataclass(frozen=True)
class PauliFrustrationAudit:
    """JW Pauli expansion and an induced-claw obstruction."""

    terms: tuple[tuple[str, float], ...]
    edge_count: int
    minimum_degree: int
    maximum_degree: int
    claw_center: tuple[str, float] | None
    claw_leaves: tuple[tuple[str, float], ...]


def _independent_append(
    basis: list[np.ndarray],
    candidate: np.ndarray,
    *,
    tolerance: float,
) -> bool:
    vector = candidate.reshape(-1)
    if not basis:
        basis.append(candidate)
        return True
    design = np.column_stack([item.reshape(-1) for item in basis])
    coefficients, *_ = np.linalg.lstsq(design, vector, rcond=None)
    if np.linalg.norm(vector - design @ coefficients) <= tolerance:
        return False
    basis.append(candidate)
    return True


def common_commutant_audit(
    atoms: Sequence[np.ndarray],
    *,
    tolerance: float = 1e-11,
) -> CommonCommutantAudit:
    """Test common orbital blocks and compute the generated Lie algebra."""

    matrices = tuple(np.asarray(atom, dtype=float) for atom in atoms)
    if not matrices:
        raise ValueError("at least one atom is required")
    size = matrices[0].shape[0]
    if any(item.shape != (size, size) for item in matrices):
        raise ValueError("atoms must be square with one common size")
    identity = np.eye(size)
    commutator_design = np.vstack(
        [
            np.kron(identity, atom)
            - np.kron(atom.T, identity)
            for atom in matrices
        ]
    )
    singular_values = np.linalg.svd(
        commutator_design,
        compute_uv=False,
    )
    rank = int(np.sum(singular_values > tolerance))
    nonzero = singular_values[singular_values > tolerance]

    # Antisymmetric logarithms generate the relevant real Lie algebra.
    generators = [
        0.5 * (atom - atom.T)
        for atom in matrices
    ]
    lie_basis: list[np.ndarray] = []
    for generator in generators:
        _independent_append(
            lie_basis,
            generator,
            tolerance=tolerance,
        )
    changed = True
    while changed:
        changed = False
        current = tuple(lie_basis)
        for left in current:
            for right in current:
                changed = (
                    _independent_append(
                        lie_basis,
                        left @ right - right @ left,
                        tolerance=tolerance,
                    )
                    or changed
                )

    return CommonCommutantAudit(
        rank=rank,
        nullity=size * size - rank,
        smallest_nonzero_singular_value=(
            float(np.min(nonzero)) if len(nonzero) else 0.0
        ),
        lie_closure_dimension=len(lie_basis),
    )


def _pauli_anticommutes(first: str, second: str) -> bool:
    conflicts = sum(
        left != "I" and right != "I" and left != right
        for left, right in zip(first, second, strict=True)
    )
    return bool(conflicts % 2)


def pauli_frustration_audit(
    hamiltonian: np.ndarray,
    *,
    tolerance: float = 1e-10,
) -> PauliFrustrationAudit:
    """Expand a four-mode JW Hamiltonian and find an induced claw."""

    matrix = np.asarray(hamiltonian, dtype=complex)
    if matrix.shape != (16, 16):
        raise ValueError("audit requires a four-mode 16x16 Hamiltonian")
    paulis = {
        "I": np.eye(2),
        "X": np.asarray([[0, 1], [1, 0]], dtype=complex),
        "Y": np.asarray([[0, -1j], [1j, 0]], dtype=complex),
        "Z": np.diag([1, -1]),
    }
    terms: list[tuple[str, float]] = []
    for labels in product("IXYZ", repeat=4):
        operator = paulis[labels[3]]
        for qubit in (2, 1, 0):
            operator = np.kron(operator, paulis[labels[qubit]])
        coefficient = np.trace(operator.conj().T @ matrix) / 16.0
        if (
            labels != ("I", "I", "I", "I")
            and abs(coefficient) > tolerance
        ):
            if abs(coefficient.imag) > tolerance:
                raise AssertionError("Hermitian Pauli coefficient is complex")
            terms.append(("".join(labels), float(coefficient.real)))

    count = len(terms)
    adjacency = np.zeros((count, count), dtype=bool)
    for left in range(count):
        for right in range(left + 1, count):
            anticommutes = _pauli_anticommutes(
                terms[left][0],
                terms[right][0],
            )
            adjacency[left, right] = anticommutes
            adjacency[right, left] = anticommutes

    claw: tuple[int, tuple[int, int, int]] | None = None
    for center in range(count):
        neighbors = tuple(np.flatnonzero(adjacency[center]))
        for leaves in combinations(neighbors, 3):
            if all(
                not adjacency[left, right]
                for left, right in combinations(leaves, 2)
            ):
                claw = (center, leaves)
                break
        if claw is not None:
            break

    degrees = np.sum(adjacency, axis=1)
    return PauliFrustrationAudit(
        terms=tuple(terms),
        edge_count=int(np.sum(adjacency) // 2),
        minimum_degree=int(np.min(degrees)),
        maximum_degree=int(np.max(degrees)),
        claw_center=(terms[claw[0]] if claw is not None else None),
        claw_leaves=(
            tuple(terms[index] for index in claw[1])
            if claw is not None
            else ()
        ),
    )
