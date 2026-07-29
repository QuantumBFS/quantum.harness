from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from numbers import Integral

import jax
import jax.numpy as jnp
import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares
from scipy.sparse.linalg import LinearOperator, eigsh

from qcontrol.objectives import normalized_infidelity
from qcontrol.open_loop import OpenLoopResult
from qcontrol.propagation import propagate
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem


RankMap = dict[float, int]
AngleMap = dict[float, NDArray[np.float64]]
_RANK_THRESHOLDS = (1e-6, 1e-8, 1e-10)
_MAX_DENSE_PARAMETERS = 80
_ACCEPTANCE_LOSS = 1e-8
_POLISH_LOSS_TOLERANCE = 1e-12
_POLISH_GRADIENT_TOLERANCE = 1e-10
_POLISH_RESIDUAL_TOLERANCE = 1e-12
_POLISH_PHASE_TOLERANCE = 1e-12


@dataclass(frozen=True)
class EndpointPolishResult:
    normalized_pulse: tuple[float, ...]
    loss: float
    gradient_norm: float
    projected_gradient_norm: float
    residual_norm: float
    phase_consistency_error: float
    evaluations: int
    jacobian_evaluations: int
    status: int
    message: str
    cost: float
    optimality: float
    step_norm: float
    converged: bool
    source_loss: float
    source_gradient_norm: float
    duration: float
    fixed_phase_real: float
    fixed_phase_imag: float


class EndpointPolishingError(RuntimeError):
    def __init__(self, message: str, diagnostics: EndpointPolishResult) -> None:
        self.diagnostics = diagnostics
        super().__init__(message)


@dataclass(frozen=True)
class LandscapeResult:
    leading_eigenvalues: NDArray[np.float64]
    leading_eigenvectors: NDArray[np.float64]
    jacobian_singular_values: NDArray[np.float64]
    hessian_ranks: RankMap
    hessian_rank_is_lower_bound: dict[float, bool]
    jacobian_ranks: RankMap
    model_basis: NDArray[np.float64]
    endpoint_basis: NDArray[np.float64]
    dense_hessian: NDArray[np.float64] | None
    dense_eigenvalues: NDArray[np.float64] | None
    dense_eigenvectors: NDArray[np.float64] | None
    dense_hvp_projector_residuals: dict[float, float]
    dense_hvp_principal_angles: AngleMap
    polishing: EndpointPolishResult | None


def hessian_vector_product(
    loss_fn: Callable[[jax.Array], jax.Array],
    point: jax.Array,
    vector: jax.Array,
) -> jax.Array:
    _, product = jax.jvp(jax.grad(loss_fn), (point,), (vector,))
    return product


def dense_hessian(
    loss_fn: Callable[[jax.Array], jax.Array],
    point: object,
) -> NDArray[np.float64]:
    point_array = jnp.asarray(point, dtype=jnp.float64)
    if point_array.ndim != 1:
        raise ValueError("point must be a one-dimensional real vector")
    if point_array.size > _MAX_DENSE_PARAMETERS:
        raise ValueError("dense Hessian validation supports at most 80 parameters")
    matrix = np.asarray(jax.hessian(loss_fn)(point_array), dtype=np.float64)
    return np.asarray(0.5 * (matrix + matrix.T), dtype=np.float64)


def _generalized_pauli_basis(dimension: int) -> jax.Array:
    generators: list[NDArray[np.complex128]] = []
    for row in range(dimension):
        for column in range(row + 1, dimension):
            symmetric = np.zeros((dimension, dimension), dtype=np.complex128)
            symmetric[row, column] = 1.0 / np.sqrt(2.0)
            symmetric[column, row] = 1.0 / np.sqrt(2.0)
            generators.append(symmetric)

            antisymmetric = np.zeros((dimension, dimension), dtype=np.complex128)
            antisymmetric[row, column] = -1.0j / np.sqrt(2.0)
            antisymmetric[column, row] = 1.0j / np.sqrt(2.0)
            generators.append(antisymmetric)

    for index in range(1, dimension):
        diagonal = np.zeros((dimension, dimension), dtype=np.complex128)
        normalization = np.sqrt(index * (index + 1.0))
        diagonal[np.arange(index), np.arange(index)] = 1.0 / normalization
        diagonal[index, index] = -index / normalization
        generators.append(diagonal)

    return jnp.asarray(np.stack(generators), dtype=jnp.complex128)


def _target_endpoint_residual(
    system: ControlSystem,
    space: PulseSpace,
    reference_point: jax.Array,
) -> tuple[Callable[[jax.Array], jax.Array], complex]:
    reference = propagate(system, space.to_physical(reference_point))
    target = jnp.asarray(system.target, dtype=jnp.complex128)
    overlap = jnp.trace(target.conj().T @ reference)
    overlap_magnitude = float(np.abs(np.asarray(overlap)))
    if not np.isfinite(overlap_magnitude) or overlap_magnitude == 0.0:
        raise ValueError("accepted endpoint has no well-defined target phase")
    fixed_phase = complex(np.asarray(overlap / jnp.abs(overlap)))
    fixed_target = jax.lax.stop_gradient(target * overlap / jnp.abs(overlap))
    generators = _generalized_pauli_basis(system.dimension)
    identity = jnp.eye(system.dimension, dtype=jnp.complex128)

    def residual(candidate: jax.Array) -> jax.Array:
        endpoint = propagate(system, space.to_physical(candidate))
        relative = fixed_target.conj().T @ endpoint
        delta_a = (relative - relative.conj().T) / (2.0j)
        traceless = delta_a - (
            jnp.trace(delta_a) / jnp.float64(system.dimension)
        ) * identity
        return jnp.real(jnp.einsum("kij,ij->k", generators.conj(), traceless))

    return residual, fixed_phase


def _projected_gradient_norm(
    point: NDArray[np.float64],
    gradient: NDArray[np.float64],
) -> float:
    projected = np.array(gradient, dtype=np.float64, copy=True)
    lower_active = point <= -1.0 + 1e-10
    upper_active = point >= 1.0 - 1e-10
    projected[lower_active & (gradient > 0.0)] = 0.0
    projected[upper_active & (gradient < 0.0)] = 0.0
    return float(np.linalg.norm(projected))


def polish_endpoint(
    system: ControlSystem,
    space: PulseSpace,
    accepted: OpenLoopResult,
    *,
    max_nfev: int = 100,
) -> EndpointPolishResult:
    if not isinstance(system, ControlSystem):
        raise ValueError("system must be a ControlSystem")
    if not isinstance(space, PulseSpace):
        raise ValueError("space must be a PulseSpace")
    if not isinstance(accepted, OpenLoopResult):
        raise ValueError("accepted must be an OpenLoopResult")
    if accepted.loss > _ACCEPTANCE_LOSS or not np.isfinite(accepted.loss):
        raise ValueError("OpenLoopResult must satisfy the 1e-8 acceptance threshold")
    if (
        isinstance(max_nfev, (bool, np.bool_))
        or not isinstance(max_nfev, Integral)
        or max_nfev <= 0
    ):
        raise ValueError("max_nfev must be a positive integer")

    initial = jnp.asarray(accepted.normalized_pulse, dtype=jnp.float64)
    if initial.shape != (space.parameter_count,):
        raise ValueError("accepted pulse shape does not match the PulseSpace")
    initial_numpy = np.asarray(initial, dtype=np.float64)
    if not np.all(np.isfinite(initial_numpy)) or np.any(np.abs(initial_numpy) > 1.0):
        raise ValueError("accepted pulse must be finite and within [-1, 1]")

    residual_fn, fixed_phase = _target_endpoint_residual(
        system,
        space,
        initial,
    )
    compiled_residual = jax.jit(residual_fn).lower(initial).compile()
    compiled_jacobian = jax.jit(jax.jacrev(residual_fn)).lower(initial).compile()
    loss_fn = lambda candidate: normalized_infidelity(candidate, system, space)
    compiled_value_gradient = (
        jax.jit(jax.value_and_grad(loss_fn)).lower(initial).compile()
    )

    def scipy_residual(point: NDArray[np.float64]) -> NDArray[np.float64]:
        values = compiled_residual(jnp.asarray(point, dtype=jnp.float64))
        return np.ascontiguousarray(np.asarray(values, dtype=np.float64))

    def scipy_jacobian(point: NDArray[np.float64]) -> NDArray[np.float64]:
        values = compiled_jacobian(jnp.asarray(point, dtype=jnp.float64))
        return np.ascontiguousarray(np.asarray(values, dtype=np.float64))

    def diagnostics(
        point: NDArray[np.float64],
        *,
        evaluations: int,
        jacobian_evaluations: int,
        status: int,
        message: str,
        cost: float,
        optimality: float,
        solver_success: bool,
    ) -> EndpointPolishResult:
        finite_and_bounded = bool(
            point.shape == (space.parameter_count,)
            and np.all(np.isfinite(point))
            and np.all(np.abs(point) <= 1.0)
        )
        if finite_and_bounded:
            value, gradient_array = compiled_value_gradient(
                jnp.asarray(point, dtype=jnp.float64)
            )
            gradient = np.asarray(gradient_array, dtype=np.float64)
            loss = float(value)
            gradient_norm = float(np.linalg.norm(gradient))
            projected_gradient_norm = _projected_gradient_norm(point, gradient)
            residual_norm = float(np.linalg.norm(scipy_residual(point)))
            endpoint = propagate(system, space.to_physical(point))
            overlap = np.trace(system.target.conj().T @ np.asarray(endpoint))
            phase_consistency_error = abs(abs(overlap) / system.dimension - 1.0)
        else:
            loss = float("inf")
            gradient_norm = float("inf")
            projected_gradient_norm = float("inf")
            residual_norm = float("inf")
            phase_consistency_error = float("inf")

        converged = bool(
            solver_success
            and finite_and_bounded
            and np.isfinite(loss)
            and loss <= _POLISH_LOSS_TOLERANCE
            and gradient_norm <= _POLISH_GRADIENT_TOLERANCE
            and projected_gradient_norm <= _POLISH_GRADIENT_TOLERANCE
            and residual_norm <= _POLISH_RESIDUAL_TOLERANCE
            and phase_consistency_error <= _POLISH_PHASE_TOLERANCE
        )
        return EndpointPolishResult(
            normalized_pulse=tuple(float(value) for value in point),
            loss=loss,
            gradient_norm=gradient_norm,
            projected_gradient_norm=projected_gradient_norm,
            residual_norm=residual_norm,
            phase_consistency_error=float(phase_consistency_error),
            evaluations=evaluations,
            jacobian_evaluations=jacobian_evaluations,
            status=status,
            message=message,
            cost=cost,
            optimality=optimality,
            step_norm=float(np.linalg.norm(point - initial_numpy)),
            converged=converged,
            source_loss=float(accepted.loss),
            source_gradient_norm=float(accepted.gradient_norm),
            duration=system.duration,
            fixed_phase_real=float(fixed_phase.real),
            fixed_phase_imag=float(fixed_phase.imag),
        )

    try:
        solver = least_squares(
            scipy_residual,
            initial_numpy,
            jac=scipy_jacobian,
            bounds=(-1.0, 1.0),
            method="trf",
            tr_solver="lsmr",
            x_scale="jac",
            ftol=1e-15,
            xtol=1e-15,
            gtol=1e-15,
            max_nfev=int(max_nfev),
        )
    except Exception as error:
        failed = diagnostics(
            initial_numpy,
            evaluations=0,
            jacobian_evaluations=0,
            status=-1,
            message=f"{type(error).__name__}: {error}",
            cost=float("inf"),
            optimality=float("inf"),
            solver_success=False,
        )
        raise EndpointPolishingError(
            f"endpoint polishing solver failed: {error}",
            failed,
        ) from error

    candidate = np.asarray(solver.x, dtype=np.float64)
    result = diagnostics(
        candidate,
        evaluations=int(solver.nfev),
        jacobian_evaluations=int(solver.njev or 0),
        status=int(solver.status),
        message=str(solver.message),
        cost=float(solver.cost),
        optimality=float(solver.optimality),
        solver_success=bool(solver.success),
    )
    if candidate.shape != (space.parameter_count,) or not np.all(
        np.isfinite(candidate)
    ):
        raise EndpointPolishingError(
            "endpoint polishing returned a nonfinite or malformed candidate",
            result,
        )
    if np.any(np.abs(candidate) > 1.0):
        raise EndpointPolishingError(
            "endpoint polishing candidate violates normalized bounds",
            result,
        )
    if (
        result.loss > _POLISH_LOSS_TOLERANCE
        or result.phase_consistency_error > _POLISH_PHASE_TOLERANCE
    ):
        raise EndpointPolishingError(
            "endpoint polishing reached an inconsistent target/global phase",
            result,
        )
    if not result.converged:
        raise EndpointPolishingError(
            "endpoint polishing did not converge to stationarity",
            result,
        )
    return result


def endpoint_jacobian(
    system: ControlSystem,
    space: PulseSpace,
    point: object,
) -> NDArray[np.float64]:
    if not isinstance(system, ControlSystem):
        raise ValueError("system must be a ControlSystem")
    if not isinstance(space, PulseSpace):
        raise ValueError("space must be a PulseSpace")
    if space.control_count != len(system.controls):
        raise ValueError("pulse space control count does not match the system")

    point_array = jnp.asarray(point)
    if jnp.iscomplexobj(point_array) or point_array.shape != (space.parameter_count,):
        raise ValueError(
            f"point must be a real vector with shape ({space.parameter_count},)"
        )
    point_array = jnp.asarray(point_array, dtype=jnp.float64)
    concrete_point = np.asarray(point_array)
    if not np.all(np.isfinite(concrete_point)):
        raise ValueError("point must contain only finite values")
    if np.any(np.abs(concrete_point) > 1.0):
        raise ValueError("point exceeds the normalized pulse bounds")

    reference = jax.lax.stop_gradient(
        propagate(system, space.to_physical(point_array))
    )
    generators = _generalized_pauli_basis(system.dimension)
    identity = jnp.eye(system.dimension, dtype=jnp.complex128)

    def endpoint_coordinates(candidate: jax.Array) -> jax.Array:
        endpoint = propagate(system, space.to_physical(candidate))
        relative = reference.conj().T @ endpoint
        delta_a = (relative - relative.conj().T) / (2.0j)
        traceless = delta_a - (
            jnp.trace(delta_a) / jnp.float64(system.dimension)
        ) * identity
        return jnp.real(jnp.einsum("kij,ij->k", generators.conj(), traceless))

    jacobian = jax.jacrev(endpoint_coordinates)(point_array)
    return np.asarray(jacobian, dtype=np.float64)


def _relative_ranks(values: NDArray[np.float64]) -> RankMap:
    magnitudes = np.abs(np.asarray(values, dtype=np.float64))
    scale = float(np.max(magnitudes, initial=0.0))
    if not np.isfinite(scale) or scale == 0.0:
        return {threshold: 0 for threshold in _RANK_THRESHOLDS}
    return {
        threshold: int(np.count_nonzero(magnitudes > threshold * scale))
        for threshold in _RANK_THRESHOLDS
    }


def _orthonormalize(columns: NDArray[np.float64]) -> NDArray[np.float64]:
    if columns.shape[1] == 0:
        return np.empty((columns.shape[0], 0), dtype=np.float64)
    basis, _ = np.linalg.qr(np.asarray(columns, dtype=np.float64), mode="reduced")
    return np.asarray(basis, dtype=np.float64)


def _subspace_diagnostics(
    left: NDArray[np.float64],
    right: NDArray[np.float64],
) -> tuple[float, NDArray[np.float64]]:
    left_basis = _orthonormalize(left)
    right_basis = _orthonormalize(right)
    if left_basis.shape[1] != right_basis.shape[1]:
        raise ValueError("subspaces must have the same dimension")
    if left_basis.shape[1] == 0:
        return 0.0, np.empty(0, dtype=np.float64)
    left_projector = left_basis @ left_basis.T
    right_projector = right_basis @ right_basis.T
    residual = float(np.linalg.norm(left_projector - right_projector, ord=2))
    cosines = np.linalg.svd(left_basis.T @ right_basis, compute_uv=False)
    angles = np.arccos(np.clip(cosines, 0.0, 1.0))
    return residual, np.sort(np.asarray(angles, dtype=np.float64))[::-1]


def _leading_eigenpairs(
    loss_fn: Callable[[jax.Array], jax.Array],
    point: jax.Array,
    count: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    parameter_count = int(point.size)
    if count >= parameter_count:
        raise ValueError("leading_count must be smaller than the parameter count")

    compiled_hvp = jax.jit(
        lambda vector: hessian_vector_product(loss_fn, point, vector)
    ).lower(jnp.zeros_like(point)).compile()

    def matrix_vector(vector: NDArray[np.float64]) -> NDArray[np.float64]:
        product = compiled_hvp(jnp.asarray(vector, dtype=jnp.float64))
        return np.ascontiguousarray(np.asarray(product, dtype=np.float64))

    operator = LinearOperator(
        shape=(parameter_count, parameter_count),
        matvec=matrix_vector,
        rmatvec=matrix_vector,
        dtype=np.dtype(np.float64),
    )
    initial = np.linspace(-1.0, 1.0, parameter_count, dtype=np.float64)
    initial /= np.linalg.norm(initial)
    values, vectors = eigsh(
        operator,
        k=count,
        which="LA",
        v0=initial,
        ncv=min(parameter_count, max(2 * count + 1, 20)),
        tol=1e-12,
        maxiter=max(1000, 20 * parameter_count),
    )
    order = np.argsort(values)[::-1]
    return (
        np.asarray(values[order], dtype=np.float64),
        _orthonormalize(np.asarray(vectors[:, order], dtype=np.float64)),
    )


def analyze_landscape(
    system: ControlSystem,
    space: PulseSpace,
    accepted: OpenLoopResult,
    *,
    leading_count: int,
    dense_validation: bool = True,
    polish: bool = True,
) -> LandscapeResult:
    if not isinstance(system, ControlSystem):
        raise ValueError("system must be a ControlSystem")
    if not isinstance(space, PulseSpace):
        raise ValueError("space must be a PulseSpace")
    if not isinstance(accepted, OpenLoopResult):
        raise ValueError("accepted must be an OpenLoopResult")
    if accepted.loss > _ACCEPTANCE_LOSS or not np.isfinite(accepted.loss):
        raise ValueError("OpenLoopResult must satisfy the 1e-8 acceptance threshold")
    if (
        isinstance(leading_count, (bool, np.bool_))
        or not isinstance(leading_count, Integral)
        or leading_count <= 0
    ):
        raise ValueError("leading_count must be a positive integer")
    leading_count = int(leading_count)
    if not isinstance(polish, (bool, np.bool_)):
        raise ValueError("polish must be a boolean")

    polishing = polish_endpoint(system, space, accepted) if polish else None
    source_point = (
        polishing.normalized_pulse
        if polishing is not None
        else accepted.normalized_pulse
    )
    point = jnp.asarray(source_point, dtype=jnp.float64)
    if point.shape != (space.parameter_count,):
        raise ValueError("accepted pulse shape does not match the PulseSpace")
    if leading_count >= space.parameter_count:
        raise ValueError("leading_count must be smaller than the parameter count")

    loss_fn = lambda candidate: normalized_infidelity(candidate, system, space)
    leading_values, leading_vectors = _leading_eigenpairs(
        loss_fn,
        point,
        leading_count,
    )
    jacobian = endpoint_jacobian(system, space, point)
    _, singular_values, right_vectors_transpose = np.linalg.svd(
        jacobian,
        full_matrices=False,
    )
    jacobian_ranks = _relative_ranks(singular_values)
    endpoint_basis = _orthonormalize(right_vectors_transpose.T)

    dense_matrix: NDArray[np.float64] | None = None
    dense_values: NDArray[np.float64] | None = None
    dense_vectors: NDArray[np.float64] | None = None
    projector_residuals: dict[float, float] = {}
    principal_angles: AngleMap = {}
    if dense_validation:
        dense_matrix = dense_hessian(loss_fn, point)
        ascending_values, ascending_vectors = np.linalg.eigh(dense_matrix)
        order = np.argsort(ascending_values)[::-1]
        dense_values = np.asarray(ascending_values[order], dtype=np.float64)
        dense_vectors = np.asarray(ascending_vectors[:, order], dtype=np.float64)
        hessian_ranks = _relative_ranks(dense_values)
        hessian_rank_is_lower_bound = {
            threshold: False for threshold in _RANK_THRESHOLDS
        }
        for threshold, rank in hessian_ranks.items():
            if rank > leading_count:
                continue
            residual, angles = _subspace_diagnostics(
                dense_vectors[:, :rank],
                leading_vectors[:, :rank],
            )
            projector_residuals[threshold] = residual
            principal_angles[threshold] = angles
    else:
        hessian_ranks = _relative_ranks(leading_values)
        hessian_rank_is_lower_bound = {
            threshold: rank == leading_count
            for threshold, rank in hessian_ranks.items()
        }

    return LandscapeResult(
        leading_eigenvalues=leading_values,
        leading_eigenvectors=leading_vectors,
        jacobian_singular_values=np.asarray(singular_values, dtype=np.float64),
        hessian_ranks=hessian_ranks,
        hessian_rank_is_lower_bound=hessian_rank_is_lower_bound,
        jacobian_ranks=jacobian_ranks,
        model_basis=leading_vectors,
        endpoint_basis=endpoint_basis,
        dense_hessian=dense_matrix,
        dense_eigenvalues=dense_values,
        dense_eigenvectors=dense_vectors,
        dense_hvp_projector_residuals=projector_residuals,
        dense_hvp_principal_angles=principal_angles,
        polishing=polishing,
    )
