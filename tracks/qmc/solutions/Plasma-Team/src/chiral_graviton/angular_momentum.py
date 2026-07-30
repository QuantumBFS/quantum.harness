"""Many-body angular-momentum operators in a fixed LLL shell."""

from __future__ import annotations

import numpy as np
from scipy import linalg, sparse

from .basis import FockBasis, apply_one_body


def angular_momentum_raising(source: FockBasis, target: FockBasis) -> sparse.csr_matrix:
    """Return L_+ from ``source`` to the sector with Lz increased by one."""

    if source.system != target.system or target.two_lz != source.two_lz + 2:
        raise ValueError("target must describe the same system at two_lz+2")

    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    target_index = target.index
    two_q = source.system.two_q
    two_m_values = source.system.two_m_values

    for col, state in enumerate(source.states):
        for orbital in source.occupied(state):
            if orbital + 1 >= source.system.n_orbitals:
                continue
            applied = apply_one_body(state, orbital + 1, orbital)
            if applied is None:
                continue
            new_state, sign = applied
            row = target_index.get(new_state)
            if row is None:
                continue
            two_m = two_m_values[orbital]
            coefficient = 0.5 * np.sqrt((two_q - two_m) * (two_q + two_m + 2))
            rows.append(row)
            cols.append(col)
            data.append(sign * coefficient)

    return sparse.csr_matrix((data, (rows, cols)), shape=(target.dimension, source.dimension))


def angular_momentum_lowering(source: FockBasis, target: FockBasis) -> sparse.csr_matrix:
    """Return L_- from ``source`` to the sector with Lz decreased by one."""

    if source.system != target.system or target.two_lz != source.two_lz - 2:
        raise ValueError("target must describe the same system at two_lz-2")
    return angular_momentum_raising(target, source).conjugate().transpose().tocsr()


def l2_operator(basis: FockBasis) -> sparse.csr_matrix:
    """Return L^2 = L_-L_+ + Lz(Lz+1) in one fixed-Lz sector."""

    target = FockBasis(basis.system, basis.two_lz + 2)
    raising = angular_momentum_raising(basis, target)
    lz = basis.two_lz / 2.0
    identity = sparse.identity(basis.dimension, dtype=np.float64, format="csr")
    return (raising.transpose() @ raising + lz * (lz + 1.0) * identity).tocsr()


def highest_weight_basis(basis: FockBasis, *, tolerance: float = 1e-11) -> np.ndarray:
    """Orthonormal columns spanning ``ker(L_+)`` in a sector with Lz>=0.

    A vector in the `M=L` sector annihilated by L_+ belongs to total angular
    momentum L exactly. Consequently, call this with ``two_lz=2*L``.
    """

    if basis.two_lz < 0:
        raise ValueError("highest-weight construction requires non-negative Lz")
    target = FockBasis(basis.system, basis.two_lz + 2)
    raising = angular_momentum_raising(basis, target).toarray()
    if raising.shape[0] == 0:
        return np.eye(basis.dimension, dtype=np.float64)
    kernel = linalg.null_space(raising, rcond=tolerance)
    if kernel.shape[1] == 0:
        raise ValueError("CG002: requested total-L sector is empty")
    return np.asarray(kernel, dtype=np.float64)


def assign_total_l(l2_expectation: float, *, tolerance: float = 1e-7) -> int:
    """Map an L^2 expectation to integer L when it is sufficiently close."""

    if l2_expectation < -tolerance:
        raise ValueError("negative L^2 expectation")
    estimate = int(round((-1.0 + np.sqrt(1.0 + 4.0 * max(l2_expectation, 0.0))) / 2.0))
    if abs(l2_expectation - estimate * (estimate + 1)) > tolerance:
        raise ValueError(f"L^2={l2_expectation:.12g} is not a clean integer-L eigenvalue")
    return estimate
