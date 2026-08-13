"""Hermitian-slice representatives of the Altland--Zirnbauer tenfold way."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .families import FamilyCase


@dataclass(frozen=True)
class _AZSpec:
    label: str
    trs_square: int | None
    phs_square: int | None
    time_reversal: np.ndarray | None
    particle_hole: np.ndarray | None
    chiral: np.ndarray | None


_I2 = np.eye(2, dtype=complex)
_X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
_Z = np.diag([1.0, -1.0]).astype(complex)
_J = np.array([[0.0, 1.0], [-1.0, 0.0]], dtype=complex)
_I4 = np.eye(4, dtype=complex)

_T_MINUS = np.kron(_I2, _J)
_C_MINUS_LEFT = np.kron(_J, _I2)
_C_MINUS_RIGHT = np.kron(_I2, _J)
_SUBLATTICE = np.kron(_Z, _I2)
_PARTICLE_HOLE_PLUS = np.kron(_X, _I2)


def _derived_chiral(time_reversal: np.ndarray, particle_hole: np.ndarray) -> np.ndarray:
    operator = time_reversal @ particle_hole.conj()
    if not np.allclose(operator, operator.conj().T, atol=1e-14):
        operator = 1j * operator
    return operator


_SPECS = {
    "az_a": _AZSpec("A", None, None, None, None, None),
    "az_ai": _AZSpec("AI", 1, None, _I4, None, None),
    "az_bdi": _AZSpec("BDI", 1, 1, _I4, _SUBLATTICE, _SUBLATTICE),
    "az_d": _AZSpec("D", None, 1, None, _I4, None),
    "az_diii": _AZSpec(
        "DIII",
        -1,
        1,
        _T_MINUS,
        _PARTICLE_HOLE_PLUS,
        _derived_chiral(_T_MINUS, _PARTICLE_HOLE_PLUS),
    ),
    "az_aii": _AZSpec("AII", -1, None, _T_MINUS, None, None),
    "az_cii": _AZSpec(
        "CII",
        -1,
        -1,
        _C_MINUS_LEFT,
        _C_MINUS_RIGHT,
        _derived_chiral(_C_MINUS_LEFT, _C_MINUS_RIGHT),
    ),
    "az_c": _AZSpec("C", None, -1, None, _C_MINUS_LEFT, None),
    "az_ci": _AZSpec(
        "CI",
        1,
        -1,
        _I4,
        _C_MINUS_LEFT,
        _derived_chiral(_I4, _C_MINUS_LEFT),
    ),
    "az_aiii": _AZSpec("AIII", None, None, None, None, _SUBLATTICE),
}


def available_cases() -> dict[str, FamilyCase]:
    return {
        case: FamilyCase(
            family=f"az_{spec.label.lower()}_hermitian",
            shape=(4, 4),
            prior_status="az_reconnaissance",
        )
        for case, spec in _SPECS.items()
    }


def symmetry_operators(case: str) -> dict[str, object]:
    spec = _SPECS[case]
    return {
        "label": spec.label,
        "T": None if spec.time_reversal is None else spec.time_reversal.copy(),
        "C": None if spec.particle_hole is None else spec.particle_hole.copy(),
        "S": None if spec.chiral is None else spec.chiral.copy(),
        "T_square": spec.trs_square,
        "C_square": spec.phs_square,
        "has_chiral": spec.chiral is not None,
    }


def _project_antiunitary(
    matrix: np.ndarray,
    operator: np.ndarray,
    *,
    sign: int,
) -> np.ndarray:
    transformed = operator @ matrix.conj() @ operator.conj().T
    return 0.5 * (matrix + sign * transformed)


def random_generator(
    case: str,
    rng: np.random.Generator,
    *,
    scale: float,
) -> np.ndarray:
    spec = _SPECS[case]
    size = 4
    raw = (
        rng.standard_normal((size, size))
        + 1j * rng.standard_normal((size, size))
    ) / np.sqrt(2.0 * size)
    generator = 0.5 * (raw + raw.conj().T)

    if spec.time_reversal is not None:
        generator = _project_antiunitary(
            generator,
            spec.time_reversal,
            sign=1,
        )
    if spec.particle_hole is not None:
        generator = _project_antiunitary(
            generator,
            spec.particle_hole,
            sign=-1,
        )
    if (
        spec.chiral is not None
        and spec.time_reversal is None
        and spec.particle_hole is None
    ):
        generator = 0.5 * (
            generator - spec.chiral @ generator @ spec.chiral.conj().T
        )

    generator = 0.5 * (generator + generator.conj().T)
    norm = float(np.linalg.norm(generator))
    if norm == 0.0:
        raise RuntimeError(f"AZ projection produced a zero generator for {case}")
    return generator * (scale * np.sqrt(size) / norm)


def structure_residual(case: str, generator: np.ndarray) -> float:
    spec = _SPECS[case]
    matrix = np.asarray(generator)
    scale = max(1.0, float(np.linalg.norm(matrix)))
    residuals = [float(np.linalg.norm(matrix - matrix.conj().T))]

    if spec.time_reversal is not None:
        transformed = (
            spec.time_reversal @ matrix.conj() @ spec.time_reversal.conj().T
        )
        residuals.append(float(np.linalg.norm(transformed - matrix)))
    if spec.particle_hole is not None:
        transformed = (
            spec.particle_hole @ matrix.conj() @ spec.particle_hole.conj().T
        )
        residuals.append(float(np.linalg.norm(transformed + matrix)))
    if spec.chiral is not None:
        transformed = spec.chiral @ matrix @ spec.chiral.conj().T
        residuals.append(float(np.linalg.norm(transformed + matrix)))

    return max(residuals) / scale
