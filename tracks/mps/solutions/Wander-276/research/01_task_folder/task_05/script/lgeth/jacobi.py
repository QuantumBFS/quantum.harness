"""Metric-normalized curvature and finite Jacobi compression theory."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import linalg
from scipy.special import eval_jacobi, gammaln

from .channels import _validated_channel_pair


@dataclass(frozen=True)
class NormalizedCurvature:
    """Curvature whitened by the channel Gram matrix on its support."""

    rank: int
    kernel_dimension: int
    cutoff: float
    active_basis: np.ndarray
    gamma_eigenvalues: np.ndarray
    Y: np.ndarray
    J: np.ndarray
    omega: np.ndarray


@dataclass(frozen=True)
class JacobiParameters:
    """Finite-dimensional parameters of a Haar signature compression."""

    r: int
    M: int
    interior_dimension: int
    exponent: int
    plus_atoms: int
    minus_atoms: int


def canonical_channel_form(M: int) -> np.ndarray:
    """Return the Hermitian channel form for ``[X_v,X_w]``."""

    channels = int(M)
    if channels < 1:
        raise ValueError("M must be positive")
    identity = np.eye(channels, dtype=complex)
    zero = np.zeros_like(identity)
    return np.block(
        [
            [zero, 1j * identity],
            [-1j * identity, zero],
        ]
    )


def normalized_curvature(
    channel_v: np.ndarray,
    channel_w: np.ndarray,
    rtol: float = 1e-12,
    atol: float = 0.0,
) -> NormalizedCurvature:
    """Return ``Omega=Gamma^{-1/2} F Gamma^{-1/2}=Y J Y^dagger``."""

    x, y = _validated_channel_pair(channel_v, channel_w)
    if rtol < 0.0 or atol < 0.0:
        raise ValueError("rank tolerances must be nonnegative")
    doubled = np.concatenate([x, y], axis=1)
    gamma = doubled @ doubled.conj().T
    eigenvalues, eigenvectors = np.linalg.eigh(
        0.5 * (gamma + gamma.conj().T)
    )
    scale = max(float(eigenvalues[-1]), 0.0)
    cutoff = max(float(atol), float(rtol) * scale)
    keep = eigenvalues > cutoff
    active_values = eigenvalues[keep]
    active_basis = eigenvectors[:, keep]
    rank = int(active_values.size)
    if rank == 0:
        raise ValueError("the channel Gram matrix has empty support")
    projected = active_basis.conj().T @ doubled
    Y = projected / np.sqrt(active_values)[:, None]
    J = canonical_channel_form(x.shape[1])
    omega = Y @ J @ Y.conj().T
    omega = 0.5 * (omega + omega.conj().T)
    return NormalizedCurvature(
        rank=rank,
        kernel_dimension=x.shape[0] - rank,
        cutoff=cutoff,
        active_basis=active_basis,
        gamma_eigenvalues=active_values,
        Y=Y,
        J=J,
        omega=omega,
    )


def haar_row_isometry(
    r: int,
    doubled_channels: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sample an ``r x doubled_channels`` complex Haar row isometry."""

    rows = int(r)
    columns = int(doubled_channels)
    if rows < 1 or columns < 1 or rows > columns:
        raise ValueError("require 1 <= r <= doubled_channels")
    gaussian = (
        rng.normal(size=(columns, rows))
        + 1j * rng.normal(size=(columns, rows))
    ) / np.sqrt(2.0)
    q, r_factor = np.linalg.qr(gaussian, mode="reduced")
    phases = np.diag(r_factor)
    phases = np.where(
        np.abs(phases) > 0.0,
        phases / np.abs(phases),
        1.0,
    )
    q = q * phases.conj()[None, :]
    return q.conj().T


def jacobi_parameters(r: int, M: int) -> JacobiParameters:
    """Return interior Jacobi size/exponent and forced boundary atoms."""

    rank = int(r)
    channels = int(M)
    if channels < 1 or rank < 1 or rank > 2 * channels:
        raise ValueError("require M>=1 and 1<=r<=2M")
    if rank <= channels:
        interior = rank
        exponent = channels - rank
        atoms = 0
    else:
        interior = 2 * channels - rank
        exponent = rank - channels
        atoms = rank - channels
    return JacobiParameters(
        r=rank,
        M=channels,
        interior_dimension=interior,
        exponent=exponent,
        plus_atoms=atoms,
        minus_atoms=atoms,
    )


def _jacobi_norm(order: int, exponent: int) -> float:
    degree = int(order)
    alpha = int(exponent)
    log_norm = (
        (2 * alpha + 1) * np.log(2.0)
        - np.log(2 * degree + 2 * alpha + 1)
        + 2 * gammaln(degree + alpha + 1)
        - gammaln(degree + 1)
        - gammaln(degree + 2 * alpha + 1)
    )
    return float(np.exp(log_norm))


def jacobi_one_point_density(
    x: np.ndarray,
    r: int,
    M: int,
) -> np.ndarray:
    """Return the normalized interior one-eigenvalue Jacobi density."""

    parameters = jacobi_parameters(r, M)
    values = np.asarray(x, dtype=float)
    density = np.zeros_like(values)
    interior = parameters.interior_dimension
    if interior == 0:
        return density
    mask = np.abs(values) <= 1.0
    points = values[mask]
    weight = np.maximum(1.0 - points * points, 0.0) ** (
        parameters.exponent
    )
    kernel = np.zeros_like(points)
    for order in range(interior):
        polynomial = eval_jacobi(
            order,
            parameters.exponent,
            parameters.exponent,
            points,
        )
        kernel += polynomial * polynomial / _jacobi_norm(
            order,
            parameters.exponent,
        )
    density[mask] = weight * kernel / interior
    density = np.maximum(density, 0.0)
    return density


def sample_jacobi_compression(
    r: int,
    M: int,
    samples: int,
    seed: int,
) -> np.ndarray:
    """Sample spectra of a Haar compression of ``diag(+1_M,-1_M)``."""

    parameters = jacobi_parameters(r, M)
    count = int(samples)
    if count < 1:
        raise ValueError("samples must be positive")
    rng = np.random.default_rng(int(seed))
    signature = np.concatenate(
        [
            np.ones(parameters.M, dtype=float),
            -np.ones(parameters.M, dtype=float),
        ]
    )
    spectra = np.empty((count, parameters.r), dtype=float)
    for sample in range(count):
        rows = haar_row_isometry(
            parameters.r,
            2 * parameters.M,
            rng,
        )
        omega = (rows * signature[None, :]) @ rows.conj().T
        spectra[sample] = np.linalg.eigvalsh(
            0.5 * (omega + omega.conj().T)
        )
    return spectra


def sample_jacobi_interior(
    r: int,
    M: int,
    samples: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample the finite Jacobi law and remove only algebraically forced atoms.

    The Boolean labels are fixed by the exact intersection dimensions, not by
    a floating-point threshold.  The full spectra are ordered, so the first
    ``minus_atoms`` and last ``plus_atoms`` entries carry the labels.
    """

    parameters = jacobi_parameters(r, M)
    full = sample_jacobi_compression(r, M, samples, seed)
    labels = np.zeros_like(full, dtype=bool)
    if parameters.minus_atoms:
        labels[:, : parameters.minus_atoms] = True
        labels[:, -parameters.plus_atoms :] = True
        if not np.allclose(
            full[:, : parameters.minus_atoms], -1.0, atol=2e-10, rtol=0.0
        ):
            raise RuntimeError("negative Jacobi atoms failed the exact label audit")
        if not np.allclose(
            full[:, -parameters.plus_atoms :], 1.0, atol=2e-10, rtol=0.0
        ):
            raise RuntimeError("positive Jacobi atoms failed the exact label audit")
    interior = full[~labels].reshape(
        int(samples), parameters.interior_dimension
    )
    return interior, labels


def sample_jacobi_wishart(
    r: int,
    M: int,
    samples: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample the exact complex Jacobi law via a matrix-beta construction.

    For interior size ``k`` and exponent ``a``, two independent complex
    Wishart matrices with ``k+a=M`` columns generate the eigenvalues on
    ``[0,1]``.  The affine map ``lambda=2t-1`` gives the signature-compression
    spectrum; the intersection-theorem atoms are then inserted explicitly.
    """

    parameters = jacobi_parameters(r, M)
    count = int(samples)
    if count < 1:
        raise ValueError("samples must be positive")
    k = parameters.interior_dimension
    full = np.empty((count, parameters.r), dtype=float)
    interior = np.empty((count, k), dtype=float)
    labels = np.zeros_like(full, dtype=bool)
    rng = np.random.default_rng(int(seed))
    for sample in range(count):
        if k:
            gaussian_x = (
                rng.normal(size=(k, parameters.M))
                + 1j * rng.normal(size=(k, parameters.M))
            ) / np.sqrt(2.0)
            gaussian_y = (
                rng.normal(size=(k, parameters.M))
                + 1j * rng.normal(size=(k, parameters.M))
            ) / np.sqrt(2.0)
            first = gaussian_x @ gaussian_x.conj().T
            second = gaussian_y @ gaussian_y.conj().T
            beta_values = linalg.eigvalsh(
                first,
                first + second,
                check_finite=False,
                driver="gvd",
            )
            interior[sample] = 2.0 * beta_values - 1.0
        if parameters.minus_atoms:
            full[sample, : parameters.minus_atoms] = -1.0
            labels[sample, : parameters.minus_atoms] = True
        start = parameters.minus_atoms
        full[sample, start : start + k] = interior[sample]
        if parameters.plus_atoms:
            full[sample, -parameters.plus_atoms :] = 1.0
            labels[sample, -parameters.plus_atoms :] = True
    return full, interior, labels
