"""Natural semigroup-cone extensions of the four surviving AZ classes."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from . import az_families


@dataclass(frozen=True)
class AZConeCase:
    family: str
    shape: tuple[int, int] = (4, 4)
    prior_status: str = "candidate"


_CASES = {
    "azcone_bdi_split": AZConeCase(
        "bdi_split_contraction",
        prior_status="known_nonnegative",
    ),
    "azcone_bdi_two_sided": AZConeCase(
        "bdi_mixed_contraction_expansion",
    ),
    "azcone_aii_kramers": AZConeCase(
        "aii_nonhermitian_kramers",
        prior_status="known_nonnegative",
    ),
    "azcone_diii_phs": AZConeCase(
        "diii_phs_preserving_metric_cone",
    ),
    "azcone_diii_generic": AZConeCase(
        "diii_generic_metric_cone",
    ),
    "azcone_cii_kramers": AZConeCase(
        "cii_kramers_metric_cone",
        prior_status="known_nonnegative",
    ),
    "azcone_cii_generic": AZConeCase(
        "cii_generic_metric_cone",
    ),
}


def available_cases() -> dict[str, AZConeCase]:
    return dict(_CASES)


def bdi_two_sided_boundary_counterexample(q: float) -> list[np.ndarray]:
    """Return a two-layer exact BDI two-sided-cone counterexample.

    The active two-dimensional subspace contains one positive- and one
    negative-metric direction.  Both generators square to zero, and the full
    four-dimensional determinant is exactly ``16 * (1 - q**2)``.
    """
    if q <= 0.0:
        raise ValueError("q must be positive")
    metric = np.asarray(
        az_families.symmetry_operators("az_bdi")["S"]
    ).real
    positive_null = np.array([1.0, 0.0, 1.0, 0.0])
    negative_null = np.array([1.0, 0.0, -1.0, 0.0])
    contraction = q * metric @ np.outer(positive_null, positive_null)
    expansion = -q * metric @ np.outer(negative_null, negative_null)
    return [contraction, expansion]


def _complex_random(
    rng: np.random.Generator,
    *,
    size: int,
) -> np.ndarray:
    return (
        rng.standard_normal((size, size))
        + 1j * rng.standard_normal((size, size))
    ) / math.sqrt(2.0 * size)


def _antiunitary_projection(
    matrix: np.ndarray,
    operator: np.ndarray,
    *,
    sign: int,
) -> np.ndarray:
    transformed = operator @ matrix.conj() @ operator.conj().T
    return 0.5 * (matrix + sign * transformed)


def _positive_semidefinite(
    rng: np.random.Generator,
    *,
    size: int,
    antiunitary: np.ndarray | None = None,
) -> np.ndarray:
    raw = _complex_random(rng, size=size)
    positive = raw @ raw.conj().T
    if antiunitary is not None:
        transformed = antiunitary @ positive.conj() @ antiunitary.conj().T
        positive = 0.5 * (positive + transformed)
    return 0.5 * (positive + positive.conj().T)


def _normalize(matrix: np.ndarray, *, scale: float) -> np.ndarray:
    norm = float(np.linalg.norm(matrix))
    if norm == 0.0:
        raise RuntimeError("AZ cone construction produced a zero generator")
    return matrix * (scale * math.sqrt(matrix.shape[0]) / norm)


def _metric_cone_generator(
    case: str,
    rng: np.random.Generator,
    *,
    cone_symmetry: str | None,
) -> np.ndarray:
    base_case = {
        "azcone_diii_phs": "az_diii",
        "azcone_diii_generic": "az_diii",
        "azcone_cii_kramers": "az_cii",
        "azcone_cii_generic": "az_cii",
    }[case]
    operators = az_families.symmetry_operators(base_case)
    metric = np.asarray(operators["S"])
    antiunitary = (
        None
        if cone_symmetry is None
        else np.asarray(operators[cone_symmetry])
    )
    base = az_families.random_generator(base_case, rng, scale=1.0)
    positive = _positive_semidefinite(
        rng,
        size=metric.shape[0],
        antiunitary=antiunitary,
    )
    return base + metric @ positive


def random_generator(
    case: str,
    rng: np.random.Generator,
    *,
    scale: float,
) -> np.ndarray:
    if case not in _CASES:
        raise ValueError(f"unknown AZ cone case: {case}")

    if case in {"azcone_bdi_split", "azcone_bdi_two_sided"}:
        metric = np.asarray(az_families.symmetry_operators("az_bdi")["S"])
        raw = rng.standard_normal((4, 4)) / 2.0
        algebra = 0.5 * (raw - metric @ raw.T @ metric)
        cone_raw = rng.standard_normal((4, 4)) / 2.0
        positive = cone_raw @ cone_raw.T
        direction = (
            rng.choice((-1.0, 1.0))
            if case == "azcone_bdi_two_sided"
            else 1.0
        )
        generator = algebra + direction * metric @ positive
    elif case == "azcone_aii_kramers":
        time_reversal = np.asarray(
            az_families.symmetry_operators("az_aii")["T"]
        )
        raw = _complex_random(rng, size=4)
        generator = _antiunitary_projection(
            raw,
            time_reversal,
            sign=1,
        )
    elif case == "azcone_diii_phs":
        generator = _metric_cone_generator(
            case,
            rng,
            cone_symmetry="C",
        )
    elif case == "azcone_diii_generic":
        generator = _metric_cone_generator(
            case,
            rng,
            cone_symmetry=None,
        )
    elif case == "azcone_cii_kramers":
        generator = _metric_cone_generator(
            case,
            rng,
            cone_symmetry="T",
        )
    elif case == "azcone_cii_generic":
        generator = _metric_cone_generator(
            case,
            rng,
            cone_symmetry=None,
        )
    else:
        raise AssertionError("unreachable AZ cone case")

    return _normalize(generator, scale=scale)


def _antiunitary_residual(
    matrix: np.ndarray,
    *,
    operator: np.ndarray,
    sign: int,
) -> float:
    transformed = operator @ matrix.conj() @ operator.conj().T
    return float(np.linalg.norm(transformed - sign * matrix))


def _metric_cone_residual(
    matrix: np.ndarray,
    *,
    metric: np.ndarray,
    allow_either_direction: bool = False,
) -> float:
    cone = matrix.conj().T @ metric + metric @ matrix
    cone = 0.5 * (cone + cone.conj().T)
    forward = max(0.0, -float(np.linalg.eigvalsh(cone)[0]))
    if not allow_either_direction:
        return forward
    backward = max(0.0, float(np.linalg.eigvalsh(cone)[-1]))
    return min(forward, backward)


def structure_residual(case: str, generator: np.ndarray) -> float:
    if case not in _CASES:
        raise ValueError(f"unknown AZ cone case: {case}")
    matrix = np.asarray(generator, dtype=complex)
    scale = max(1.0, float(np.linalg.norm(matrix)))
    residuals: list[float] = []

    if case in {"azcone_bdi_split", "azcone_bdi_two_sided"}:
        operators = az_families.symmetry_operators("az_bdi")
        metric = np.asarray(operators["S"])
        residuals.append(float(np.linalg.norm(matrix.imag)))
        residuals.append(
            _metric_cone_residual(
                matrix,
                metric=metric,
                allow_either_direction=case == "azcone_bdi_two_sided",
            )
        )
    elif case == "azcone_aii_kramers":
        time_reversal = np.asarray(
            az_families.symmetry_operators("az_aii")["T"]
        )
        residuals.append(
            _antiunitary_residual(
                matrix,
                operator=time_reversal,
                sign=1,
            )
        )
    elif case.startswith("azcone_diii"):
        operators = az_families.symmetry_operators("az_diii")
        residuals.append(
            _metric_cone_residual(
                matrix,
                metric=np.asarray(operators["S"]),
            )
        )
        if case == "azcone_diii_phs":
            residuals.append(
                _antiunitary_residual(
                    matrix,
                    operator=np.asarray(operators["C"]),
                    sign=-1,
                )
            )
    elif case.startswith("azcone_cii"):
        operators = az_families.symmetry_operators("az_cii")
        residuals.append(
            _metric_cone_residual(
                matrix,
                metric=np.asarray(operators["S"]),
            )
        )
        if case == "azcone_cii_kramers":
            residuals.append(
                _antiunitary_residual(
                    matrix,
                    operator=np.asarray(operators["T"]),
                    sign=1,
                )
            )
    else:
        raise AssertionError("unreachable AZ cone case")

    return max(residuals, default=0.0) / scale
