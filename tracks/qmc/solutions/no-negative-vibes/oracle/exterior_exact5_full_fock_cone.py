"""Search trace-compatible cones coupling exact5 exterior grades.

The complete number-conserving Fock representation is
``Gamma(B) = direct_sum_k wedge^k(B)``.  Sector-wise positivity is not
necessary: a cone may couple grades whose traces cancel.  Numerical searches
in this module are discovery heuristics only.  Promotion requires exact
rational replay of

``A_i R = R P_i,  P_i >= 0,  R C = I,  C R >= 0``.

The last two identities make the redundant lift trace-compatible, since
``tr(A_w) = tr(C R P_w) >= 0`` for every word.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path

import numpy as np
import sympy as sp
from scipy.optimize import linprog, minimize

from .exterior_candidates import candidate_card, candidate_id, exact_atoms_from_card
from .exterior_exact5_polyhedral_cone import (
    _canonical_ray,
    _cone_residuals,
    _rationalize_ray,
    exact_polyhedral_certificate,
)
from .exterior_exact5_shared_cone import (
    _matrix_payload,
    _negative_objective_and_gradient,
    _rational_payload,
    _validated_exact_matrices,
    exact_compound_matrix,
    exact_simplicial_certificate,
    signed_monomial_triage,
)


SCHEMA_VERSION = "exterior-exact5-full-fock-cone-v1"


def combined_grade_lift(
    matrix: sp.MatrixBase,
    grades: Sequence[int],
) -> sp.ImmutableMatrix:
    """Return an exact direct sum of exterior grades in the declared order."""

    exact = sp.ImmutableMatrix(matrix)
    if exact.rows != exact.cols:
        raise ValueError("matrix must be square")
    selected = tuple(int(grade) for grade in grades)
    if (
        not selected
        or len(set(selected)) != len(selected)
        or any(not 0 <= grade <= exact.rows for grade in selected)
    ):
        raise ValueError("grades must be unique valid exterior grades")
    return sp.ImmutableMatrix(
        sp.diag(*(exact_compound_matrix(exact, grade) for grade in selected))
    )


def exact_fock_lift(matrix: sp.MatrixBase) -> sp.ImmutableMatrix:
    """Return ``Gamma(matrix)`` in increasing-grade lexicographic basis."""

    exact = sp.ImmutableMatrix(matrix)
    if exact.rows != exact.cols:
        raise ValueError("matrix must be square")
    return combined_grade_lift(exact, tuple(range(exact.rows + 1)))


def particle_hole_pair_lift(
    matrix: sp.MatrixBase,
    grade: int,
) -> sp.ImmutableMatrix:
    """Return the paired block ``wedge^k B direct_sum wedge^(n-k) B``."""

    exact = sp.ImmutableMatrix(matrix)
    if exact.rows != exact.cols:
        raise ValueError("matrix must be square")
    if not isinstance(grade, int) or isinstance(grade, bool):
        raise TypeError("grade must be an integer")
    if not 0 <= grade <= exact.rows:
        raise ValueError("grade is outside the exterior algebra")
    complement = exact.rows - grade
    grades = (grade,) if complement == grade else (grade, complement)
    return combined_grade_lift(exact, grades)


def _base_right_inverse(ray_matrix: sp.ImmutableMatrix) -> sp.ImmutableMatrix:
    """Construct one exact sparse right inverse of a full-row-rank matrix."""

    dimension, ray_count = ray_matrix.shape
    if ray_matrix.rank() != dimension:
        raise ValueError("ray matrix must have full row rank")
    pivots = ray_matrix.rref()[1]
    if len(pivots) != dimension:
        raise RuntimeError("full-row-rank matrix did not expose enough pivots")
    inverse = ray_matrix[:, pivots].inv()
    result = sp.zeros(ray_count, dimension)
    for local_row, ray_index in enumerate(pivots):
        result[ray_index, :] = inverse[local_row, :]
    exact = sp.ImmutableMatrix(result)
    if ray_matrix * exact != sp.eye(dimension):
        raise RuntimeError("right-inverse construction failed")
    return exact


def _is_positive_retract(
    ray_matrix: sp.ImmutableMatrix,
    right_inverse: sp.ImmutableMatrix,
) -> bool:
    dimension = ray_matrix.rows
    return bool(
        ray_matrix * right_inverse == sp.eye(dimension)
        and all(entry >= 0 for entry in right_inverse * ray_matrix)
    )


def exact_positive_retract(
    ray_matrix: sp.MatrixBase,
    *,
    max_denominator: int = 1_048_576,
    tolerance: float = 1.0e-9,
) -> sp.ImmutableMatrix | None:
    """Find and exact-replay ``C`` with ``R C = I`` and ``C R >= 0``.

    The LP is parameterized by the exact nullspace of ``R``.  Consequently
    rationalizing its free variables preserves ``R C = I`` identically; a
    candidate is returned only after exact SymPy inequalities pass.
    """

    rays = sp.ImmutableMatrix(ray_matrix)
    dimension, ray_count = rays.shape
    if dimension < 1 or rays.rank() != dimension:
        return None
    if max_denominator < 1 or tolerance < 0.0:
        raise ValueError("invalid rationalization or LP tolerance")

    base = _base_right_inverse(rays)
    if _is_positive_retract(rays, base):
        return base
    null_vectors = rays.nullspace()
    if not null_vectors:
        return None
    nullspace = sp.ImmutableMatrix.hstack(*null_vectors)
    freedom = nullspace.cols
    base_retract = base * rays

    variable_count = freedom * dimension
    inequalities = np.zeros((ray_count * ray_count, variable_count))
    bounds = np.zeros(ray_count * ray_count)
    row_index = 0
    for output_row in range(ray_count):
        for output_column in range(ray_count):
            bounds[row_index] = float(base_retract[output_row, output_column])
            for null_index in range(freedom):
                left = nullspace[output_row, null_index]
                if left == 0:
                    continue
                for physical_index in range(dimension):
                    right = rays[physical_index, output_column]
                    if right != 0:
                        variable = null_index * dimension + physical_index
                        inequalities[row_index, variable] = -float(left * right)
            row_index += 1

    result = linprog(
        np.zeros(variable_count),
        A_ub=inequalities,
        b_ub=bounds,
        bounds=[(None, None)] * variable_count,
        method="highs",
        options={
            "dual_feasibility_tolerance": max(1.0e-9, tolerance),
            "primal_feasibility_tolerance": max(1.0e-9, tolerance),
        },
    )
    if not result.success:
        return None

    denominator_schedule = tuple(
        dict.fromkeys(
            min(value, max_denominator)
            for value in (32, 256, 4096, 65536, max_denominator)
        )
    )
    for denominator in denominator_schedule:
        free = sp.ImmutableMatrix(
            freedom,
            dimension,
            [
                sp.Rational(Fraction(float(value)).limit_denominator(denominator))
                for value in result.x
            ],
        )
        candidate = sp.ImmutableMatrix(base + nullspace * free)
        if _is_positive_retract(rays, candidate):
            return candidate
    return None


def exact_trace_compatible_certificate(
    matrices: Sequence[sp.MatrixBase],
    rays: Sequence[sp.MatrixBase],
    *,
    max_denominator: int = 1_048_576,
    tolerance: float = 1.0e-9,
) -> dict[str, object] | None:
    """Promote a redundant invariant cone only after the exact trace gate."""

    checked = _validated_exact_matrices(matrices)
    canonical = tuple(_canonical_ray(ray) for ray in rays)
    invariant = exact_polyhedral_certificate(
        checked,
        canonical,
        tolerance=tolerance,
    )
    if invariant is None:
        return None
    ray_matrix = sp.ImmutableMatrix.hstack(*canonical)
    right_inverse = exact_positive_retract(
        ray_matrix,
        max_denominator=max_denominator,
        tolerance=tolerance,
    )
    if right_inverse is None:
        return None
    retract = sp.ImmutableMatrix(right_inverse * ray_matrix)
    if ray_matrix * right_inverse != sp.eye(ray_matrix.rows):
        raise RuntimeError("exact right-inverse replay failed")
    if any(entry < 0 for entry in retract):
        raise RuntimeError("exact positive-retract replay failed")
    result = dict(invariant)
    result.update(
        {
            "status": "exact-trace-compatible-certificate",
            "method": "rational-redundant-trace-compatible-cone",
            "right_inverse": _matrix_payload(right_inverse),
            "positive_retract": _matrix_payload(retract),
            "right_inverse_replay": True,
            "positive_retract_replay": True,
            "minimum_retract_entry": _rational_payload(min(retract)),
        }
    )
    return result


def fast_full_fock_diagnostics(
    card: Mapping[str, object],
    *,
    search_grades: Sequence[int] = (2, 4),
    diagnostic_word_power: int = 6,
) -> dict[str, object]:
    """Run exact sign/trace gates and a light spectral Perron diagnostic."""

    atoms = exact_atoms_from_card(card)
    fock_atoms = tuple(exact_fock_lift(atom) for atom in atoms)
    combined = tuple(combined_grade_lift(atom, search_grades) for atom in atoms)

    first_negative: dict[str, int] | None = None
    for atom_index, matrix in enumerate(combined):
        for row in range(matrix.rows):
            for column in range(matrix.cols):
                if matrix[row, column] < 0:
                    first_negative = {
                        "atom": atom_index,
                        "row": row,
                        "column": column,
                    }
                    break
            if first_negative is not None:
                break
        if first_negative is not None:
            break

    spectra: list[dict[str, object]] = []
    for atom_index, matrix in enumerate(combined):
        values = np.linalg.eigvals(np.asarray(matrix.tolist(), dtype=float))
        radius = float(np.max(np.abs(values)))
        perron = any(
            abs(value.imag) <= 1.0e-8 * max(1.0, radius)
            and value.real >= -1.0e-10
            and abs(abs(value) - radius) <= 1.0e-8 * max(1.0, radius)
            for value in values
        )
        spectra.append(
            {
                "atom": atom_index,
                "spectral_radius": radius,
                "nonnegative_real_peripheral_eigenvalue": perron,
            }
        )

    grade_word_traces = []
    for grade in range(atoms[0].rows + 1):
        compound = exact_compound_matrix(atoms[0], grade)
        grade_word_traces.append(
            {
                "grade": grade,
                "trace": _rational_payload(
                    sp.trace(compound**diagnostic_word_power)
                ),
            }
        )
    full_trace = sp.trace(fock_atoms[0] ** diagnostic_word_power)
    determinant_trace = sp.det(sp.eye(atoms[0].rows) + atoms[0] ** diagnostic_word_power)
    if full_trace != determinant_trace:
        raise RuntimeError("Fock trace/determinant identity failed")

    restricted = signed_monomial_triage(combined)
    return {
        "candidate_id": candidate_id(card),
        "search_grades": [int(grade) for grade in search_grades],
        "combined_dimension": combined[0].rows,
        "positive_diagonal_status": (
            "exact-certificate"
            if first_negative is None
            else "restricted-obstruction"
        ),
        "positive_diagonal_witness": first_negative,
        "signed_monomial": restricted,
        # This exact identity is stronger and much cheaper than expanding the
        # 15-dimensional characteristic polynomial.
        "transpose_spectral_identity": combined[1] == combined[0].T,
        "spectral_perron_gate": spectra,
        "word_power": diagnostic_word_power,
        "grade_word_traces": grade_word_traces,
        "combined_word_trace": _rational_payload(
            sum(
                sp.trace(
                    exact_compound_matrix(atoms[0], int(grade))
                    ** diagnostic_word_power
                )
                for grade in search_grades
            )
        ),
        "full_fock_word_trace": _rational_payload(full_trace),
        "fock_trace_equals_determinant": True,
    }


def _cross_grade_simplicial_search(
    matrices: Sequence[sp.MatrixBase],
    *,
    split: int,
    attempts: int,
    maxiter: int,
    rng_seed: int,
    tolerance: float,
    max_denominator: int,
) -> dict[str, object]:
    """Search dense bases first so rays genuinely couple both grade blocks."""

    checked = _validated_exact_matrices(matrices)
    floats = tuple(np.asarray(matrix.tolist(), dtype=float) for matrix in checked)
    scaled = tuple(
        matrix / max(1.0, float(np.max(np.abs(matrix)))) for matrix in floats
    )
    dimension = floats[0].shape[0]
    rng = np.random.default_rng(rng_seed)
    initials = []
    for _ in range(attempts):
        dense, _ = np.linalg.qr(rng.normal(size=(dimension, dimension)))
        initials.append(dense @ (np.eye(dimension) + 0.2 * rng.normal(size=(dimension, dimension))))
    if not initials:
        return {
            "status": "no-exact-certificate-found",
            "method": "cross-grade-common-simplicial",
            "attempts": 0,
            "best": {},
        }

    best: dict[str, object] = {}
    for attempt_index, initial in enumerate(initials):
        result = minimize(
            lambda flat: _negative_objective_and_gradient(
                flat,
                scaled,
                target_margin=1.0e-7,
                orthogonality_weight=1.0e-7,
            ),
            initial.ravel(),
            method="L-BFGS-B",
            jac=True,
            options={"maxiter": maxiter, "ftol": 1.0e-14, "gtol": 1.0e-9},
        )
        transform = np.asarray(result.x).reshape((dimension, dimension))
        condition = float(np.linalg.cond(transform))
        transformed = tuple(np.linalg.solve(transform, matrix @ transform) for matrix in floats)
        margin = float(min(np.min(matrix) for matrix in transformed))
        coupled_columns = sum(
            np.linalg.norm(transform[:split, column]) > 1.0e-10
            and np.linalg.norm(transform[split:, column]) > 1.0e-10
            for column in range(dimension)
        )
        record = {
            "attempt": attempt_index,
            "objective": float(result.fun),
            "minimum_entry": margin,
            "condition_number": condition,
            "cross_grade_columns": coupled_columns,
            "transform": transform.tolist(),
        }
        if not best or float(record["objective"]) < float(best["objective"]):
            best = record
        if margin < -tolerance or condition > 1.0e10:
            continue
        for denominator in (256, 4096, 65536, max_denominator):
            certificate = exact_simplicial_certificate(
                checked,
                transform,
                max_denominator=min(denominator, max_denominator),
            )
            if certificate is not None:
                certificate["cross_grade_columns"] = coupled_columns
                return certificate
    return {
        "status": "no-exact-certificate-found",
        "method": "cross-grade-common-simplicial",
        "attempts": attempts,
        "best": best,
    }


def _trace_compatible_column_generation(
    matrices: Sequence[sp.MatrixBase],
    initial_transform: Sequence[Sequence[float]],
    *,
    ray_counts: Sequence[int],
    tolerance: float,
    max_denominator: int,
) -> dict[str, object]:
    checked = _validated_exact_matrices(matrices)
    dimension = checked[0].rows
    counts = tuple(sorted(set(int(count) for count in ray_counts)))
    if not counts or counts[0] < dimension:
        raise ValueError("ray counts must start at or above the dimension")
    numerical = np.asarray(initial_transform, dtype=float)
    if numerical.shape != (dimension, dimension):
        raise ValueError("initial transform has the wrong dimension")
    rays = [
        _rationalize_ray(numerical[:, column], max_denominator=max_denominator)
        for column in range(dimension)
    ]
    if sp.ImmutableMatrix.hstack(*rays).rank() != dimension:
        return {
            "status": "rank-deficient-rational-seed",
            "milestones": [],
        }
    float_matrices = tuple(np.asarray(matrix.tolist(), dtype=float) for matrix in checked)
    milestones: list[dict[str, object]] = []
    while len(rays) <= counts[-1]:
        maximum, aggregate, worst, failures = _cone_residuals(float_matrices, rays)
        if len(rays) in counts:
            certificate = None
            if maximum <= max(1.0e-8, 100.0 * tolerance):
                certificate = exact_trace_compatible_certificate(
                    checked,
                    rays,
                    max_denominator=max_denominator,
                    tolerance=tolerance,
                )
            milestone = {
                "ray_count": len(rays),
                "maximum_relative_residual": maximum,
                "aggregate_relative_residual": aggregate,
                "violations": failures,
                "exact_trace_status": (
                    "exact-trace-compatible-certificate"
                    if certificate is not None
                    else "no-exact-trace-compatible-certificate"
                ),
            }
            milestones.append(milestone)
            if certificate is not None:
                return {
                    "status": "exact-trace-compatible-certificate",
                    "milestones": milestones,
                    "certificate": certificate,
                }
        if len(rays) == counts[-1]:
            break
        atom_index, ray_index = worst
        new_ray = _canonical_ray(checked[atom_index] * rays[ray_index])
        if new_ray in rays:
            break
        rays.append(new_ray)
    return {
        "status": "no-exact-trace-compatible-certificate-found",
        "milestones": milestones,
    }


def search_seed61_combined(
    *,
    grades: Sequence[int] = (2, 4),
    attempts: int = 2,
    maxiter: int = 250,
    rng_seed: int = 610121,
    ray_counts: Sequence[int] = (15, 18, 21),
    tolerance: float = 1.0e-9,
    max_denominator: int = 65536,
) -> dict[str, object]:
    """Run the light exact5 seed-61 cross-grade search."""

    card = candidate_card(template="exact5-shear-loop-pair", seed=61)
    atoms = exact_atoms_from_card(card)
    selected = tuple(int(grade) for grade in grades)
    matrices = tuple(combined_grade_lift(atom, selected) for atom in atoms)
    split = exact_compound_matrix(atoms[0], selected[0]).rows
    diagnostics = fast_full_fock_diagnostics(card, search_grades=selected)
    combined_trace = diagnostics["combined_word_trace"]
    assert isinstance(combined_trace, Mapping)
    if int(combined_trace["numerator"]) < 0:
        return {
            "schema_version": SCHEMA_VERSION,
            "candidate": "exact5-shear-loop-pair:61",
            "grades": list(selected),
            "status": "exact-negative-trace-obstruction",
            "route": "diagnostic-word-early-stop",
            "diagnostics": diagnostics,
        }
    restricted = diagnostics["signed_monomial"]
    if isinstance(restricted, Mapping) and restricted["status"] == "exact-certificate":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "exact-trace-compatible-certificate",
            "route": "shared-signed-monomial",
            "diagnostics": diagnostics,
            "certificate": restricted,
        }

    simplicial = _cross_grade_simplicial_search(
        matrices,
        split=split,
        attempts=attempts,
        maxiter=maxiter,
        rng_seed=rng_seed,
        tolerance=tolerance,
        max_denominator=max_denominator,
    )
    if simplicial["status"] == "exact-certificate":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "exact-trace-compatible-certificate",
            "route": "cross-grade-simplicial",
            "diagnostics": diagnostics,
            "certificate": simplicial,
        }
    best = simplicial.get("best")
    transform = best.get("transform") if isinstance(best, Mapping) else None
    if transform is None:
        redundant = {
            "status": "no-numerical-transform",
            "milestones": [],
        }
    else:
        redundant = _trace_compatible_column_generation(
            matrices,
            transform,
            ray_counts=ray_counts,
            tolerance=tolerance,
            max_denominator=max_denominator,
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": "exact5-shear-loop-pair:61",
        "grades": list(selected),
        "status": (
            "exact-trace-compatible-certificate"
            if redundant["status"] == "exact-trace-compatible-certificate"
            else "no-exact-certificate-found"
        ),
        "diagnostics": diagnostics,
        "simplicial": simplicial,
        "redundant": redundant,
    }


def _parse_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in value.split(","))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grades", type=_parse_ints, default=(2, 4))
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--maxiter", type=int, default=250)
    parser.add_argument("--rng-seed", type=int, default=610121)
    parser.add_argument("--ray-counts", type=_parse_ints, default=(15, 18, 21))
    parser.add_argument("--tolerance", type=float, default=1.0e-9)
    parser.add_argument("--max-denominator", type=int, default=65536)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    result = search_seed61_combined(
        grades=args.grades,
        attempts=args.attempts,
        maxiter=args.maxiter,
        rng_seed=args.rng_seed,
        ray_counts=args.ray_counts,
        tolerance=args.tolerance,
        max_denominator=args.max_denominator,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(result, allow_nan=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, output)
    print(json.dumps(result, allow_nan=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "combined_grade_lift",
    "exact_fock_lift",
    "exact_positive_retract",
    "exact_trace_compatible_certificate",
    "fast_full_fock_diagnostics",
    "particle_hole_pair_lift",
    "search_seed61_combined",
]
