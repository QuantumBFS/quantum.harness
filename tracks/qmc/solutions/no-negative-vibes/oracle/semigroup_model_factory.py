"""Turn a transpose-closed positive semigroup into Hermitian Fock models.

Suppose a real matrix family ``C`` is closed under multiplication and
transpose, and every word ``D`` in ``C`` obeys ``det(I+D) >= 0``.  For any
finite atoms ``B_a`` in ``C`` and positive coefficients ``q_a``, define

    H = -sum_a q_a [Gamma(B_a) + Gamma(B_a)^dagger].

The continuous-time expansion of ``exp(-beta H)`` has positive scalar
coefficients.  Every operator word is the Gaussian lift of a word in ``C``,
so its trace is a nonnegative determinant.  This construction is a model
factory built on an existing positivity theorem; it is not a new positivity
mechanism by itself.

Important: this module is a conditional constructor, not a membership oracle.
It accepts arbitrary real square atoms and does not prove that they belong to
such a semigroup.  Callers must supply the closure and determinant-positivity
theorem; otherwise the returned model can have negative word weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
from typing import Iterable, Sequence

import numpy as np

from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


@dataclass(frozen=True)
class HermitianSemigroupModel:
    one_particle_atoms: tuple[np.ndarray, ...]
    coefficients: tuple[float, ...]
    fock_atoms: tuple[np.ndarray, ...]
    hamiltonian: np.ndarray

    @property
    def modes(self) -> int:
        return self.one_particle_atoms[0].shape[0]


@dataclass(frozen=True)
class SemigroupWordWeight:
    word: tuple[tuple[int, bool], ...]
    one_particle_product: np.ndarray
    determinant_trace: float
    direct_fock_trace: float
    scalar_coefficient: float
    total_weight: float
    trace_identity_residual: float


def _real_square(matrix: np.ndarray, *, name: str) -> np.ndarray:
    candidate = np.asarray(matrix, dtype=float)
    if candidate.ndim != 2 or candidate.shape[0] != candidate.shape[1]:
        raise ValueError(f"{name} must be square")
    if candidate.shape[0] < 1:
        raise ValueError(f"{name} must be nonempty")
    if not np.all(np.isfinite(candidate)):
        raise ValueError(f"{name} must have finite entries")
    return candidate


def hermitian_semigroup_model(
    one_particle_atoms: Sequence[np.ndarray],
    coefficients: Sequence[float],
) -> HermitianSemigroupModel:
    """Construct ``-sum q_a [Gamma(B_a)+Gamma(B_a)^dagger]``."""

    atoms = tuple(
        _real_square(atom, name="one-particle atom")
        for atom in one_particle_atoms
    )
    strengths = tuple(float(value) for value in coefficients)
    if not atoms:
        raise ValueError("at least one atom is required")
    if len(atoms) != len(strengths):
        raise ValueError("atoms and coefficients must have equal length")
    shape = atoms[0].shape
    if any(atom.shape != shape for atom in atoms):
        raise ValueError("all atoms must have the same shape")
    if shape[0] > 10:
        raise ValueError("dense Fock construction is restricted to ten modes")
    if any(
        not math.isfinite(value) or value <= 0.0
        for value in strengths
    ):
        raise ValueError("coefficients must be positive and finite")

    fock_atoms = tuple(
        number_conserving_gaussian_fock_matrix(atom)
        for atom in atoms
    )
    fock_dimension = fock_atoms[0].shape[0]
    hamiltonian = np.zeros((fock_dimension, fock_dimension))
    for coefficient, fock in zip(strengths, fock_atoms, strict=True):
        hamiltonian -= coefficient * (fock + fock.T)
    return HermitianSemigroupModel(
        one_particle_atoms=atoms,
        coefficients=strengths,
        fock_atoms=fock_atoms,
        hamiltonian=hamiltonian,
    )


def semigroup_word_weight(
    model: HermitianSemigroupModel,
    word: Sequence[tuple[int, bool]],
) -> SemigroupWordWeight:
    """Evaluate one oriented continuous-time word.

    Each pair is ``(atom_index, transpose_atom)``.  Both orientations carry
    the same positive scalar coefficient in the Hermitian Hamiltonian.
    """

    oriented_word = tuple((int(index), bool(transpose)) for index, transpose in word)
    if not oriented_word:
        raise ValueError("word must contain at least one branch")
    if any(
        not 0 <= index < len(model.one_particle_atoms)
        for index, _ in oriented_word
    ):
        raise ValueError("word contains an invalid atom index")

    one_particle_product = np.eye(model.modes)
    fock_dimension = model.fock_atoms[0].shape[0]
    fock_product = np.eye(fock_dimension)
    scalar = 1.0
    for index, transpose in oriented_word:
        atom = model.one_particle_atoms[index]
        fock = model.fock_atoms[index]
        if transpose:
            atom = atom.T
            fock = fock.T
        one_particle_product = one_particle_product @ atom
        fock_product = fock_product @ fock
        scalar *= model.coefficients[index]

    determinant_trace = float(
        np.linalg.det(np.eye(model.modes) + one_particle_product)
    )
    direct_trace = float(np.trace(fock_product))
    return SemigroupWordWeight(
        word=oriented_word,
        one_particle_product=one_particle_product,
        determinant_trace=determinant_trace,
        direct_fock_trace=direct_trace,
        scalar_coefficient=scalar,
        total_weight=scalar * determinant_trace,
        trace_identity_residual=abs(direct_trace - determinant_trace),
    )


def oriented_branch_alphabet(
    model: HermitianSemigroupModel,
) -> tuple[tuple[int, bool], ...]:
    """Return all atom/transpose labels in the CT expansion."""

    return tuple(
        (index, transpose)
        for index in range(len(model.one_particle_atoms))
        for transpose in (False, True)
    )


def enumerate_semigroup_words(
    model: HermitianSemigroupModel,
    *,
    maximum_depth: int,
) -> Iterable[SemigroupWordWeight]:
    """Enumerate all nonempty oriented words through a small depth."""

    if maximum_depth < 1:
        raise ValueError("maximum_depth must be positive")
    alphabet = oriented_branch_alphabet(model)
    for depth in range(1, maximum_depth + 1):
        for word in product(alphabet, repeat=depth):
            yield semigroup_word_weight(model, word)
