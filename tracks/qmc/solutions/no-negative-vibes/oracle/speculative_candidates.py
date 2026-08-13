"""Speculative low-dimensional semigroups and adversarial relaxations.

Each positive control is paired with a minimal relaxation which removes the
algebraic reason for positivity.  The common scan dispatch imports this module
through the same ``available_cases/random_generator/structure_residual`` API
as the established candidate families.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class SpeculativeCase:
    family: str
    shape: tuple[int, int] = (4, 4)
    prior_status: str = "candidate"


_CASES = {
    "linf_contract4": SpeculativeCase(
        "fixed_weighted_linf_contraction",
        prior_status="theorem_nonnegative",
    ),
    "linf_moving_metric4": SpeculativeCase(
        "slice_dependent_weighted_linf_contraction",
    ),
    "reciprocal_parabolic4": SpeculativeCase(
        "reciprocal_parabolic_flag",
        prior_status="theorem_nonnegative",
    ),
    "reciprocal_bicoupled4": SpeculativeCase(
        "reciprocal_diagonal_with_bidirectional_coupling",
    ),
    "lusztig_d4_positive": SpeculativeCase(
        "split_so44_lusztig_positive_root_wedge",
        shape=(8, 8),
        prior_status="known_nonnegative",
    ),
    "lusztig_d4_signed": SpeculativeCase(
        "split_so44_simple_root_wedge_with_signed_coefficients",
        shape=(8, 8),
        prior_status="known_nonnegative",
    ),
    "commuting_dense4": SpeculativeCase(
        "dense_real_circulant_abelian_algebra",
        prior_status="theorem_nonnegative",
    ),
    "near_commuting4": SpeculativeCase(
        "two_nearby_dense_real_circulant_algebras",
    ),
}

_SIZE = 4
_D4_SIZE = 8
_LINF_METRICS = (
    np.array([8.0, 1.0, 1.0, 1.0]),
    np.array([1.0, 8.0, 1.0, 1.0]),
)


def _cyclic_shift(size: int) -> np.ndarray:
    shift = np.zeros((size, size))
    shift[np.arange(size), (np.arange(size) + 1) % size] = 1.0
    return shift


_SHIFT = _cyclic_shift(_SIZE)
_CIRCULANT_BASIS = tuple(
    np.linalg.matrix_power(_SHIFT, power) for power in range(_SIZE)
)


def _plane_rotation(size: int, *, angle: float) -> np.ndarray:
    rotation = np.eye(size)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    rotation[np.ix_([0, 1], [0, 1])] = np.array(
        [[cosine, -sine], [sine, cosine]]
    )
    return rotation


_NEAR_ROTATION = _plane_rotation(_SIZE, angle=0.28)
_NEAR_CIRCULANT_BASIS = tuple(
    _NEAR_ROTATION @ basis @ _NEAR_ROTATION.T
    for basis in _CIRCULANT_BASIS
)


def _d4_bases() -> tuple[
    tuple[np.ndarray, ...],
    tuple[np.ndarray, ...],
    tuple[np.ndarray, ...],
]:
    cartan: list[np.ndarray] = []
    for index in range(4):
        element = np.zeros((_D4_SIZE, _D4_SIZE))
        element[index, index] = 1.0
        element[4 + index, 4 + index] = -1.0
        cartan.append(element)

    raising: list[np.ndarray] = []
    for index in range(3):
        element = np.zeros((_D4_SIZE, _D4_SIZE))
        element[index, index + 1] = 1.0
        element[4 + index + 1, 4 + index] = -1.0
        raising.append(element)
    final_root = np.zeros((_D4_SIZE, _D4_SIZE))
    final_root[2, 7] = 1.0
    final_root[3, 6] = -1.0
    raising.append(final_root)
    lowering = [element.T for element in raising]
    return tuple(cartan), tuple(raising), tuple(lowering)


_D4_CARTAN, _D4_RAISING, _D4_LOWERING = _d4_bases()
_D4_BASIS = _D4_CARTAN + _D4_RAISING + _D4_LOWERING


def available_cases() -> dict[str, SpeculativeCase]:
    return dict(_CASES)


def _normalize(matrix: np.ndarray, *, scale: float) -> np.ndarray:
    norm = float(np.linalg.norm(matrix))
    if norm == 0.0:
        raise RuntimeError("speculative candidate construction produced zero")
    return matrix * (scale * math.sqrt(matrix.shape[0]) / norm)


def _weighted_linf_generator(
    rng: np.random.Generator,
    *,
    metric: np.ndarray,
) -> np.ndarray:
    matrix = rng.standard_normal((_SIZE, _SIZE)) / math.sqrt(_SIZE)
    np.fill_diagonal(matrix, 0.0)
    weighted_radius = (
        np.abs(matrix) @ metric
    ) / metric
    killing = np.abs(rng.standard_normal(_SIZE)) / math.sqrt(_SIZE) + 0.05
    matrix[np.diag_indices(_SIZE)] = -weighted_radius - killing
    return matrix


def _moving_linf_generator(
    rng: np.random.Generator,
    *,
    metric_index: int,
) -> np.ndarray:
    """Sample near a shear boundary where changing norms is adversarial."""
    metric = _LINF_METRICS[metric_index]
    matrix = np.zeros((_SIZE, _SIZE))
    row, column = ((0, 1) if metric_index == 0 else (1, 0))
    matrix[row, column] = (
        rng.choice((-1.0, 1.0))
        * (abs(float(rng.standard_normal())) + 1.0)
    )
    weighted_radius = (np.abs(matrix) @ metric) / metric
    matrix[np.diag_indices(_SIZE)] = -weighted_radius - 0.01
    return matrix


def _reciprocal_generator(
    rng: np.random.Generator,
    *,
    bidirectional: bool,
) -> np.ndarray:
    half = _SIZE // 2
    upper_left = rng.standard_normal((half, half))
    upper_right = rng.standard_normal((half, half))
    lower_left = (
        rng.standard_normal((half, half))
        if bidirectional
        else np.zeros((half, half))
    )
    return np.block(
        [
            [upper_left, upper_right],
            [lower_left, -upper_left.T],
        ]
    )


def _lusztig_generator(
    rng: np.random.Generator,
    *,
    positive: bool,
) -> np.ndarray:
    raising_coefficients = rng.standard_normal(4)
    lowering_coefficients = rng.standard_normal(4)
    if positive:
        raising_coefficients = np.abs(raising_coefficients) + 0.05
        lowering_coefficients = np.abs(lowering_coefficients) + 0.05
    cartan_coefficients = rng.standard_normal(4)

    matrix = np.zeros((_D4_SIZE, _D4_SIZE))
    for coefficient, element in zip(cartan_coefficients, _D4_CARTAN):
        matrix += coefficient * element
    for coefficient, element in zip(raising_coefficients, _D4_RAISING):
        matrix += coefficient * element
    for coefficient, element in zip(lowering_coefficients, _D4_LOWERING):
        matrix += coefficient * element
    return matrix


def _circulant_generator(
    rng: np.random.Generator,
    *,
    rotated: bool,
) -> np.ndarray:
    coefficients = rng.standard_normal(_SIZE)
    basis = _NEAR_CIRCULANT_BASIS if rotated else _CIRCULANT_BASIS
    return sum(
        (
            coefficient * basis_matrix
            for coefficient, basis_matrix in zip(coefficients, basis)
        ),
        start=np.zeros((_SIZE, _SIZE)),
    )


def random_generator(
    case: str,
    rng: np.random.Generator,
    *,
    scale: float,
) -> np.ndarray:
    if case not in _CASES:
        raise ValueError(f"unknown speculative case: {case}")

    if case == "linf_contract4":
        matrix = _weighted_linf_generator(
            rng,
            metric=_LINF_METRICS[0],
        )
    elif case == "linf_moving_metric4":
        metric_index = int(rng.integers(len(_LINF_METRICS)))
        matrix = _moving_linf_generator(
            rng,
            metric_index=metric_index,
        )
    elif case == "reciprocal_parabolic4":
        matrix = _reciprocal_generator(rng, bidirectional=False)
    elif case == "reciprocal_bicoupled4":
        matrix = _reciprocal_generator(rng, bidirectional=True)
    elif case == "lusztig_d4_positive":
        matrix = _lusztig_generator(rng, positive=True)
    elif case == "lusztig_d4_signed":
        matrix = _lusztig_generator(rng, positive=False)
    elif case == "commuting_dense4":
        matrix = _circulant_generator(rng, rotated=False)
    elif case == "near_commuting4":
        matrix = _circulant_generator(
            rng,
            rotated=bool(rng.integers(2)),
        )
    else:
        raise AssertionError("unreachable speculative case")

    return _normalize(matrix, scale=scale)


def _weighted_linf_residual(
    matrix: np.ndarray,
    *,
    metric: np.ndarray,
) -> float:
    diagonal = np.diag(matrix)
    off_diagonal = matrix - np.diag(diagonal)
    logarithmic_rows = diagonal + (np.abs(off_diagonal) @ metric) / metric
    return max(0.0, float(np.max(logarithmic_rows)))


def _reciprocal_residual(
    matrix: np.ndarray,
    *,
    bidirectional: bool,
) -> float:
    half = matrix.shape[0] // 2
    upper_left = matrix[:half, :half]
    lower_left = matrix[half:, :half]
    lower_right = matrix[half:, half:]
    residuals = [float(np.linalg.norm(lower_right + upper_left.T))]
    if not bidirectional:
        residuals.append(float(np.linalg.norm(lower_left)))
    return max(residuals)


def _lusztig_residual(
    matrix: np.ndarray,
    *,
    positive: bool,
) -> float:
    design = np.column_stack(
        [element.reshape(-1) for element in _D4_BASIS]
    )
    coefficients, *_ = np.linalg.lstsq(
        design,
        matrix.reshape(-1),
        rcond=None,
    )
    projection = (design @ coefficients).reshape(matrix.shape)
    residuals = [float(np.linalg.norm(matrix - projection))]
    if positive:
        root_coefficients = coefficients[len(_D4_CARTAN) :]
        residuals.append(
            max(0.0, -float(np.min(root_coefficients)))
        )
    return max(residuals)


def _linear_span_residual(
    matrix: np.ndarray,
    basis: tuple[np.ndarray, ...],
) -> float:
    design = np.column_stack([element.reshape(-1) for element in basis])
    coefficients, *_ = np.linalg.lstsq(
        design,
        matrix.reshape(-1),
        rcond=None,
    )
    projection = (design @ coefficients).reshape(matrix.shape)
    return float(np.linalg.norm(matrix - projection))


def structure_residual(case: str, generator: np.ndarray) -> float:
    if case not in _CASES:
        raise ValueError(f"unknown speculative case: {case}")
    matrix = np.asarray(generator)
    scale = max(1.0, float(np.linalg.norm(matrix)))
    real_matrix = np.asarray(matrix.real, dtype=float)
    residuals = [float(np.linalg.norm(matrix.imag))]

    if case == "linf_contract4":
        residuals.append(
            _weighted_linf_residual(
                real_matrix,
                metric=_LINF_METRICS[0],
            )
        )
    elif case == "linf_moving_metric4":
        residuals.append(
            min(
                _weighted_linf_residual(real_matrix, metric=metric)
                for metric in _LINF_METRICS
            )
        )
    elif case == "reciprocal_parabolic4":
        residuals.append(
            _reciprocal_residual(real_matrix, bidirectional=False)
        )
    elif case == "reciprocal_bicoupled4":
        residuals.append(
            _reciprocal_residual(real_matrix, bidirectional=True)
        )
    elif case == "lusztig_d4_positive":
        residuals.append(_lusztig_residual(real_matrix, positive=True))
    elif case == "lusztig_d4_signed":
        residuals.append(_lusztig_residual(real_matrix, positive=False))
    elif case == "commuting_dense4":
        residuals.append(
            _linear_span_residual(real_matrix, _CIRCULANT_BASIS)
        )
    elif case == "near_commuting4":
        residuals.append(
            min(
                _linear_span_residual(real_matrix, basis)
                for basis in (
                    _CIRCULANT_BASIS,
                    _NEAR_CIRCULANT_BASIS,
                )
            )
        )
    else:
        raise AssertionError("unreachable speculative case")

    return max(residuals) / scale
