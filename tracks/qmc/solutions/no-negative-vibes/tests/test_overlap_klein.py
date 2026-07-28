from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import math
from pathlib import Path
import warnings

import pytest
import sympy as sp

from oracle.fock_basis import quadratic_term
from oracle.metzler_system import ExactMetzlerSystem, MetzlerRow
from oracle.overlap_klein import (
    AnchorSolve,
    ExactDualCertificate,
    ExactPrimalCertificate,
    bridge_labels,
    build_system,
    classify_anchor,
    certificate_from_json,
    certificate_to_json,
    find_zero_dual,
    execution_metadata,
    overlap_geometry,
    quadratic_basis,
    reconstruct_exact_primal,
    run_anchor_scan,
    solve_anchor,
    support_edges,
    verify_primal,
    verify_zero_dual,
    validate_blas_thread_environment,
    write_result,
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
