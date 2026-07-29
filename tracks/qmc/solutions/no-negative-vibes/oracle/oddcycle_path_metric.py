"""Last-letter path-metric discovery for oddcycle alphabets."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

import numpy as np

from .symmetric_oddcycle_discovery import oddcycle_matrix


SCHEMA = "oddcycle-last-letter-path-metric-v1"
EXACT_DENOMINATOR = 1_000_000_000
EXACT_POINTS = (("1/1000", "1", "1"), ("4/5", "1", "1"))
EXACT_METRIC_NUMERATORS = (
    (
        (-3378410, -10603980, 201640, -96552957, 10767675),
        (-10603980, -29512927, -3753778, -48291294, -10414788),
        (201640, -3753778, -10312845, -24139143, -1953082),
        (-96552957, -48291294, -24139143, -39984, -168960185),
        (10767675, -10414788, -1953082, -168960185, 20339717),
    ),
    (
        (-48578627, 9269750, -3727966, -100888160, 25722529),
        (9269750, -20210814, 3454447, -39427850, 122679),
        (-3727966, 3454447, -14144559, -45263453, 3196645),
        (-100888160, -39427850, -45263453, 23615722, -165984898),
        (25722529, 122679, 3196645, -165984898, -15168371),
    ),
    (
        (-2980907, 3419654, 8046813, -65079173, 10992433),
        (3419654, -19563999, -90968, -36555548, 14412802),
        (8046813, -90968, -15949901, -16471793, 8814117),
        (-65079173, -36555548, -16471793, 12178170, -108475898),
        (10992433, 14412802, 8814117, -108475898, 5639253),
    ),
    (
        (-20551540, 28379085, 1514191, -68450933, 17925403),
        (28379085, 7710934, 7777300, -21125542, 47177699),
        (1514191, 7777300, -15602536, -22544880, -3302188),
        (-68450933, -21125542, -22544880, 18405155, -121129139),
        (17925403, 47177699, -3302188, -121129139, -24769367),
    ),
)
EXACT_TIME_VECTORS = (
    (0, 0, 0, 0, 1),
    (0, 0, 0, 1, 0),
    (0, 0, 0, 1, 0),
    (0, 0, 0, 1, 0),
)


def last_letter_path_metric_sdp(
    points: Sequence[Sequence[float]],
    *,
    solver: str = "CLARABEL",
    validation_tolerance: float = 1.0e-7,
    rational_denominator: int = 0,
) -> dict[str, object]:
    """Search metrics that telescope on every cyclically read word."""

    try:
        import cvxpy as cp
    except ImportError as error:  # pragma: no cover - optional dependency
        raise RuntimeError("last_letter_path_metric_sdp requires cvxpy") from error

    normalized_points = tuple(
        tuple(float(value) for value in point) for point in points
    )
    if not normalized_points or any(len(point) != 3 for point in normalized_points):
        raise ValueError("points must be a nonempty sequence of triples")
    atoms = tuple(
        atom
        for point in normalized_points
        for matrix in (oddcycle_matrix(*point),)
        for atom in (matrix, matrix.T)
    )
    dimension = atoms[0].shape[0]
    state_count = len(atoms)
    metrics = tuple(
        cp.Variable((dimension, dimension), symmetric=True)
        for _ in atoms
    )
    margin = cp.Variable()
    identity = np.eye(dimension)
    gaps = tuple(
        metrics[previous]
        - atom.T @ metrics[current] @ atom
        for previous in range(state_count)
        for current, atom in enumerate(atoms)
    )
    problem = cp.Problem(
        cp.Maximize(margin),
        [
            *(gap - margin * identity >> 0 for gap in gaps),
            sum(cp.norm(metric, "fro") for metric in metrics) <= 1,
        ],
    )
    problem.solve(solver=solver)
    base = {
        "schema": SCHEMA,
        "points": [list(point) for point in normalized_points],
        "state_count": state_count,
        "transition_count": len(gaps),
        "solver": solver,
        "solver_status": str(problem.status),
    }
    if margin.value is None or any(metric.value is None for metric in metrics):
        return {**base, "status": "solver-inconclusive"}
    values = tuple(
        0.5
        * (
            np.asarray(metric.value, dtype=float)
            + np.asarray(metric.value, dtype=float).T
        )
        for metric in metrics
    )
    gap_eigenvalues = []
    for previous in range(state_count):
        for current, atom in enumerate(atoms):
            gap = values[previous] - atom.T @ values[current] @ atom
            gap_eigenvalues.append(np.linalg.eigvalsh(gap))
    verified_margin = float(min(eigenvalues[0] for eigenvalues in gap_eigenvalues))
    inertia = []
    for value in values:
        eigenvalues = np.linalg.eigvalsh(value)
        inertia.append(
            {
                "positive": int(
                    np.count_nonzero(eigenvalues > validation_tolerance)
                ),
                "negative": int(
                    np.count_nonzero(eigenvalues < -validation_tolerance)
                ),
                "zero": int(
                    np.count_nonzero(
                        np.abs(eigenvalues) <= validation_tolerance
                    )
                ),
                "eigenvalues": eigenvalues.tolist(),
            }
        )
    strict = (
        problem.status in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}
        and float(margin.value) > validation_tolerance
        and verified_margin > validation_tolerance
    )
    correct_inertia = all(
        record["positive"] == 1
        and record["negative"] == dimension - 1
        and record["zero"] == 0
        for record in inertia
    )
    result = {
        **base,
        "status": (
            "strict-last-letter-path-metric-found"
            if strict and correct_inertia
            else "no-strict-path-metric-numerically"
        ),
        "objective_margin": float(margin.value),
        "verified_margin": verified_margin,
        "correct_split_inertia": correct_inertia,
        "metric_inertias": inertia,
        "metrics": [value.tolist() for value in values],
        "cyclic_telescope": (
            "R_last-W.T R_last W is positive definite for every nonempty word"
            if strict
            else "not certified"
        ),
    }
    if rational_denominator > 0:
        result["rational_certificate"] = _rationalize_path_metrics(
            normalized_points,
            values,
            denominator=rational_denominator,
        )
    return result


def _rationalize_path_metrics(
    points: Sequence[Sequence[float]],
    values: Sequence[np.ndarray],
    *,
    denominator: int,
) -> dict[str, object]:
    """Round an interior path-metric solution and replay every gate exactly."""

    if denominator < 1:
        raise ValueError("denominator must be positive")
    try:
        import sympy as sp
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError("path-metric rationalization requires sympy") from error

    exact_points = tuple(
        tuple(sp.Rational(str(float(value))) for value in point)
        for point in points
    )
    numerators = tuple(
        tuple(
            tuple(
                int(round(float(value[row, column]) * denominator))
                for column in range(5)
            )
            for row in range(5)
        )
        for value in values
    )
    return _verify_exact_path_metrics(
        exact_points,
        numerators,
        denominator=denominator,
    )


def _verify_exact_path_metrics(
    points: Sequence[Sequence[object]],
    numerators: Sequence[Sequence[Sequence[int]]],
    *,
    denominator: int,
) -> dict[str, object]:
    """Replay fixed rational path-metric gates without an SDP solver."""

    if denominator < 1:
        raise ValueError("denominator must be positive")
    try:
        import sympy as sp
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError("exact path-metric replay requires sympy") from error

    exact_points = tuple(
        tuple(sp.Rational(value) for value in point) for point in points
    )
    atoms = tuple(
        atom
        for p, q, r in exact_points
        for matrix in (
            sp.ImmutableMatrix(
                [
                    [0, 0, 2, 0, 0],
                    [2, 0, 0, 0, 0],
                    [0, 2, 0, p, 0],
                    [0, 0, 0, 1, q],
                    [0, 0, -r, 0, 1],
                ]
            ),
        )
        for atom in (matrix, matrix.T)
    )
    integer_numerators = tuple(
        tuple(tuple(int(entry) for entry in row) for row in matrix)
        for matrix in numerators
    )
    if len(integer_numerators) != len(atoms) or any(
        len(matrix) != 5 or any(len(row) != 5 for row in matrix)
        for matrix in integer_numerators
    ):
        raise ValueError("one 5-by-5 metric numerator is required per atom")
    metrics = tuple(
        sp.ImmutableMatrix(numerator) / denominator
        for numerator in integer_numerators
    )
    inertia_records = []
    correct_inertia = True
    for numerator in integer_numerators:
        matrix = sp.ImmutableMatrix(numerator)
        minors = [sp.Integer(1)] + [
            sp.factor(matrix[:size, :size].det())
            for size in range(1, 6)
        ]
        nonzero = all(minor != 0 for minor in minors)
        sign_changes = sum(
            (left > 0) != (right > 0)
            for left, right in zip(minors, minors[1:])
        )
        valid = nonzero and sign_changes == 4
        correct_inertia = correct_inertia and valid
        inertia_records.append(
            {
                "leading_principal_minor_numerators": [
                    int(minor) for minor in minors[1:]
                ],
                "negative_eigenvalue_count_by_jacobi": sign_changes,
                "split_inertia_1_4": valid,
            }
        )
    gap_records = []
    all_gaps_positive = True
    for previous, previous_metric in enumerate(metrics):
        for current, atom in enumerate(atoms):
            gap = sp.ImmutableMatrix(
                previous_metric - atom.T * metrics[current] * atom
            )
            minors = [
                sp.factor(gap[:size, :size].det())
                for size in range(1, 6)
            ]
            positive = all(minor > 0 for minor in minors)
            all_gaps_positive = all_gaps_positive and positive
            gap_records.append(
                {
                    "previous_state": previous,
                    "current_letter": current,
                    "positive_definite_by_sylvester": positive,
                    "leading_principal_minors": [
                        {
                            "numerator": int(sp.numer(minor)),
                            "denominator": int(sp.denom(minor)),
                        }
                        for minor in minors
                    ],
                }
            )
    return {
        "denominator": int(denominator),
        "metrics": [
            [list(row) for row in numerator] for numerator in integer_numerators
        ],
        "correct_split_inertia": correct_inertia,
        "all_transition_gaps_positive_definite": all_gaps_positive,
        "inertias": inertia_records,
        "transitions": gap_records,
        "exact_arbitrary_word_contraction": (
            correct_inertia and all_gaps_positive
        ),
    }


def _verify_exact_time_orientation(
    points: Sequence[Sequence[object]],
    numerators: Sequence[Sequence[Sequence[int]]],
    time_vectors: Sequence[Sequence[int]],
    *,
    denominator: int,
) -> dict[str, object]:
    """Check that every inverse transition preserves chosen future sheets."""

    try:
        import sympy as sp
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError("exact time-orientation replay requires sympy") from error

    exact_points = tuple(
        tuple(sp.Rational(value) for value in point) for point in points
    )
    atoms = tuple(
        atom
        for p, q, r in exact_points
        for matrix in (
            sp.ImmutableMatrix(
                [
                    [0, 0, 2, 0, 0],
                    [2, 0, 0, 0, 0],
                    [0, 2, 0, p, 0],
                    [0, 0, 0, 1, q],
                    [0, 0, -r, 0, 1],
                ]
            ),
        )
        for atom in (matrix, matrix.T)
    )
    metrics = tuple(
        sp.ImmutableMatrix(numerator) / denominator for numerator in numerators
    )
    vectors = tuple(sp.ImmutableMatrix(vector) for vector in time_vectors)
    if len(vectors) != len(metrics) or any(vector.shape != (5, 1) for vector in vectors):
        raise ValueError("one five-component time vector is required per metric")
    norms = tuple(
        sp.factor((vector.T * metric * vector)[0])
        for vector, metric in zip(vectors, metrics, strict=True)
    )
    scalars = tuple(
        tuple(
            sp.factor(
                (vectors[previous].T * metrics[previous] * atom.inv() * vectors[current])[
                    0
                ]
            )
            for current, atom in enumerate(atoms)
        )
        for previous in range(len(metrics))
    )
    nonzero = all(value != 0 for row in scalars for value in row)
    orientation_signs = [sp.Integer(1)]
    if nonzero:
        orientation_signs.extend(sp.sign(scalars[index][0]) for index in range(1, 4))
    else:
        orientation_signs.extend(sp.Integer(1) for _ in range(3))
    oriented_scalars = tuple(
        tuple(
            sp.factor(
                orientation_signs[previous]
                * orientation_signs[current]
                * scalars[previous][current]
            )
            for current in range(4)
        )
        for previous in range(4)
    )
    time_like = all(value > 0 for value in norms)
    future_preserving = nonzero and all(
        value > 0 for row in oriented_scalars for value in row
    )
    atom_determinants = tuple(sp.factor(atom.det()) for atom in atoms)
    return {
        "time_vectors": [list(vector) for vector in time_vectors],
        "orientation_signs": [int(value) for value in orientation_signs],
        "oriented_time_vectors": [
            [
                int(orientation_signs[index] * entry)
                for entry in time_vectors[index]
            ]
            for index in range(len(time_vectors))
        ],
        "time_like_norms": [
            {
                "numerator": int(sp.numer(value)),
                "denominator": int(sp.denom(value)),
            }
            for value in norms
        ],
        "all_time_vectors_positive": time_like,
        "transition_orientation_scalars": [
            [
                {
                    "numerator": int(sp.numer(value)),
                    "denominator": int(sp.denom(value)),
                }
                for value in row
            ]
            for row in oriented_scalars
        ],
        "all_inverse_transitions_future_preserving": future_preserving,
        "atom_determinants": [int(value) for value in atom_determinants],
        "all_atom_determinants_positive": all(
            value > 0 for value in atom_determinants
        ),
    }


def exact_last_letter_path_metric_certificate() -> dict[str, object]:
    """Verify the frozen two-point, four-state certificate exactly."""

    certificate = _verify_exact_path_metrics(
        EXACT_POINTS,
        EXACT_METRIC_NUMERATORS,
        denominator=EXACT_DENOMINATOR,
    )
    orientation = _verify_exact_time_orientation(
        EXACT_POINTS,
        EXACT_METRIC_NUMERATORS,
        EXACT_TIME_VECTORS,
        denominator=EXACT_DENOMINATOR,
    )
    valid = bool(certificate["exact_arbitrary_word_contraction"])
    determinant_positive = (
        valid
        and orientation["all_time_vectors_positive"]
        and orientation["all_inverse_transitions_future_preserving"]
        and orientation["all_atom_determinants_positive"]
    )
    return {
        "schema": SCHEMA,
        "status": (
            "exact-positive-last-letter-path-metric-certificate"
            if determinant_positive
            else "exact-unoriented-last-letter-path-metric-certificate"
            if valid
            else "exact-certificate-failed"
        ),
        "points": [list(point) for point in EXACT_POINTS],
        "state_count": len(EXACT_METRIC_NUMERATORS),
        "transition_count": len(certificate["transitions"]),
        "cyclic_telescope": (
            "R_last-W.T R_last W is positive definite for every nonempty word"
            if valid
            else "not certified"
        ),
        "certificate": certificate,
        "time_orientation": orientation,
        "exact_arbitrary_word_determinant_positive": determinant_positive,
    }


__all__ = [
    "EXACT_DENOMINATOR",
    "EXACT_METRIC_NUMERATORS",
    "EXACT_POINTS",
    "EXACT_TIME_VECTORS",
    "SCHEMA",
    "exact_last_letter_path_metric_certificate",
    "last_letter_path_metric_sdp",
]


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--point",
        nargs=3,
        type=float,
        action="append",
        required=True,
        metavar=("P", "Q", "R"),
    )
    parser.add_argument("--solver", default="CLARABEL")
    parser.add_argument("--rational-denominator", type=int, default=0)
    parser.add_argument("--summary", action="store_true")
    arguments = parser.parse_args()
    payload = last_letter_path_metric_sdp(
        arguments.point,
        solver=arguments.solver,
        rational_denominator=arguments.rational_denominator,
    )
    if arguments.summary:
        rational = payload.get("rational_certificate")
        payload = {
            key: payload.get(key)
            for key in (
                "schema",
                "points",
                "state_count",
                "transition_count",
                "solver_status",
                "status",
                "objective_margin",
                "verified_margin",
                "correct_split_inertia",
                "metric_inertias",
                "cyclic_telescope",
            )
        }
        if rational is not None:
            payload["rational_certificate"] = {
                "denominator": rational["denominator"],
                "metrics": rational["metrics"],
                "correct_split_inertia": rational["correct_split_inertia"],
                "all_transition_gaps_positive_definite": rational[
                    "all_transition_gaps_positive_definite"
                ],
                "exact_arbitrary_word_contraction": rational[
                    "exact_arbitrary_word_contraction"
                ],
            }
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":  # pragma: no cover - discovery CLI
    _main()
