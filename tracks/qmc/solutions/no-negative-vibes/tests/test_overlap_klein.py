from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import json
import math
import os
from pathlib import Path
import pickle
import subprocess
import sys
import warnings

import pytest
import numpy as np
import sympy as sp

import oracle.overlap_klein as overlap_klein
from oracle.fock_basis import quadratic_term
from oracle.metzler_system import ExactMetzlerSystem, MetzlerRow
from oracle.overlap_klein import (
    AnchorSolve,
    ExactDualCertificate,
    ExactPrimalCertificate,
    bridge_labels,
    build_system,
    classify_anchor,
    classify_r01_fixture,
    certificate_from_json,
    certificate_to_json,
    find_zero_dual,
    execution_metadata,
    overlap_geometry,
    quadratic_basis,
    _q_sqrt_two_to_float,
    _numeric_system_matrix,
    reconstruct_exact_primal,
    run_anchor_scan,
    solve_anchor,
    support_edges,
    verify_primal,
    verify_zero_dual,
    validate_blas_thread_environment,
    write_result,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "overlap_klein_r01.json"
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
        coefficients=(1.0 + 1e-12, math.sqrt(2) / 2),
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


def test_primal_reconstruction_forces_an_accepted_anchor_before_nsimplify() -> None:
    system = _synthetic_system([[1, 0]])
    accepted_outer_tolerance = AnchorSolve(
        label="x",
        sign=1,
        status="feasible",
        coefficients=(1.0 + 5e-9, 0.0),
        min_slack=1.0,
        message="synthetic",
    )

    certificate = reconstruct_exact_primal(
        system, accepted_outer_tolerance
    )

    assert certificate.coefficients == (sp.Integer(1), sp.Integer(0))
    assert verify_primal(system, certificate)


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


@pytest.mark.parametrize("scale", (10**5, 10**12))
def test_dual_zero_proof_is_invariant_under_positive_row_scaling(
    scale: int,
) -> None:
    system = _synthetic_system([[scale, 0], [-scale, 0]])

    certificate = find_zero_dual(system, "x")

    inverse_scale = sp.Rational(1, scale)
    assert certificate.plus_weights == (inverse_scale, sp.Integer(0))
    assert certificate.minus_weights == (sp.Integer(0), inverse_scale)
    assert verify_zero_dual(system, certificate)


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


def test_empty_metzler_system_has_both_anchored_primals_but_no_zero_dual() -> None:
    system = ExactMetzlerSystem(
        labels=("x", "y"),
        rows=(),
        coefficients=sp.ImmutableSparseMatrix(0, 2, {}),
    )

    for sign in (-1, 1):
        solve = solve_anchor(system, "x", sign)
        assert solve.status == "feasible"
        assert verify_primal(
            system, reconstruct_exact_primal(system, solve)
        )
    with pytest.raises(ArithmeticError, match="dual"):
        find_zero_dual(system, "x")


def test_structurally_zero_anchor_has_both_primals_but_no_zero_dual() -> None:
    system = _synthetic_system([[0, 1], [0, -1]])

    for sign in (-1, 1):
        solve = solve_anchor(system, "x", sign)
        assert solve.status == "feasible"
        certificate = reconstruct_exact_primal(system, solve)
        assert certificate.coefficients[0] == sign
        assert verify_primal(system, certificate)
    with pytest.raises(ArithmeticError, match="dual"):
        find_zero_dual(system, "x")


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


def test_certificate_json_serializer_enforces_the_parser_length_limit() -> None:
    enormous = sp.Integer(10) ** 300
    certificate = ExactPrimalCertificate(
        anchor_label="x",
        anchor_sign=1,
        coefficients=(sp.Integer(1), enormous),
    )
    payload = {
        "kind": "primal",
        "anchor_label": "x",
        "anchor_sign": 1,
        "coefficients": ["1", sp.sstr(enormous)],
    }

    with pytest.raises(ValueError, match="too long"):
        certificate_to_json(certificate)
    with pytest.raises(ValueError, match="short strings"):
        certificate_from_json(
            payload, _synthetic_system([[1, 0], [0, 1]])
        )


def test_build_system_uses_the_fixed_overlap_klein_geometry() -> None:
    """Catches a runner that compiles a different transform or basis."""
    system = build_system("number-conserving", "rings-bridges")

    assert system.labels == tuple(
        item.label
        for item in quadratic_basis("number-conserving", "rings-bridges")
    )
    assert system.coefficients.shape == (560, 24)


@pytest.fixture(scope="module")
def number_conserving_anchor_scan() -> dict[str, object]:
    """One real scan shared by payload-evidence tests."""
    return run_anchor_scan(
        "number-conserving",
        "rings-bridges",
        workers=1,
        source_commit="a" * 40,
    )


def test_anchor_scan_is_deterministic_across_worker_counts(
    number_conserving_anchor_scan: dict[str, object],
) -> None:
    """Catches completion-order output or execution metadata in the payload."""
    one = number_conserving_anchor_scan
    two = run_anchor_scan(
        "number-conserving",
        "rings-bridges",
        workers=2,
        source_commit="a" * 40,
    )
    assert one == two
    assert one["schema_version"] == 1
    assert one["protocol"] == "overlap-klein-v1"
    assert one["source_commit"] == "a" * 40
    assert one["anchor_count"] == len(bridge_labels("number-conserving"))


def test_result_payload_contains_replayable_terminal_evidence(
    number_conserving_anchor_scan: dict[str, object],
) -> None:
    """Catches omitted solver diagnostics or certificate classifications."""
    result = number_conserving_anchor_scan
    system = build_system("number-conserving", "rings-bridges")
    for anchor in result["anchors"]:
        assert set(anchor) >= {"label", "positive", "negative", "classification"}
        assert set(anchor["positive"]) >= {"status", "solver_message"}
        assert set(anchor["negative"]) >= {"status", "solver_message"}
        if anchor["classification"] == "certified-feasible":
            primals = [
                sign["exact_primal_certificate"]
                for sign in (anchor["positive"], anchor["negative"])
                if "exact_primal_certificate" in sign
            ]
            assert primals
            for payload in primals:
                certificate = certificate_from_json(payload, system)
                assert isinstance(certificate, ExactPrimalCertificate)
                assert verify_primal(system, certificate)
        elif anchor["classification"] == "certified-zero":
            assert anchor["positive"]["status"] == "infeasible"
            assert anchor["negative"]["status"] == "infeasible"
            certificate = certificate_from_json(anchor["zero_certificate"], system)
            assert isinstance(certificate, ExactDualCertificate)
            assert verify_zero_dual(system, certificate)
        else:
            assert anchor["classification"] == "numerical-only"
            assert "zero_certificate" not in anchor
            assert all(
                "exact_primal_certificate" not in sign
                for sign in (anchor["positive"], anchor["negative"])
            )


def test_r01_fixture_schema_v2_orders_e001_and_e002_without_losing_cells() -> None:
    """Catches retaining the single-experiment schema or dropping an R01 cell."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert payload["fixture_schema_version"] == 2
    assert payload["protocol"] == "overlap-klein-v1"
    assert "experiment_id" not in payload
    assert "source_commit" not in payload
    assert "package_versions" not in payload
    assert "cells" not in payload

    experiments = payload["experiments"]
    assert [
        (experiment["experiment_id"], experiment["source_commit"])
        for experiment in experiments
    ] == [
        (
            "R01-E001",
            "24c80c4e1c1f182278e799b7f5de53deb65bf2f4",
        ),
        (
            "R01-E002",
            "d42786ae8a47899c90ac4811424c66aad2910713",
        ),
    ]
    assert [
        [
            (cell["family"], cell["mask"])
            for cell in experiment["cells"]
        ]
        for experiment in experiments
    ] == [
        [
            ("number-conserving", "rings-bridges"),
            ("number-conserving", "rings-diagonals-bridges"),
        ],
        [
            ("bdg", "rings-bridges"),
            ("bdg", "rings-diagonals-bridges"),
        ],
    ]

    for experiment in experiments:
        assert len(experiment["cells"]) == 2
        for cell in experiment["cells"]:
            system = build_system(cell["family"], cell["mask"])
            expected_labels = bridge_labels(cell["family"])
            assert cell["system_shape"] == list(system.coefficients.shape)
            assert cell["anchor_count"] == len(expected_labels)
            assert [anchor["label"] for anchor in cell["anchors"]] == list(
                expected_labels
            )


def test_r01_fixture_covers_both_number_conserving_cells_without_duplicates() -> None:
    """Catches missing, repeated, or convention-drifted R01-E001 evidence."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    experiment = next(
        experiment
        for experiment in payload["experiments"]
        if experiment["experiment_id"] == "R01-E001"
    )
    assert experiment["source_commit"] == (
        "24c80c4e1c1f182278e799b7f5de53deb65bf2f4"
    )
    assert [
        (cell["family"], cell["mask"], cell["system_shape"])
        for cell in experiment["cells"]
    ] == [
        ("number-conserving", "rings-bridges", [560, 24]),
        ("number-conserving", "rings-diagonals-bridges", [748, 32]),
    ]
    for cell in experiment["cells"]:
        system = build_system(cell["family"], cell["mask"])
        expected_labels = bridge_labels(cell["family"])
        assert cell["system_shape"] == list(system.coefficients.shape)
        assert cell["anchor_count"] == len(expected_labels)
        assert [anchor["label"] for anchor in cell["anchors"]] == list(
            expected_labels
        )


def test_r01_fixture_v2_records_exact_raw_provenance_per_host() -> None:
    """Catches swapped workers, roles, hashes, or false cross-host metadata."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    observed = []
    for experiment in payload["experiments"]:
        for cell in experiment["cells"]:
            assert cell[
                "scientific_payload_equal_after_removing_only_top_level_execution"
            ] is True
            assert cell["package_versions"] == {
                "numpy": "2.4.6",
                "oracle": "0.1.0",
                "scipy": "1.17.1",
                "sympy": "1.14.0",
            }
            for raw in cell["raw_results"]:
                assert raw["execution"]["blas_threads"] == {
                    "MKL_NUM_THREADS": "1",
                    "OMP_NUM_THREADS": "1",
                    "OPENBLAS_NUM_THREADS": "1",
                }
                assert raw["execution"]["process_start_method"] == "spawn"
                assert raw["execution"]["wall_time_seconds"] > 0
            observed.append(
                (
                    experiment["experiment_id"],
                    cell["family"],
                    cell["mask"],
                    cell["system_shape"],
                    cell["host_role"],
                    [
                        (
                            raw["role"],
                            raw["path"],
                            raw["sha256"],
                            raw["execution"]["workers"],
                        )
                        for raw in cell["raw_results"]
                    ],
                )
            )

    assert observed == [
        (
            "R01-E001",
            "number-conserving",
            "rings-bridges",
            [560, 24],
            "WSL",
            [
                (
                    "smoke",
                    "tracks/qmc/results/no-negative-vibes/overlap-klein-v1/"
                    "R01-E001-smoke-rings-bridges-attempt-01.json",
                    "42ce1da95f7cdf4f3c9b7339001518265aa619ef1b654975ae03cdf932804da1",
                    1,
                ),
                (
                    "production",
                    "tracks/qmc/results/no-negative-vibes/overlap-klein-v1/"
                    "R01-E001-rings-bridges-attempt-01.json",
                    "5317ca436b30bd734ad917cfe32c2c74b3436cb9f5b6165eb80dc14637a2859d",
                    14,
                ),
            ],
        ),
        (
            "R01-E001",
            "number-conserving",
            "rings-diagonals-bridges",
            [748, 32],
            "WSL",
            [
                (
                    "smoke",
                    "tracks/qmc/results/no-negative-vibes/overlap-klein-v1/"
                    "R01-E001-smoke-rings-diagonals-bridges-attempt-01.json",
                    "777d4ea88fb1ae4c83b20017b17e15aefeab1d8dd38650ebcc6d23f154ad0129",
                    1,
                ),
                (
                    "production",
                    "tracks/qmc/results/no-negative-vibes/overlap-klein-v1/"
                    "R01-E001-rings-diagonals-bridges-attempt-01.json",
                    "37d175bb701c573fdba433614765fe58302ee37f764393824c89cd38ebb68e36",
                    14,
                ),
            ],
        ),
        (
            "R01-E002",
            "bdg",
            "rings-bridges",
            [1052, 42],
            "WSL",
            [
                (
                    "smoke",
                    "tracks/qmc/results/no-negative-vibes/overlap-klein-v1/"
                    "R01-E002-smoke-rings-bridges-attempt-01.json",
                    "e86f5e96a879f1deaab8ad4aac38d8e66aa8bf23807060b53aee14c215729788",
                    1,
                ),
                (
                    "production",
                    "tracks/qmc/results/no-negative-vibes/overlap-klein-v1/"
                    "R01-E002-rings-bridges-attempt-01.json",
                    "ece5bc0595ffedba6633adf9afb0c19cfbfcbb9197e119929528b4297dbdf1c9",
                    14,
                ),
            ],
        ),
        (
            "R01-E002",
            "bdg",
            "rings-diagonals-bridges",
            [1456, 58],
            "CPU",
            [
                (
                    "smoke",
                    "tracks/qmc/results/no-negative-vibes/overlap-klein-v1/"
                    "R01-E002-smoke-rings-diagonals-bridges-attempt-01.json",
                    "dc4699c3df42720d3c4cce720124699c885d2b782ec85e9934635e5a529e8bb7",
                    1,
                ),
                (
                    "production",
                    "tracks/qmc/results/no-negative-vibes/overlap-klein-v1/"
                    "R01-E002-rings-diagonals-bridges-attempt-01.json",
                    "c5e62e1cd2c8af829c7b003d36a13460a0d965360f6c9ab8af98ccec06dcc3e3",
                    62,
                ),
            ],
        ),
    ]


@pytest.fixture(scope="module")
def r01_fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def r01_classification_run(
    r01_fixture_payload: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    payload = copy.deepcopy(r01_fixture_payload)
    before = copy.deepcopy(payload)
    summary = classify_r01_fixture(payload)
    return payload, before, summary


@pytest.fixture(scope="module")
def verified_r01_summary(
    r01_classification_run: tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ],
) -> dict[str, object]:
    return r01_classification_run[2]


def _first_r01_anchor(payload: dict[str, object]) -> dict[str, object]:
    return payload["experiments"][0]["cells"][0]["anchors"][0]


def _set_r01_path(
    payload: dict[str, object],
    path: tuple[str | int, ...],
    value: object,
) -> None:
    current: object = payload
    for key in path[:-1]:
        if isinstance(key, int):
            assert isinstance(current, list)
            current = current[key]
        else:
            assert isinstance(current, dict)
            current = current[key]
    final = path[-1]
    if isinstance(final, int):
        assert isinstance(current, list)
        current[final] = value
    else:
        assert isinstance(current, dict)
        current[final] = value


def _forbid_r01_build_system(
    *args: object,
    **kwargs: object,
) -> object:
    raise AssertionError("exact replay started before structural classification")


def test_r01_fixture_classifies_exact_bridge_coordinate_no_go(
    verified_r01_summary: dict[str, object],
) -> None:
    expected = {
        "outcome": "exact-bridge-coordinate-no-go",
        "fixture_schema_version": 2,
        "protocol": "overlap-klein-v1",
        "totals": {
            "experiments": 2,
            "cells": 4,
            "anchors": 24,
            "certified_zero": 24,
            "certified_feasible": 0,
            "numerical_only": 0,
            "dual_certificates": 24,
            "primal_certificates": 0,
        },
        "cells": [
            {
                "experiment_id": "R01-E001",
                "family": "number-conserving",
                "mask": "rings-bridges",
                "system_shape": [560, 24],
                "zero_labels": [
                    "h0<-4",
                    "h1<-5",
                    "h4<-0",
                    "h5<-1",
                ],
                "unresolved_labels": [],
            },
            {
                "experiment_id": "R01-E001",
                "family": "number-conserving",
                "mask": "rings-diagonals-bridges",
                "system_shape": [748, 32],
                "zero_labels": [
                    "h0<-4",
                    "h1<-5",
                    "h4<-0",
                    "h5<-1",
                ],
                "unresolved_labels": [],
            },
            {
                "experiment_id": "R01-E002",
                "family": "bdg",
                "mask": "rings-bridges",
                "system_shape": [1052, 42],
                "zero_labels": [
                    "h0<-4",
                    "h1<-5",
                    "h4<-0",
                    "h5<-1",
                    "pa0,4",
                    "pa1,5",
                    "pc0,4",
                    "pc1,5",
                ],
                "unresolved_labels": [],
            },
            {
                "experiment_id": "R01-E002",
                "family": "bdg",
                "mask": "rings-diagonals-bridges",
                "system_shape": [1456, 58],
                "zero_labels": [
                    "h0<-4",
                    "h1<-5",
                    "h4<-0",
                    "h5<-1",
                    "pa0,4",
                    "pa1,5",
                    "pc0,4",
                    "pc1,5",
                ],
                "unresolved_labels": [],
            },
        ],
        "audits": {
            "noncommutativity": "not-applicable-no-bridge-primal",
            "topology": "preempted-by-exact-bridge-no-go",
            "known_reduction": "not-applicable-empty-survivor-set",
            "word_trace": "skipped-no-survivor-rays",
        },
    }

    assert verified_r01_summary == expected
    forbidden = {
        "rays",
        "operators",
        "commutators",
        "support_graph",
        "forms",
        "word_traces",
        "known_mechanism",
    }
    assert forbidden.isdisjoint(verified_r01_summary)


def test_r01_classifier_does_not_mutate_the_exact_payload_it_receives(
    r01_classification_run: tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ],
) -> None:
    payload, before, _ = r01_classification_run
    assert payload == before


def test_r01_classifier_rejects_a_nonmapping_payload_before_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        overlap_klein,
        "build_system",
        _forbid_r01_build_system,
    )
    with pytest.raises(ValueError, match="mapping|JSON object"):
        classify_r01_fixture([])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("path", "replacement", "message"),
    [
        (("fixture_schema_version",), 1, "fixture schema"),
        (("protocol",), "other-protocol", "protocol"),
        (("raw_schema_version",), 2, "raw schema"),
        (("exact_field",), "R", "exact field"),
        (
            ("transform", "name"),
            "other-transform",
            "transform",
        ),
        (
            ("transform", "formula"),
            "U = I",
            "transform",
        ),
        (
            ("transform", "convention"),
            "left composed after right",
            "transform",
        ),
        (
            ("experiments", 0, "experiment_id"),
            "R01-E999",
            "experiment",
        ),
        (
            ("experiments", 0, "source_commit"),
            "0" * 40,
            "source commit",
        ),
        (
            ("experiments", 1, "source_commit"),
            "f" * 40,
            "source commit",
        ),
        (
            ("experiments", 0, "cells", 0, "family"),
            "bdg",
            "family|cell",
        ),
        (
            ("experiments", 0, "cells", 0, "mask"),
            "rings",
            "mask|cell",
        ),
        (
            ("experiments", 0, "cells", 0, "system_shape"),
            [1, 1],
            "system shape",
        ),
        (
            ("experiments", 0, "cells", 0, "host_role"),
            "PRIVATE",
            "host role|provenance",
        ),
        (
            ("experiments", 0, "cells", 0, "package_versions"),
            {
                "numpy": "0",
                "oracle": "0.1.0",
                "scipy": "1.17.1",
                "sympy": "1.14.0",
            },
            "package",
        ),
        (
            ("experiments", 1, "cells", 1, "package_versions"),
            {
                "numpy": "2.4.6",
                "oracle": "0.1.0",
                "scipy": "1.17.1",
                "sympy": "0",
            },
            "package",
        ),
        (
            (
                "experiments",
                0,
                "cells",
                0,
                "scientific_payload_equal_after_removing_only_top_level_execution",
            ),
            False,
            "payload equality|scientific payload",
        ),
        (
            (
                "experiments",
                0,
                "cells",
                0,
                "raw_results",
                0,
                "path",
            ),
            "tracks/qmc/results/no-negative-vibes/wrong.json",
            "raw provenance|raw path",
        ),
        (
            (
                "experiments",
                0,
                "cells",
                0,
                "raw_results",
                0,
                "sha256",
            ),
            "0" * 64,
            "raw provenance|SHA",
        ),
        (
            (
                "experiments",
                1,
                "cells",
                1,
                "raw_results",
                1,
                "sha256",
            ),
            "f" * 64,
            "raw provenance|SHA",
        ),
        (
            (
                "experiments",
                0,
                "cells",
                0,
                "raw_results",
                0,
                "role",
            ),
            "archive",
            "raw provenance|role",
        ),
        (
            (
                "experiments",
                0,
                "cells",
                0,
                "raw_results",
                0,
                "execution",
                "workers",
            ),
            2,
            "worker|raw provenance",
        ),
        (
            (
                "experiments",
                0,
                "cells",
                0,
                "raw_results",
                0,
                "execution",
                "blas_threads",
                "OMP_NUM_THREADS",
            ),
            "2",
            "BLAS|thread",
        ),
        (
            (
                "experiments",
                0,
                "cells",
                0,
                "raw_results",
                0,
                "execution",
                "process_start_method",
            ),
            "fork",
            "spawn|start method",
        ),
        (
            (
                "experiments",
                0,
                "cells",
                0,
                "raw_results",
                0,
                "execution",
                "wall_time_seconds",
            ),
            0,
            "wall time",
        ),
        (
            ("experiments", 0, "cells", 0, "anchors", 0, "anchor_kind"),
            "pair-creation",
            "anchor kind",
        ),
    ],
    ids=[
        "fixture-schema",
        "protocol",
        "raw-schema",
        "exact-field",
        "transform-name",
        "transform-formula",
        "transform-convention",
        "experiment-id",
        "source-commit",
        "second-source-commit",
        "family",
        "mask",
        "system-shape",
        "host-role",
        "packages",
        "last-cell-packages",
        "scientific-payload-equality",
        "raw-path",
        "raw-sha",
        "last-raw-sha",
        "raw-role",
        "workers",
        "blas-threads",
        "spawn-method",
        "wall-time",
        "anchor-kind",
    ],
)
def test_r01_classifier_rejects_wrong_fixed_metadata_before_replay(
    r01_fixture_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str | int, ...],
    replacement: object,
    message: str,
) -> None:
    payload = copy.deepcopy(r01_fixture_payload)
    _set_r01_path(payload, path, replacement)
    monkeypatch.setattr(
        overlap_klein,
        "build_system",
        _forbid_r01_build_system,
    )

    with pytest.raises(ValueError, match=message):
        classify_r01_fixture(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-anchor",
        "extra-anchor",
        "duplicate-anchor",
        "reordered-anchors",
        "wrong-anchor-count",
        "reordered-experiments",
        "reordered-cells",
        "reordered-raw-roles",
    ],
)
def test_r01_classifier_rejects_incomplete_or_reordered_coverage_before_replay(
    r01_fixture_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    payload = copy.deepcopy(r01_fixture_payload)
    experiments = payload["experiments"]
    first_cell = experiments[0]["cells"][0]
    anchors = first_cell["anchors"]

    if mutation == "missing-anchor":
        anchors.pop()
    elif mutation == "extra-anchor":
        extra = copy.deepcopy(anchors[0])
        extra["label"] = "h9<-9"
        extra["zero_certificate"]["anchor_label"] = "h9<-9"
        anchors.append(extra)
    elif mutation == "duplicate-anchor":
        anchors[-1] = copy.deepcopy(anchors[0])
    elif mutation == "reordered-anchors":
        anchors[0], anchors[1] = anchors[1], anchors[0]
    elif mutation == "wrong-anchor-count":
        first_cell["anchor_count"] = 99
    elif mutation == "reordered-experiments":
        experiments[0], experiments[1] = experiments[1], experiments[0]
    elif mutation == "reordered-cells":
        cells = experiments[0]["cells"]
        cells[0], cells[1] = cells[1], cells[0]
    elif mutation == "reordered-raw-roles":
        raw_results = first_cell["raw_results"]
        raw_results[0], raw_results[1] = raw_results[1], raw_results[0]
    else:
        raise AssertionError(mutation)

    monkeypatch.setattr(
        overlap_klein,
        "build_system",
        _forbid_r01_build_system,
    )
    with pytest.raises(
        ValueError,
        match="coverage|order|experiment|cell|raw provenance",
    ):
        classify_r01_fixture(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        "zero-with-feasible-status",
        "zero-without-certificate",
        "zero-with-primal-shaped-certificate",
        "feasible-without-primal",
        "numerical-only-with-zero-certificate",
        "unknown-classification",
    ],
)
def test_r01_classifier_rejects_inconsistent_evidence_before_replay(
    r01_fixture_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    payload = copy.deepcopy(r01_fixture_payload)
    anchor = _first_r01_anchor(payload)

    if mutation == "zero-with-feasible-status":
        anchor["positive"]["status"] = "feasible"
    elif mutation == "zero-without-certificate":
        anchor.pop("zero_certificate")
    elif mutation == "zero-with-primal-shaped-certificate":
        anchor["zero_certificate"] = {
            "kind": "primal",
            "anchor_label": anchor["label"],
            "anchor_sign": 1,
            "coefficients": ["0"] * 24,
        }
    elif mutation == "feasible-without-primal":
        anchor["classification"] = "certified-feasible"
        anchor["positive"] = {"status": "feasible"}
        anchor["negative"] = {"status": "infeasible"}
        anchor.pop("zero_certificate")
    elif mutation == "numerical-only-with-zero-certificate":
        anchor["classification"] = "numerical-only"
    elif mutation == "unknown-classification":
        anchor["classification"] = "unknown"
    else:
        raise AssertionError(mutation)

    monkeypatch.setattr(
        overlap_klein,
        "build_system",
        _forbid_r01_build_system,
    )
    with pytest.raises(
        ValueError,
        match="classification|certified-zero|zero certificate|replayable primal",
    ):
        classify_r01_fixture(payload)


def test_r01_classifier_returns_incomplete_without_replaying_other_duals(
    r01_fixture_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = copy.deepcopy(r01_fixture_payload)
    anchor = _first_r01_anchor(payload)
    anchor["classification"] = "numerical-only"
    anchor.pop("zero_certificate")
    monkeypatch.setattr(
        overlap_klein,
        "build_system",
        _forbid_r01_build_system,
    )

    assert classify_r01_fixture(payload) == {
        "outcome": "evidence-incomplete",
        "fixture_schema_version": 2,
        "protocol": "overlap-klein-v1",
        "unresolved": [
            {
                "experiment_id": "R01-E001",
                "family": "number-conserving",
                "mask": "rings-bridges",
                "label": "h0<-4",
            }
        ],
    }


def test_r01_classifier_rejects_a_corrupted_exact_double_dual(
    r01_fixture_payload: dict[str, object],
) -> None:
    payload = copy.deepcopy(r01_fixture_payload)
    certificate = _first_r01_anchor(payload)["zero_certificate"]
    certificate["plus_weights"] = ["0"] * len(certificate["plus_weights"])

    with pytest.raises(ValueError, match="dual certificate does not verify"):
        classify_r01_fixture(payload)


def test_r01_classifier_rejects_certified_feasible_without_a_primal(
    r01_fixture_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = copy.deepcopy(r01_fixture_payload)
    anchor = _first_r01_anchor(payload)
    anchor["classification"] = "certified-feasible"
    anchor["positive"] = {"status": "feasible"}
    anchor["negative"] = {"status": "infeasible"}
    anchor.pop("zero_certificate")
    monkeypatch.setattr(
        overlap_klein,
        "build_system",
        _forbid_r01_build_system,
    )

    with pytest.raises(ValueError, match="replayable primal"):
        classify_r01_fixture(payload)


def test_r01_classifier_rejects_a_false_exact_primal(
    r01_fixture_payload: dict[str, object],
) -> None:
    payload = copy.deepcopy(r01_fixture_payload)
    anchor = _first_r01_anchor(payload)
    anchor["classification"] = "certified-feasible"
    anchor["positive"] = {
        "status": "feasible",
        "certificate": {
            "kind": "primal",
            "anchor_label": "h0<-4",
            "anchor_sign": 1,
            "coefficients": ["0"] * 24,
        },
    }
    anchor["negative"] = {"status": "infeasible"}
    anchor.pop("zero_certificate")

    with pytest.raises(ValueError, match="primal certificate does not verify"):
        classify_r01_fixture(payload)


def test_r01_classifier_rejects_a_sign_mismatched_replayed_primal(
    r01_fixture_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = copy.deepcopy(r01_fixture_payload)
    anchor = _first_r01_anchor(payload)
    anchor["classification"] = "certified-feasible"
    anchor["positive"] = {
        "status": "feasible",
        "certificate": {
            "kind": "primal",
            "anchor_label": "h0<-4",
            "anchor_sign": 1,
            "coefficients": ["0"] * 24,
        },
    }
    anchor["negative"] = {"status": "infeasible"}
    anchor.pop("zero_certificate")
    real_system = build_system("number-conserving", "rings-bridges")
    monkeypatch.setattr(
        overlap_klein,
        "build_system",
        lambda family, mask: real_system,
    )
    monkeypatch.setattr(
        overlap_klein,
        "certificate_from_json",
        lambda certificate, system: ExactPrimalCertificate(
            anchor_label="h0<-4",
            anchor_sign=-1,
            coefficients=tuple(sp.zeros(len(system.labels), 1)),
        ),
    )

    with pytest.raises(ValueError, match="sign"):
        classify_r01_fixture(payload)


def test_r01_classifier_builds_four_systems_and_parses_each_dual_once(
    r01_fixture_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_shapes = {
        ("number-conserving", "rings-bridges"): (560, 24),
        ("number-conserving", "rings-diagonals-bridges"): (748, 32),
        ("bdg", "rings-bridges"): (1052, 42),
        ("bdg", "rings-diagonals-bridges"): (1456, 58),
    }
    build_calls: list[tuple[str, str]] = []
    parsed_labels: list[str] = []

    def fake_build_system(family: str, mask: str) -> ExactMetzlerSystem:
        build_calls.append((family, mask))
        row_count, column_count = expected_shapes[(family, mask)]
        rows = (MetzlerRow("even", 1, 0),) * row_count
        labels = tuple(f"x{index}" for index in range(column_count))
        return ExactMetzlerSystem(
            labels=labels,
            rows=rows,
            coefficients=sp.ImmutableSparseMatrix(
                row_count,
                column_count,
                {},
            ),
        )

    def fake_certificate_from_json(
        certificate: dict[str, object],
        system: ExactMetzlerSystem,
    ) -> ExactDualCertificate:
        assert system.coefficients.shape in expected_shapes.values()
        label = certificate["anchor_label"]
        assert isinstance(label, str)
        parsed_labels.append(label)
        return ExactDualCertificate(
            anchor_label=label,
            plus_weights=(),
            minus_weights=(),
        )

    def forbid_direct_verification(
        *args: object,
        **kwargs: object,
    ) -> bool:
        raise AssertionError("classifier duplicated exact certificate replay")

    monkeypatch.setattr(overlap_klein, "build_system", fake_build_system)
    monkeypatch.setattr(
        overlap_klein,
        "certificate_from_json",
        fake_certificate_from_json,
    )
    monkeypatch.setattr(
        overlap_klein,
        "verify_zero_dual",
        forbid_direct_verification,
    )
    monkeypatch.setattr(
        overlap_klein,
        "verify_primal",
        forbid_direct_verification,
    )

    summary = classify_r01_fixture(copy.deepcopy(r01_fixture_payload))

    assert summary["outcome"] == "exact-bridge-coordinate-no-go"
    assert build_calls == [
        ("number-conserving", "rings-bridges"),
        ("number-conserving", "rings-diagonals-bridges"),
        ("bdg", "rings-bridges"),
        ("bdg", "rings-diagonals-bridges"),
    ]
    assert len(parsed_labels) == 24


def test_r01_fixture_classifications_are_consistent_and_all_certificates_replay() -> None:
    """Catches unsupported classifications or compact certificate corruption."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    experiments = payload["experiments"]
    assert len(experiments) == 2
    assert all(len(experiment["cells"]) == 2 for experiment in experiments)
    assert [
        [
            [anchor["classification"] for anchor in cell["anchors"]]
            for cell in experiment["cells"]
        ]
        for experiment in experiments
    ] == [
        [["certified-zero"] * 4, ["certified-zero"] * 4],
        [["certified-zero"] * 8, ["certified-zero"] * 8],
    ]
    for experiment in experiments:
        for cell in experiment["cells"]:
            system = build_system(cell["family"], cell["mask"])
            for anchor in cell["anchors"]:
                assert anchor["positive"]["status"] in {
                    "feasible",
                    "infeasible",
                }
                assert anchor["negative"]["status"] in {
                    "feasible",
                    "infeasible",
                }
                if anchor["classification"] == "certified-feasible":
                    replayed = 0
                    for sign_name in ("positive", "negative"):
                        branch = anchor[sign_name]
                        if "certificate" in branch:
                            certificate = certificate_from_json(
                                branch["certificate"], system
                            )
                            assert verify_primal(system, certificate)
                            assert certificate.anchor_label == anchor["label"]
                            assert certificate.anchor_sign == (
                                1 if sign_name == "positive" else -1
                            )
                            replayed += 1
                    assert replayed >= 1
                elif anchor["classification"] == "certified-zero":
                    assert anchor["positive"]["status"] == "infeasible"
                    assert anchor["negative"]["status"] == "infeasible"
                    certificate = certificate_from_json(
                        anchor["zero_certificate"], system
                    )
                    assert verify_zero_dual(system, certificate)
                    assert certificate.anchor_label == anchor["label"]
                elif anchor["classification"] == "numerical-only":
                    assert "zero_certificate" not in anchor
                else:
                    raise AssertionError(anchor["classification"])


def test_r01_bdg_anchor_kinds_and_number_conserving_inclusion_are_explicit() -> None:
    """Catches conflating hopping/pair anchors or a zero-pairing hopping ray."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    bdg_experiment = next(
        experiment
        for experiment in payload["experiments"]
        if experiment["experiment_id"] == "R01-E002"
    )
    expected_kinds = [
        ("h0<-4", "hopping"),
        ("h1<-5", "hopping"),
        ("h4<-0", "hopping"),
        ("h5<-1", "hopping"),
        ("pa0,4", "pair-annihilation"),
        ("pa1,5", "pair-annihilation"),
        ("pc0,4", "pair-creation"),
        ("pc1,5", "pair-creation"),
    ]
    hopping_primal_count = 0
    for cell in bdg_experiment["cells"]:
        assert [
            (anchor["label"], anchor["anchor_kind"])
            for anchor in cell["anchors"]
        ] == expected_kinds
        system = build_system(cell["family"], cell["mask"])
        pairing_indices = [
            index
            for index, label in enumerate(system.labels)
            if label.startswith(("pa", "pc"))
        ]
        assert pairing_indices
        for anchor in cell["anchors"]:
            if anchor["anchor_kind"] != "hopping":
                continue
            for sign_name in ("positive", "negative"):
                branch = anchor[sign_name]
                if "certificate" not in branch:
                    continue
                hopping_primal_count += 1
                certificate = certificate_from_json(
                    branch["certificate"], system
                )
                assert isinstance(certificate, ExactPrimalCertificate)
                assert any(
                    sp.simplify(certificate.coefficients[index]) != 0
                    for index in pairing_indices
                )

    assert hopping_primal_count == 0


def test_classifier_keeps_two_feasible_sign_certificates_separate() -> None:
    """Catches collapsing two exact primal witnesses into one ambiguous field."""
    system = _synthetic_system([[0, 1]])
    anchor = classify_anchor(
        system,
        "x",
        positive_solve=solve_anchor(system, "x", 1),
        negative_solve=solve_anchor(system, "x", -1),
    )

    assert anchor["classification"] == "certified-feasible"
    assert "zero_certificate" not in anchor
    for sign in (anchor["positive"], anchor["negative"]):
        certificate = certificate_from_json(sign["exact_primal_certificate"], system)
        assert isinstance(certificate, ExactPrimalCertificate)
        assert verify_primal(system, certificate)


def test_classifier_requires_a_replaying_double_dual_for_zero() -> None:
    """Catches promoting two nominal infeasibilities without both exact duals."""
    system = _synthetic_system([[1, 0], [-1, 0]])
    anchor = classify_anchor(
        system,
        "x",
        positive_solve=solve_anchor(system, "x", 1),
        negative_solve=solve_anchor(system, "x", -1),
    )

    assert anchor["classification"] == "certified-zero"
    certificate = certificate_from_json(anchor["zero_certificate"], system)
    assert isinstance(certificate, ExactDualCertificate)
    assert verify_zero_dual(system, certificate)


def test_classifier_downgrades_an_unreplayable_double_dual() -> None:
    """Catches calling nominal infeasibility a zero without an exact dual."""
    system = _synthetic_system([[0, 1], [0, -1]])
    anchor = classify_anchor(
        system,
        "x",
        positive_solve=AnchorSolve("x", 1, "infeasible", (), None, "nominal"),
        negative_solve=AnchorSolve("x", -1, "infeasible", (), None, "nominal"),
    )

    assert anchor["classification"] == "numerical-only"
    assert "zero_certificate" not in anchor
    assert "dual_replay_diagnostic" in anchor


def test_classifier_downgrades_a_failed_exact_primal_reconstruction() -> None:
    """Catches treating a floating feasible solve as certified without replay."""
    system = _synthetic_system([[1, 0], [0, 1]])
    anchor = classify_anchor(
        system,
        "x",
        positive_solve=AnchorSolve(
            "x", 1, "feasible", (1.0, math.nan), 0.0, "nominal"
        ),
        negative_solve=AnchorSolve("x", -1, "error", (), None, "failed"),
    )

    assert anchor["classification"] == "numerical-only"
    assert "exact_primal_certificate" not in anchor["positive"]
    assert "exact_replay_diagnostic" in anchor["positive"]


def test_blas_thread_validator_requires_all_three_thread_limits() -> None:
    """Catches running a parallel scan with a missing or non-unit BLAS limit."""
    expected = {
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    assert validate_blas_thread_environment(expected) == expected
    for name in expected:
        invalid = {**expected, name: "2"}
        with pytest.raises(ValueError, match=name):
            validate_blas_thread_environment(invalid)


def test_execution_metadata_records_validated_threads_and_spawn() -> None:
    """Catches an execution payload that hides BLAS limits or start method."""
    settings = {
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    assert execution_metadata(
        workers=2, wall_time_seconds=1.25, thread_settings=settings
    ) == {
        "workers": 2,
        "wall_time_seconds": 1.25,
        "blas_threads": settings,
        "process_start_method": "spawn",
    }


def test_q_sqrt_two_numeric_solves_do_not_emit_bitcount_warning() -> None:
    """Catches a warning leak from either numeric coefficient conversion path."""
    system = _synthetic_system([[sp.sqrt(2), 0], [-sp.sqrt(2), 0]])
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message=".*bitcount function is deprecated.*",
            category=DeprecationWarning,
            module=r"mpmath\.libmp\.libintmath",
        )
        assert solve_anchor(system, "x", 1).status == "infeasible"
        certificate = find_zero_dual(system, "x")
        assert verify_zero_dual(system, certificate)


def test_q_sqrt_two_to_float_uses_the_exact_field_decomposition() -> None:
    """Catches restoring SymPy/mpmath float conversion for exact coefficients."""
    expression = sp.Rational(3, 2) - sp.sqrt(2) / 3
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message=".*bitcount function is deprecated.*",
            category=DeprecationWarning,
            module=r"mpmath\.libmp\.libintmath",
        )
        observed = _q_sqrt_two_to_float(expression)
        assert solve_anchor(
            _synthetic_system([[sp.sqrt(2), 0], [-sp.sqrt(2), 0]]),
            "x",
            1,
        ).status == "infeasible"

    assert observed == pytest.approx(1.5 - math.sqrt(2.0) / 3.0)


def test_numeric_system_matrix_converts_only_sparse_exact_entries_once() -> None:
    """Catches dense structural-zero conversion or a mutable worker matrix."""
    system = _synthetic_system(
        [[sp.sqrt(2), 0], [0, -sp.Rational(3, 2)]]
    )

    matrix = _numeric_system_matrix(system)

    assert matrix.flags.c_contiguous
    assert not matrix.flags.writeable
    assert np.array_equal(
        matrix,
        np.array([[math.sqrt(2.0), 0.0], [0.0, -1.5]]),
    )


def test_anchor_worker_reuses_the_initialized_numeric_matrix() -> None:
    """Catches workers rebuilding a numeric system for each anchor-sign task."""
    system = _synthetic_system([[sp.sqrt(2), 0], [0, 1]])
    matrix = _numeric_system_matrix(system)
    spawn_matrix = pickle.loads(pickle.dumps(matrix))
    assert spawn_matrix.flags.writeable
    try:
        overlap_klein._initialize_anchor_worker(system, spawn_matrix)
        positive = overlap_klein._solve_anchor_worker(("x", 1))
        negative = overlap_klein._solve_anchor_worker(("x", -1))

        assert overlap_klein._WORKER_NUMERIC_MATRIX is not spawn_matrix
        assert overlap_klein._WORKER_NUMERIC_MATRIX is not None
        assert not overlap_klein._WORKER_NUMERIC_MATRIX.flags.writeable
        assert positive.status == "feasible"
        assert negative.status == "infeasible"
        assert not matrix.flags.writeable
    finally:
        overlap_klein._WORKER_SYSTEM = None
        overlap_klein._WORKER_NUMERIC_MATRIX = None


def _runner_environment_without_blas_limits() -> dict[str, str]:
    environment = dict(os.environ)
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        environment.pop(name, None)
    return environment


def test_runner_help_succeeds_without_blas_environment() -> None:
    """Catches validating BLAS before argparse can serve --help."""
    result = subprocess.run(
        [sys.executable, "-m", "oracle.overlap_klein", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        env=_runner_environment_without_blas_limits(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "Traceback" not in result.stderr


def test_runner_missing_blas_limit_is_a_clean_argument_error(tmp_path: Path) -> None:
    """Catches a missing required thread limit leaking a traceback or output."""
    output = tmp_path / "result.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "oracle.overlap_klein",
            "--family",
            "number-conserving",
            "--mask",
            "rings-bridges",
            "--workers",
            "1",
            "--source-commit",
            "a" * 40,
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=_runner_environment_without_blas_limits(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "OMP_NUM_THREADS must be set to the string '1'" in result.stderr
    assert "Traceback" not in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("workers", (0, -1, True))
def test_anchor_scan_rejects_nonpositive_or_boolean_worker_counts(
    workers: int,
) -> None:
    """Catches accepting invalid worker counts before starting processes."""
    with pytest.raises(ValueError, match="workers"):
        run_anchor_scan(
            "number-conserving",
            "rings-bridges",
            workers=workers,
            source_commit="c" * 40,
        )


@pytest.mark.parametrize("source_commit", ("A" * 39, "g" * 40, "a" * 41))
def test_anchor_scan_requires_a_canonical_full_git_commit(
    source_commit: str,
) -> None:
    """Catches accepting abbreviated or non-hex source provenance."""
    with pytest.raises(ValueError, match="source_commit"):
        run_anchor_scan(
            "number-conserving",
            "rings-bridges",
            workers=1,
            source_commit=source_commit,
        )


def test_write_result_creates_sorted_utf8_json_at_the_requested_path(
    tmp_path: Path,
) -> None:
    """Catches writing an unstable encoding or a sibling instead of output."""
    output = tmp_path / "nested" / "result.json"
    write_result({"z": "\u221a2", "a": {"b": 1}}, output)

    assert output.read_bytes() == b'{\n  "a": {\n    "b": 1\n  },\n  "z": "\xe2\x88\x9a2"\n}\n'
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "a": {"b": 1},
        "z": "\u221a2",
    }
