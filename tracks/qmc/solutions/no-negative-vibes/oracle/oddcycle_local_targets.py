"""Exact named local Hamiltonian targets for odd-cycle reconstruction."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import sympy as sp

from oracle.fock_basis import quadratic_term
from oracle.oddcycle_local_hs_scan import LocalitySpec, locality_specs
from oracle.oddcycle_word_operator import (
    NormalOrderedLabel,
    normal_ordered_monomial,
)


_MODES = 5
_T_VALUES = (sp.Rational(1, 2), sp.Rational(1), sp.Rational(2))
_INTERACTION_VALUES = (
    sp.Rational(-2),
    sp.Rational(-1),
    sp.Rational(-1, 2),
    sp.Rational(1, 2),
    sp.Rational(1),
    sp.Rational(2),
)


@dataclass(frozen=True)
class TargetPoint:
    """One exact rational point in a named local Hamiltonian family."""

    target_id: str
    family: str
    formula: str
    parameters: tuple[tuple[str, sp.Rational], ...]
    hamiltonian: sp.ImmutableSparseMatrix
    locality: LocalitySpec


def hermitian_hop(modes: int, i: int, j: int) -> sp.ImmutableSparseMatrix:
    """Return ``c_i^dagger c_j + c_j^dagger c_i`` exactly."""

    return sp.ImmutableSparseMatrix(
        quadratic_term(modes, "hop", i, j)
        + quadratic_term(modes, "hop", j, i)
    )


def density(modes: int, i: int) -> sp.ImmutableSparseMatrix:
    """Return the exact occupation operator on one mode."""

    return quadratic_term(modes, "hop", i, i)


def density_density(
    modes: int, i: int, j: int
) -> sp.ImmutableSparseMatrix:
    """Return the exact density interaction ``n_i n_j``."""

    return sp.ImmutableSparseMatrix(density(modes, i) * density(modes, j))


def _operator_sum(
    operators: tuple[sp.MatrixBase, ...],
) -> sp.ImmutableSparseMatrix:
    result = sp.zeros(1 << _MODES)
    for operator in operators:
        result += operator
    return sp.ImmutableSparseMatrix(result)


def _rational_token(value: sp.Rational) -> str:
    prefix = "m" if value.p < 0 else ""
    numerator = abs(int(value.p))
    if value.q == 1:
        return f"{prefix}{numerator}"
    return f"{prefix}{numerator}over{int(value.q)}"


def _target_id(
    family: str, parameters: tuple[tuple[str, sp.Rational], ...]
) -> str:
    fields = "--".join(
        f"{name}-{_rational_token(value)}" for name, value in parameters
    )
    return f"{family}--{fields}"


def _target_point(
    family: str,
    formula: str,
    parameters: tuple[tuple[str, sp.Rational], ...],
    hamiltonian: sp.MatrixBase,
    locality: LocalitySpec,
) -> TargetPoint:
    return TargetPoint(
        target_id=_target_id(family, parameters),
        family=family,
        formula=formula,
        parameters=parameters,
        hamiltonian=sp.ImmutableSparseMatrix(hamiltonian),
        locality=locality,
    )


@cache
def first_target_library() -> tuple[TargetPoint, ...]:
    """Return the deterministic first exact local target portfolio."""

    specs = locality_specs()
    path_edges = tuple((index, index + 1) for index in range(4))
    ring_edges = (*path_edges, (4, 0))
    path_hopping = _operator_sum(
        tuple(hermitian_hop(_MODES, *edge) for edge in path_edges)
    )
    path_interaction = _operator_sum(
        tuple(density_density(_MODES, *edge) for edge in path_edges)
    )
    ring_interaction = _operator_sum(
        tuple(density_density(_MODES, *edge) for edge in ring_edges)
    )
    frustrated_ring_hopping = sp.ImmutableSparseMatrix(
        -sum(
            (
                hermitian_hop(_MODES, *edge)
                for edge in path_edges
            ),
            sp.zeros(1 << _MODES),
        )
        + hermitian_hop(_MODES, 4, 0)
    )

    targets = []
    for hopping in _T_VALUES:
        for interaction in _INTERACTION_VALUES:
            parameters = (("t", hopping), ("V", interaction))
            targets.append(
                _target_point(
                    "path-t-v",
                    (
                        "H=-t sum_(i=0)^3 (c_i^dagger c_(i+1)+h.c.)"
                        "+V sum_(i=0)^3 n_i n_(i+1)"
                    ),
                    parameters,
                    -hopping * path_hopping
                    + interaction * path_interaction,
                    specs["path-edge"],
                )
            )
            targets.append(
                _target_point(
                    "ring-frustrated-t-v",
                    (
                        "H=-t sum_(i=0)^3 (c_i^dagger c_(i+1)+h.c.)"
                        "+t(c_4^dagger c_0+h.c.)"
                        "+V sum_<ij>_ring n_i n_j"
                    ),
                    parameters,
                    hopping * frustrated_ring_hopping
                    + interaction * ring_interaction,
                    specs["ring-edge"],
                )
            )

    correlated_terms = _operator_sum(
        tuple(
            normal_ordered_monomial(
                _MODES,
                NormalOrderedLabel(
                    create=(offset, offset + 1),
                    annihilate=(offset + 1, offset + 2),
                ),
            )
            + normal_ordered_monomial(
                _MODES,
                NormalOrderedLabel(
                    create=(offset + 1, offset + 2),
                    annihilate=(offset, offset + 1),
                ),
            )
            for offset in range(3)
        )
    )
    pair_hop_terms = _operator_sum(
        tuple(
            normal_ordered_monomial(
                _MODES,
                NormalOrderedLabel(
                    create=(offset, offset + 1),
                    annihilate=(offset + 2, offset + 3),
                ),
            )
            + normal_ordered_monomial(
                _MODES,
                NormalOrderedLabel(
                    create=(offset + 2, offset + 3),
                    annihilate=(offset, offset + 1),
                ),
            )
            for offset in range(2)
        )
    )
    pair_hop_locality = LocalitySpec(
        "path-arc4-target",
        2,
        (
            frozenset((0, 1, 2, 3)),
            frozenset((1, 2, 3, 4)),
        ),
    )
    for coupling in _INTERACTION_VALUES:
        parameters = (("J", coupling),)
        targets.append(
            _target_point(
                "path-correlated-hop",
                (
                    "H=J sum_(i=0)^2 "
                    "(c_i^dagger c_(i+1)^dagger "
                    "c_(i+2) c_(i+1)+h.c.)"
                ),
                parameters,
                coupling * correlated_terms,
                specs["path-arc3"],
            )
        )
        targets.append(
            _target_point(
                "path-pair-hop",
                (
                    "H=J sum_(i=0)^1 "
                    "(c_i^dagger c_(i+1)^dagger "
                    "c_(i+3) c_(i+2)+h.c.)"
                ),
                parameters,
                coupling * pair_hop_terms,
                pair_hop_locality,
            )
        )
    return tuple(targets)


__all__ = [
    "TargetPoint",
    "density",
    "density_density",
    "first_target_library",
    "hermitian_hop",
]
