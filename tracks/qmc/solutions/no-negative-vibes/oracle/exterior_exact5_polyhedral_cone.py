"""Search seed-61 grade 2 for a redundant shared invariant polyhedral cone.

The numerical phase grows a ray matrix ``R`` by the worst unrepresented image
``A_i r_j``.  A discovery is promoted only when exact rational arithmetic
constructs nonnegative matrices ``P_i`` satisfying ``A_i R = R P_i``.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import numpy as np
import sympy as sp
from scipy.optimize import linprog, nnls

from .exterior_candidates import candidate_card, exact_atoms_from_card
from .exterior_exact5_shared_cone import (
    _matrix_payload,
    _rational_payload,
    _validated_exact_matrices,
    exact_compound_matrix,
    numerical_simplicial_search,
)


SCHEMA_VERSION = "exterior-exact5-polyhedral-cone-v1"


def _canonical_ray(vector: sp.MatrixBase) -> sp.ImmutableMatrix:
    ray = sp.ImmutableMatrix(vector)
    if ray.cols != 1 or not ray.rows:
        raise ValueError("a ray must be a nonzero column vector")
    first = next((entry for entry in ray if entry != 0), None)
    if first is None:
        raise ValueError("a ray must be nonzero")
    return sp.ImmutableMatrix(ray / abs(first))


def _rationalize_ray(
    vector: Sequence[float] | np.ndarray,
    *,
    max_denominator: int,
) -> sp.ImmutableMatrix:
    values = np.asarray(vector, dtype=float)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("ray must be one finite vector")
    rational = sp.ImmutableMatrix(
        [
            sp.Rational(
                Fraction(float(value)).limit_denominator(max_denominator)
            )
            for value in values
        ]
    )
    return _canonical_ray(rational)


def _float_columns(rays: Sequence[sp.MatrixBase]) -> np.ndarray:
    matrix = np.asarray(sp.Matrix.hstack(*rays).tolist(), dtype=float)
    norms = np.linalg.norm(matrix, axis=0)
    if np.any(norms == 0.0) or not np.all(np.isfinite(norms)):
        raise ValueError("rays must be finite and nonzero")
    return matrix / norms


def _cone_residuals(
    matrices: tuple[np.ndarray, ...],
    rays: Sequence[sp.MatrixBase],
) -> tuple[float, float, tuple[int, int], int]:
    columns = _float_columns(rays)
    maximum = -1.0
    squared = 0.0
    worst = (0, 0)
    failures = 0
    for atom_index, matrix in enumerate(matrices):
        for ray_index in range(columns.shape[1]):
            target = matrix @ columns[:, ray_index]
            coefficients, residual = nnls(columns, target)
            relative = float(residual / max(1.0, np.linalg.norm(target)))
            squared += relative * relative
            if relative > 1.0e-10:
                failures += 1
            if relative > maximum:
                maximum = relative
                worst = (atom_index, ray_index)
    return maximum, float(np.sqrt(squared)), worst, failures


def _exact_nonnegative_coordinates(
    rays: sp.ImmutableMatrix,
    target: sp.ImmutableMatrix,
    *,
    tolerance: float,
) -> sp.ImmutableMatrix | None:
    """Recover one exact basic feasible conic representation."""

    dimension, ray_count = rays.shape
    float_rays = np.asarray(rays.tolist(), dtype=float)
    scales = np.linalg.norm(float_rays, axis=0)
    normalized = float_rays / scales
    float_target = np.asarray(target, dtype=float).reshape(dimension)
    result = linprog(
        np.linspace(0.0, 1.0e-9, ray_count),
        A_eq=normalized,
        b_eq=float_target,
        bounds=(0.0, None),
        method="highs",
        options={
            "dual_feasibility_tolerance": max(1.0e-9, tolerance),
            "primal_feasibility_tolerance": max(1.0e-9, tolerance),
        },
    )
    if not result.success:
        return None

    order = tuple(int(index) for index in np.argsort(-result.x))
    positive = tuple(index for index in order if result.x[index] > tolerance)
    pool = tuple(dict.fromkeys((*positive, *order[: min(ray_count, dimension + 4)])))

    def solve_support(support: tuple[int, ...]) -> sp.ImmutableMatrix | None:
        submatrix = rays[:, support]
        if submatrix.rank() != len(support):
            return None
        solution_set = sp.linsolve((submatrix, target))
        if solution_set is sp.EmptySet:
            return None
        solution = tuple(next(iter(solution_set)))
        if any(value.free_symbols or value < 0 for value in solution):
            return None
        coefficients = [sp.S.Zero] * ray_count
        for index, value in zip(support, solution, strict=True):
            coefficients[index] = value
        exact = sp.ImmutableMatrix(coefficients)
        if rays * exact != target:
            return None
        return exact

    for cutoff in (1.0e-7, 1.0e-9, 1.0e-11, tolerance):
        support = tuple(index for index in order if result.x[index] > cutoff)
        if support and len(support) <= dimension:
            exact = solve_support(support)
            if exact is not None:
                return exact

    max_support = min(dimension, len(pool))
    for size in range(1, max_support + 1):
        if len(pool) > 14 and size not in (dimension - 1, dimension):
            continue
        for support in combinations(pool, size):
            exact = solve_support(tuple(support))
            if exact is not None:
                return exact
    return None


def exact_polyhedral_certificate(
    matrices: Sequence[sp.MatrixBase],
    rays: Sequence[sp.MatrixBase],
    *,
    tolerance: float = 1.0e-10,
) -> dict[str, object] | None:
    """Replay ``A_i R = R P_i`` exactly with rational ``P_i >= 0``."""

    checked = _validated_exact_matrices(matrices)
    canonical = tuple(_canonical_ray(ray) for ray in rays)
    ray_matrix = sp.ImmutableMatrix.hstack(*canonical)
    dimension = checked[0].rows
    if ray_matrix.rows != dimension or ray_matrix.rank() != dimension:
        return None

    actions: list[sp.ImmutableMatrix] = []
    for matrix in checked:
        columns: list[sp.ImmutableMatrix] = []
        for ray in canonical:
            coordinates = _exact_nonnegative_coordinates(
                ray_matrix,
                sp.ImmutableMatrix(matrix * ray),
                tolerance=tolerance,
            )
            if coordinates is None:
                return None
            columns.append(coordinates)
        action = sp.ImmutableMatrix.hstack(*columns)
        if matrix * ray_matrix != ray_matrix * action:
            raise RuntimeError("exact cone replay produced an invalid action")
        if any(entry < 0 for entry in action):
            raise RuntimeError("exact cone replay produced a negative action")
        actions.append(action)

    minimum = min(entry for action in actions for entry in action)
    return {
        "status": "exact-certificate",
        "method": "rational-redundant-polyhedral-cone",
        "dimension": dimension,
        "ray_count": ray_matrix.cols,
        "rank": ray_matrix.rank(),
        "minimum_action_entry": _rational_payload(minimum),
        "rays": _matrix_payload(ray_matrix),
        "actions": [_matrix_payload(action) for action in actions],
    }


def _pf_rays(
    matrices: tuple[np.ndarray, ...],
    *,
    max_denominator: int,
) -> tuple[sp.ImmutableMatrix, ...]:
    rays: list[sp.ImmutableMatrix] = []
    for matrix in matrices:
        values, vectors = np.linalg.eig(matrix)
        for index in np.argsort(-np.abs(values))[:2]:
            vector = vectors[:, index]
            if np.max(np.abs(np.imag(vector))) > 1.0e-9:
                continue
            real = np.real(vector)
            for sign in (1.0, -1.0):
                try:
                    ray = _rationalize_ray(
                        sign * real,
                        max_denominator=max_denominator,
                    )
                except ValueError:
                    continue
                if ray not in rays:
                    rays.append(ray)
    return tuple(rays)


def polyhedral_column_generation(
    matrices: Sequence[sp.MatrixBase],
    initial_rays: Sequence[sp.MatrixBase],
    *,
    ray_counts: Sequence[int] = (12, 16, 20, 24),
    tolerance: float = 1.0e-10,
    seed_pf_rays: bool = False,
    max_denominator: int = 65536,
) -> dict[str, object]:
    """Grow one full-dimensional cone and exact-replay at requested sizes."""

    checked = _validated_exact_matrices(matrices)
    counts = tuple(sorted(set(int(count) for count in ray_counts)))
    dimension = checked[0].rows
    if not counts or counts[0] < dimension or tolerance < 0.0:
        raise ValueError("ray_counts must be nonempty and at least the dimension")
    rays = [_canonical_ray(ray) for ray in initial_rays]
    if len(rays) < dimension or sp.Matrix.hstack(*rays).rank() != dimension:
        raise ValueError("initial rays must span the ambient space")
    float_matrices = tuple(
        np.asarray(matrix.tolist(), dtype=float) for matrix in checked
    )
    if seed_pf_rays:
        for ray in _pf_rays(
            float_matrices,
            max_denominator=max_denominator,
        ):
            if ray not in rays and len(rays) < counts[0]:
                rays.append(ray)

    milestones: list[dict[str, object]] = []
    exact_hit: dict[str, object] | None = None
    while len(rays) <= counts[-1]:
        maximum, aggregate, worst, failures = _cone_residuals(
            float_matrices,
            rays,
        )
        if len(rays) in counts:
            certificate = None
            if maximum <= max(1.0e-8, 100.0 * tolerance):
                certificate = exact_polyhedral_certificate(
                    checked,
                    rays,
                    tolerance=tolerance,
                )
            milestone: dict[str, object] = {
                "ray_count": len(rays),
                "maximum_relative_residual": maximum,
                "aggregate_relative_residual": aggregate,
                "violations": failures,
                "worst_atom": worst[0],
                "worst_ray": worst[1],
                "exact_status": (
                    "exact-certificate"
                    if certificate is not None
                    else "no-exact-certificate"
                ),
            }
            milestones.append(milestone)
            print(json.dumps(milestone, sort_keys=True), flush=True)
            if certificate is not None:
                exact_hit = certificate
                break
        if len(rays) == counts[-1]:
            break
        atom_index, ray_index = worst
        new_ray = _canonical_ray(checked[atom_index] * rays[ray_index])
        if new_ray in rays:
            break
        rays.append(new_ray)

    return {
        "status": (
            "exact-certificate" if exact_hit is not None else "no-exact-certificate-found"
        ),
        "method": "worst-image-column-generation",
        "seed_pf_rays": seed_pf_rays,
        "milestones": milestones,
        "certificate": exact_hit,
    }


def search_seed61(
    *,
    attempts: int,
    maxiter: int,
    rng_seed: int,
    ray_counts: Sequence[int],
    denominators: Sequence[int],
    tolerance: float,
) -> dict[str, object]:
    """Reuse the best simplicial transform, then search redundant cones."""

    atoms = exact_atoms_from_card(
        candidate_card(template="exact5-shear-loop-pair", seed=61)
    )
    matrices = tuple(exact_compound_matrix(atom, 2) for atom in atoms)
    simplicial = numerical_simplicial_search(
        matrices,
        attempts=attempts,
        maxiter=maxiter,
        rng_seed=rng_seed,
        tolerance=tolerance,
        target_margin=1.0e-7,
        max_denominator=max(denominators),
    )
    best = simplicial.get("best", {})
    transform = best.get("transform") if isinstance(best, Mapping) else None
    if transform is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "no-simplicial-seed",
            "simplicial": simplicial,
            "searches": [],
        }

    numerical = np.asarray(transform, dtype=float)
    searches: list[dict[str, object]] = []
    for denominator in denominators:
        initial = tuple(
            _rationalize_ray(
                numerical[:, column],
                max_denominator=denominator,
            )
            for column in range(numerical.shape[1])
        )
        for seed_pf in (False, True):
            result = polyhedral_column_generation(
                matrices,
                initial,
                ray_counts=ray_counts,
                tolerance=tolerance,
                seed_pf_rays=seed_pf,
                max_denominator=denominator,
            )
            result["initial_max_denominator"] = denominator
            searches.append(result)
            if result["status"] == "exact-certificate":
                return {
                    "schema_version": SCHEMA_VERSION,
                    "status": "exact-certificate",
                    "candidate": "exact5-shear-loop-pair-seed-61-grade-2",
                    "simplicial": simplicial,
                    "searches": searches,
                    "certificate": result["certificate"],
                }
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "no-exact-certificate-found",
        "candidate": "exact5-shear-loop-pair-seed-61-grade-2",
        "simplicial": simplicial,
        "searches": searches,
    }


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parse_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in value.split(","))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", type=int, default=32)
    parser.add_argument("--maxiter", type=int, default=2000)
    # Replays search_card_shared_cones(..., rng_seed=121) at grade 2.
    parser.add_argument("--rng-seed", type=int, default=2139)
    parser.add_argument("--ray-counts", type=_parse_ints, default=(12, 16, 20, 24))
    parser.add_argument(
        "--denominators",
        type=_parse_ints,
        default=(2048, 16384, 65536, 1048576),
    )
    parser.add_argument("--tolerance", type=float, default=1.0e-10)
    parser.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = search_seed61(
        attempts=args.attempts,
        maxiter=args.maxiter,
        rng_seed=args.rng_seed,
        ray_counts=args.ray_counts,
        denominators=args.denominators,
        tolerance=args.tolerance,
    )
    if args.output:
        _write_json_atomic(Path(args.output), result)
    print(json.dumps(result, allow_nan=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "exact_polyhedral_certificate",
    "polyhedral_column_generation",
    "search_seed61",
]
