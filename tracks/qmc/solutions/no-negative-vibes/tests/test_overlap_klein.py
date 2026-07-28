from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
import sympy as sp

from oracle.fock_basis import quadratic_term
from oracle.metzler_system import ExactMetzlerSystem, MetzlerRow
from oracle.overlap_klein import (
    AnchorSolve,
    ExactDualCertificate,
    ExactPrimalCertificate,
    bridge_labels,
    certificate_from_json,
    certificate_to_json,
    find_zero_dual,
    overlap_geometry,
    quadratic_basis,
    reconstruct_exact_primal,
    solve_anchor,
    support_edges,
    verify_primal,
    verify_zero_dual,
)


def _synthetic_system(
    coefficients: list[list[sp.Expr | int]],
) -> ExactMetzlerSystem:
    rows = tuple(
        MetzlerRow("even", index + 1, 0)
        for index in range(len(coefficients))
    )
    return ExactMetzlerSystem(
        labels=("x", "y"),
        rows=rows,
        coefficients=sp.ImmutableSparseMatrix(coefficients),
    )


def test_overlap_geometry_has_two_fixed_plaquettes_and_two_bridges() -> None:
    geometry = overlap_geometry()
    assert geometry.modes == 6
    assert geometry.blocks == ((0, 1, 2, 3), (2, 3, 4, 5))
    assert geometry.bridge_edges == ((0, 4), (1, 5))
    assert geometry.ring_edges == (
        (0, 1),
        (0, 3),
        (1, 2),
        (2, 3),
        (2, 5),
        (3, 4),
        (4, 5),
    )
    assert geometry.diagonal_edges == ((0, 2), (1, 3), (2, 4), (3, 5))


def test_overlap_geometry_is_immutable() -> None:
    geometry = overlap_geometry()
    with pytest.raises(FrozenInstanceError):
        geometry.modes = 7  # type: ignore[misc]


def test_support_masks_are_nested_and_do_not_become_complete_graph() -> None:
    rings = set(support_edges("rings"))
    bridges = set(support_edges("rings-bridges"))
    full = set(support_edges("rings-diagonals-bridges"))
    assert rings < bridges < full
    assert len(full) == 13
    assert (0, 5) not in full
    assert (1, 4) not in full


def test_support_edges_have_a_stable_lexicographic_order() -> None:
    assert support_edges("rings-diagonals-bridges") == (
        (0, 1),
        (0, 2),
        (0, 3),
        (0, 4),
        (1, 2),
        (1, 3),
        (1, 5),
        (2, 3),
        (2, 4),
        (2, 5),
        (3, 4),
        (3, 5),
        (4, 5),
    )


def test_number_conserving_basis_has_directed_hops_and_onsite_terms() -> None:
    basis = quadratic_basis("number-conserving", "rings-bridges")
    labels = {item.label for item in basis}
    assert len(basis) == 6 + 2 * 9
    assert {"n0", "h0<-1", "h1<-0", "h0<-4", "h4<-0"} <= labels
    assert all(item.kind == "hop" for item in basis)
    assert tuple(item.label for item in basis) == tuple(sorted(labels))


def test_basis_labels_map_to_the_intended_exact_quadratic_terms() -> None:
    basis = {
        item.label: item
        for item in quadratic_basis("bdg", "rings-bridges")
    }
    expected = {
        "n0": ("hop", 0, 0),
        "h0<-4": ("hop", 0, 4),
        "h4<-0": ("hop", 4, 0),
        "pc0,4": ("pair_create", 0, 4),
        "pa0,4": ("pair_annihilate", 0, 4),
    }
    for label, (kind, i, j) in expected.items():
        item = basis[label]
        assert (item.kind, item.i, item.j) == (kind, i, j)
        assert item.fock == quadratic_term(6, kind, i, j)


def test_bdg_bridge_pairing_has_hand_derived_jordan_wigner_signs() -> None:
    basis = {
        item.label: item
        for item in quadratic_basis("bdg", "rings-bridges")
    }
    pair_creation = basis["pc0,4"].fock
    pair_annihilation = basis["pa0,4"].fock

    assert pair_creation[0b010001, 0] == 1
    assert pair_creation[0b010101, 0b000100] == -1
    assert pair_annihilation[0, 0b010001] == 1
    assert pair_annihilation[0b000100, 0b010101] == -1
    assert pair_annihilation == pair_creation.T


def test_bdg_basis_adds_independent_creation_and_annihilation_terms() -> None:
    number = quadratic_basis("number-conserving", "rings-bridges")
    bdg = quadratic_basis("bdg", "rings-bridges")
    labels = {item.label for item in bdg}
    assert len(bdg) == len(number) + 2 * len(support_edges("rings-bridges"))
    assert {"pc0,4", "pa0,4"} <= labels
    assert set(bridge_labels("bdg")) == {
        "h0<-4",
        "h4<-0",
        "pc0,4",
        "pa0,4",
        "h1<-5",
        "h5<-1",
        "pc1,5",
        "pa1,5",
    }


def test_number_conserving_bridge_labels_exclude_pairing_terms() -> None:
    assert bridge_labels("number-conserving") == (
        "h0<-4",
        "h1<-5",
        "h4<-0",
        "h5<-1",
    )


@pytest.mark.parametrize(
    "mask",
    ("", "rings-diagonals", "complete"),
)
def test_unknown_support_masks_are_rejected(mask: str) -> None:
    with pytest.raises(ValueError, match="unknown support mask"):
        support_edges(mask)


def test_bdg_basis_rejects_an_unknown_support_mask() -> None:
    with pytest.raises(ValueError, match="unknown support mask"):
        quadratic_basis("bdg", "complete")


@pytest.mark.parametrize("family", ("", "hopping", "pairing"))
def test_unknown_quadratic_families_are_rejected(family: str) -> None:
    with pytest.raises(ValueError, match="unknown quadratic family"):
        quadratic_basis(family, "rings")
    with pytest.raises(ValueError, match="unknown quadratic family"):
        bridge_labels(family)


def test_anchor_solver_and_exact_primal_replay() -> None:
    system = _synthetic_system([[1, 0], [0, 1]])

    solve = solve_anchor(system, "x", +1)
    certificate = reconstruct_exact_primal(system, solve)

    assert solve.status == "feasible"
    assert solve.label == "x"
    assert solve.sign == 1
    assert solve.min_slack is not None
    assert solve.min_slack >= -1e-9
    assert certificate.coefficients[0] == 1
    assert verify_primal(system, certificate)


def test_anchor_solver_has_no_artificial_coefficient_box() -> None:
    system = _synthetic_system([[-2, 1]])

    solve = solve_anchor(system, "x", +1)

    assert solve.status == "feasible"
    assert solve.coefficients[0] == pytest.approx(1.0)
    assert solve.coefficients[1] >= 2.0 - 1e-9


def test_anchor_solver_distinguishes_infeasible_and_numerical_error() -> None:
    infeasible = solve_anchor(_synthetic_system([[-1, 0]]), "x", +1)
    enormous = sp.Integer(10) ** 10000
    errored = solve_anchor(_synthetic_system([[enormous, 0]]), "x", +1)

    assert infeasible.status == "infeasible"
    assert infeasible.coefficients == ()
    assert infeasible.min_slack is None
    assert errored.status == "error"
    assert errored.coefficients == ()
    assert errored.min_slack is None
    assert errored.message


@pytest.mark.parametrize(("label", "sign"), (("missing", 1), ("x", 0), ("x", True)))
def test_anchor_solver_rejects_invalid_anchor_requests(
    label: str, sign: int
) -> None:
    with pytest.raises(ValueError):
        solve_anchor(_synthetic_system([[1, 0]]), label, sign)


def test_primal_reconstruction_enforces_anchor_and_denominator_limit() -> None:
    system = _synthetic_system([[1, 0], [0, 1]])
    valid = AnchorSolve(
        label="x",
        sign=1,
        status="feasible",
        coefficients=(1.0 + 1e-12, float(sp.sqrt(2) / 2)),
        min_slack=0.0,
        message="synthetic",
    )
    certificate = reconstruct_exact_primal(system, valid)

    assert certificate.coefficients == (sp.Integer(1), sp.sqrt(2) / 2)
    assert verify_primal(system, certificate)

    excessive_denominator = AnchorSolve(
        label="x",
        sign=1,
        status="feasible",
        coefficients=(1.0, 0.5),
        min_slack=0.0,
        message="synthetic",
    )
    with pytest.raises(ArithmeticError, match="denominator"):
        reconstruct_exact_primal(
            system, excessive_denominator, max_denominator=1
        )


def test_primal_reconstruction_never_upgrades_an_invalid_float_solution() -> None:
    system = _synthetic_system([[0, -1]])
    invalid = AnchorSolve(
        label="x",
        sign=1,
        status="feasible",
        coefficients=(1.0, 1.0),
        min_slack=0.0,
        message="synthetic",
    )

    with pytest.raises(ArithmeticError, match="exact Metzler"):
        reconstruct_exact_primal(system, invalid)

    infeasible = AnchorSolve(
        label="x",
        sign=1,
        status="infeasible",
        coefficients=(),
        min_slack=None,
        message="synthetic",
    )
    with pytest.raises(ArithmeticError, match="not feasible"):
        reconstruct_exact_primal(system, infeasible)


def test_dual_certificate_proves_anchor_is_identically_zero() -> None:
    system = _synthetic_system([[1, 0], [-1, 0], [0, 1]])

    assert solve_anchor(system, "x", +1).status == "infeasible"
    assert solve_anchor(system, "x", -1).status == "infeasible"
    certificate = find_zero_dual(system, "x")

    assert verify_zero_dual(system, certificate)
    assert all(
        weight >= 0
        for weight in certificate.plus_weights + certificate.minus_weights
    )


def test_dual_reconstruction_handles_q_sqrt_two_and_degenerate_rows() -> None:
    root_two = sp.sqrt(2)
    system = _synthetic_system(
        [
            [root_two, 0],
            [root_two, 0],
            [-root_two, 0],
            [-root_two, 0],
            [0, 1],
        ]
    )

    certificate = find_zero_dual(system, "x")

    assert verify_zero_dual(system, certificate)
    assert sp.simplify(
        sum(certificate.plus_weights[:2]) - root_two / 2
    ) == 0
    assert sp.simplify(
        sum(certificate.minus_weights[2:4]) - root_two / 2
    ) == 0


def test_dual_search_refuses_to_claim_a_missing_zero_proof() -> None:
    with pytest.raises(ArithmeticError, match="dual"):
        find_zero_dual(_synthetic_system([[1, 0], [0, 1]]), "x")


def test_verifiers_reject_wrong_anchor_or_exact_identity() -> None:
    system = _synthetic_system([[1, 0], [-1, 0], [0, 1]])
    wrong_primal = ExactPrimalCertificate(
        anchor_label="x",
        anchor_sign=1,
        coefficients=(sp.Integer(-1), sp.Integer(0)),
    )
    wrong_dual = ExactDualCertificate(
        anchor_label="x",
        plus_weights=(sp.Integer(0),) * 3,
        minus_weights=(sp.Integer(0),) * 3,
    )

    assert not verify_primal(system, wrong_primal)
    assert not verify_zero_dual(system, wrong_dual)


def test_exact_primal_certificate_json_round_trip() -> None:
    system = _synthetic_system([[1, 0], [0, 1]])
    certificate = reconstruct_exact_primal(
        system, solve_anchor(system, "x", +1)
    )

    payload = certificate_to_json(certificate)
    replayed = certificate_from_json(payload, system)

    assert payload == {
        "kind": "primal",
        "anchor_label": "x",
        "anchor_sign": 1,
        "coefficients": ["1", "0"],
    }
    assert replayed == certificate
    assert verify_primal(system, replayed)


def test_exact_dual_certificate_json_round_trip() -> None:
    system = _synthetic_system([[sp.sqrt(2), 0], [-sp.sqrt(2), 0]])
    certificate = find_zero_dual(system, "x")

    payload = certificate_to_json(certificate)
    replayed = certificate_from_json(payload, system)

    assert payload["kind"] == "dual"
    assert replayed == certificate
    assert verify_zero_dual(system, replayed)


@pytest.mark.parametrize(
    "payload",
    (
        {
            "kind": "primal",
            "anchor_label": "missing",
            "anchor_sign": 1,
            "coefficients": ["1", "0"],
        },
        {
            "kind": "primal",
            "anchor_label": "x",
            "anchor_sign": 1,
            "coefficients": ["1"],
        },
        {
            "kind": "primal",
            "anchor_label": "x",
            "anchor_sign": 1,
            "coefficients": ["1", "__import__('os').system('echo bad')"],
        },
        {
            "kind": "primal",
            "anchor_label": "x",
            "anchor_sign": 1,
            "coefficients": ["1", "sqrt(3)"],
        },
        {
            "kind": "primal",
            "anchor_label": "x",
            "anchor_sign": 1,
            "coefficients": ["1", "1.0"],
        },
        {
            "kind": "primal",
            "anchor_label": "x",
            "anchor_sign": 1,
            "coefficients": ["1", "0"],
            "unexpected": "field",
        },
        {
            "kind": "unknown",
            "anchor_label": "x",
        },
    ),
)
def test_certificate_json_rejects_malformed_or_unsafe_payloads(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        certificate_from_json(
            payload, _synthetic_system([[1, 0], [0, 1]])
        )


def test_certificate_json_rejects_noncanonical_or_false_certificates() -> None:
    system = _synthetic_system([[1, 0], [0, 1]])
    noncanonical = {
        "kind": "primal",
        "anchor_label": "x",
        "anchor_sign": 1,
        "coefficients": ["1", "2/2"],
    }
    false_certificate = {
        "kind": "primal",
        "anchor_label": "x",
        "anchor_sign": 1,
        "coefficients": ["-1", "0"],
    }

    with pytest.raises(ValueError, match="canonical"):
        certificate_from_json(noncanonical, system)
    with pytest.raises(ValueError, match="verify"):
        certificate_from_json(false_certificate, system)
