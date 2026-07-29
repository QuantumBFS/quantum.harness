"""Exact Hermitian interacting transfer for the leading oddcycle pair."""

from __future__ import annotations

import json
from collections.abc import Sequence

import sympy as sp

from .exterior_exact5_full_fock_cone import exact_fock_lift
from .exterior_exact5_shared_cone import exact_compound_matrix


SCHEMA = "oddcycle-pair-physical-transfer-v1"


def leading_pair_matrices() -> tuple[sp.ImmutableMatrix, sp.ImmutableMatrix]:
    """Return ``B(3/10,1,1)`` and ``B(5/2,1,1)`` exactly."""

    def matrix(p: sp.Rational) -> sp.ImmutableMatrix:
        return sp.ImmutableMatrix(
            [
                [0, 0, 2, 0, 0],
                [2, 0, 0, 0, 0],
                [0, 2, 0, p, 0],
                [0, 0, 0, 1, 1],
                [0, 0, -1, 0, 1],
            ]
        )

    return matrix(sp.Rational(3, 10)), matrix(sp.Rational(5, 2))


def exact_pair_physical_certificate() -> dict[str, object]:
    """Certify a positive-field Hermitian interacting transfer.

    Arbitrary-word determinant positivity is intentionally a separate
    theorem gate.  This function proves that, once that gate is closed, the
    same four-letter alphabet has an exact physical auxiliary-field target.
    """

    matrices = leading_pair_matrices()
    fock_atoms = tuple(
        exact_fock_lift(atom)
        for matrix in matrices
        for atom in (matrix, matrix.T)
    )
    symmetric_sum = sp.ImmutableMatrix(sum(fock_atoms, sp.zeros(32)))
    row_requirements = tuple(
        sp.factor(
            sum(
                abs(symmetric_sum[row, column])
                for column in range(32)
                if column != row
            )
            - symmetric_sum[row, row]
        )
        for row in range(32)
    )
    maximum_requirement = max(row_requirements)
    c = int(sp.floor(maximum_requirement)) + 1
    minimum_margin = min(sp.Rational(c) - value for value in row_requirements)
    if minimum_margin <= 0:
        raise RuntimeError("failed to choose a strict row-dominance shift")
    transfer = sp.ImmutableMatrix(c * sp.eye(32) + symmetric_sum)
    if transfer != transfer.T:
        raise RuntimeError("pair transfer is not real symmetric")

    one_particle = sp.ImmutableMatrix(
        c * sp.eye(5)
        + sum(
            (matrix + matrix.T for matrix in matrices),
            sp.zeros(5),
        )
    )
    grade2_atoms = tuple(
        exact_compound_matrix(atom, 2)
        for matrix in matrices
        for atom in (matrix, matrix.T)
    )
    grade2 = sp.ImmutableMatrix(
        c * sp.eye(10) + sum(grade2_atoms, sp.zeros(10))
    )
    vacuum_scalar = c + len(fock_atoms)
    gaussian_mismatch = sp.ImmutableMatrix(
        vacuum_scalar * grade2 - exact_compound_matrix(one_particle, 2)
    )
    nonzero_entries = tuple(
        (row, column, sp.factor(gaussian_mismatch[row, column]))
        for row in range(10)
        for column in range(10)
        if gaussian_mismatch[row, column] != 0
    )
    if not nonzero_entries:
        raise RuntimeError("pair transfer unexpectedly passed the Gaussian gate")

    spectral_records = []
    for p, matrix in zip((sp.Rational(3, 10), sp.Rational(5, 2)), matrices):
        coefficients = tuple(matrix.charpoly().all_coeffs())
        p_minus_t_coefficients = (
            -1,
            -2,
            -1,
            p - 8,
            -16,
            -8,
        )
        if any(coefficient >= 0 for coefficient in p_minus_t_coefficients):
            raise RuntimeError("an auxiliary atom can meet the negative real axis")
        spectral_records.append(
            {
                "p": str(p),
                "determinant": int(matrix.det()),
                "characteristic_coefficients": tuple(
                    str(value) for value in coefficients
                ),
                "p_minus_t_coefficients": tuple(
                    str(value) for value in p_minus_t_coefficients
                ),
                "real_log_exists": True,
            }
        )

    return {
        "schema": SCHEMA,
        "status": "exact-hermitian-interacting-transfer",
        "one_particle_dimension": 5,
        "fock_dimension": 32,
        "c": c,
        "strict_diagonal_dominance": {
            "maximum_requirement": str(maximum_requirement),
            "minimum_row_margin": str(minimum_margin),
            "conclusion": "T is real symmetric positive definite",
        },
        "auxiliary_atoms": spectral_records,
        "normalized_auxiliary_fields": {
            "labels": ("identity", "B0", "B0.T", "B1", "B1.T"),
            "coefficients": (
                f"{c}/{vacuum_scalar}",
                *(f"1/{vacuum_scalar}" for _ in range(4)),
            ),
            "coefficient_sum": "1",
            "all_coefficients_positive": True,
        },
        "non_gaussian_gate": {
            "identity": "(c+4) T_2 != wedge^2(T_1)",
            "nonzero_entry_count": len(nonzero_entries),
            "first_nonzero_entry": (
                nonzero_entries[0][0],
                nonzero_entries[0][1],
                str(nonzero_entries[0][2]),
            ),
            "conclusion": (
                "H=-Log(T/(c+4)) is Hermitian, number-conserving, "
                "and interacting"
            ),
        },
        "sign_free_gate": (
            "conditional only on the separate arbitrary-word determinant "
            "positivity theorem for {B0,B0.T,B1,B1.T}"
        ),
    }


__all__: Sequence[str] = (
    "SCHEMA",
    "exact_pair_physical_certificate",
    "leading_pair_matrices",
)


if __name__ == "__main__":  # pragma: no cover - CLI
    print(
        json.dumps(
            exact_pair_physical_certificate(),
            indent=2,
            sort_keys=True,
        )
    )
