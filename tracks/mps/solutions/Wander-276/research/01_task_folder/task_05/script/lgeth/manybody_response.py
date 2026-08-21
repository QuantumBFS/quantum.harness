"""Sparse resolvent responses on a genuine fixed-quasihole sequence."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, replace

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh, lobpcg, splu

from .combinatorics import laughlin_zero_mode_count
from .lattice import (
    KapitLaughlinParent,
    build_kapit_laughlin_parent,
    manybody_one_body_operator,
    projected_site_potential,
)


@dataclass(frozen=True)
class ManyBodyCase:
    """One registered physical fixed-two-quasihole system."""

    N: int
    n_flux: int
    expected_rank: int
    theta_x: float
    theta_y: float


@dataclass(frozen=True)
class SmallCaseAudit:
    """Reason an unregistered small physical system is excluded."""

    N: int
    n_flux: int
    expected_rank: int
    observed_rank: int
    accepted: bool


@dataclass(frozen=True)
class KernelFrame:
    """Numerically complete orthonormal frame for one exact zero-mode space."""

    frame: np.ndarray
    zero_eigenvalues: np.ndarray
    external_gap: float
    residual_norm: float
    orthonormality_error: float
    method: str
    observed_rank: int


@dataclass(frozen=True)
class SiteResponseCache:
    """Resolvent solutions for a selected physical-site tangent basis."""

    case: ManyBodyCase
    site_indices: tuple[int, ...]
    solutions: np.ndarray
    tangent_gram: np.ndarray
    external_gap: float
    shift_values: tuple[float, float]
    maximum_relative_residual: float
    maximum_shift_difference: float
    maximum_kernel_leakage: float


def registered_fixed_two_qh_cases() -> tuple[ManyBodyCase, ...]:
    """Return the preregistered genuine particle-number sequence."""

    return tuple(
        ManyBodyCase(
            N=N,
            n_flux=2 * N + 2,
            expected_rank=laughlin_zero_mode_count(N, 2 * N + 2),
            theta_x=0.17,
            theta_y=0.29,
        )
        for N in (3, 4, 5)
    )


def _zero_tolerance(eigenvalues: np.ndarray) -> float:
    values = np.asarray(eigenvalues, dtype=float)
    scale = max(float(np.max(np.abs(values))), 1.0)
    return 1e-9 * scale


def audit_unregistered_small_case(
    N: int,
    n_flux: int,
    theta_x: float,
    theta_y: float,
) -> SmallCaseAudit:
    """Return the exact-count audit for a proposed small physical parent."""

    system = build_kapit_laughlin_parent(
        int(N),
        int(n_flux),
        float(theta_x),
        float(theta_y),
    )
    eigenvalues = np.linalg.eigvalsh(system.parent.toarray())
    expected = laughlin_zero_mode_count(int(N), int(n_flux))
    observed = int(
        np.count_nonzero(np.abs(eigenvalues) < _zero_tolerance(eigenvalues))
    )
    return SmallCaseAudit(
        N=int(N),
        n_flux=int(n_flux),
        expected_rank=expected,
        observed_rank=observed,
        accepted=observed == expected,
    )


def _dense_kernel_frame(
    system: KapitLaughlinParent,
    case: ManyBodyCase,
) -> KernelFrame:
    parent = system.parent.toarray()
    parent = 0.5 * (parent + parent.conj().T)
    eigenvalues, eigenvectors = np.linalg.eigh(parent)
    tolerance = _zero_tolerance(eigenvalues)
    observed = int(np.count_nonzero(np.abs(eigenvalues) < tolerance))
    if observed != case.expected_rank:
        raise RuntimeError(
            f"zero-mode count mismatch: expected {case.expected_rank}, "
            f"observed {observed}"
        )
    frame = eigenvectors[:, :observed]
    gap = float(eigenvalues[observed] - eigenvalues[observed - 1])
    residual = float(np.linalg.norm(system.parent @ frame))
    orthonormality = float(
        np.linalg.norm(frame.conj().T @ frame - np.eye(observed))
    )
    return KernelFrame(
        frame=frame,
        zero_eigenvalues=np.asarray(eigenvalues[:observed], dtype=float),
        external_gap=gap,
        residual_norm=residual,
        orthonormality_error=orthonormality,
        method="dense",
        observed_rank=observed,
    )


def _sparse_kernel_frame(
    system: KapitLaughlinParent,
    case: ManyBodyCase,
    seed: int,
) -> KernelFrame:
    dimension = system.basis.dimension
    rank = case.expected_rank
    rng = np.random.default_rng(int(seed))
    initial = (
        rng.normal(size=(dimension, rank))
        + 1j * rng.normal(size=(dimension, rank))
    )
    initial, _ = np.linalg.qr(initial)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        values, frame = lobpcg(
            system.parent,
            initial,
            largest=False,
            tol=1e-9,
            maxiter=600,
        )
    frame, _ = np.linalg.qr(frame)
    residual = float(np.linalg.norm(system.parent @ frame))
    orthonormality = float(
        np.linalg.norm(frame.conj().T @ frame - np.eye(rank))
    )
    audit_values = eigsh(
        system.parent,
        k=rank + 4,
        which="SM",
        return_eigenvectors=False,
        tol=1e-9,
        maxiter=12_000,
        ncv=min(dimension, max(2 * (rank + 4) + 1, 100)),
    )
    audit_values = np.sort(np.real(audit_values))
    tolerance = _zero_tolerance(audit_values)
    observed = int(np.count_nonzero(np.abs(audit_values) < tolerance))
    if observed != rank:
        raise RuntimeError(
            f"sparse zero-mode count mismatch: expected {rank}, observed {observed}"
        )
    gap = float(audit_values[rank] - audit_values[rank - 1])
    if gap <= 0.0:
        raise RuntimeError("sparse kernel has no open external gap")
    return KernelFrame(
        frame=frame,
        zero_eigenvalues=np.sort(np.real(values)),
        external_gap=gap,
        residual_norm=residual,
        orthonormality_error=orthonormality,
        method="lobpcg",
        observed_rank=observed,
    )


def solve_kernel_frame(
    system: KapitLaughlinParent,
    case: ManyBodyCase,
    seed: int,
) -> KernelFrame:
    """Return a complete target frame and a separately audited external gap."""

    if system.n_particles != case.N or system.n_flux != case.n_flux:
        raise ValueError("system and many-body case disagree")
    if case.expected_rank != laughlin_zero_mode_count(case.N, case.n_flux):
        raise ValueError("case rank disagrees with exact Laughlin counting")
    if system.basis.dimension <= 2_000:
        return _dense_kernel_frame(system, case)
    return _sparse_kernel_frame(system, case, seed)


def _site_tangent_operators(
    system: KapitLaughlinParent,
    site_indices: tuple[int, ...],
) -> list[sparse.csr_matrix]:
    physical_sites = int(system.orbitals.shape[0])
    operators: list[sparse.csr_matrix] = []
    for site in site_indices:
        if not 0 <= site < physical_sites:
            raise IndexError("physical site index is outside the lattice")
        potential = np.zeros(physical_sites, dtype=float)
        potential[site] = 1.0
        one_body = projected_site_potential(system.orbitals, potential)
        operators.append(manybody_one_body_operator(system.basis, one_body))
    return operators


def _tangent_gram(operators: list[sparse.csr_matrix]) -> np.ndarray:
    count = len(operators)
    gram = np.empty((count, count), dtype=complex)
    for left in range(count):
        for right in range(left, count):
            value = (
                operators[left]
                .conjugate()
                .multiply(operators[right])
                .sum()
            )
            gram[left, right] = value
            gram[right, left] = np.conjugate(value)
    gram = 0.5 * (gram + gram.conj().T)
    if np.max(np.abs(gram.imag)) < 1e-10:
        return gram.real
    return gram


def _project_complement(frame: np.ndarray, values: np.ndarray) -> np.ndarray:
    return values - frame @ (frame.conj().T @ values)


def _reshape_site_solutions(
    matrix: np.ndarray,
    sites: int,
    dimension: int,
    rank: int,
) -> np.ndarray:
    return (
        np.asarray(matrix)
        .reshape(dimension, sites, rank)
        .transpose(1, 0, 2)
    )


def build_site_response_cache(
    system: KapitLaughlinParent,
    kernel: KernelFrame,
    relative_shifts: tuple[float, float] = (1e-3, 5e-4),
    site_indices: tuple[int, ...] | None = None,
) -> SiteResponseCache:
    """Build selected site responses by two-shift sparse extrapolation."""

    relative = tuple(float(value) for value in relative_shifts)
    if len(relative) != 2 or not (relative[0] > relative[1] > 0.0):
        raise ValueError("require two positive descending relative shifts")
    if not np.isclose(relative[1], 0.5 * relative[0]):
        raise ValueError("Richardson extrapolation requires a half shift")
    chosen = (
        tuple(range(system.orbitals.shape[0]))
        if site_indices is None
        else tuple(int(index) for index in site_indices)
    )
    if not chosen or len(set(chosen)) != len(chosen):
        raise ValueError("site indices must be nonempty and distinct")
    operators = _site_tangent_operators(system, chosen)
    frame = np.asarray(kernel.frame, dtype=complex)
    right_hand_sides = [
        _project_complement(frame, np.asarray(operator @ frame))
        for operator in operators
    ]
    combined_rhs = np.concatenate(right_hand_sides, axis=1)
    identity = sparse.eye(
        system.basis.dimension,
        format="csc",
        dtype=complex,
    )
    absolute = (
        relative[0] * kernel.external_gap,
        relative[1] * kernel.external_gap,
    )
    first_solver = splu(
        (system.parent + absolute[0] * identity).tocsc()
    )
    first = first_solver.solve(combined_rhs)
    del first_solver
    second_solver = splu(
        (system.parent + absolute[1] * identity).tocsc()
    )
    second = second_solver.solve(combined_rhs)
    del second_solver
    first = _project_complement(frame, first)
    second = _project_complement(frame, second)
    extrapolated = _project_complement(frame, 2.0 * second - first)
    sites = len(chosen)
    dimension = system.basis.dimension
    rank = kernel.frame.shape[1]
    solutions = _reshape_site_solutions(
        extrapolated,
        sites,
        dimension,
        rank,
    )
    first_by_site = _reshape_site_solutions(
        first,
        sites,
        dimension,
        rank,
    )
    second_by_site = _reshape_site_solutions(
        second,
        sites,
        dimension,
        rank,
    )
    relative_residuals: list[float] = []
    shift_differences: list[float] = []
    kernel_leakage: list[float] = []
    for index, rhs in enumerate(right_hand_sides):
        solution = solutions[index]
        rhs_norm = float(np.linalg.norm(rhs))
        solution_norm = max(float(np.linalg.norm(solution)), 1e-30)
        relative_residuals.append(
            float(np.linalg.norm(system.parent @ solution - rhs))
            / rhs_norm
        )
        shift_differences.append(
            float(
                np.linalg.norm(
                    second_by_site[index] - first_by_site[index]
                )
            )
            / solution_norm
        )
        kernel_leakage.append(
            float(np.linalg.norm(frame.conj().T @ solution))
        )
    case = ManyBodyCase(
        N=system.n_particles,
        n_flux=system.n_flux,
        expected_rank=rank,
        theta_x=system.theta_x,
        theta_y=system.theta_y,
    )
    return SiteResponseCache(
        case=case,
        site_indices=chosen,
        solutions=solutions,
        tangent_gram=_tangent_gram(operators),
        external_gap=kernel.external_gap,
        shift_values=absolute,
        maximum_relative_residual=max(relative_residuals),
        maximum_shift_difference=max(shift_differences),
        maximum_kernel_leakage=max(kernel_leakage),
    )


def dense_resolvent_response(
    system: KapitLaughlinParent,
    kernel: KernelFrame,
    site_indices: tuple[int, ...] | None = None,
) -> np.ndarray:
    """Return exact dense complement responses in the supplied target gauge."""

    chosen = (
        tuple(range(system.orbitals.shape[0]))
        if site_indices is None
        else tuple(int(index) for index in site_indices)
    )
    operators = _site_tangent_operators(system, chosen)
    eigenvalues, eigenvectors = np.linalg.eigh(system.parent.toarray())
    rank = kernel.frame.shape[1]
    external_values = eigenvalues[rank:]
    external_frame = eigenvectors[:, rank:]
    if external_values.size == 0 or external_values[0] <= 0.0:
        raise RuntimeError("dense spectral inverse has no external sector")
    responses: list[np.ndarray] = []
    for operator in operators:
        rhs = _project_complement(
            kernel.frame,
            np.asarray(operator @ kernel.frame),
        )
        coefficients = external_frame.conj().T @ rhs
        responses.append(
            external_frame
            @ (coefficients / external_values[:, None])
        )
    return np.asarray(responses)


def response_pair_grams(solutions: np.ndarray) -> np.ndarray:
    """Return all target-space products ``A_s^dagger A_t``."""

    values = np.asarray(solutions, dtype=complex)
    if values.ndim != 3:
        raise ValueError("solutions must have shape (site, ambient, rank)")
    return np.einsum(
        "sai,taj->stij",
        values.conj(),
        values,
        optimize=True,
    )


def rotate_response_target_gauge(
    cache: SiteResponseCache,
    unitary: np.ndarray,
) -> SiteResponseCache:
    """Return the same response cache in a rotated target frame."""

    matrix = np.asarray(unitary, dtype=complex)
    rank = cache.solutions.shape[-1]
    if matrix.shape != (rank, rank):
        raise ValueError("target unitary has the wrong shape")
    if not np.allclose(
        matrix.conj().T @ matrix,
        np.eye(rank),
        atol=1e-10,
    ):
        raise ValueError("target transformation must be unitary")
    return replace(
        cache,
        solutions=np.einsum(
            "sai,ij->saj",
            cache.solutions,
            matrix,
            optimize=True,
        ),
    )
