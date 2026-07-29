"""Dense-spin Jordan-Wigner oracle for the self-dual transfer gates.

This is intentionally an exponential small-system reference, not the
production Gaussian implementation.  It verifies the Majorana bilinears and
the parity sign of the periodic boundary bond before covariance-matrix code is
introduced.

Convention:

    gamma[2j]   = (prod_{k<j} X_k) Z_j
    gamma[2j+1] = (prod_{k<j} X_k) Y_j
    X_j         = i gamma[2j] gamma[2j+1]
    Z_j Z_{j+1} = i gamma[2j+1] gamma[2j+2]

For the periodic bond,

    Z_{L-1} Z_0 = -P i gamma[2L-1] gamma[0],

where ``P=prod_j X_j``.  A quadratic boundary gate therefore requires a fixed
parity sector.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

ComplexMatrix = NDArray[np.complex128]

IDENTITY_2 = np.eye(2, dtype=np.complex128)
PAULI_X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
PAULI_Y = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
PAULI_Z = np.array([[1, 0], [0, -1]], dtype=np.complex128)


def _kron_all(factors: list[ComplexMatrix]) -> ComplexMatrix:
    result = np.array([[1.0]], dtype=np.complex128)
    for factor in factors:
        result = np.kron(result, factor)
    return result


def _site_operator(n_sites: int, site: int, operator: ComplexMatrix) -> ComplexMatrix:
    if not 0 <= site < n_sites:
        raise ValueError(f"site {site} outside 0..{n_sites - 1}")
    factors = [IDENTITY_2] * n_sites
    factors[site] = operator
    return _kron_all(factors)


def majorana_operators(n_sites: int) -> tuple[ComplexMatrix, ...]:
    if n_sites < 1:
        raise ValueError("n_sites must be positive")
    operators: list[ComplexMatrix] = []
    for site in range(n_sites):
        prefix = [PAULI_X if index < site else IDENTITY_2 for index in range(n_sites)]
        even = prefix.copy()
        odd = prefix.copy()
        even[site] = PAULI_Z
        odd[site] = PAULI_Y
        operators.extend((_kron_all(even), _kron_all(odd)))
    return tuple(operators)


def clifford_residual(gammas: tuple[ComplexMatrix, ...]) -> float:
    """Maximum norm of ``{gamma_a,gamma_b} - 2 delta_ab``."""

    if not gammas:
        raise ValueError("gammas must not be empty")
    dimension = gammas[0].shape[0]
    identity = np.eye(dimension, dtype=np.complex128)
    residual = 0.0
    for left_index, left in enumerate(gammas):
        for right_index, right in enumerate(gammas):
            expected = 2.0 * identity if left_index == right_index else 0.0
            residual = max(
                residual,
                float(np.linalg.norm(left @ right + right @ left - expected)),
            )
    return residual


def parity_operator(n_sites: int) -> ComplexMatrix:
    return _kron_all([PAULI_X] * n_sites)


def project_parity(n_sites: int, parity: int) -> ComplexMatrix:
    if parity not in (-1, 1):
        raise ValueError("parity must be -1 or +1")
    identity = np.eye(1 << n_sites, dtype=np.complex128)
    return 0.5 * (identity + parity * parity_operator(n_sites))


def _exp_involution(coefficient: float, involution: ComplexMatrix) -> ComplexMatrix:
    dimension = involution.shape[0]
    return (
        np.cosh(coefficient) * np.eye(dimension, dtype=np.complex128)
        + np.sinh(coefficient) * involution
    )


def spin_mx_layer(coefficients: NDArray[np.floating]) -> ComplexMatrix:
    values = np.asarray(coefficients, dtype=np.float64)
    if values.ndim != 1 or values.size < 1:
        raise ValueError("coefficients must be a non-empty rank-1 array")
    n_sites = int(values.size)
    result = np.eye(1 << n_sites, dtype=np.complex128)
    for site, coefficient in enumerate(values):
        result = result @ _exp_involution(
            float(coefficient), _site_operator(n_sites, site, PAULI_X)
        )
    return result


def majorana_mx_layer(coefficients: NDArray[np.floating]) -> ComplexMatrix:
    values = np.asarray(coefficients, dtype=np.float64)
    if values.ndim != 1 or values.size < 1:
        raise ValueError("coefficients must be a non-empty rank-1 array")
    n_sites = int(values.size)
    gammas = majorana_operators(n_sites)
    result = np.eye(1 << n_sites, dtype=np.complex128)
    for site, coefficient in enumerate(values):
        bilinear = 1j * gammas[2 * site] @ gammas[2 * site + 1]
        result = result @ _exp_involution(float(coefficient), bilinear)
    return result


def spin_mz_layer(
    coefficients: NDArray[np.floating], *, periodic: bool
) -> ComplexMatrix:
    values = np.asarray(coefficients, dtype=np.float64)
    if values.ndim != 1 or values.size < 1:
        raise ValueError("coefficients must be a non-empty rank-1 array")
    n_sites = int(values.size if periodic else values.size + 1)
    if n_sites < 2:
        raise ValueError("MZ layer requires at least two sites")
    result = np.eye(1 << n_sites, dtype=np.complex128)
    for bond, coefficient in enumerate(values):
        left = bond
        right = (bond + 1) % n_sites
        zz = _site_operator(n_sites, left, PAULI_Z) @ _site_operator(
            n_sites, right, PAULI_Z
        )
        result = result @ _exp_involution(float(coefficient), zz)
    return result


def majorana_mz_layer(
    coefficients: NDArray[np.floating],
    *,
    periodic: bool,
    parity_sector: int | None = None,
) -> ComplexMatrix:
    values = np.asarray(coefficients, dtype=np.float64)
    if values.ndim != 1 or values.size < 1:
        raise ValueError("coefficients must be a non-empty rank-1 array")
    n_sites = int(values.size if periodic else values.size + 1)
    if n_sites < 2:
        raise ValueError("MZ layer requires at least two sites")
    if periodic and parity_sector not in (-1, 1):
        raise ValueError("periodic MZ layer requires parity_sector=-1 or +1")

    gammas = majorana_operators(n_sites)
    result = np.eye(1 << n_sites, dtype=np.complex128)
    for bond, coefficient in enumerate(values):
        if bond < n_sites - 1:
            bilinear = 1j * gammas[2 * bond + 1] @ gammas[2 * (bond + 1)]
        else:
            bilinear = (
                -int(parity_sector)
                * 1j
                * gammas[2 * n_sites - 1]
                @ gammas[0]
            )
        result = result @ _exp_involution(float(coefficient), bilinear)
    return result
