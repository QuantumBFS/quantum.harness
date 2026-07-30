"""Pair-Casimir form of fixed-LLL projected-density scalars.

This module works only in the one- and two-particle tensor-product spaces.
It never constructs an N-electron basis.  The ordered cross contraction for
one unordered particle pair is fitted as a degree-ell polynomial of
``J_i dot J_j`` using a scaled power basis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from numbers import Integral

import numpy as np

from .projected_density import (
    MAX_PROJECTED_DENSITY_TWO_Q,
    projected_density_tensor,
)


_APPROVED_RANKS = (2, 3, 4)
_MAX_RECONSTRUCTION_RESIDUAL = 1.0e-10


def _checked_integer(name: str, value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    return int(value)


def _angular_momentum_matrices(
    two_q: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dimension = two_q + 1
    j = 0.5 * two_q
    jz = np.diag(np.arange(dimension, dtype=float) - j).astype(np.complex128)
    jplus = np.zeros((dimension, dimension), dtype=np.complex128)
    for orbital in range(two_q):
        jplus[orbital + 1, orbital] = math.sqrt(
            (two_q - orbital) * (orbital + 1)
        )
    return jz, jplus, jplus.T.conj()


@dataclass(frozen=True)
class PairCasimirDecomposition:
    """One-body constant and scaled pair-Casimir polynomial."""

    two_q: int
    ell: int
    self_scalar: complex
    scale: float
    coefficients: np.ndarray
    reconstruction_residual: float

    @property
    def degree(self) -> int:
        return len(self.coefficients) - 1

    def evaluate_matrix(self, pair_dot: np.ndarray) -> np.ndarray:
        checked = np.asarray(pair_dot, dtype=np.complex128)
        if checked.ndim != 2 or checked.shape[0] != checked.shape[1]:
            raise ValueError("pair_dot must be a square matrix")
        if not np.all(np.isfinite(checked)):
            raise ValueError("pair_dot must be finite")
        scaled = checked / self.scale
        identity = np.eye(len(scaled), dtype=np.complex128)
        result = np.zeros_like(scaled)
        for coefficient in self.coefficients[::-1]:
            result = result @ scaled + coefficient * identity
        return result

    def evaluate_scalar(self, pair_dot: float) -> complex:
        checked = complex(pair_dot)
        if not np.isfinite(checked.real) or not np.isfinite(checked.imag):
            raise ValueError("pair_dot must be finite")
        scaled = checked / self.scale
        result = 0.0j
        for coefficient in self.coefficients[::-1]:
            result = result * scaled + coefficient
        return complex(result)


def pair_casimir_decomposition(
    *, two_q: int, ell: int
) -> PairCasimirDecomposition:
    """Return the approved rank-2/3/4 pair-Casimir decomposition."""

    checked_two_q = _checked_integer("two_q", two_q)
    checked_ell = _checked_integer("ell", ell)
    if checked_two_q <= 0 or checked_two_q > MAX_PROJECTED_DENSITY_TWO_Q:
        raise ValueError(
            f"invalid pair-Casimir flux; two_q must be in "
            f"1..{MAX_PROJECTED_DENSITY_TWO_Q}"
        )
    if checked_ell not in _APPROVED_RANKS or checked_ell > checked_two_q:
        raise ValueError("invalid pair-Casimir rank; approved ranks are 2, 3, 4")
    return _pair_casimir_decomposition(checked_two_q, checked_ell)


@lru_cache(maxsize=None)
def _pair_casimir_decomposition(
    two_q: int, ell: int
) -> PairCasimirDecomposition:
    dimension = two_q + 1
    jz, jplus, jminus = _angular_momentum_matrices(two_q)
    identity = np.eye(dimension, dtype=np.complex128)
    pair_dimension = dimension * dimension
    pair_identity = np.eye(pair_dimension, dtype=np.complex128)
    pair_dot = (
        np.kron(jz, jz)
        + 0.5 * np.kron(jplus, jminus)
        + 0.5 * np.kron(jminus, jplus)
    )
    tensors = {
        m: projected_density_tensor(two_q=two_q, ell=ell, m=m)
        for m in range(-ell, ell + 1)
    }
    self_matrix = sum(
        ((-1) ** m) * tensors[m] @ tensors[-m]
        for m in range(-ell, ell + 1)
    )
    self_scalar = complex(np.trace(self_matrix) / dimension)
    self_residual = np.linalg.norm(self_matrix - self_scalar * identity) / max(
        np.linalg.norm(self_matrix), np.finfo(float).tiny
    )
    if not np.isfinite(self_residual) or self_residual > _MAX_RECONSTRUCTION_RESIDUAL:
        raise ValueError("projected-density self contraction is not scalar")

    cross = sum(
        ((-1) ** m)
        * (
            np.kron(tensors[m], tensors[-m])
            + np.kron(tensors[-m], tensors[m])
        )
        for m in range(-ell, ell + 1)
    )
    scale = float(np.max(np.abs(np.linalg.eigvalsh(pair_dot))))
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("pair-Casimir scale must be finite and positive")
    scaled = pair_dot / scale
    powers = [pair_identity]
    for _ in range(ell):
        powers.append(powers[-1] @ scaled)
    design = np.column_stack([power.reshape(-1) for power in powers])
    coefficients = np.asarray(
        np.linalg.lstsq(design, cross.reshape(-1), rcond=None)[0],
        dtype=np.complex128,
    )
    reconstructed = sum(
        coefficient * power
        for coefficient, power in zip(coefficients, powers, strict=True)
    )
    cross_norm = max(np.linalg.norm(cross), np.finfo(float).tiny)
    residual = float(np.linalg.norm(reconstructed - cross) / cross_norm)
    if not np.all(np.isfinite(coefficients)) or not math.isfinite(residual):
        raise ValueError("pair-Casimir reconstruction is non-finite")
    if residual > _MAX_RECONSTRUCTION_RESIDUAL:
        raise ValueError(
            f"pair-Casimir reconstruction failed: residual={residual:.6e}"
        )
    coefficients.setflags(write=False)
    return PairCasimirDecomposition(
        two_q=two_q,
        ell=ell,
        self_scalar=self_scalar,
        scale=scale,
        coefficients=coefficients,
        reconstruction_residual=residual,
    )


__all__ = ["PairCasimirDecomposition", "pair_casimir_decomposition"]
