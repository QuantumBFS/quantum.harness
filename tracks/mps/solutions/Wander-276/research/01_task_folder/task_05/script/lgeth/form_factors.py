"""Exact and empirical form factors for degenerate quantum geometry."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import eval_jacobi, gammaln, roots_jacobi

from .jacobi import jacobi_parameters


@dataclass(frozen=True)
class FormFactorParts:
    """Raw, disconnected, and connected form-factor components."""

    raw: np.ndarray
    disconnected: np.ndarray
    connected: np.ndarray
    normalization: int


@dataclass(frozen=True)
class JacobiFormFactor:
    """Finite-dimensional connected Jacobi form factor."""

    times: np.ndarray
    connected_continuous: np.ndarray
    connected_full: np.ndarray
    plateau_full: float
    unfolded_nodes: np.ndarray
    quadrature_order: int
    interior_dimension: int
    atom_count_each: int
    rank: int
    channels: int
    exponent: int
    mass_error: float
    orthogonality_error: float


def _validated_spectra_times(
    spectra: np.ndarray,
    times: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(spectra, dtype=float)
    grid = np.asarray(times, dtype=float)
    if (
        values.ndim != 2
        or values.shape[0] < 1
        or values.shape[1] < 1
        or np.any(~np.isfinite(values))
    ):
        raise ValueError("spectra must be a finite nonempty two-dimensional array")
    if grid.ndim != 1 or grid.size < 1 or np.any(~np.isfinite(grid)):
        raise ValueError("times must be a finite nonempty one-dimensional array")
    return values, grid


def form_factor_parts(
    spectra: np.ndarray,
    times: np.ndarray,
    phase_scale: float = 2.0 * np.pi,
) -> FormFactorParts:
    """Return one consistently normalized form-factor decomposition."""

    values, grid = _validated_spectra_times(spectra, times)
    scale = float(phase_scale)
    if not np.isfinite(scale):
        raise ValueError("phase_scale must be finite")
    levels = int(values.shape[1])
    partition = np.empty((values.shape[0], grid.size), dtype=np.complex128)
    for start in range(0, values.shape[0], 512):
        stop = min(start + 512, values.shape[0])
        phases = np.exp(
            -1j
            * scale
            * values[start:stop, :, None]
            * grid[None, None, :]
        )
        partition[start:stop] = np.sum(phases, axis=1)
    raw = np.mean(np.abs(partition) ** 2, axis=0) / levels
    disconnected = np.abs(np.mean(partition, axis=0)) ** 2 / levels
    connected = raw - disconnected
    connected[np.abs(connected) < 5e-15] = 0.0
    return FormFactorParts(
        raw=raw,
        disconnected=disconnected,
        connected=connected,
        normalization=levels,
    )


def degenerate_energy_form_factor(
    dimension: int,
    times: np.ndarray,
) -> FormFactorParts:
    """Return the exact centered SFF of a rank-``dimension`` flat band."""

    rank = int(dimension)
    if rank < 1:
        raise ValueError("dimension must be positive")
    spectra = np.zeros((2, rank), dtype=float)
    return form_factor_parts(spectra, times, phase_scale=1.0)


def _log_jacobi_norm(order: int, exponent: int) -> float:
    degree = int(order)
    alpha = int(exponent)
    return float(
        (2 * alpha + 1) * np.log(2.0)
        - np.log(2 * degree + 2 * alpha + 1)
        + 2 * gammaln(degree + alpha + 1)
        - gammaln(degree + 1)
        - gammaln(degree + 2 * alpha + 1)
    )


def _weighted_jacobi_projector(
    interior_dimension: int,
    exponent: int,
    quadrature_order: int,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    k = int(interior_dimension)
    alpha = int(exponent)
    order = int(quadrature_order)
    if k < 1:
        raise ValueError("interior_dimension must be positive")
    if alpha < 0:
        raise ValueError("exponent must be nonnegative")
    if order < max(32, k):
        raise ValueError("quadrature_order must be at least max(32,k)")
    nodes, weights = roots_jacobi(order, alpha, alpha)
    basis = np.empty((order, k), dtype=float)
    square_root_weights = np.sqrt(weights)
    for degree in range(k):
        polynomial = eval_jacobi(degree, alpha, alpha, nodes)
        basis[:, degree] = (
            square_root_weights
            * polynomial
            * np.exp(-0.5 * _log_jacobi_norm(degree, alpha))
        )
    if np.any(~np.isfinite(basis)):
        raise RuntimeError("nonfinite orthonormal Jacobi basis")
    gram = basis.T @ basis
    orthogonality_error = float(
        np.max(np.abs(gram - np.eye(k, dtype=float)))
    )
    if orthogonality_error > 2e-8:
        raise RuntimeError(
            "Gauss--Jacobi basis failed orthogonality: "
            f"{orthogonality_error:.3e}"
        )
    projector = basis @ basis.T
    density_mass = np.diag(projector)
    mass_error = float(abs(np.sum(density_mass) - k))
    if mass_error > 2e-8:
        raise RuntimeError(
            f"Jacobi quadrature mass failed: {mass_error:.3e}"
        )
    unfolded_nodes = np.cumsum(density_mass) - 0.5 * density_mass
    return projector, unfolded_nodes, mass_error, orthogonality_error


def finite_jacobi_form_factor(
    r: int,
    M: int,
    times: np.ndarray,
    quadrature_order: int = 512,
) -> JacobiFormFactor:
    """Return the exact finite-rank unfolded complex-Jacobi connected SFF."""

    parameters = jacobi_parameters(r, M)
    grid = np.asarray(times, dtype=float)
    if (
        grid.ndim != 1
        or grid.size < 1
        or np.any(~np.isfinite(grid))
        or np.any(grid < 0.0)
    ):
        raise ValueError("times must be a finite nonnegative one-dimensional grid")
    k = int(parameters.interior_dimension)
    if k < 1:
        raise ValueError("the continuous Jacobi sector is empty")
    projector, unfolded, mass_error, orthogonality_error = (
        _weighted_jacobi_projector(
            k,
            parameters.exponent,
            quadrature_order,
        )
    )
    cluster_kernel = np.abs(projector) ** 2
    continuous = np.empty(grid.size, dtype=float)
    for index, time in enumerate(grid):
        phase = np.exp(-2j * np.pi * float(time) * unfolded)
        cluster = float(
            np.real(np.vdot(phase, cluster_kernel @ phase))
        )
        value = 1.0 - cluster / k
        if -5e-11 < value < 0.0:
            value = 0.0
        continuous[index] = value
    atom_count = int(parameters.plus_atoms)
    full = (k / parameters.r) * continuous
    return JacobiFormFactor(
        times=grid,
        connected_continuous=continuous,
        connected_full=full,
        plateau_full=float(k / parameters.r),
        unfolded_nodes=unfolded,
        quadrature_order=int(quadrature_order),
        interior_dimension=k,
        atom_count_each=atom_count,
        rank=int(parameters.r),
        channels=int(parameters.M),
        exponent=int(parameters.exponent),
        mass_error=mass_error,
        orthogonality_error=orthogonality_error,
    )


def atom_raw_decomposition(
    interior_spectra: np.ndarray,
    minus_atoms: int,
    plus_atoms: int,
    times: np.ndarray,
    phase_scale: float = 2.0 * np.pi,
) -> dict[str, np.ndarray]:
    """Decompose a full raw SFF into exact atom and continuum terms."""

    interior, grid = _validated_spectra_times(interior_spectra, times)
    negative = int(minus_atoms)
    positive = int(plus_atoms)
    if negative < 0 or positive < 0:
        raise ValueError("atom counts must be nonnegative")
    total = int(interior.shape[1] + negative + positive)
    if total < 1:
        raise ValueError("the full spectrum must be nonempty")
    scale = float(phase_scale)
    continuum_partition = np.sum(
        np.exp(
            -1j
            * scale
            * interior[:, :, None]
            * grid[None, None, :]
        ),
        axis=1,
    )
    atom_partition = (
        negative * np.exp(1j * scale * grid)
        + positive * np.exp(-1j * scale * grid)
    )
    atom_atom = np.abs(atom_partition) ** 2 / total
    atom_continuum = (
        2.0
        * np.real(
            atom_partition.conj()
            * np.mean(continuum_partition, axis=0)
        )
        / total
    )
    continuum_continuum = (
        np.mean(np.abs(continuum_partition) ** 2, axis=0) / total
    )
    full = atom_atom + atom_continuum + continuum_continuum
    return {
        "full": full,
        "atom_atom": atom_atom,
        "atom_continuum": atom_continuum,
        "continuum_continuum": continuum_continuum,
        "normalization": np.asarray(total, dtype=int),
    }
