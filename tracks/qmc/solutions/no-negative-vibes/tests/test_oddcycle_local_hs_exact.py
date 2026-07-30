import hashlib
import json

import numpy as np
import sympy as sp

from oracle.oddcycle_local_hs_exact import (
    diagonal_sign_gauge_audit,
    exact_local_hs_certificate,
    exact_positive_null_vector,
)
from oracle.oddcycle_local_hs_scan import LocalitySpec
from oracle.oddcycle_word_operator import (
    NormalOrderedLabel,
    WordPairColumn,
    normal_ordered_labels,
    reconstruct_normal_ordered,
)


_WORDS = ((0,), (2,), (0, 0))
_TRANSPOSE_WORDS = ((1,), (3,), (1, 1))


def _synthetic_column(
    index: int,
    *,
    two_body: int = 2,
    three_body: int = 0,
) -> WordPairColumn:
    labels = normal_ordered_labels(3)
    coordinates = {label: sp.Integer(0) for label in labels}
    coordinates[NormalOrderedLabel((), ())] = sp.Integer(2)
    for left in range(3):
        for right in range(3):
            if left != right:
                coordinates[
                    NormalOrderedLabel((left,), (right,))
                ] = sp.Integer(-1)
    coordinates[
        NormalOrderedLabel((0, 1), (0, 1))
    ] = sp.Integer(two_body)
    coordinates[
        NormalOrderedLabel((0, 1, 2), (0, 1, 2))
    ] = sp.Integer(three_body)
    return WordPairColumn(
        word=_WORDS[index],
        transpose_word=_TRANSPOSE_WORDS[index],
        matrix_orbit_key=((index, 1),),
        fock_pair=reconstruct_normal_ordered(coordinates, 3),
        coordinates=coordinates,
    )


def _local_two_body_spec() -> LocalitySpec:
    return LocalitySpec(
        name="three-mode-cluster",
        max_body_order=2,
        allowed_supports=(frozenset(range(3)),),
    )


def test_exact_positive_null_vector_replays_over_rationals():
    matrix = sp.ImmutableMatrix([[1, -1], [2, -2]])

    weights = exact_positive_null_vector(matrix, np.array([0.5, 0.5]))

    assert weights == (sp.Rational(1, 2), sp.Rational(1, 2))
    assert matrix * sp.Matrix(weights) == sp.zeros(2, 1)


def test_positive_triangle_is_not_diagonal_gauge_stoquastic():
    hamiltonian = sp.ImmutableMatrix(
        [[0, 1, 1], [1, 0, 1], [1, 1, 0]]
    )

    audit = diagonal_sign_gauge_audit(hamiltonian)

    assert audit["status"] == "exact-gauge-frustrated"
    assert len(audit["conflict_cycle_zero_based"]) == 3


def test_exact_local_certificate_replays_every_gate_and_audits_physical_h():
    columns = (
        _synthetic_column(0, three_body=1),
        _synthetic_column(1, three_body=-1),
    )

    certificate = exact_local_hs_certificate(
        columns,
        np.array([0.5, 0.5]),
        _local_two_body_spec(),
    )

    assert certificate["status"] == "exact-local-interacting-hs-survivor"
    assert all(certificate["gates"].values())
    assert certificate["scalar_coordinate_dropped"] == {
        "numerator": 2,
        "denominator": 1,
    }
    assert [field["weight"] for field in certificate["fields"]] == [
        {"numerator": 1, "denominator": 2},
        {"numerator": 1, "denominator": 2},
    ]
    hopping_01 = next(
        term
        for term in certificate["physical_terms"]
        if term["create_zero_based"] == [0]
        and term["annihilate_zero_based"] == [1]
    )
    assert hopping_01["coefficient"] == {
        "numerator": 1,
        "denominator": 1,
    }
    assert all(
        term["body_order"] <= 2
        for term in certificate["physical_terms"]
    )
    novelty = certificate["novelty"]
    assert novelty["diagonal_sign_gauge_audit_on"] == "H=-V modulo scalar"
    assert novelty["diagonal_sign_gauge"]["status"] == (
        "exact-gauge-frustrated"
    )
    assert novelty["exact_gauge_frustrated"] is True

    stored_digest = certificate["exact_certificate_sha256"]
    canonical_payload = dict(certificate)
    canonical_payload.pop("exact_certificate_sha256")
    observed_digest = hashlib.sha256(
        json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert stored_digest == observed_digest


def test_exact_local_certificate_requires_a_nonzero_two_body_term():
    columns = (
        _synthetic_column(0, two_body=0, three_body=1),
        _synthetic_column(1, two_body=0, three_body=-1),
    )

    certificate = exact_local_hs_certificate(
        columns,
        np.array([0.5, 0.5]),
        _local_two_body_spec(),
    )

    assert certificate["status"] == "exact-local-hs-gate-failed"
    assert certificate["gates"]["exact_forbidden_coordinates_zero"] is True
    assert certificate["gates"]["nonzero_body_order_two_term"] is False
    assert certificate["gates"]["exact_full_fock_equality"] is True


def test_exact_local_certificate_rejects_surviving_higher_body_terms():
    spec = LocalitySpec(
        name="three-mode-unbounded",
        max_body_order=3,
        allowed_supports=(frozenset(range(3)),),
    )

    certificate = exact_local_hs_certificate(
        (_synthetic_column(0, three_body=1),),
        np.array([1.0]),
        spec,
    )

    assert certificate["status"] == "exact-local-hs-gate-failed"
    assert certificate["gates"]["nonzero_body_order_two_term"] is True
    assert certificate["gates"]["no_body_order_above_two"] is False
    assert certificate["gates"]["exact_full_fock_equality"] is True


def test_higher_nullity_rationalization_failure_is_inconclusive():
    columns = (
        _synthetic_column(0, three_body=1),
        _synthetic_column(1, three_body=0),
        _synthetic_column(2, three_body=0),
    )

    certificate = exact_local_hs_certificate(
        columns,
        np.array([1.0, 1.0e-12, 1.0]),
        _local_two_body_spec(),
    )

    assert certificate["status"] == "exact-promotion-inconclusive"
    assert certificate["exact_forbidden_nullity"] == 2


def test_exactly_missing_positive_kernel_is_a_conclusive_terminal_status():
    trivial = exact_local_hs_certificate(
        (_synthetic_column(0, three_body=1),),
        np.array([1.0]),
        _local_two_body_spec(),
    )
    sign_indefinite = exact_local_hs_certificate(
        (
            _synthetic_column(0, three_body=1),
            _synthetic_column(1, three_body=1),
        ),
        np.array([0.5, 0.5]),
        _local_two_body_spec(),
    )

    assert trivial["status"] == "no-positive-exact-kernel"
    assert trivial["exact_forbidden_nullity"] == 0
    assert sign_indefinite["status"] == "no-positive-exact-kernel"
    assert sign_indefinite["exact_forbidden_nullity"] == 1
