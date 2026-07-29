"""Exact Hodge reduction of the oddcycle grade-(3,4) sector."""

from __future__ import annotations

from collections.abc import Sequence

import sympy as sp

from .exterior_exact5_shared_cone import exact_compound_matrix
from .oddcycle_pair_physical import leading_pair_matrices


SCHEMA = "oddcycle-grade34-hodge-reduction-v1"
_GRADE4_GAUGE = sp.diag(1, 1, 1, -1, 1)
_EDGE_TO_TRIPLE = (0, 1, 3, 6, 2, 4, 7, 5, 8, 9)
_HODGE_SIGNS = (1, 1, -1, 1, 1, -1, 1, -1, 1, -1)


def _hodge_transform() -> sp.ImmutableMatrix:
    transform = sp.zeros(10)
    for edge, triple in enumerate(_EDGE_TO_TRIPLE):
        transform[edge, triple] = _HODGE_SIGNS[edge]
    return sp.ImmutableMatrix(transform)


def exact_symbolic_hodge_identity() -> dict[str, object]:
    """Verify ``wedge^2(P)=8 H wedge^3(B) H^T`` for symbolic ``p``."""

    p = sp.symbols("p", positive=True)
    matrix = sp.ImmutableMatrix(
        [
            [0, 0, 2, 0, 0],
            [2, 0, 0, 0, 0],
            [0, 2, 0, p, 0],
            [0, 0, 0, 1, 1],
            [0, 0, -1, 0, 1],
        ]
    )
    positive_grade4 = sp.ImmutableMatrix(
        _GRADE4_GAUGE
        * exact_compound_matrix(matrix, 4)
        * _GRADE4_GAUGE
    )
    transform = _hodge_transform()
    left = exact_compound_matrix(positive_grade4, 2)
    right = sp.ImmutableMatrix(
        8
        * transform
        * exact_compound_matrix(matrix, 3)
        * transform.T
    )
    identity = left == right
    transpose_identity = (
        exact_compound_matrix(positive_grade4.T, 2)
        == sp.ImmutableMatrix(
            8
            * transform
            * exact_compound_matrix(matrix.T, 3)
            * transform.T
        )
    )
    if not identity or not transpose_identity:
        raise RuntimeError("symbolic Hodge identity failed")
    return {
        "schema": SCHEMA,
        "status": "exact-symbolic-hodge-identity",
        "determinant_per_letter": 8,
        "grade4_atom_entrywise_nonnegative_for_p_positive": all(
            entry.is_nonnegative is not False for entry in positive_grade4
        ),
        "forward_identity": identity,
        "transpose_identity": transpose_identity,
        "edge_to_triple_permutation": _EDGE_TO_TRIPLE,
        "hodge_signs": _HODGE_SIGNS,
        "word_consequence": (
            "wedge^2(P_w)=8^n H wedge^3(W) H^T"
        ),
    }


def exact_word_grade34_reduction(word: str = "012301") -> dict[str, object]:
    """Replay the grade-(3,4) scalar reduction for one four-letter word."""

    pair = leading_pair_matrices()
    atoms = (pair[0], pair[0].T, pair[1], pair[1].T)
    product = sp.eye(5)
    positive_product = sp.eye(5)
    for symbol in word:
        if symbol not in {"0", "1", "2", "3"}:
            raise ValueError("word must contain only symbols 0,1,2,3")
        atom = atoms[int(symbol)]
        product = atom * product
        positive_atom = (
            _GRADE4_GAUGE
            * exact_compound_matrix(atom, 4)
            * _GRADE4_GAUGE
        )
        positive_product = positive_atom * positive_product
    length = len(word)
    determinant_growth = 8**length
    chi3 = sp.trace(exact_compound_matrix(product, 3))
    chi4 = sp.trace(exact_compound_matrix(product, 4))
    e2_positive = sp.trace(exact_compound_matrix(positive_product, 2))
    trace_positive = sp.trace(positive_product)
    hodge_matrix_identity = (
        exact_compound_matrix(positive_product, 2)
        == sp.ImmutableMatrix(
            determinant_growth
            * _hodge_transform()
            * exact_compound_matrix(product, 3)
            * _hodge_transform().T
        )
    )
    scalar_identity = (
        e2_positive + determinant_growth * trace_positive
        == determinant_growth * (chi3 + chi4)
    )
    if not hodge_matrix_identity or not scalar_identity:
        raise RuntimeError("word-level Hodge reduction failed")
    return {
        "schema": SCHEMA,
        "status": "exact-word-grade34-reduction",
        "word": word,
        "length": length,
        "determinant_growth": determinant_growth,
        "hodge_matrix_identity": hodge_matrix_identity,
        "scalar_identity": scalar_identity,
        "chi3": int(chi3),
        "chi4": int(chi4),
        "positive_grade4_trace": int(trace_positive),
        "positive_grade4_e2": int(e2_positive),
        "reduced_target": (
            "e2(P_w)+8^n trace(P_w)>0"
        ),
    }


__all__: Sequence[str] = (
    "SCHEMA",
    "exact_symbolic_hodge_identity",
    "exact_word_grade34_reduction",
)
