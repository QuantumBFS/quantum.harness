from __future__ import annotations

import numpy as np
import pytest

from oracle.exterior_cone import (
    common_transform_certificate,
    compound_matrix,
    determinant_from_compound_traces,
    subset_basis,
    transformed_nonnegative_margin,
)


def test_subset_basis_is_lexicographic_and_validates_grade() -> None:
    """Catches a basis-order change or an invalid exterior grade."""
    assert subset_basis(4, 2) == (
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 2),
        (1, 3),
        (2, 3),
    )
    with pytest.raises(ValueError):
        subset_basis(3, 4)


def test_compound_matrix_uses_fixed_minor_convention() -> None:
    """Catches exchanging declared minor rows and columns."""
    matrix = np.array([[1, 2, 0], [0, 3, 4], [5, 0, 6]], dtype=float)
    expected = np.array(
        [[3, 4, 8], [-10, 6, 12], [-15, -20, 18]],
        dtype=float,
    )

    np.testing.assert_allclose(compound_matrix(matrix, 2), expected)


def test_compound_is_multiplicative() -> None:
    """Catches a compound that is not the declared exterior representation."""
    left = np.array([[1, 1, 0], [0, 1, 2], [1, 0, 1]], dtype=float)
    right = np.array([[2, 0, 1], [1, 1, 0], [0, 1, 1]], dtype=float)

    np.testing.assert_allclose(
        compound_matrix(left @ right, 2),
        compound_matrix(left, 2) @ compound_matrix(right, 2),
    )


def test_compound_trace_sum_reconstructs_det_i_plus_b() -> None:
    """Catches omitting an exterior grade from the determinant expansion."""
    matrix = np.array([[0.5, 1.0], [-0.25, 2.0]])

    assert determinant_from_compound_traces(matrix) == pytest.approx(
        np.linalg.det(np.eye(2) + matrix)
    )


@pytest.mark.parametrize(
    "matrices",
    [
        (np.ones((2, 3)),),
        (np.array([[1.0, np.nan], [0.0, 1.0]]),),
        (np.eye(2), np.eye(3)),
    ],
)
def test_transformed_margin_rejects_invalid_matrix_inputs(
    matrices: tuple[np.ndarray, ...],
) -> None:
    """Catches accepting nonsquare, nonfinite, or mixed-size atoms."""
    with pytest.raises(ValueError):
        transformed_nonnegative_margin(matrices, np.eye(2), tolerance=1.0e-12)


@pytest.mark.parametrize(
    "transform",
    [np.ones((2, 3)), np.array([[1.0, 0.0], [0.0, 0.0]])],
)
def test_transformed_margin_rejects_invalid_transform(
    transform: np.ndarray,
) -> None:
    """Catches accepting transforms with the wrong shape or no inverse."""
    with pytest.raises(ValueError):
        transformed_nonnegative_margin((np.eye(2),), transform, tolerance=1.0e-12)


def test_transformed_margin_rejects_imaginary_residue_above_tolerance() -> None:
    """Catches treating a materially complex transformed entry as nonnegative."""
    transform = np.array([[1.0, 1.0j], [0.0, 1.0]])

    assert (
        transformed_nonnegative_margin(
            (np.diag([1.0, 2.0]),), transform, tolerance=1.0e-12
        )
        is None
    )


def test_common_transform_certificate_uses_one_positive_diagonal_basis() -> None:
    """Catches a certificate that skips grades or emits non-JSON values."""
    atom = np.diag([2.0, 3.0])
    transform_library = {
        0: (("identity-0", np.eye(1)),),
        1: (("identity-1", np.eye(2)),),
        2: (("identity-2", np.eye(1)),),
    }

    certificate = common_transform_certificate(
        (atom,), transform_library, tolerance=1.0e-12
    )

    assert certificate == {
        "dimension": 2,
        "basis_convention": "lexicographic-subsets",
        "grades": [
            {
                "grade": 0,
                "transform_id": "identity-0",
                "transform": [[1.0]],
                "minimum_entry": 1.0,
            },
            {
                "grade": 1,
                "transform_id": "identity-1",
                "transform": [[1.0, 0.0], [0.0, 1.0]],
                "minimum_entry": 0.0,
            },
            {
                "grade": 2,
                "transform_id": "identity-2",
                "transform": [[1.0]],
                "minimum_entry": 6.0,
            },
        ],
    }


def test_common_transform_certificate_fails_for_an_unavoidable_negative_diagonal() -> None:
    """Catches selecting a different transform for different atoms at one grade."""
    atom_a = np.diag([2.0, 3.0])
    atom_b = np.diag([-1.0, 2.0])
    transform_library = {
        0: (("identity-0", np.eye(1)),),
        1: (
            ("identity-1", np.eye(2)),
            ("swap-1", np.array([[0.0, 1.0], [1.0, 0.0]])),
        ),
        2: (("identity-2", np.eye(1)),),
    }

    assert (
        common_transform_certificate(
            (atom_a, atom_b), transform_library, tolerance=1.0e-12
        )
        is None
    )
