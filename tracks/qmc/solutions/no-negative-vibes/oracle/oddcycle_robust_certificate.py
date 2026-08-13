"""One-command exact replay for the robust oddcycle candidate."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from fractions import Fraction
from pathlib import Path

import numpy
import sympy as sp

from .exterior_exact5_full_fock_cone import exact_fock_lift
from .exterior_exact5_shared_cone import exact_compound_matrix
from .oddcycle_final_certificate import _source_commit
from .oddcycle_metric_dual import (
    _bareiss_determinant,
    _fraction_matmul,
    _fraction_transpose,
)
from .oddcycle_path_metric import (
    _verify_exact_path_metrics,
    _verify_exact_time_orientation,
)


SCHEMA = "oddcycle-robust-final-certificate-v1"
THEOREM_SCHEMA = "oddcycle-robust-path-certificate-v1"
DUAL_SCHEMA = "oddcycle-robust-exact-dual-v1"
PHYSICAL_SCHEMA = "oddcycle-robust-physical-transfer-v1"
FROZEN_SCHEMA = "oddcycle-robust-frozen-certificate-v1"
CELL_ID = "cell-4321"


def _frozen_data() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "protocols"
        / "oddcycle-robust-candidate-v1"
        / "frozen-certificate.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != FROZEN_SCHEMA
        or payload.get("cell_id") != CELL_ID
    ):
        raise RuntimeError("invalid robust oddcycle frozen certificate")
    return payload


def _exact_points(
    payload: dict[str, object],
) -> tuple[tuple[str, str, str], ...]:
    points = payload.get("points")
    if (
        not isinstance(points, list)
        or len(points) != 2
        or any(not isinstance(point, list) or len(point) != 3 for point in points)
    ):
        raise RuntimeError("robust certificate requires two exact points")
    return tuple(tuple(str(value) for value in point) for point in points)


def _exact_point_matrices(
    points: tuple[tuple[str, str, str], ...],
) -> tuple[sp.ImmutableMatrix, ...]:
    return tuple(
        sp.ImmutableMatrix(
            [
                [0, 0, 2, 0, 0],
                [2, 0, 0, 0, 0],
                [0, 2, 0, sp.Rational(p), 0],
                [0, 0, 0, 1, sp.Rational(q)],
                [0, 0, -sp.Rational(r), 0, 1],
            ]
        )
        for p, q, r in points
    )


def exact_robust_path_certificate() -> dict[str, object]:
    """Replay the four Lorentz metrics and coherent time orientation."""

    payload = _frozen_data()
    points = _exact_points(payload)
    path_metric = payload.get("path_metric")
    if not isinstance(path_metric, dict):
        raise RuntimeError("missing robust path-metric data")
    denominator = int(path_metric["denominator"])
    numerators = path_metric["numerators"]
    time_vectors = path_metric["time_vectors"]
    certificate = _verify_exact_path_metrics(
        points,
        numerators,
        denominator=denominator,
    )
    orientation = _verify_exact_time_orientation(
        points,
        numerators,
        time_vectors,
        denominator=denominator,
    )
    contraction = bool(certificate["exact_arbitrary_word_contraction"])
    determinant_positive = (
        contraction
        and orientation["all_time_vectors_positive"]
        and orientation["all_inverse_transitions_future_preserving"]
        and orientation["all_atom_determinants_positive"]
    )
    return {
        "schema": THEOREM_SCHEMA,
        "status": (
            "exact-positive-last-letter-path-metric-certificate"
            if determinant_positive
            else "exact-certificate-failed"
        ),
        "points": [list(point) for point in points],
        "state_count": len(numerators),
        "transition_count": len(certificate["transitions"]),
        "certificate": certificate,
        "time_orientation": orientation,
        "exact_arbitrary_word_determinant_positive": determinant_positive,
    }


def _fraction_point_matrix(
    point: tuple[str, str, str],
) -> list[list[Fraction]]:
    p, q, r = (Fraction(value) for value in point)
    return [
        [Fraction(0), Fraction(0), Fraction(2), Fraction(0), Fraction(0)],
        [Fraction(2), Fraction(0), Fraction(0), Fraction(0), Fraction(0)],
        [Fraction(0), Fraction(2), Fraction(0), p, Fraction(0)],
        [Fraction(0), Fraction(0), Fraction(0), Fraction(1), q],
        [Fraction(0), Fraction(0), -r, Fraction(0), Fraction(1)],
    ]


def exact_robust_no_common_metric_certificate() -> dict[str, object]:
    """Replay the frozen exact dual for the common-quadratic-metric test."""

    payload = _frozen_data()
    points = _exact_points(payload)
    dual = payload.get("dual")
    if not isinstance(dual, dict):
        raise RuntimeError("missing robust dual data")
    records = dual.get("multipliers")
    if not isinstance(records, list) or len(records) != 4:
        raise RuntimeError("robust dual requires four multipliers")
    multipliers: list[list[list[Fraction]]] = []
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("invalid robust dual multiplier")
        denominator = int(record["denominator"])
        numerator = record["numerator"]
        multipliers.append(
            [
                [Fraction(int(entry), denominator) for entry in row]
                for row in numerator
            ]
        )
    matrices = [_fraction_point_matrix(point) for point in points]
    cancellation = [[Fraction(0) for _ in range(5)] for _ in range(5)]
    for index, matrix in enumerate(matrices):
        transpose = _fraction_transpose(matrix)
        forward_multiplier = multipliers[index]
        transpose_multiplier = multipliers[2 + index]
        forward_image = _fraction_matmul(
            _fraction_matmul(matrix, forward_multiplier),
            transpose,
        )
        transpose_image = _fraction_matmul(
            _fraction_matmul(transpose, transpose_multiplier),
            matrix,
        )
        for row in range(5):
            for column in range(5):
                cancellation[row][column] += (
                    forward_multiplier[row][column]
                    - forward_image[row][column]
                    + transpose_multiplier[row][column]
                    - transpose_image[row][column]
                )
    multiplier_records = []
    all_positive = True
    for record in records:
        numerator = record["numerator"]
        leading_minors = [
            _bareiss_determinant(
                [list(row[:size]) for row in numerator[:size]]
            )
            for size in range(1, 6)
        ]
        positive = all(minor > 0 for minor in leading_minors)
        all_positive = all_positive and positive
        multiplier_records.append(
            {
                "denominator": int(record["denominator"]),
                "numerator": numerator,
                "leading_principal_minor_numerators": leading_minors,
                "positive_definite_by_sylvester": positive,
            }
        )
    trace_sum = sum(
        (
            multipliers[block][index][index]
            for block in range(4)
            for index in range(5)
        ),
        Fraction(0),
    )
    cancellation_zero = all(
        entry == 0 for row in cancellation for entry in row
    )
    certified = cancellation_zero and all_positive and trace_sum == 1
    return {
        "schema": DUAL_SCHEMA,
        "status": (
            "exact-no-common-quadratic-metric-certificate"
            if certified
            else "certificate-replay-failed"
        ),
        "points": [list(point) for point in points],
        "projection_denominator": int(dual["projection_denominator"]),
        "cancellation_exact_zero": cancellation_zero,
        "normalization_trace": {
            "numerator": trace_sum.numerator,
            "denominator": trace_sum.denominator,
        },
        "all_multipliers_positive_definite": all_positive,
        "multipliers": multiplier_records,
        "interpretation": (
            "no real symmetric R can make all forward and transpose "
            "Lyapunov gaps positive definite"
        ),
    }


def exact_robust_physical_certificate() -> dict[str, object]:
    """Certify the positive-field Hermitian interacting transfer exactly."""

    payload = _frozen_data()
    points = _exact_points(payload)
    matrices = _exact_point_matrices(points)
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
    shift = int(sp.floor(maximum_requirement)) + 1
    minimum_margin = min(
        sp.Rational(shift) - requirement
        for requirement in row_requirements
    )
    transfer = sp.ImmutableMatrix(shift * sp.eye(32) + symmetric_sum)
    if minimum_margin <= 0 or transfer != transfer.T:
        raise RuntimeError("robust transfer failed symmetric SPD gate")

    one_particle = sp.ImmutableMatrix(
        shift * sp.eye(5)
        + sum(
            (matrix + matrix.T for matrix in matrices),
            sp.zeros(5),
        )
    )
    grade_two = sp.ImmutableMatrix(
        shift * sp.eye(10)
        + sum(
            (
                exact_compound_matrix(atom, 2)
                for matrix in matrices
                for atom in (matrix, matrix.T)
            ),
            sp.zeros(10),
        )
    )
    vacuum_scalar = shift + len(fock_atoms)
    gaussian_mismatch = sp.ImmutableMatrix(
        vacuum_scalar * grade_two
        - exact_compound_matrix(one_particle, 2)
    )
    nonzero_entries = tuple(
        (row, column, sp.factor(gaussian_mismatch[row, column]))
        for row in range(10)
        for column in range(10)
        if gaussian_mismatch[row, column] != 0
    )
    if not nonzero_entries:
        raise RuntimeError("robust transfer unexpectedly passed Gaussian gate")

    spectral_records = []
    for point_index, (point, matrix) in enumerate(
        zip(points, matrices, strict=True)
    ):
        p, q, r = (sp.Rational(value) for value in point)
        p_minus_t_coefficients = (
            sp.Integer(-1),
            sp.Integer(-2),
            sp.Integer(-1),
            sp.factor(p * q * r - 8),
            sp.Integer(-16),
            sp.Integer(-8),
        )
        if matrix.det() == 0 or any(
            coefficient >= 0 for coefficient in p_minus_t_coefficients
        ):
            raise RuntimeError("a robust auxiliary atom can meet the negative axis")
        for label, atom in (
            (f"B{point_index}", matrix),
            (f"B{point_index}.T", matrix.T),
        ):
            spectral_records.append(
                {
                    "label": label,
                    "point": list(point),
                    "determinant": int(atom.det()),
                    "characteristic_coefficients": [
                        str(value) for value in atom.charpoly().all_coeffs()
                    ],
                    "p_minus_t_coefficients": [
                        str(value) for value in p_minus_t_coefficients
                    ],
                    "negative_real_eigenvalue_count": 0,
                    "real_log_exists": True,
                }
            )
    first_row, first_column, first_value = nonzero_entries[0]
    return {
        "schema": PHYSICAL_SCHEMA,
        "status": "exact-hermitian-interacting-transfer",
        "one_particle_dimension": 5,
        "fock_dimension": 32,
        "c": shift,
        "strict_diagonal_dominance": {
            "maximum_requirement": str(maximum_requirement),
            "minimum_row_margin": str(minimum_margin),
            "conclusion": "T is real symmetric positive definite",
        },
        "auxiliary_atoms": spectral_records,
        "normalized_auxiliary_fields": {
            "labels": ("identity", "B0", "B0.T", "B1", "B1.T"),
            "coefficients": (
                f"{shift}/{vacuum_scalar}",
                *(f"1/{vacuum_scalar}" for _ in range(4)),
            ),
            "coefficient_sum": "1",
            "all_coefficients_positive": True,
        },
        "non_gaussian_gate": {
            "identity": "(c+4) T_2 != wedge^2(T_1)",
            "nonzero_entry_count": len(nonzero_entries),
            "first_raw_entry": (
                first_row,
                first_column,
                str(first_value),
            ),
            "first_normalized_entry": (
                first_row,
                first_column,
                str(sp.factor(first_value / vacuum_scalar**2)),
            ),
            "conclusion": (
                "H=-Log(T/(c+4)) is Hermitian, number-conserving, "
                "and interacting"
            ),
        },
        "sign_free_gate": (
            "closed by the robust exact arbitrary-word path certificate"
        ),
    }


def robust_certificate_summary() -> dict[str, object]:
    """Replay all exact gates for cell-4321 and return compact JSON data."""

    started = time.perf_counter()
    theorem = exact_robust_path_certificate()
    novelty = exact_robust_no_common_metric_certificate()
    physical = exact_robust_physical_certificate()
    exact_payload = {
        "theorem": theorem,
        "novelty": novelty,
        "physical": physical,
    }
    digest = hashlib.sha256(
        json.dumps(
            exact_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    gates = {
        "arbitrary_word_determinant_positive": bool(
            theorem["exact_arbitrary_word_determinant_positive"]
        ),
        "no_common_strict_quadratic_metric": (
            novelty["status"]
            == "exact-no-common-quadratic-metric-certificate"
        ),
        "hermitian_interacting_positive_field_model": (
            physical["status"] == "exact-hermitian-interacting-transfer"
            and physical["normalized_auxiliary_fields"][
                "all_coefficients_positive"
            ]
            and all(
                record["real_log_exists"]
                for record in physical["auxiliary_atoms"]
            )
        ),
    }
    certificate = theorem["certificate"]
    orientation = theorem["time_orientation"]
    return {
        "schema": SCHEMA,
        "status": (
            "all-exact-gates-passed"
            if all(gates.values())
            else "exact-gate-failed"
        ),
        "source_commit": _source_commit(),
        "candidate": {
            "cell_id": CELL_ID,
            "dimension": 5,
            "points": theorem["points"],
            "alphabet": (
                "B(1/2000,11/10,9/10)",
                "B(1/2000,11/10,9/10)^T",
                "B(49/40,11/10,9/10)",
                "B(49/40,11/10,9/10)^T",
            ),
        },
        "gates": gates,
        "exact_certificate_sha256": digest,
        "theorem": {
            "metric_denominator": certificate["denominator"],
            "split_inertias_passed": sum(
                record["split_inertia_1_4"]
                for record in certificate["inertias"]
            ),
            "transition_gaps_passed": sum(
                record["positive_definite_by_sylvester"]
                for record in certificate["transitions"]
            ),
            "future_transitions_passed": (
                len(orientation["transition_orientation_scalars"])
                * len(orientation["transition_orientation_scalars"][0])
                if orientation["all_inverse_transitions_future_preserving"]
                else 0
            ),
            "time_vectors": orientation["time_vectors"],
        },
        "novelty": {
            "projection_denominator": novelty["projection_denominator"],
            "normalization_trace": novelty["normalization_trace"],
            "positive_multipliers": sum(
                record["positive_definite_by_sylvester"]
                for record in novelty["multipliers"]
            ),
        },
        "physical": {
            "fock_dimension": physical["fock_dimension"],
            "shift": physical["c"],
            "minimum_row_margin": physical[
                "strict_diagonal_dominance"
            ]["minimum_row_margin"],
            "field_coefficients": physical[
                "normalized_auxiliary_fields"
            ]["coefficients"],
            "real_log_letters": sum(
                record["real_log_exists"]
                for record in physical["auxiliary_atoms"]
            ),
            "non_gaussian_entry_count": physical["non_gaussian_gate"][
                "nonzero_entry_count"
            ],
            "first_normalized_non_gaussian_entry": physical[
                "non_gaussian_gate"
            ]["first_normalized_entry"],
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": numpy.__version__,
            "sympy": sp.__version__,
        },
        "exact_replay_wall_seconds": time.perf_counter() - started,
    }


__all__ = (
    "CELL_ID",
    "SCHEMA",
    "exact_robust_no_common_metric_certificate",
    "exact_robust_path_certificate",
    "exact_robust_physical_certificate",
    "robust_certificate_summary",
)


if __name__ == "__main__":  # pragma: no cover - CLI
    print(
        json.dumps(
            robust_certificate_summary(),
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
