"""Exact exclusion of Wei's Majorana contraction class for the oddcycle alphabet.

The replay uses rational linear algebra and the frozen Gordan--Stiemke dual.
It does not call a solver, eigensolver, sampler, logarithm, or parameter scan.
"""

from __future__ import annotations

import hashlib
import json
import platform
import time

import sympy as sp

from .oddcycle_metric_dual import exact_no_common_metric_certificate
from .oddcycle_path_metric import EXACT_POINTS


SCHEMA = "oddcycle-majorana-wei-no-go-v1"
_DIMENSION = 5


def _base_matrix(p: str) -> sp.ImmutableMatrix:
    return sp.ImmutableMatrix(
        [
            [0, 0, 2, 0, 0],
            [2, 0, 0, 0, 0],
            [0, 2, 0, sp.Rational(p), 0],
            [0, 0, 0, 1, 1],
            [0, 0, -1, 0, 1],
        ]
    )


def exact_main_alphabet() -> tuple[sp.ImmutableMatrix, ...]:
    """Return the four exact one-particle letters used by the final theorem."""

    bases = tuple(_base_matrix(point[0]) for point in EXACT_POINTS)
    alphabet = tuple(atom for base in bases for atom in (base, base.T))
    if len(alphabet) != 4 or len(set(alphabet)) != 4:
        raise RuntimeError("the main alphabet must contain four distinct letters")
    if any(atom.shape != (_DIMENSION, _DIMENSION) for atom in alphabet):
        raise RuntimeError("every main-alphabet letter must be five-dimensional")
    if any(atom.det() != 8 for atom in alphabet):
        raise RuntimeError("every main-alphabet determinant must equal eight")
    return alphabet


def exact_commutant_certificate() -> dict[str, object]:
    """Prove by exact rank that the four-letter commutant is scalar."""

    alphabet = exact_main_alphabet()
    columns = []
    for row in range(_DIMENSION):
        for column in range(_DIMENSION):
            basis = sp.zeros(_DIMENSION)
            basis[row, column] = 1
            commutators = tuple(basis * atom - atom * basis for atom in alphabet)
            columns.append(
                sp.Matrix(
                    [
                        entry
                        for commutator in commutators
                        for entry in commutator
                    ]
                )
            )
    system = sp.Matrix.hstack(*columns)
    identity_vector = sp.Matrix(list(sp.eye(_DIMENSION)))
    if system * identity_vector != sp.zeros(system.rows, 1):
        raise RuntimeError("the identity must lie in the common commutant")
    rank = int(system.rank())
    if rank != 24:
        raise RuntimeError(
            f"expected exact commutant constraint rank 24, observed {rank}"
        )
    return {
        "ambient_dimension": _DIMENSION**2,
        "constraint_rank": rank,
        "nullity": _DIMENSION**2 - rank,
        "scalar_only": True,
    }


def _exact_dual_summary() -> dict[str, object]:
    """Replay the frozen dual and expose only the theorem-level exact gates.

    In the Nambu convention ``G(B)=diag(B**-1, B.T)``, the upper-left
    principal gaps are initially
    ``H-B**-T H B**-1`` and ``H-B**-1 H B**-T``.  Congruence by ``B.T`` and
    ``B`` puts ``R=-H`` into the two orientations of the frozen dual.  The
    lower-right gaps for ``D`` already have those orientations.

    Pairing positive-semidefinite gaps with four positive-definite
    multipliers gives nonnegative traces whose exact sum is zero.  Every
    diagonal-block gap is therefore zero; this is the meaning of
    ``nonstrict_gaps_forced_to_zero`` below.
    """

    dual = exact_no_common_metric_certificate()
    expected_status = "exact-no-common-quadratic-metric-certificate"
    leading_minors = dual.get("leading_principal_minor_numerators")
    gates = (
        dual.get("status") == expected_status,
        dual.get("cancellation_exact_zero") is True,
        dual.get("normalization_trace") == {"numerator": 1, "denominator": 1},
        dual.get("all_multipliers_positive_definite") is True,
        isinstance(leading_minors, list) and len(leading_minors) == 4,
        isinstance(leading_minors, list)
        and all(
            isinstance(record, list)
            and len(record) == _DIMENSION
            and all(minor > 0 for minor in record)
            for record in leading_minors
        ),
    )
    if not all(gates):
        raise RuntimeError("the frozen exact common-metric dual failed replay")
    return {
        "exact_cancellation": True,
        "normalization_trace": {"numerator": 1, "denominator": 1},
        "positive_definite_multipliers": 4,
        "nonstrict_gaps_forced_to_zero": True,
    }


def _exact_compatibility_certificate() -> dict[str, object]:
    """Check the orthogonal-complex-structure sign in exact symbolic algebra.

    Tensoring the two-dimensional coefficient matrices below with ``I_5``
    gives the full ten-dimensional identity.  A Hermitian boundary metric
    has coefficient matrix ``[[0,k],[conjugate(k),0]]``.  Its product with
    the Nambu bilinear form has sign ``+1``, whereas a Wei orthogonal complex
    structure requires sign ``-1``.
    """

    u, v = sp.symbols("u v", real=True)
    k = u + sp.I * v
    omega = sp.ImmutableMatrix([[0, 1], [1, 0]])
    boundary = sp.ImmutableMatrix([[0, k], [sp.conjugate(k), 0]])
    product = sp.simplify(boundary * omega * boundary.T)
    expected = sp.expand(u**2 + v**2) * omega
    if product != expected:
        raise RuntimeError("the exact Nambu boundary compatibility sign changed")
    return {
        "wei_sign": -1,
        "boundary_sign": 1,
        "compatible": False,
    }


def exact_nambu_boundary_certificate() -> dict[str, object]:
    """Reduce every possible nonstrict Wei metric to the scalar boundary.

    Exact duality forces all diagonal principal gaps to equality.  If a
    nonzero Hermitian diagonal block ``H`` obeyed both congruence equalities,
    its kernel would be invariant under the transpose-closed alphabet.
    Scalar commutant then makes the alphabet irreducible, so ``H`` would be
    invertible.  But ``B.T*H*B=H`` and ``det(B)=8`` imply
    ``det(H)=64*det(H)``, a contradiction.  Hence both diagonal blocks
    vanish.  Positivity with zero diagonal gaps forces the off-diagonal gap
    to vanish, so the off-diagonal block commutes with every letter and is
    ``k*I_5``.
    """

    dual = _exact_dual_summary()
    commutant = exact_commutant_certificate()
    alphabet = exact_main_alphabet()
    if not commutant["scalar_only"] or any(atom.det() ** 2 == 1 for atom in alphabet):
        raise RuntimeError("the exact scalar-boundary reduction failed")
    return {
        "dual": dual,
        "commutant": commutant,
        "boundary": {
            "diagonal_blocks_zero": True,
            "off_diagonal_block": "k*I_5",
        },
    }


def majorana_wei_no_go_summary() -> dict[str, object]:
    """Return the exact machine-readable Majorana/Wei exclusion certificate."""

    started = time.perf_counter()
    boundary = exact_nambu_boundary_certificate()
    compatibility = _exact_compatibility_certificate()
    alphabet = exact_main_alphabet()
    alphabet_summary = {
        "dimension": _DIMENSION,
        "points": tuple(point[0] for point in EXACT_POINTS),
        "letter_count": len(alphabet),
        "determinant": int(alphabet[0].det()),
    }
    payload = {
        "alphabet": alphabet_summary,
        "dual": boundary["dual"],
        "commutant": boundary["commutant"],
        "boundary": boundary["boundary"],
        "compatibility": compatibility,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    # Imported lazily so the final certificate can import this module without
    # creating a module-initialization cycle.
    from .oddcycle_final_certificate import _source_commit

    return {
        "schema": SCHEMA,
        "source_commit": _source_commit(),
        "status": "exact-no-wei-contraction-certificate",
        **payload,
        "exact_certificate_sha256": digest,
        "environment": {
            "python": platform.python_version(),
            "sympy": sp.__version__,
        },
        "exact_replay_wall_seconds": time.perf_counter() - started,
    }


__all__ = [
    "SCHEMA",
    "exact_commutant_certificate",
    "exact_main_alphabet",
    "exact_nambu_boundary_certificate",
    "majorana_wei_no_go_summary",
]


if __name__ == "__main__":  # pragma: no cover - exact replay CLI
    print(
        json.dumps(majorana_wei_no_go_summary(), indent=2, sort_keys=True),
        flush=True,
    )
