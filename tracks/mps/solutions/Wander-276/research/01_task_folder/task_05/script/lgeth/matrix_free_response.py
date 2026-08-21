"""Streamed response solves using a factorized positive parent operator."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, cg, lobpcg

from .lattice import (
    KapitLaughlinParent,
    manybody_one_body_operator,
    projected_site_potential,
)
from .manybody_response import KernelFrame, ManyBodyCase
from .protected_parent import (
    pair_annihilation_constraint_derivative,
    projected_onsite_generator,
)


@dataclass(frozen=True)
class StreamedResponse:
    """One streamed operator panel and its iterative-solver audit."""

    channels: np.ndarray
    shift_values: tuple[float, float]
    maximum_relative_residual: float
    maximum_shift_difference: float
    maximum_kernel_leakage: float
    maximum_iterations: int
    failed_columns: int
    tangent_fiber_norm: float


def solve_kernel_frame_factored(
    system,
    case: ManyBodyCase,
    seed: int,
    tolerance: float = 1e-9,
    maxiter: int = 800,
) -> KernelFrame:
    """Find the complete kernel and external gap from ``C^dagger C`` actions."""

    if system.n_particles != case.N or system.n_flux != case.n_flux:
        raise ValueError("system and many-body case disagree")
    dimension = system.basis.dimension
    rank = int(case.expected_rank)
    audit_width = min(dimension - 1, rank + 4)
    if audit_width <= rank:
        raise ValueError("factored parent has no external audit sector")
    if dimension <= 2_000:
        parent = system.constraints.conj().T @ system.constraints
        eigenvalues, eigenvectors = np.linalg.eigh(parent.toarray())
        frame = np.asarray(eigenvectors[:, :rank], dtype=complex)
        audit_values = np.asarray(eigenvalues[:audit_width], dtype=float)
        method = "factored_dense_audit"
    else:
        rng = np.random.default_rng(int(seed))
        initial = rng.normal(size=(dimension, audit_width))
        initial = initial + 1j * rng.normal(size=initial.shape)
        initial, _ = np.linalg.qr(initial)
        operator = factored_parent_operator(system.constraints)
        preconditioner = _jacobi_preconditioner(
            system.constraints, shift=1e-10
        )
        eigenvalues, eigenvectors = lobpcg(
            operator,
            initial,
            M=preconditioner,
            largest=False,
            tol=float(tolerance),
            maxiter=int(maxiter),
        )
        order = np.argsort(np.real(eigenvalues))
        audit_values = np.real(eigenvalues[order])
        frame = np.asarray(eigenvectors[:, order[:rank]], dtype=complex)
        frame, _ = np.linalg.qr(frame)
        method = "factored_lobpcg"
    scale = max(float(np.max(np.abs(audit_values))), 1.0)
    zero_tolerance = 1e-8 * scale
    observed = int(
        np.count_nonzero(np.abs(audit_values) < zero_tolerance)
    )
    if observed != rank:
        raise RuntimeError(
            f"factored zero-mode count mismatch: expected {rank}, "
            f"observed {observed}"
        )
    gap = float(audit_values[rank] - audit_values[rank - 1])
    if gap <= 0.0:
        raise RuntimeError("factored kernel has no open external gap")
    residual = float(
        np.linalg.norm(system.constraints.conj().T @ (system.constraints @ frame))
    )
    orthonormality = float(
        np.linalg.norm(frame.conj().T @ frame - np.eye(rank))
    )
    return KernelFrame(
        frame=frame,
        zero_eigenvalues=np.asarray(audit_values[:rank], dtype=float),
        external_gap=gap,
        residual_norm=residual,
        orthonormality_error=orthonormality,
        method=method,
        observed_rank=observed,
    )


def _project_complement(frame: np.ndarray, values: np.ndarray) -> np.ndarray:
    return values - frame @ (frame.conj().T @ values)


def factored_parent_operator(
    constraints: sparse.spmatrix,
    shift: float = 0.0,
) -> LinearOperator:
    """Return ``C^dagger C + shift`` without forming the parent matrix."""

    factor = sparse.csr_matrix(constraints, dtype=complex)
    dimension = factor.shape[1]
    offset = float(shift)
    if offset < 0.0:
        raise ValueError("parent shift must be nonnegative")

    def matvec(vector: np.ndarray) -> np.ndarray:
        values = factor.conj().T @ (factor @ vector)
        return np.asarray(values) + offset * np.asarray(vector)

    def matmat(matrix: np.ndarray) -> np.ndarray:
        values = factor.conj().T @ (factor @ matrix)
        return np.asarray(values) + offset * np.asarray(matrix)

    return LinearOperator(
        (dimension, dimension),
        matvec=matvec,
        matmat=matmat,
        dtype=np.dtype(complex),
    )


def _jacobi_preconditioner(
    constraints: sparse.spmatrix,
    shift: float,
) -> LinearOperator:
    factor = sparse.csr_matrix(constraints, dtype=complex)
    diagonal = np.asarray(
        factor.conjugate().multiply(factor).sum(axis=0)
    ).ravel().real
    diagonal = diagonal + float(shift)
    floor = max(float(np.max(diagonal)) * 1e-13, 1e-15)
    inverse = 1.0 / np.maximum(diagonal, floor)
    return LinearOperator(
        (inverse.size, inverse.size),
        matvec=lambda vector: inverse * np.asarray(vector).reshape(-1),
        matmat=lambda matrix: inverse[:, None] * matrix,
        dtype=np.dtype(complex),
    )


def _solve_columns(
    constraints: sparse.spmatrix,
    right_hand_sides: np.ndarray,
    shift: float,
    rtol: float,
    maxiter: int,
    initial: np.ndarray | None = None,
    block_size: int = 8,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    operator = factored_parent_operator(constraints, shift=shift)
    preconditioner = _jacobi_preconditioner(constraints, shift)
    right = np.asarray(right_hand_sides, dtype=complex)
    solution = np.empty_like(right)
    info_values = np.empty(right.shape[1], dtype=int)
    iterations = np.empty(right.shape[1], dtype=int)
    width = max(1, int(block_size))
    for start in range(0, right.shape[1], width):
        stop = min(start + width, right.shape[1])
        block_right = right[:, start:stop]
        block_initial = (
            None if initial is None else initial[:, start:stop]
        )
        block_solution, info, count = _block_cg(
            operator,
            preconditioner,
            block_right,
            rtol=float(rtol),
            maxiter=int(maxiter),
            initial=block_initial,
        )
        if info != 0:
            block_solution, block_info, block_iterations = (
                _scalar_cg_fallback(
                    operator,
                    preconditioner,
                    block_right,
                    rtol=float(rtol),
                    maxiter=int(maxiter),
                    initial=block_solution,
                )
            )
            solution[:, start:stop] = block_solution
            info_values[start:stop] = block_info
            iterations[start:stop] = count + block_iterations
        else:
            solution[:, start:stop] = block_solution
            info_values[start:stop] = 0
            iterations[start:stop] = count
    return solution, info_values, iterations


def _stable_dense_solve(matrix: np.ndarray, right: np.ndarray) -> np.ndarray:
    values = 0.5 * (matrix + matrix.conj().T)
    try:
        if np.linalg.cond(values) < 1e12:
            return np.linalg.solve(values, right)
    except np.linalg.LinAlgError:
        pass
    return np.linalg.pinv(values, rcond=1e-12) @ right


def _block_cg(
    operator: LinearOperator,
    preconditioner: LinearOperator,
    right: np.ndarray,
    rtol: float,
    maxiter: int,
    initial: np.ndarray | None,
) -> tuple[np.ndarray, int, int]:
    """Preconditioned block CG with a scalar-CG fallback signal."""

    solution = (
        np.zeros_like(right)
        if initial is None
        else np.asarray(initial, dtype=complex).copy()
    )
    residual = right - operator @ solution
    right_norms = np.maximum(np.linalg.norm(right, axis=0), 1e-30)
    if float(np.max(np.linalg.norm(residual, axis=0) / right_norms)) <= rtol:
        return solution, 0, 0
    preconditioned = preconditioner @ residual
    direction = preconditioned.copy()
    gram = residual.conj().T @ preconditioned
    for iteration in range(1, int(maxiter) + 1):
        action = operator @ direction
        curvature = direction.conj().T @ action
        alpha = _stable_dense_solve(curvature, gram)
        if not np.all(np.isfinite(alpha)):
            return solution, 1, iteration
        solution = solution + direction @ alpha
        residual = residual - action @ alpha
        relative = np.linalg.norm(residual, axis=0) / right_norms
        if float(np.max(relative)) <= rtol:
            return solution, 0, iteration
        preconditioned = preconditioner @ residual
        next_gram = residual.conj().T @ preconditioned
        beta = _stable_dense_solve(gram, next_gram)
        if not np.all(np.isfinite(beta)):
            return solution, 1, iteration
        direction = preconditioned + direction @ beta
        gram = next_gram
    return solution, int(maxiter), int(maxiter)


def _scalar_cg_fallback(
    operator: LinearOperator,
    preconditioner: LinearOperator,
    right: np.ndarray,
    rtol: float,
    maxiter: int,
    initial: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    solution = np.empty_like(right)
    infos = np.empty(right.shape[1], dtype=int)
    iterations = np.empty(right.shape[1], dtype=int)
    for column in range(right.shape[1]):
        count = 0

        def callback(_: np.ndarray) -> None:
            nonlocal count
            count += 1

        vector, info = cg(
            operator,
            right[:, column],
            x0=initial[:, column],
            rtol=float(rtol),
            atol=0.0,
            maxiter=int(maxiter),
            M=preconditioner,
            callback=callback,
        )
        solution[:, column] = vector
        infos[column] = int(info)
        iterations[column] = count
    return solution, infos, iterations


def _richardson_responses(
    constraints: sparse.spmatrix,
    frame: np.ndarray,
    right_hand_sides: np.ndarray,
    external_gap: float,
    relative_shifts: tuple[float, float],
    rtol: float,
    maxiter: int,
) -> tuple[np.ndarray, tuple[float, float], float, float, float, int, int]:
    relative = tuple(float(value) for value in relative_shifts)
    if len(relative) != 2 or not relative[0] > relative[1] > 0.0:
        raise ValueError("require two positive descending relative shifts")
    if not np.isclose(relative[1], 0.5 * relative[0]):
        raise ValueError("Richardson extrapolation requires a half shift")
    shifts = (
        relative[0] * float(external_gap),
        relative[1] * float(external_gap),
    )
    right = _project_complement(frame, np.asarray(right_hand_sides))
    first, info_first, iterations_first = _solve_columns(
        constraints, right, shifts[0], rtol, maxiter
    )
    second, info_second, iterations_second = _solve_columns(
        constraints, right, shifts[1], rtol, maxiter, initial=first
    )
    first = _project_complement(frame, first)
    second = _project_complement(frame, second)
    extrapolated = _project_complement(frame, 2.0 * second - first)
    parent = factored_parent_operator(constraints)
    right_norms = np.linalg.norm(right, axis=0)
    residuals = np.linalg.norm(parent @ extrapolated - right, axis=0)
    relative_residual = float(
        np.max(residuals / np.maximum(right_norms, 1e-30))
    )
    solution_norms = np.linalg.norm(extrapolated, axis=0)
    shift_difference = float(
        np.max(
            np.linalg.norm(second - first, axis=0)
            / np.maximum(solution_norms, 1e-30)
        )
    )
    leakage = float(np.linalg.norm(frame.conj().T @ extrapolated))
    maximum_iterations = int(
        max(np.max(iterations_first), np.max(iterations_second))
    )
    failed = int(
        np.count_nonzero(info_first) + np.count_nonzero(info_second)
    )
    return (
        extrapolated,
        shifts,
        relative_residual,
        shift_difference,
        leakage,
        maximum_iterations,
        failed,
    )


def _reshape_channels(
    solutions: np.ndarray,
    labels: int,
    dimension: int,
    rank: int,
) -> np.ndarray:
    return (
        np.asarray(solutions)
        .reshape(dimension, labels, rank)
        .transpose(1, 0, 2)
    )


def streamed_density_panel_response(
    system: KapitLaughlinParent,
    kernel: KernelFrame,
    coefficients: np.ndarray,
    relative_shifts: tuple[float, float] = (1e-3, 5e-4),
    rtol: float = 1e-10,
    maxiter: int = 8_000,
) -> StreamedResponse:
    """Solve one local-density panel without caching every site response."""

    fields = np.asarray(coefficients, dtype=float)
    if fields.ndim != 2 or fields.shape[1] != system.orbitals.shape[0]:
        raise ValueError("density panel and physical lattice disagree")
    frame = np.asarray(kernel.frame, dtype=complex)
    right_blocks: list[np.ndarray] = []
    tangent_norms: list[float] = []
    fiber_norm = 0.0
    for field in fields:
        onebody = projected_site_potential(system.orbitals, field)
        tangent = manybody_one_body_operator(system.basis, onebody)
        applied = np.asarray(tangent @ frame)
        fiber_norm = max(
            fiber_norm, float(np.linalg.norm(frame.conj().T @ applied))
        )
        right_blocks.append(_project_complement(frame, applied))
        tangent_norm = float(
            np.sqrt(
                np.real(
                    tangent.conjugate().multiply(tangent).sum()
                )
            )
        )
        if tangent_norm <= 1e-14:
            raise ValueError("density panel contains a null tangent")
        tangent_norms.append(tangent_norm)
    combined = np.concatenate(right_blocks, axis=1)
    solved = _richardson_responses(
        system.constraints,
        frame,
        combined,
        kernel.external_gap,
        relative_shifts,
        rtol,
        maxiter,
    )
    channels = _reshape_channels(
        solved[0], fields.shape[0], system.basis.dimension, frame.shape[1]
    )
    channels = channels / np.asarray(tangent_norms)[:, None, None]
    return StreamedResponse(
        channels=channels,
        shift_values=solved[1],
        maximum_relative_residual=solved[2],
        maximum_shift_difference=solved[3],
        maximum_kernel_leakage=solved[4],
        maximum_iterations=solved[5],
        failed_columns=solved[6],
        tangent_fiber_norm=fiber_norm,
    )


def streamed_protected_panel_response(
    system: KapitLaughlinParent,
    kernel: KernelFrame,
    coefficients: np.ndarray,
    relative_shifts: tuple[float, float] = (1e-3, 5e-4),
    rtol: float = 1e-10,
    maxiter: int = 8_000,
) -> StreamedResponse:
    """Solve one panel of exact-degeneracy-preserving constraint tangents."""

    fields = np.asarray(coefficients, dtype=float)
    if fields.ndim != 2 or fields.shape[1] != system.orbitals.shape[0]:
        raise ValueError("protected panel and physical lattice disagree")
    frame = np.asarray(kernel.frame, dtype=complex)
    right_blocks: list[np.ndarray] = []
    fiber_norm = 0.0
    for field in fields:
        generator = projected_onsite_generator(system, field)
        frame_derivative = -np.asarray(system.orbitals) @ generator
        constraint_tangent = pair_annihilation_constraint_derivative(
            system.basis,
            system.orbitals,
            frame_derivative,
        )
        applied = system.constraints.conj().T @ (
            constraint_tangent @ frame
        )
        applied = np.asarray(applied)
        fiber_norm = max(
            fiber_norm, float(np.linalg.norm(frame.conj().T @ applied))
        )
        right_blocks.append(_project_complement(frame, applied))
    combined = np.concatenate(right_blocks, axis=1)
    solved = _richardson_responses(
        system.constraints,
        frame,
        combined,
        kernel.external_gap,
        relative_shifts,
        rtol,
        maxiter,
    )
    channels = _reshape_channels(
        solved[0], fields.shape[0], system.basis.dimension, frame.shape[1]
    )
    return StreamedResponse(
        channels=channels,
        shift_values=solved[1],
        maximum_relative_residual=solved[2],
        maximum_shift_difference=solved[3],
        maximum_kernel_leakage=solved[4],
        maximum_iterations=solved[5],
        failed_columns=solved[6],
        tangent_fiber_norm=fiber_norm,
    )


def analytic_protected_panel_response(
    system,
    kernel: KernelFrame,
    coefficients: np.ndarray,
) -> StreamedResponse:
    """Evaluate the protected response using the exact intertwiner theorem.

    For ``C_lambda Gamma_N(V_lambda) = L_lambda C_0``, differentiation on
    ``ker(C_0)`` gives ``dH P = -H dGamma(G) P``.  The complement response is
    therefore exactly ``-Q dGamma(G) P`` and requires no resolvent solve.
    """

    fields = np.asarray(coefficients, dtype=float)
    if fields.ndim != 2 or fields.shape[1] != system.orbitals.shape[0]:
        raise ValueError("protected panel and physical lattice disagree")
    frame = np.asarray(kernel.frame, dtype=complex)
    parent = factored_parent_operator(system.constraints)
    channels: list[np.ndarray] = []
    relative_residuals: list[float] = []
    fiber_norm = 0.0
    for field in fields:
        generator = projected_onsite_generator(system, field)
        fock_generator = manybody_one_body_operator(system.basis, generator)
        generator_action = np.asarray(fock_generator @ frame)
        response = -_project_complement(frame, generator_action)
        tangent_action = -np.asarray(parent @ generator_action)
        fiber_norm = max(
            fiber_norm,
            float(np.linalg.norm(frame.conj().T @ tangent_action)),
        )
        residual = np.asarray(parent @ response) - tangent_action
        relative_residuals.append(
            float(np.linalg.norm(residual))
            / max(float(np.linalg.norm(tangent_action)), 1e-30)
        )
        channels.append(response)
    values = np.asarray(channels, dtype=complex)
    leakage = float(
        max(np.linalg.norm(frame.conj().T @ value) for value in values)
    )
    return StreamedResponse(
        channels=values,
        shift_values=(0.0, 0.0),
        maximum_relative_residual=max(relative_residuals),
        maximum_shift_difference=0.0,
        maximum_kernel_leakage=leakage,
        maximum_iterations=0,
        failed_columns=0,
        tangent_fiber_norm=fiber_norm,
    )
