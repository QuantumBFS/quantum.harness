"""Independent exact audit of the seed-61 redundant-cone certificate.

This module deliberately does not call the cone-search certificate builder or
its compound-matrix helper.  It decodes the frozen exact card and result,
rebuilds exterior powers directly from minors, and checks what the resulting
intertwining identities do and do not prove.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from itertools import combinations
from pathlib import Path

import sympy as sp

from .exterior_candidates import candidate_card
from .exterior_inverse_hs import (
    exact_history_weight,
    inverse_hs_from_card,
)


def _decode_rational(payload: object) -> sp.Rational:
    if not isinstance(payload, Mapping):
        raise TypeError("rational payload must be a mapping")
    if set(payload) != {"numerator", "denominator"}:
        raise ValueError("rational payload has invalid fields")
    numerator = payload["numerator"]
    denominator = payload["denominator"]
    if (
        not isinstance(numerator, int)
        or isinstance(numerator, bool)
        or not isinstance(denominator, int)
        or isinstance(denominator, bool)
        or denominator <= 0
    ):
        raise ValueError("rational payload must contain canonical integers")
    return sp.Rational(numerator, denominator)


def _decode_matrix(payload: object) -> sp.ImmutableMatrix:
    if not isinstance(payload, list) or not payload:
        raise TypeError("matrix payload must be one nonempty list")
    if any(not isinstance(row, list) for row in payload):
        raise TypeError("matrix rows must be lists")
    widths = {len(row) for row in payload}
    if len(widths) != 1 or next(iter(widths)) == 0:
        raise ValueError("matrix payload must be rectangular and nonempty")
    return sp.ImmutableMatrix(
        [
            [_decode_rational(entry) for entry in row]
            for row in payload
        ]
    )


def _compound_from_minors(
    matrix: sp.MatrixBase,
    grade: int,
) -> sp.ImmutableMatrix:
    """Rebuild ``Lambda^grade(matrix)`` directly in lexicographic basis."""

    exact = sp.ImmutableMatrix(matrix)
    if exact.rows != exact.cols:
        raise ValueError("matrix must be square")
    basis = tuple(combinations(range(exact.rows), grade))
    return sp.ImmutableMatrix(
        [
            [
                sp.det(exact.extract(row_subset, column_subset))
                for column_subset in basis
            ]
            for row_subset in basis
        ]
    )


def _signed_nonnegative(
    matrices: Sequence[sp.MatrixBase],
    signs: Sequence[int],
) -> bool:
    diagonal = sp.diag(*signs)
    return all(
        entry >= 0
        for matrix in matrices
        for entry in diagonal * matrix * diagonal
    )


def audit_seed61_certificate(result_path: Path) -> dict[str, object]:
    """Return an exact scope audit of the frozen seed-61 certificate."""

    raw = result_path.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise TypeError("result must contain one JSON object")
    certificate = payload.get("certificate")
    if not isinstance(certificate, Mapping):
        raise ValueError("result has no exact certificate")

    card = candidate_card(template="exact5-shear-loop-pair", seed=61)
    card_atoms = card.get("atoms")
    if not isinstance(card_atoms, list) or len(card_atoms) != 2:
        raise ValueError("seed-61 card must contain one transpose pair")
    atoms = tuple(_decode_matrix(atom["matrix"]) for atom in card_atoms)
    first, second = atoms
    if second != first.T:
        raise ArithmeticError("the frozen card is not transpose paired")
    if sp.det(first) != 1 or sp.det(second) != 1:
        raise ArithmeticError("the frozen atoms are not unimodular")

    compounds = {
        grade: tuple(_compound_from_minors(atom, grade) for atom in atoms)
        for grade in range(6)
    }
    rays = _decode_matrix(certificate.get("rays"))
    actions_payload = certificate.get("actions")
    if not isinstance(actions_payload, list):
        raise TypeError("certificate actions must be a list")
    actions = tuple(_decode_matrix(action) for action in actions_payload)

    if rays.shape != (10, 12) or rays.rank() != 10:
        raise ArithmeticError("the grade-2 ray matrix must have shape 10x12 and rank 10")
    if len(actions) != 2 or any(action.shape != (12, 12) for action in actions):
        raise ArithmeticError("the certificate must contain two 12x12 actions")
    if any(entry < 0 for action in actions for entry in action):
        raise ArithmeticError("the certificate contains a negative action entry")
    if any(
        atom * rays != rays * action
        for atom, action in zip(compounds[2], actions, strict=True)
    ):
        raise ArithmeticError("the frozen grade-2 intertwining identity failed")

    grade1_signs = (1, 1, -1, -1, -1)
    grade3_signs = (1, 1, 1, -1, -1, -1, -1, -1, -1, 1)
    if not _signed_nonnegative(compounds[1], grade1_signs):
        raise ArithmeticError("the independent grade-1 signed gauge failed")
    if not _signed_nonnegative(compounds[3], grade3_signs):
        raise ArithmeticError("the independent grade-3 signed gauge failed")
    if any(matrix != sp.ones(1, 1) for matrix in compounds[0] + compounds[5]):
        raise ArithmeticError("grades 0 and 5 are not the positive scalar representation")

    # The sixth power is an exact counterexample to the missing implication
    # "invariant redundant cone => nonnegative trace".
    sector_traces: list[sp.Expr] = []
    first_power = first**6
    for grade in range(6):
        compound_power = compounds[grade][0] ** 6
        if compound_power != _compound_from_minors(first_power, grade):
            raise ArithmeticError("exterior powers failed multiplicativity")
        sector_traces.append(sp.trace(compound_power))
    determinant = sp.det(sp.eye(5) + first_power)
    if determinant != sum(sector_traces, start=sp.Integer(0)):
        raise ArithmeticError("determinant/exterior-trace expansion failed")
    if sector_traces[2] >= 0 or sector_traces[4] >= 0:
        raise ArithmeticError("the exact B^6 negative-sector witnesses disappeared")
    if determinant <= 0:
        raise ArithmeticError("the B^6 determinant cancellation witness changed sign")

    # If a trace-compatible frame C with R*C=I and C*R>=0 existed, then
    # tr(A_0^6)=tr((C*R)*P_0^6)>=0.  The exact negative trace above therefore
    # rules out such a frame for this frozen lift without a numerical LP.
    action_power = actions[0] ** 6
    compound_power = compounds[2][0] ** 6
    if compound_power * rays != rays * action_power:
        raise ArithmeticError("the length-six intertwining identity failed")

    inverse = inverse_hs_from_card(card)
    if inverse.coefficient <= 0:
        raise ArithmeticError("inverse HS coefficient is not positive")
    if inverse.hamiltonian != inverse.hamiltonian.T:
        raise ArithmeticError("inverse HS Hamiltonian is not Hermitian")
    if inverse.gaussian_branches[1] != inverse.gaussian_branches[0].T:
        raise ArithmeticError("inverse HS branches are not transpose paired")
    history = exact_history_weight(inverse, (0,) * 6)
    if history.determinant != determinant or history.total_weight <= 0:
        raise ArithmeticError("inverse HS history does not match the determinant")

    return {
        "candidate": "exact5-shear-loop-pair-seed-61",
        "result_sha256": hashlib.sha256(raw).hexdigest(),
        "exact_grade2_intertwining": True,
        "ray_shape": list(rays.shape),
        "ray_rank": rays.rank(),
        "minimum_action_entry": str(
            min(entry for action in actions for entry in action)
        ),
        "arbitrary_word_positive_sectors": [0, 1, 3, 5],
        "grade1_signed_gauge": list(grade1_signs),
        "grade3_signed_gauge": list(grade3_signs),
        "counterexample_word": [0] * 6,
        "counterexample_sector_traces": [
            str(value) for value in sector_traces
        ],
        "counterexample_determinant": str(determinant),
        "trace_compatible_frame_for_this_lift": False,
        "inverse_hs_coefficient": str(inverse.coefficient),
        "inverse_hs_hermitian": True,
        "inverse_hs_positive_history_coefficient": bool(
            history.scalar_coefficient > 0
        ),
        "theorem_status": "incomplete-sector-trace-certificate",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    print(
        json.dumps(
            audit_seed61_certificate(args.result),
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["audit_seed61_certificate"]
