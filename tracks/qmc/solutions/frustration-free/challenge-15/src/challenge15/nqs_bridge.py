"""Bridge projected NQS parameters to canonical determinant coefficients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from scipy import sparse

from challenge15.fermions import DeterminantBasis
from challenge15.oracle import (
    OracleResult,
    nqs_sector_coefficients,
)
from challenge15.spec import SphereSpec


@dataclass(frozen=True, slots=True)
class DeterminantState:
    basis: DeterminantBasis
    coefficients: np.ndarray

    def __post_init__(self) -> None:
        if not isinstance(self.basis, DeterminantBasis):
            raise TypeError("basis must be a DeterminantBasis")
        coefficients = np.asarray(self.coefficients, dtype=np.complex128)
        if coefficients.shape != (self.basis.dimension,):
            raise ValueError("coefficients must have one entry per basis state")
        if not np.all(np.isfinite(coefficients)):
            raise ValueError("determinant coefficients must be finite")
        norm = float(np.linalg.norm(coefficients))
        if not np.isfinite(norm) or norm == 0.0:
            raise ValueError("determinant coefficients must have nonzero norm")
        normalized = np.ascontiguousarray(coefficients / norm, dtype=np.complex128)
        sealed = np.frombuffer(
            normalized.tobytes(), dtype=np.complex128
        ).reshape(normalized.shape)
        object.__setattr__(self, "coefficients", sealed)


def mixed_transition_amplitude(
    final_coefficients: np.ndarray,
    operator: sparse.spmatrix,
    initial: DeterminantState,
) -> complex:
    """Contract an exact determinant final with a determinant initial state."""

    if not isinstance(initial, DeterminantState):
        raise TypeError("initial must be a DeterminantState")
    coefficients = initial.coefficients
    if coefficients.shape != (initial.basis.dimension,):
        raise ValueError("initial coefficients must match their determinant basis")
    if not np.all(np.isfinite(coefficients)):
        raise ValueError("initial coefficients must be finite")
    if coefficients.flags.writeable:
        raise ValueError("initial coefficients must be immutable")
    norm = float(np.linalg.norm(coefficients))
    if not np.isfinite(norm) or not np.isclose(
        norm, 1.0, rtol=0.0, atol=1e-12
    ):
        raise ValueError("initial coefficients must be unit normalized")

    if not sparse.issparse(operator):
        raise TypeError("operator must be a scipy sparse matrix")
    if operator.shape[1] != initial.basis.dimension:
        raise ValueError("operator domain must match the initial determinant basis")
    if not np.all(np.isfinite(operator.data)):
        raise ValueError("operator entries must be finite")

    final = np.asarray(final_coefficients, dtype=np.complex128)
    if final.shape != (operator.shape[0],):
        raise ValueError("final coefficients must match the operator codomain")
    if not np.all(np.isfinite(final)):
        raise ValueError("final coefficients must be finite")

    amplitude = complex(np.vdot(final, operator @ coefficients))
    if not np.isfinite(amplitude):
        raise ArithmeticError("mixed transition amplitude must remain finite")
    return amplitude


def nqs_determinant_state(
    spec: SphereSpec,
    model_parameters: Mapping[str, Any],
    oracle: OracleResult,
    *,
    target_l: Literal[0, 2],
    determinant_block: int = 256,
    carrier_block: int | None = None,
) -> DeterminantState:
    """Return the normalized M=0 determinant state for one NQS sector."""

    if (
        not isinstance(target_l, int)
        or isinstance(target_l, bool)
        or target_l not in (0, 2)
    ):
        raise ValueError("target_l must be 0 or 2")
    basis = DeterminantBasis.with_two_m(spec, 0)
    sector_coefficients = nqs_sector_coefficients(
        spec,
        model_parameters,
        oracle,
        target_l=target_l,
        determinant_block=determinant_block,
        carrier_block=carrier_block,
    )
    determinant_coefficients = (
        oracle.exact_sector(target_l).isometry @ sector_coefficients
    )
    return DeterminantState(
        basis=basis,
        coefficients=determinant_coefficients,
    )
