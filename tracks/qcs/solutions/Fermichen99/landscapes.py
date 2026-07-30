"""Landscape and subspace diagnostics for the sim-to-real control study."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp
import numpy as np
from scipy.sparse.linalg import LinearOperator, eigsh

from sim_to_real import Array, ControlProblem, make_propagator


@dataclass(frozen=True)
class SubspaceMetrics:
    """Principal-angle summary for two equal-column orthonormal bases."""

    mean_overlap: float
    minimum_overlap: float
    largest_angle_degrees: float


def traceless_hermitian_basis(dim: int) -> Array:
    """Return an orthonormal generalized Gell-Mann basis for su(dim).

    Every basis matrix is Hermitian and traceless, with
    ``Tr(B_a^dagger B_b) = delta_ab``.
    """

    if dim < 2:
        raise ValueError("dim must be at least two")
    basis: list[np.ndarray] = []

    for row in range(dim):
        for col in range(row + 1, dim):
            symmetric = np.zeros((dim, dim), dtype=np.complex128)
            symmetric[row, col] = 1.0 / np.sqrt(2.0)
            symmetric[col, row] = 1.0 / np.sqrt(2.0)
            basis.append(symmetric)

            antisymmetric = np.zeros((dim, dim), dtype=np.complex128)
            antisymmetric[row, col] = -1j / np.sqrt(2.0)
            antisymmetric[col, row] = 1j / np.sqrt(2.0)
            basis.append(antisymmetric)

    for count in range(1, dim):
        diagonal = np.zeros((dim, dim), dtype=np.complex128)
        normalization = np.sqrt(count * (count + 1.0))
        diagonal[np.arange(count), np.arange(count)] = 1.0 / normalization
        diagonal[count, count] = -count / normalization
        basis.append(diagonal)

    return jnp.asarray(np.stack(basis), dtype=jnp.complex128)


def endpoint_coordinates(
    problem: ControlProblem,
    params: Array,
    *,
    n_steps: int = 100,
) -> Array:
    """Map the final gate to local traceless-Hermitian coordinates.

    The relative unitary is phase-aligned before extracting its anti-Hermitian
    tangent.  At the target this gives the d^2-1 physical endpoint directions
    while removing global phase.
    """

    unitary = make_propagator(problem, integrator="expm", n_steps=n_steps)(params)
    relative = problem.target.conj().T @ unitary
    phase = jnp.angle(jnp.trace(relative))
    relative = relative * jnp.exp(-1j * phase)
    tangent = (relative - relative.conj().T) / (2j)
    basis = traceless_hermitian_basis(problem.dim)
    return jnp.real(jnp.einsum("aij,ij->a", basis.conj(), tangent))


def endpoint_jacobian(
    problem: ControlProblem,
    params: Array,
    *,
    n_steps: int = 100,
) -> Array:
    coordinate_fn = lambda theta: endpoint_coordinates(
        problem, theta, n_steps=n_steps
    )
    return jax.jacrev(coordinate_fn)(params)


def explicit_hessian(loss_fn: Callable[[Array], Array], params: Array) -> Array:
    return jax.hessian(loss_fn)(params)


def hessian_vector_product(
    loss_fn: Callable[[Array], Array],
    params: Array,
    vector: Array,
) -> Array:
    """Forward-over-reverse Hessian-vector product."""

    return jax.jvp(jax.grad(loss_fn), (params,), (vector,))[1]


def krylov_hessian_eigensystem(
    loss_fn: Callable[[Array], Array],
    params: Array,
    dimension: int,
    *,
    tolerance: float = 1e-8,
    maxiter: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Top Hessian eigenpairs using only autodiff HVPs.

    This is the scalable stage-2 extractor: SciPy's symmetric Krylov solver
    sees a linear operator and never materializes the full Hessian.
    """

    params_jax = jnp.asarray(params, dtype=jnp.float64)
    ambient_dimension = int(params_jax.size)
    if dimension <= 0 or dimension >= ambient_dimension:
        raise ValueError("dimension must lie between 1 and n_params-1")
    compiled_hvp = jax.jit(
        lambda vector: hessian_vector_product(
            loss_fn, params_jax, vector
        )
    )

    def matvec(vector: np.ndarray) -> np.ndarray:
        product = compiled_hvp(jnp.asarray(vector, dtype=jnp.float64))
        return np.asarray(product, dtype=np.float64)

    operator = LinearOperator(
        shape=(ambient_dimension, ambient_dimension),
        matvec=matvec,
        dtype=np.float64,
    )
    eigenvalues, eigenvectors = eigsh(
        operator,
        k=dimension,
        which="LA",
        tol=tolerance,
        maxiter=maxiter,
    )
    order = np.argsort(eigenvalues)[::-1]
    return eigenvalues[order], eigenvectors[:, order]


def sorted_eigensystem(matrix: Array) -> tuple[Array, Array]:
    """Eigenpairs sorted from largest to smallest algebraic eigenvalue."""

    eigenvalues, eigenvectors = jnp.linalg.eigh(matrix)
    order = jnp.argsort(eigenvalues)[::-1]
    return eigenvalues[order], eigenvectors[:, order]


def hessian_subspace(
    hessian: Array,
    dimension: int,
    *,
    largest: bool = True,
) -> tuple[Array, Array]:
    eigenvalues, eigenvectors = sorted_eigensystem(hessian)
    if dimension <= 0 or dimension > eigenvectors.shape[1]:
        raise ValueError("invalid subspace dimension")
    if largest:
        return eigenvalues[:dimension], eigenvectors[:, :dimension]
    return eigenvalues[-dimension:], eigenvectors[:, -dimension:]


def jacobian_subspace(
    jacobian: Array,
    dimension: int,
) -> tuple[Array, Array]:
    """Return singular values and leading right-singular parameter directions."""

    _, singular_values, right_vectors_h = jnp.linalg.svd(
        jacobian, full_matrices=True
    )
    if dimension <= 0 or dimension > right_vectors_h.shape[0]:
        raise ValueError("invalid subspace dimension")
    return singular_values, right_vectors_h.conj().T[:, :dimension]


def stacked_jacobian_subspace(
    jacobians: Array | np.ndarray,
    dimension: int,
    *,
    normalize_blocks: bool = True,
    weights: Array | np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Build model-uncertainty-robust directions from stacked Jacobians.

    The input has shape ``(n_models, n_generators, n_params)``.  Normalizing
    each model block gives every plausible model equal influence regardless of
    its local endpoint sensitivity.  The resulting right singular vectors are
    also the leading eigendirections of ``sum_m w_m J_m.T @ J_m``.
    """

    blocks = np.asarray(jacobians, dtype=np.float64)
    if blocks.ndim != 3:
        raise ValueError("jacobians must have shape (models, rows, parameters)")
    n_models, _, n_params = blocks.shape
    if n_models <= 0 or dimension <= 0 or dimension > n_params:
        raise ValueError("invalid ensemble or subspace dimension")

    scaled = blocks.copy()
    if normalize_blocks:
        norms = np.linalg.norm(scaled, axis=(1, 2))
        if np.any(norms <= 0.0):
            raise ValueError("Jacobian blocks must have nonzero norm")
        scaled /= norms[:, None, None]
    if weights is not None:
        weights_np = np.asarray(weights, dtype=np.float64)
        if weights_np.shape != (n_models,) or np.any(weights_np < 0.0):
            raise ValueError("weights must be non-negative per-model values")
        if not np.any(weights_np > 0.0):
            raise ValueError("at least one weight must be positive")
        scaled *= np.sqrt(weights_np)[:, None, None]

    stacked = scaled.reshape(-1, n_params)
    _, singular_values, right_vectors_h = np.linalg.svd(
        stacked,
        full_matrices=True,
    )
    return singular_values, right_vectors_h.T[:, :dimension]


def random_subspace(
    ambient_dimension: int,
    dimension: int,
    *,
    seed: int,
) -> Array:
    if dimension <= 0 or dimension > ambient_dimension:
        raise ValueError("invalid subspace dimension")
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(ambient_dimension, dimension))
    orthonormal, _ = np.linalg.qr(matrix)
    return jnp.asarray(orthonormal[:, :dimension], dtype=jnp.float64)


def subspace_metrics(left: Array, right: Array) -> SubspaceMetrics:
    """Compare two subspaces through squared cosines of principal angles."""

    if left.shape != right.shape:
        raise ValueError("subspace bases must have the same shape")
    left_np = np.array(left, dtype=np.float64, copy=True)
    right_np = np.array(right, dtype=np.float64, copy=True)
    overlap_matrix = np.einsum(
        "ik,il->kl", left_np, right_np, optimize=False
    )
    singular_values = np.linalg.svd(overlap_matrix, compute_uv=False)
    singular_values = np.clip(singular_values, 0.0, 1.0)
    overlaps = singular_values**2
    largest_angle = np.degrees(np.arccos(np.min(singular_values)))
    return SubspaceMetrics(
        mean_overlap=float(np.mean(overlaps)),
        minimum_overlap=float(np.min(overlaps)),
        largest_angle_degrees=float(largest_angle),
    )


def coverage_spectrum(reference: Array, candidate: Array) -> np.ndarray:
    """Return how well a candidate space covers every reference direction.

    ``reference`` has ``r`` orthonormal columns and defines the physical
    directions that must be covered. ``candidate`` may have any number of
    orthonormal columns. The returned ``r`` squared principal cosines lie in
    ``[0, 1]``; missing dimensions are padded with zeros. Consequently, the
    smallest value is a worst-case coverage certificate for every linear
    combination in the reference space.
    """

    reference_np = np.asarray(reference, dtype=np.float64)
    candidate_np = np.asarray(candidate, dtype=np.float64)
    if reference_np.ndim != 2 or candidate_np.ndim != 2:
        raise ValueError("subspace bases must be matrices")
    if reference_np.shape[0] != candidate_np.shape[0]:
        raise ValueError("subspace bases must share an ambient dimension")
    reference_rank = reference_np.shape[1]
    if reference_rank <= 0 or candidate_np.shape[1] <= 0:
        raise ValueError("subspace bases must have at least one column")

    overlap = np.einsum(
        "ir,ik->rk",
        reference_np,
        candidate_np,
        optimize=False,
    )
    singular_values = np.linalg.svd(overlap, compute_uv=False)
    squared_cosines = np.zeros(reference_rank, dtype=np.float64)
    squared_cosines[: singular_values.size] = np.clip(
        singular_values, 0.0, 1.0
    ) ** 2
    return squared_cosines


def projection_fraction(vector: Array, basis: Array) -> float:
    """Fraction of squared vector norm captured by an orthonormal basis."""

    vector_np = np.asarray(vector)
    basis_np = np.asarray(basis)
    denominator = float(np.vdot(vector_np, vector_np).real)
    if denominator == 0.0:
        return 1.0
    coefficients = basis_np.conj().T @ vector_np
    numerator = float(np.vdot(coefficients, coefficients).real)
    return numerator / denominator
