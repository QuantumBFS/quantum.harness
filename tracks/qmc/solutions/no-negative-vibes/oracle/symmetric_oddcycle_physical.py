"""Exact physical transfer realization of the fixed symmetric-oddcycle atom."""

from __future__ import annotations

from collections.abc import Sequence

import sympy as sp

from .exterior_exact5_full_fock_cone import exact_fock_lift
from .exterior_exact5_shared_cone import exact_compound_matrix
from .symmetric_oddcycle_cones import fixed_candidate_matrix


SCHEMA = "symmetric-oddcycle-physical-transfer-v1"


def _word_product(word: str) -> sp.ImmutableMatrix:
    matrix = fixed_candidate_matrix()
    atoms = (matrix, matrix.T)
    product = sp.eye(matrix.rows)
    for symbol in word:
        if symbol not in {"0", "1"}:
            raise ValueError("word must contain only 0 and 1")
        product = atoms[int(symbol)] * product
    return sp.ImmutableMatrix(product)


def exact_fock_trace_replay(word: str = "01011") -> dict[str, object]:
    """Replay ``Tr Gamma(W) = det(I + W)`` and multiplicativity exactly."""

    matrix = fixed_candidate_matrix()
    atoms = (matrix, matrix.T)
    fock_atoms = tuple(exact_fock_lift(atom) for atom in atoms)
    fock_product = sp.eye(fock_atoms[0].rows)
    for symbol in word:
        if symbol not in {"0", "1"}:
            raise ValueError("word must contain only 0 and 1")
        fock_product = fock_atoms[int(symbol)] * fock_product
    product = _word_product(word)
    direct_lift = exact_fock_lift(product)
    if fock_product != direct_lift:
        raise RuntimeError("exterior Fock lift failed multiplicativity")
    fock_trace = int(sp.trace(direct_lift))
    determinant = int((sp.eye(matrix.rows) + product).det())
    if fock_trace != determinant:
        raise RuntimeError("Fock trace/determinant identity failed")
    return {
        "word": word,
        "fock_trace": fock_trace,
        "determinant": determinant,
        "multiplicative": True,
    }


def exact_physical_transfer_certificate(
    *,
    c: int = 19,
    replay_word: str = "01011",
) -> dict[str, object]:
    """Certify the normalized three-field transfer and its interaction gate."""

    if not isinstance(c, int) or isinstance(c, bool) or c < 0:
        raise ValueError("c must be a nonnegative integer")

    matrix = fixed_candidate_matrix()
    gamma = exact_fock_lift(matrix)
    symmetric_part = sp.ImmutableMatrix(gamma + gamma.T)
    row_requirements = tuple(
        int(
            sum(
                abs(symmetric_part[row, column])
                for column in range(symmetric_part.cols)
                if column != row
            )
            - symmetric_part[row, row]
        )
        for row in range(symmetric_part.rows)
    )
    maximum_requirement = max(row_requirements)
    maximizing_rows = tuple(
        row for row, value in enumerate(row_requirements)
        if value == maximum_requirement
    )
    row_margins = tuple(c - value for value in row_requirements)
    minimum_margin = min(row_margins)
    if minimum_margin <= 0:
        raise ValueError(
            f"c={c} does not pass the strict diagonal-dominance gate"
        )

    transfer = sp.ImmutableMatrix(c * sp.eye(gamma.rows) + symmetric_part)
    if any(
        transfer[row, row]
        <= sum(
            abs(transfer[row, column])
            for column in range(transfer.cols)
            if column != row
        )
        for row in range(transfer.rows)
    ):
        raise RuntimeError("reported transfer is not strictly diagonally dominant")

    characteristic = matrix.charpoly().as_poly()
    expected_coefficients = (1, -2, 1, -7, 16, -8)
    if tuple(int(value) for value in characteristic.all_coeffs()) != expected_coefficients:
        raise RuntimeError("fixed candidate characteristic polynomial changed")
    # For t>0, p(-t) has the six strictly negative coefficients below.
    negative_axis_coefficients = (-1, -2, -1, -7, -16, -8)
    if any(value >= 0 for value in negative_axis_coefficients):
        raise RuntimeError("negative-real-axis spectral gate failed")

    grade1 = sp.ImmutableMatrix(c * sp.eye(5) + matrix + matrix.T)
    grade2_atom = exact_compound_matrix(matrix, 2)
    grade2 = sp.ImmutableMatrix(
        c * sp.eye(grade2_atom.rows) + grade2_atom + grade2_atom.T
    )
    vacuum_scalar = c + 2
    gaussian_mismatch = sp.ImmutableMatrix(
        vacuum_scalar * grade2 - exact_compound_matrix(grade1, 2)
    )
    nonzero_entries = tuple(
        (row, column, int(gaussian_mismatch[row, column]))
        for row in range(gaussian_mismatch.rows)
        for column in range(gaussian_mismatch.cols)
        if gaussian_mismatch[row, column] != 0
    )
    if not nonzero_entries:
        raise RuntimeError("physical transfer unexpectedly passed the Gaussian gate")

    replay = exact_fock_trace_replay(replay_word)
    return {
        "schema": SCHEMA,
        "status": "exact-sign-free-physical-transfer",
        "one_particle_dimension": matrix.rows,
        "fock_dimension": gamma.rows,
        "c": c,
        "strict_diagonal_dominance": {
            "maximum_requirement": maximum_requirement,
            "maximizing_rows_zero_based": maximizing_rows,
            "minimum_row_margin": minimum_margin,
            "conclusion": "T_c is real symmetric positive definite",
        },
        "principal_real_log_gate": {
            "determinant": int(matrix.det()),
            "characteristic_coefficients": expected_coefficients,
            "p_minus_t_coefficients": negative_axis_coefficients,
            "spectrum_avoids_nonpositive_real_axis": True,
        },
        "normalized_auxiliary_fields": {
            "labels": ("identity", "B", "B.T"),
            "coefficients": (
                f"{c}/{vacuum_scalar}",
                f"1/{vacuum_scalar}",
                f"1/{vacuum_scalar}",
            ),
            "coefficient_sum": "1",
            "vacuum_scalar": vacuum_scalar,
        },
        "trace_replay": replay,
        "non_gaussian_gate": {
            "identity": "(c+2) T_2 != wedge^2(T_1)",
            "nonzero_entry_count": len(nonzero_entries),
            "first_nonzero_entry": nonzero_entries[0],
            "conclusion": "H=-Log(T_c/(c+2)) is number-conserving and interacting",
        },
        "weight_conclusion": (
            "positive coefficients times det(I+W) for every "
            "{I,B,B.T} auxiliary-field word"
        ),
    }


__all__: Sequence[str] = (
    "SCHEMA",
    "exact_fock_trace_replay",
    "exact_physical_transfer_certificate",
)
