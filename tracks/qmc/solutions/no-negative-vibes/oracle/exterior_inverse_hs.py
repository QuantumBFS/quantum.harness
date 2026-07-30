"""Exact inverse Hamiltonian/HS map for transpose-paired exterior cards.

For a real one-particle matrix ``B``, let ``Gamma(B)`` denote its
number-conserving action on the complete fermionic Fock space.  Every exterior
candidate card contains the pair ``(B, B.T)`` with one shared positive
coefficient ``q``.  Therefore

``H = -q * (Gamma(B) + Gamma(B.T))``

is an exactly Hermitian (generally nonlocal) Hamiltonian, and ``-H`` is an
exact positive-coefficient two-branch Gaussian decomposition.  This module
checks the identity with rational arithmetic; it deliberately does not claim
that the resulting determinant histories are nonnegative at arbitrary depth.
That separate claim requires a semigroup/cone certificate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations, product

import sympy as sp

from oracle.exterior_candidates import candidate_id, exact_atoms_from_card


# Exact shallow sector-trace probe survivors for the five-mode odd-cycle
# grammar.  These are search priorities, not arbitrary-depth certificates.
TRACE_CLEAN_EXACT5_ODDCYCLE_SEEDS = (
    13,
    61,
    97,
    100,
    117,
    124,
    132,
    147,
    211,
    238,
    244,
)


@dataclass(frozen=True)
class ExactInverseHS:
    """Exact two-branch inverse construction for one candidate card."""

    card_id: str
    template: str
    seed: int
    coefficient: sp.Rational
    one_particle_branches: tuple[sp.ImmutableMatrix, sp.ImmutableMatrix]
    gaussian_branches: tuple[
        sp.ImmutableSparseMatrix,
        sp.ImmutableSparseMatrix,
    ]
    hamiltonian: sp.ImmutableSparseMatrix

    @property
    def minus_hamiltonian(self) -> sp.ImmutableSparseMatrix:
        """Return the positive Gaussian-branch sum ``-H``."""

        return sp.ImmutableSparseMatrix(-self.hamiltonian)


@dataclass(frozen=True)
class ExactHistoryWeight:
    """Exact equality between one Fock trace and one determinant history."""

    word: tuple[int, ...]
    scalar_coefficient: sp.Rational
    fock_trace: sp.Expr
    determinant: sp.Expr
    total_weight: sp.Expr


@dataclass(frozen=True)
class ExactTaylorTrace:
    """One exact Taylor-order equality for the reconstructed Hamiltonian."""

    order: int
    direct_trace: sp.Expr
    auxiliary_sum: sp.Expr


def _subsets(size: int, particles: int) -> tuple[tuple[int, ...], ...]:
    return tuple(combinations(range(size), particles))


def exact_gaussian_fock_lift(
    one_particle_matrix: sp.MatrixBase,
) -> sp.ImmutableSparseMatrix:
    """Return ``Gamma(B)`` exactly in occupation-bit-mask order.

    The matrix element between equally occupied sectors is the corresponding
    minor of ``B``.  This is the direct sum of all exterior powers.
    """

    if one_particle_matrix.rows != one_particle_matrix.cols:
        raise ValueError("one_particle_matrix must be square")
    modes = one_particle_matrix.rows
    if modes < 1:
        raise ValueError("one_particle_matrix must be nonempty")
    matrix = sp.ImmutableMatrix(one_particle_matrix)

    entries: dict[tuple[int, int], sp.Expr] = {(0, 0): sp.Integer(1)}
    for particles in range(1, modes + 1):
        subsets = _subsets(modes, particles)
        for row_subset in subsets:
            row_mask = sum(1 << index for index in row_subset)
            for column_subset in subsets:
                column_mask = sum(1 << index for index in column_subset)
                minor = sp.det(matrix.extract(row_subset, column_subset))
                if minor != 0:
                    entries[(row_mask, column_mask)] = minor
    dimension = 1 << modes
    return sp.ImmutableSparseMatrix(dimension, dimension, entries)


def _positive_orbit_coefficient(card: Mapping[str, object]) -> sp.Rational:
    orbits = card.get("orbits")
    if not isinstance(orbits, list) or len(orbits) != 1:
        raise ValueError("card must have exactly one coefficient orbit")
    orbit = orbits[0]
    if not isinstance(orbit, Mapping):
        raise TypeError("card coefficient orbit must be a mapping")
    encoded = orbit.get("coefficient")
    if not isinstance(encoded, Mapping) or set(encoded) != {
        "numerator",
        "denominator",
    }:
        raise ValueError("card coefficient must be a canonical rational")
    numerator = encoded["numerator"]
    denominator = encoded["denominator"]
    if (
        not isinstance(numerator, int)
        or isinstance(numerator, bool)
        or not isinstance(denominator, int)
        or isinstance(denominator, bool)
        or denominator <= 0
    ):
        raise ValueError("card coefficient must have integer numerator/denominator")
    coefficient = sp.Rational(numerator, denominator)
    if coefficient <= 0:
        raise ValueError("card coefficient must be strictly positive")
    return coefficient


def inverse_hs_from_card(card: Mapping[str, object]) -> ExactInverseHS:
    """Construct the exact Hermitian Hamiltonian and its two HS branches."""

    atoms = exact_atoms_from_card(card)
    if len(atoms) != 2 or atoms[1] != atoms[0].T:
        raise ValueError("inverse construction requires one transpose pair")
    coefficient = _positive_orbit_coefficient(card)
    gaussian_branches = tuple(
        exact_gaussian_fock_lift(atom) for atom in atoms
    )
    if gaussian_branches[1] != gaussian_branches[0].T:
        raise ArithmeticError("Fock lift failed to preserve transposition")

    minus_hamiltonian = coefficient * (
        gaussian_branches[0] + gaussian_branches[1]
    )
    hamiltonian = sp.ImmutableSparseMatrix(-minus_hamiltonian)
    if hamiltonian != hamiltonian.T:
        raise ArithmeticError("reconstructed Hamiltonian is not Hermitian")

    template = card.get("template")
    seed = card.get("seed")
    if not isinstance(template, str):
        raise TypeError("card template must be a string")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("card seed must be an integer")
    return ExactInverseHS(
        card_id=candidate_id(card),
        template=template,
        seed=seed,
        coefficient=coefficient,
        one_particle_branches=(atoms[0], atoms[1]),
        gaussian_branches=(gaussian_branches[0], gaussian_branches[1]),
        hamiltonian=hamiltonian,
    )


def exact_history_weight(
    decomposition: ExactInverseHS,
    word: Sequence[int],
) -> ExactHistoryWeight:
    """Check ``Tr prod Gamma(B_s) = det(I + prod B_s)`` exactly."""

    branch_word = tuple(word)
    if any(
        not isinstance(index, int)
        or isinstance(index, bool)
        or index not in (0, 1)
        for index in branch_word
    ):
        raise ValueError("word entries must be branch indices 0 or 1")

    modes = decomposition.one_particle_branches[0].rows
    one_particle_product = sp.eye(modes)
    fock_product = sp.eye(1 << modes)
    for index in branch_word:
        one_particle_product *= decomposition.one_particle_branches[index]
        fock_product *= decomposition.gaussian_branches[index]

    fock_trace = sp.expand(sp.trace(fock_product))
    determinant = sp.expand(sp.det(sp.eye(modes) + one_particle_product))
    if fock_trace != determinant:
        raise ArithmeticError("Fock trace and determinant identity disagree")
    scalar = decomposition.coefficient ** len(branch_word)
    return ExactHistoryWeight(
        word=branch_word,
        scalar_coefficient=scalar,
        fock_trace=fock_trace,
        determinant=determinant,
        total_weight=sp.expand(scalar * determinant),
    )


def exact_taylor_trace(
    decomposition: ExactInverseHS,
    order: int,
) -> ExactTaylorTrace:
    """Compare ``Tr[(-H)^order]`` to the complete auxiliary-field sum."""

    if not isinstance(order, int) or isinstance(order, bool) or order < 0:
        raise ValueError("order must be a nonnegative integer")
    direct = sp.expand(
        sp.trace(decomposition.minus_hamiltonian ** order)
    )
    auxiliary = sp.expand(
        sum(
            (
                exact_history_weight(decomposition, word).total_weight
                for word in product((0, 1), repeat=order)
            ),
            start=sp.Integer(0),
        )
    )
    if direct != auxiliary:
        raise ArithmeticError("Hamiltonian Taylor trace and HS sum disagree")
    return ExactTaylorTrace(
        order=order,
        direct_trace=direct,
        auxiliary_sum=auxiliary,
    )


__all__ = [
    "ExactHistoryWeight",
    "ExactInverseHS",
    "ExactTaylorTrace",
    "TRACE_CLEAN_EXACT5_ODDCYCLE_SEEDS",
    "exact_gaussian_fock_lift",
    "exact_history_weight",
    "exact_taylor_trace",
    "inverse_hs_from_card",
]
