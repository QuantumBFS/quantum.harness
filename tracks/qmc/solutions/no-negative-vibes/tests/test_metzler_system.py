from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest
import sympy as sp

from oracle.fock_basis import (
    QuadraticBasisElement,
    parity_indices,
    quadratic_term,
)
from oracle.metzler_system import (
    ExactMetzlerSystem,
    MetzlerRow,
    compile_metzler_system,
    exact_linear_combination,
    exact_nonnegative,
    numeric_coefficients,
    verify_exact_metzler,
)


def _two_mode_hopping_basis() -> tuple[QuadraticBasisElement, ...]:
    return (
        QuadraticBasisElement(
            "h0<-1", "hop", 0, 1, quadratic_term(2, "hop", 0, 1)
        ),
        QuadraticBasisElement(
            "h1<-0", "hop", 1, 0, quadratic_term(2, "hop", 1, 0)
        ),
    )


def test_identity_compiler_tracks_offdiagonal_rows_and_labels() -> None:
    basis = _two_mode_hopping_basis()
    system = compile_metzler_system(sp.eye(4), basis, parity_indices(2))

    assert system.labels == ("h0<-1", "h1<-0")
    assert system.coefficients.cols == 2
    assert all(row.target_state != row.source_state for row in system.rows)
    assert np.allclose(
        numeric_coefficients(system),
        np.array(system.coefficients.tolist(), dtype=float),
    )


def test_compiler_matches_a_hand_derived_nontrivial_parity_fixture() -> None:
    inverse_sqrt_two = 1 / sp.sqrt(2)
    transform = sp.ImmutableSparseMatrix(
        [
            [inverse_sqrt_two, 0, 0, inverse_sqrt_two],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [inverse_sqrt_two, 0, 0, -inverse_sqrt_two],
        ]
    )
    basis = (
        QuadraticBasisElement(
            "pc0,1",
            "pair_create",
            0,
            1,
            quadratic_term(2, "pair_create", 0, 1),
        ),
        QuadraticBasisElement(
            "pa0,1",
            "pair_annihilate",
            0,
            1,
            quadratic_term(2, "pair_annihilate", 0, 1),
        ),
        QuadraticBasisElement(
            "h0<-1", "hop", 0, 1, quadratic_term(2, "hop", 0, 1)
        ),
        QuadraticBasisElement(
            "h1<-0", "hop", 1, 0, quadratic_term(2, "hop", 1, 0)
        ),
    )

    system = compile_metzler_system(transform, basis, parity_indices(2))

    assert system.labels == ("pc0,1", "pa0,1", "h0<-1", "h1<-0")
    assert system.rows == (
        MetzlerRow("even", 0, 3),
        MetzlerRow("even", 3, 0),
        MetzlerRow("odd", 1, 2),
        MetzlerRow("odd", 2, 1),
    )
    assert system.coefficients == sp.ImmutableSparseMatrix(
        [
            [sp.Rational(1, 2), sp.Rational(-1, 2), 0, 0],
            [sp.Rational(-1, 2), sp.Rational(1, 2), 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
    )


def test_exact_verifier_accepts_positive_hops_and_rejects_negative_hop() -> None:
    system = compile_metzler_system(
        sp.eye(4), _two_mode_hopping_basis(), parity_indices(2)
    )

    assert verify_exact_metzler(system, (sp.Integer(1), sp.Integer(2)))
    assert not verify_exact_metzler(
        system, (sp.Integer(-1), sp.Integer(2))
    )


def test_compiler_drops_only_identically_zero_constraint_rows() -> None:
    basis = (
        QuadraticBasisElement(
            "n0", "hop", 0, 0, quadratic_term(2, "hop", 0, 0)
        ),
    )

    system = compile_metzler_system(sp.eye(4), basis, parity_indices(2))

    assert system.coefficients.shape == (0, 1)
    assert numeric_coefficients(system).shape == (0, 1)
    assert system.rows == ()


@pytest.mark.parametrize(
    ("expression", "expected"),
    (
        (sp.Integer(0), True),
        (sp.Integer(7), True),
        (sp.Integer(-7), False),
        (-1 + sp.sqrt(2), True),
        (3 - 2 * sp.sqrt(2), True),
        (1 - sp.sqrt(2), False),
        (-3 + 2 * sp.sqrt(2), False),
        (sp.sqrt(2) / 2, True),
        (-sp.sqrt(2) / 2, False),
    ),
)
def test_exact_sign_decision_handles_q_sqrt_two(
    expression: sp.Expr, expected: bool
) -> None:
    assert exact_nonnegative(expression) is expected


@pytest.mark.parametrize(
    "expression",
    (
        sp.sqrt(3),
        sp.Symbol("x"),
        sp.Float("0.25"),
        sp.I,
        sp.oo,
        sp.nan,
    ),
)
def test_exact_sign_decision_rejects_unsupported_expressions(
    expression: sp.Expr,
) -> None:
    with pytest.raises(ValueError, match=r"Q\(sqrt\(2\)\)"):
        exact_nonnegative(expression)


def test_exact_linear_combination_returns_exact_immutable_slacks() -> None:
    system = ExactMetzlerSystem(
        labels=("x", "y"),
        rows=(
            MetzlerRow("even", 1, 0),
            MetzlerRow("odd", 2, 1),
        ),
        coefficients=sp.ImmutableSparseMatrix(
            [[1, sp.sqrt(2)], [-1, 1]]
        ),
    )

    observed = exact_linear_combination(
        system, (sp.Integer(2), sp.Integer(3))
    )

    assert isinstance(observed, sp.ImmutableMatrix)
    assert observed == sp.ImmutableMatrix([2 + 3 * sp.sqrt(2), 1])


def test_exact_linear_combination_rejects_wrong_or_inexact_coefficients() -> None:
    system = ExactMetzlerSystem(
        labels=("x", "y"),
        rows=(MetzlerRow("even", 1, 0),),
        coefficients=sp.ImmutableSparseMatrix([[1, 0]]),
    )

    with pytest.raises(ValueError, match="two coefficients"):
        exact_linear_combination(system, (sp.Integer(1),))
    with pytest.raises(ValueError, match="exact"):
        exact_linear_combination(system, (sp.Float("1.0"), sp.Integer(0)))


def test_system_and_row_records_are_immutable() -> None:
    row = MetzlerRow("even", 1, 0)
    system = ExactMetzlerSystem(
        labels=("x",),
        rows=(row,),
        coefficients=sp.ImmutableSparseMatrix([[1]]),
    )

    with pytest.raises(FrozenInstanceError):
        row.parity = "odd"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        system.labels = ("y",)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("transform", "message"),
    (
        (sp.zeros(3, 4), "square"),
        (sp.eye(3), "power of two"),
        (sp.diag(2, 1, 1, 1), "orthogonal"),
        (
            sp.Matrix(
                [
                    [1.0, 0, 0, 0],
                    [0, 1, 0, 0],
                    [0, 0, 1, 0],
                    [0, 0, 0, 1],
                ]
            ),
            "exact",
        ),
        (
            sp.ImmutableSparseMatrix(
                [
                    [0, 1, 0, 0],
                    [1, 0, 0, 0],
                    [0, 0, 1, 0],
                    [0, 0, 0, 1],
                ]
            ),
            "preserve",
        ),
    ),
)
def test_compiler_rejects_invalid_transforms(
    transform: sp.MatrixBase, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        compile_metzler_system(
            transform, _two_mode_hopping_basis(), parity_indices(2)
        )


@pytest.mark.parametrize(
    ("blocks", "message"),
    (
        (((0, 3),), "two parity blocks"),
        (((0, 3), (1, 1, 2)), "partition"),
        (((0, 3), (1,)), "partition"),
        (((0, 4), (1, 2)), "state index"),
        (((0, 1), (2, 3)), "even and odd"),
    ),
)
def test_compiler_rejects_invalid_parity_blocks(
    blocks: tuple[tuple[int, ...], ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        compile_metzler_system(sp.eye(4), _two_mode_hopping_basis(), blocks)


def test_compiler_rejects_invalid_basis_elements() -> None:
    valid = _two_mode_hopping_basis()[0]
    wrong_dimension = QuadraticBasisElement(
        "bad-shape",
        "hop",
        0,
        1,
        sp.ImmutableSparseMatrix(sp.eye(8)),
    )
    duplicate_label = QuadraticBasisElement(
        valid.label,
        "hop",
        1,
        0,
        quadratic_term(2, "hop", 1, 0),
    )
    inexact = QuadraticBasisElement(
        "inexact",
        "hop",
        0,
        1,
        sp.ImmutableSparseMatrix(
            sp.Float("0.5") * quadratic_term(2, "hop", 0, 1)
        ),
    )
    parity_mixing = QuadraticBasisElement(
        "parity-mixing",
        "hop",
        0,
        0,
        sp.ImmutableSparseMatrix(
            [
                [0, 1, 0, 0],
                [1, 0, 0, 0],
                [0, 0, 0, 0],
                [0, 0, 0, 0],
            ]
        ),
    )

    with pytest.raises(ValueError, match="dimension"):
        compile_metzler_system(
            sp.eye(4), (wrong_dimension,), parity_indices(2)
        )
    with pytest.raises(ValueError, match="unique"):
        compile_metzler_system(
            sp.eye(4), (valid, duplicate_label), parity_indices(2)
        )
    with pytest.raises(ValueError, match="exact"):
        compile_metzler_system(sp.eye(4), (inexact,), parity_indices(2))
    with pytest.raises(ValueError, match="preserve"):
        compile_metzler_system(
            sp.eye(4), (parity_mixing,), parity_indices(2)
        )


def test_six_mode_compiler_float_values_match_numpy_conjugation() -> None:
    from oracle.klein_hodge import overlap_klein_circuit
    from oracle.overlap_klein import quadratic_basis

    basis = quadratic_basis("number-conserving", "rings-bridges")
    transform = overlap_klein_circuit()
    system = compile_metzler_system(
        transform, basis, parity_indices(6)
    )
    rng = np.random.default_rng(20260728)
    coefficients = rng.normal(size=len(basis))
    transform_float = np.array(transform.tolist(), dtype=float)
    generator_float = sum(
        (
            value * np.array(item.fock.tolist(), dtype=float)
            for value, item in zip(coefficients, basis, strict=True)
        ),
        np.zeros((64, 64)),
    )
    direct = transform_float @ generator_float @ transform_float.T

    compiled = numeric_coefficients(system) @ coefficients
    observed = np.array(
        [
            direct[row.target_state, row.source_state]
            for row in system.rows
        ]
    )

    assert system.coefficients.rows > 0
    assert np.allclose(compiled, observed, atol=1e-12)
