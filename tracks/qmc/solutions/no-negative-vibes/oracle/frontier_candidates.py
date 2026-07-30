"""Low-dimensional semigroup candidates for rapid falsification."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class FrontierCase:
    family: str
    shape: tuple[int, int]
    prior_status: str = "candidate"


_CASES = {
    "tn_path4_sym": FrontierCase("tn_path_symmetric", (4, 4)),
    "tn_path6_sym": FrontierCase("tn_path_symmetric", (6, 6)),
    "tn_path4_asym": FrontierCase("tn_path_asymmetric", (4, 4)),
    "tn_path6_asym": FrontierCase("tn_path_asymmetric", (6, 6)),
    "tn_path4_common_gauge": FrontierCase(
        "tn_path_common_gauge",
        (4, 4),
        "factorization_control",
    ),
    "tn_path4_slice_gauge": FrontierCase(
        "tn_path_slice_gauge",
        (4, 4),
    ),
    "metzler_cycle4_sym": FrontierCase("metzler_cycle_symmetric", (4, 4)),
    "metzler_star4_sym": FrontierCase("metzler_star_symmetric", (4, 4)),
    "metzler_dense4_sym": FrontierCase("metzler_dense_symmetric", (4, 4)),
    "split_cone22": FrontierCase(
        "split_contraction_cone",
        (4, 4),
        "known_nonnegative",
    ),
    "split_mixed005": FrontierCase("mixed_split_cones_angle_0.05", (4, 4)),
    "split_mixed02": FrontierCase("mixed_split_cones_angle_0.2", (4, 4)),
    "split_mixed05": FrontierCase("mixed_split_cones_angle_0.5", (4, 4)),
    "block_upper_split11": FrontierCase(
        "block_upper_split_cones",
        (4, 4),
        "factorization_control",
    ),
    "block_bicoupled_split11": FrontierCase(
        "block_bicoupled_split_cones",
        (4, 4),
    ),
}


def available_cases() -> dict[str, FrontierCase]:
    return dict(_CASES)


def _normalize(matrix: np.ndarray, *, scale: float) -> np.ndarray:
    norm = float(np.linalg.norm(matrix))
    if norm == 0.0:
        raise RuntimeError("candidate generator construction produced zero")
    return matrix * (scale * math.sqrt(matrix.shape[0]) / norm)


def _positive_path(
    rng: np.random.Generator,
    *,
    size: int,
    symmetric: bool,
) -> np.ndarray:
    matrix = np.diag(rng.standard_normal(size))
    upper = np.abs(rng.standard_normal(size - 1)) + 0.1
    lower = upper if symmetric else np.abs(rng.standard_normal(size - 1)) + 0.1
    matrix[np.arange(size - 1), np.arange(1, size)] = upper
    matrix[np.arange(1, size), np.arange(size - 1)] = lower
    return matrix


def _symmetric_graph_generator(
    rng: np.random.Generator,
    *,
    size: int,
    edges: list[tuple[int, int]],
) -> np.ndarray:
    matrix = np.diag(rng.standard_normal(size))
    for left, right in edges:
        value = abs(float(rng.standard_normal())) + 0.1
        matrix[left, right] = value
        matrix[right, left] = value
    return matrix


def _metric(size: int) -> np.ndarray:
    half = size // 2
    return np.diag([1.0] * half + [-1.0] * half)


def _split_cone_generator(
    rng: np.random.Generator,
    *,
    size: int,
) -> np.ndarray:
    eta = _metric(size)
    raw = rng.standard_normal((size, size)) / math.sqrt(size)
    algebra = 0.5 * (raw - eta @ raw.T @ eta)
    cone_raw = rng.standard_normal((size, size)) / math.sqrt(size)
    positive = cone_raw @ cone_raw.T
    return algebra + eta @ positive


def _plane_rotation(size: int, *, angle: float) -> np.ndarray:
    rotation = np.eye(size)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    # Mix one positive-metric and one negative-metric axis.
    rotation[np.ix_([0, size // 2], [0, size // 2])] = [
        [cosine, -sine],
        [sine, cosine],
    ]
    return rotation


def _block_split_generator(
    rng: np.random.Generator,
    *,
    bidirectional: bool,
) -> np.ndarray:
    first = _split_cone_generator(rng, size=2)
    second = _split_cone_generator(rng, size=2)
    upper = rng.standard_normal((2, 2))
    lower = rng.standard_normal((2, 2)) if bidirectional else np.zeros((2, 2))
    return np.block([[first, upper], [lower, second]])


def mixed_split_boundary_counterexample(
    *,
    angle: float,
    amplitude: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return an analytic two-slice counterexample for two rotated split cones.

    The first generator is an embedded rank-one nilpotent boundary ray of the
    cone for ``eta=diag(1,1,-1,-1)``.  The second is the same ray rotated
    between axes zero and two.
    """

    if math.isclose(math.sin(angle), 0.0, abs_tol=1e-15):
        raise ValueError("angle must define a different cone")
    if amplitude <= 0.0:
        raise ValueError("amplitude must be positive")

    generator = np.zeros((4, 4))
    generator[np.ix_([0, 2], [0, 2])] = amplitude * np.array(
        [[1.0, 1.0], [-1.0, -1.0]]
    )
    rotation = _plane_rotation(4, angle=angle)
    return generator, rotation @ generator @ rotation.T


def random_generator(
    case: str,
    rng: np.random.Generator,
    *,
    scale: float,
) -> np.ndarray:
    spec = _CASES[case]
    size = spec.shape[0]

    if spec.family == "tn_path_symmetric":
        matrix = _positive_path(rng, size=size, symmetric=True)
    elif spec.family == "tn_path_asymmetric":
        matrix = _positive_path(rng, size=size, symmetric=False)
    elif spec.family == "tn_path_common_gauge":
        positive = _positive_path(rng, size=size, symmetric=True)
        gauge = np.diag([1.0, -1.0, 1.0, -1.0])
        matrix = gauge @ positive @ gauge
    elif spec.family == "tn_path_slice_gauge":
        positive = _positive_path(rng, size=size, symmetric=True)
        signs = rng.choice([-1.0, 1.0], size=size)
        gauge = np.diag(signs)
        matrix = gauge @ positive @ gauge
    elif spec.family == "metzler_cycle_symmetric":
        matrix = _symmetric_graph_generator(
            rng,
            size=size,
            edges=[(0, 1), (1, 2), (2, 3), (3, 0)],
        )
    elif spec.family == "metzler_star_symmetric":
        matrix = _symmetric_graph_generator(
            rng,
            size=size,
            edges=[(0, 1), (0, 2), (0, 3)],
        )
    elif spec.family == "metzler_dense_symmetric":
        matrix = _symmetric_graph_generator(
            rng,
            size=size,
            edges=[
                (left, right)
                for left in range(size)
                for right in range(left + 1, size)
            ],
        )
    elif spec.family == "split_contraction_cone":
        matrix = _split_cone_generator(rng, size=size)
    elif spec.family.startswith("mixed_split_cones_angle_"):
        angle = float(spec.family.rsplit("_", maxsplit=1)[-1])
        matrix = _split_cone_generator(rng, size=size)
        if rng.random() < 0.5:
            rotation = _plane_rotation(size, angle=angle)
            matrix = rotation @ matrix @ rotation.T
    elif spec.family == "block_upper_split_cones":
        matrix = _block_split_generator(rng, bidirectional=False)
    elif spec.family == "block_bicoupled_split_cones":
        matrix = _block_split_generator(rng, bidirectional=True)
    else:
        raise ValueError(f"unsupported frontier family: {spec.family}")

    return _normalize(matrix, scale=scale)


def _off_pattern_residual(
    matrix: np.ndarray,
    *,
    allowed_edges: list[tuple[int, int]],
    symmetric: bool,
    require_positive: bool,
) -> float:
    size = matrix.shape[0]
    allowed = np.eye(size, dtype=bool)
    for left, right in allowed_edges:
        allowed[left, right] = True
        allowed[right, left] = True
    residuals = [float(np.linalg.norm(matrix[~allowed]))]
    if symmetric:
        residuals.append(float(np.linalg.norm(matrix - matrix.T)))
    if require_positive:
        for left, right in allowed_edges:
            residuals.append(max(0.0, -float(matrix[left, right])))
            residuals.append(max(0.0, -float(matrix[right, left])))
    return max(residuals, default=0.0)


def _split_cone_residual(matrix: np.ndarray, *, eta: np.ndarray) -> float:
    cone = matrix.T @ eta + eta @ matrix
    hermitian_residual = float(np.linalg.norm(cone - cone.T))
    smallest = float(np.linalg.eigvalsh(0.5 * (cone + cone.T))[0])
    return max(hermitian_residual, max(0.0, -smallest))


def structure_residual(case: str, generator: np.ndarray) -> float:
    spec = _CASES[case]
    matrix = np.asarray(generator, dtype=float)
    scale = max(1.0, float(np.linalg.norm(matrix)))
    size = matrix.shape[0]
    path_edges = [(index, index + 1) for index in range(size - 1)]

    if spec.family in {"tn_path_symmetric", "tn_path_asymmetric"}:
        residual = _off_pattern_residual(
            matrix,
            allowed_edges=path_edges,
            symmetric=spec.family == "tn_path_symmetric",
            require_positive=True,
        )
    elif spec.family == "tn_path_common_gauge":
        gauge = np.diag([1.0, -1.0, 1.0, -1.0])
        residual = _off_pattern_residual(
            gauge @ matrix @ gauge,
            allowed_edges=path_edges,
            symmetric=True,
            require_positive=True,
        )
    elif spec.family == "tn_path_slice_gauge":
        residual = _off_pattern_residual(
            matrix,
            allowed_edges=path_edges,
            symmetric=True,
            require_positive=False,
        )
    elif spec.family == "metzler_cycle_symmetric":
        residual = _off_pattern_residual(
            matrix,
            allowed_edges=[(0, 1), (1, 2), (2, 3), (3, 0)],
            symmetric=True,
            require_positive=True,
        )
    elif spec.family == "metzler_star_symmetric":
        residual = _off_pattern_residual(
            matrix,
            allowed_edges=[(0, 1), (0, 2), (0, 3)],
            symmetric=True,
            require_positive=True,
        )
    elif spec.family == "metzler_dense_symmetric":
        residual = _off_pattern_residual(
            matrix,
            allowed_edges=[
                (left, right)
                for left in range(size)
                for right in range(left + 1, size)
            ],
            symmetric=True,
            require_positive=True,
        )
    elif spec.family == "split_contraction_cone":
        residual = _split_cone_residual(matrix, eta=_metric(size))
    elif spec.family.startswith("mixed_split_cones_angle_"):
        angle = float(spec.family.rsplit("_", maxsplit=1)[-1])
        eta = _metric(size)
        rotation = _plane_rotation(size, angle=angle)
        rotated_eta = rotation @ eta @ rotation.T
        residual = min(
            _split_cone_residual(matrix, eta=eta),
            _split_cone_residual(matrix, eta=rotated_eta),
        )
    elif spec.family in {
        "block_upper_split_cones",
        "block_bicoupled_split_cones",
    }:
        residuals = [
            _split_cone_residual(matrix[:2, :2], eta=_metric(2)),
            _split_cone_residual(matrix[2:, 2:], eta=_metric(2)),
        ]
        if spec.family == "block_upper_split_cones":
            residuals.append(float(np.linalg.norm(matrix[2:, :2])))
        residual = max(residuals)
    else:
        raise ValueError(f"unsupported frontier family: {spec.family}")

    return residual / scale
