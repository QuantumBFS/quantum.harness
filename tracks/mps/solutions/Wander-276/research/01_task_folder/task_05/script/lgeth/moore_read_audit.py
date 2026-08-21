"""Exact-degeneracy and transported-family audits for Moore--Read parents."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm

from .combinatorics import clustered_zero_mode_count
from .manybody_response import ManyBodyCase
from .matrix_free_response import solve_kernel_frame_factored
from .moore_read_parent import (
    build_continuum_moore_read_parent,
    three_body_annihilation_constraints,
)
from .protected_generator_response import analytic_protected_generator_response
from .protected_parent import (
    projected_local_generator_pair,
    transported_kernel_frame,
)


@dataclass(frozen=True)
class MooreReadAudit:
    """Complete small-case certificate for a protected Moore--Read bundle."""

    N: int
    n_flux: int
    basis_dimension: int
    constraint_shape: tuple[int, int]
    constraint_nnz: int
    expected_rank: int
    observed_rank: int
    internal_bandwidth: float
    external_gap: float
    kernel_residual: float
    orthonormality_error: float
    generator_commutator_norm: float
    projector_distance: float
    transported_constraint_residual: float
    response_relative_residual: float
    response_kernel_leakage: float
    tangent_fiber_norm: float
    checks: dict[str, bool]


def _projector_distance(left: np.ndarray, right: np.ndarray) -> float:
    first = np.asarray(left, dtype=complex)
    second = np.asarray(right, dtype=complex)
    if first.shape != second.shape or first.ndim != 2:
        raise ValueError("projector frames must have equal matrix shape")
    rank = first.shape[1]
    overlap = first.conj().T @ second
    squared = rank - float(np.linalg.norm(overlap, ord="fro") ** 2)
    return float(np.sqrt(max(squared, 0.0) / rank))


def audit_moore_read_case(
    N: int,
    n_flux: int,
    *,
    seed: int,
    transport_x: float = 0.07,
    transport_y: float = 0.11,
) -> MooreReadAudit:
    """Certify exact nullity, gap, and nontrivial protected transport."""

    particles = int(N)
    flux = int(n_flux)
    expected = clustered_zero_mode_count(particles, flux, k=2, r=2)
    system = build_continuum_moore_read_parent(particles, flux)
    case = ManyBodyCase(
        N=particles,
        n_flux=flux,
        expected_rank=expected,
        theta_x=0.0,
        theta_y=0.0,
    )
    kernel = solve_kernel_frame_factored(
        system,
        case,
        seed=int(seed),
    )
    generator_x, generator_y = projected_local_generator_pair(system)
    commutator = generator_x @ generator_y - generator_y @ generator_x
    exponent = (
        float(transport_x) * generator_x
        + float(transport_y) * generator_y
    )
    inverse_map = expm(-exponent)
    deformed_coefficients = np.asarray(system.orbitals) @ inverse_map
    deformed_constraints, _ = three_body_annihilation_constraints(
        system.basis,
        deformed_coefficients,
    )
    transported = transported_kernel_frame(
        system.basis,
        kernel.frame,
        exponent,
    )
    transport_residual = float(
        np.linalg.norm(deformed_constraints @ transported, ord="fro")
    )
    response = analytic_protected_generator_response(
        system,
        kernel,
        np.asarray([generator_x, generator_y]),
    )
    internal_bandwidth = float(np.ptp(kernel.zero_eigenvalues))
    commutator_norm = float(np.linalg.norm(commutator, ord="fro"))
    distance = _projector_distance(kernel.frame, transported)
    checks = {
        "exact_nullity": kernel.observed_rank == expected,
        "internal_bandwidth": internal_bandwidth < 1e-9,
        "external_gap": kernel.external_gap > 1e-8,
        "kernel_residual": kernel.residual_norm < 1e-7,
        "kernel_orthonormality": kernel.orthonormality_error < 1e-9,
        "noncommuting_generators": commutator_norm > 1e-8,
        "projector_motion": distance > 1e-8,
        "transported_kernel": transport_residual < 1e-8,
        "response_identity": response.maximum_relative_residual < 1e-9,
        "response_kernel_leakage": response.maximum_kernel_leakage < 1e-9,
        "tangent_fiber_zero": response.tangent_fiber_norm < 1e-8,
    }
    return MooreReadAudit(
        N=particles,
        n_flux=flux,
        basis_dimension=system.basis.dimension,
        constraint_shape=tuple(int(value) for value in system.constraints.shape),
        constraint_nnz=int(system.constraints.nnz),
        expected_rank=expected,
        observed_rank=kernel.observed_rank,
        internal_bandwidth=internal_bandwidth,
        external_gap=kernel.external_gap,
        kernel_residual=kernel.residual_norm,
        orthonormality_error=kernel.orthonormality_error,
        generator_commutator_norm=commutator_norm,
        projector_distance=distance,
        transported_constraint_residual=transport_residual,
        response_relative_residual=response.maximum_relative_residual,
        response_kernel_leakage=response.maximum_kernel_leakage,
        tangent_fiber_norm=response.tangent_fiber_norm,
        checks=checks,
    )
