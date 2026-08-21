"""Exactly degenerate frustration-free parent families.

The construction acts on the projected one-particle orbital space with a
smooth invertible map ``V(lambda)``.  If the undeformed local pair fields are
encoded by the coefficient frame ``U``, the deformed constraints use
``U @ V(lambda)^{-1}``.  Their common kernel is the exact bosonic Fock lift
``Gamma_N(V) ker(C_0)``.  Consequently every point of the family has the same
nullity and zero internal bandwidth even though the excited spectrum and the
embedded projector may move.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
from scipy import sparse
from scipy.linalg import expm
from scipy.sparse.linalg import eigsh, expm_multiply

from .lattice import (
    BosonBasis,
    KapitLaughlinParent,
    manybody_one_body_operator,
)


@dataclass(frozen=True)
class ProtectedParentPoint:
    """One point of the two-parameter protected parent family."""

    lambda_x: float
    lambda_y: float
    generator_x: np.ndarray
    generator_y: np.ndarray
    onebody_map: np.ndarray
    inverse_map: np.ndarray
    coefficient_frame: np.ndarray
    constraints: sparse.csr_matrix
    parent: sparse.csr_matrix


@dataclass(frozen=True)
class ProtectedPointAudit:
    """Numerical invariants at one protected-family point."""

    lambda_x: float
    lambda_y: float
    observed_rank: int
    kernel_residual: float
    internal_bandwidth: float
    external_gap: float
    projector_distance: float
    locality_second_moment: float
    map_condition_number: float


@dataclass(frozen=True)
class ProtectedFamilyAudit:
    """Aggregate exact-degeneracy and locality audit."""

    points: tuple[ProtectedPointAudit, ...]
    generator_commutator_norm: float
    maximum_traceless_fiber_tangent_norm: float
    maximum_kernel_residual: float
    maximum_internal_bandwidth: float
    minimum_external_gap: float
    maximum_projector_distance: float
    maximum_locality_ratio: float
    constant_nullity: bool


def _append_sparse_column_block(
    rows: list[int],
    columns: list[int],
    data: list[complex],
    coefficients: np.ndarray,
    intermediate_index: int,
    intermediate_dimension: int,
    column: int,
    amplitude_cutoff: float,
) -> None:
    active = np.flatnonzero(np.abs(coefficients) > amplitude_cutoff)
    if active.size == 0:
        return
    rows.extend(
        (active * intermediate_dimension + intermediate_index).tolist()
    )
    columns.extend([column] * int(active.size))
    data.extend(np.asarray(coefficients)[active].tolist())


def pair_annihilation_constraints(
    basis: BosonBasis,
    coefficient_frame: np.ndarray,
    onsite_u: float = 1.0,
    amplitude_cutoff: float = 1e-14,
) -> tuple[sparse.csr_matrix, BosonBasis]:
    """Return pair constraints for a full-rank, nonorthogonal frame."""

    frame = np.asarray(coefficient_frame, dtype=complex)
    if basis.n_particles < 2:
        raise ValueError("pair constraints require at least two particles")
    if frame.ndim != 2 or frame.shape[1] != basis.n_orbitals:
        raise ValueError("coefficient frame and basis disagree")
    if onsite_u <= 0.0:
        raise ValueError("onsite_u must be positive")
    if np.linalg.matrix_rank(frame) != basis.n_orbitals:
        raise ValueError("coefficient frame must have full column rank")
    intermediate = BosonBasis(
        basis.n_orbitals, basis.n_particles - 2
    )
    physical_sites = frame.shape[0]
    rows: list[int] = []
    columns: list[int] = []
    data: list[complex] = []
    prefactor = sqrt(0.5 * float(onsite_u))
    for column, state in enumerate(basis.states):
        for left in range(basis.n_orbitals):
            if state[left] >= 2:
                updated = list(state)
                updated[left] -= 2
                intermediate_index = intermediate.index[tuple(updated)]
                occupation_factor = sqrt(
                    state[left] * (state[left] - 1)
                )
                _append_sparse_column_block(
                    rows,
                    columns,
                    data,
                    prefactor * frame[:, left] ** 2 * occupation_factor,
                    intermediate_index,
                    intermediate.dimension,
                    column,
                    amplitude_cutoff,
                )
            if state[left] == 0:
                continue
            for right in range(left + 1, basis.n_orbitals):
                if state[right] == 0:
                    continue
                updated = list(state)
                updated[left] -= 1
                updated[right] -= 1
                intermediate_index = intermediate.index[tuple(updated)]
                occupation_factor = sqrt(state[left] * state[right])
                _append_sparse_column_block(
                    rows,
                    columns,
                    data,
                    2.0
                    * prefactor
                    * frame[:, left]
                    * frame[:, right]
                    * occupation_factor,
                    intermediate_index,
                    intermediate.dimension,
                    column,
                    amplitude_cutoff,
                )
    constraints = sparse.coo_matrix(
        (np.asarray(data, dtype=complex), (rows, columns)),
        shape=(
            physical_sites * intermediate.dimension,
            basis.dimension,
        ),
    ).tocsr()
    constraints.sum_duplicates()
    return constraints, intermediate


def pair_annihilation_constraint_derivative(
    basis: BosonBasis,
    coefficient_frame: np.ndarray,
    frame_derivative: np.ndarray,
    onsite_u: float = 1.0,
    amplitude_cutoff: float = 1e-14,
) -> sparse.csr_matrix:
    """Differentiate stacked pair constraints with respect to their frame."""

    frame = np.asarray(coefficient_frame, dtype=complex)
    derivative = np.asarray(frame_derivative, dtype=complex)
    if basis.n_particles < 2:
        raise ValueError("pair constraints require at least two particles")
    if frame.shape != derivative.shape or frame.ndim != 2:
        raise ValueError("coefficient frame and derivative must agree")
    if frame.shape[1] != basis.n_orbitals:
        raise ValueError("coefficient frame and basis disagree")
    if onsite_u <= 0.0:
        raise ValueError("onsite_u must be positive")
    intermediate = BosonBasis(
        basis.n_orbitals, basis.n_particles - 2
    )
    physical_sites = frame.shape[0]
    rows: list[int] = []
    columns: list[int] = []
    data: list[complex] = []
    prefactor = sqrt(0.5 * float(onsite_u))
    for column, state in enumerate(basis.states):
        for left in range(basis.n_orbitals):
            if state[left] >= 2:
                updated = list(state)
                updated[left] -= 2
                intermediate_index = intermediate.index[tuple(updated)]
                occupation_factor = sqrt(
                    state[left] * (state[left] - 1)
                )
                _append_sparse_column_block(
                    rows,
                    columns,
                    data,
                    2.0
                    * prefactor
                    * frame[:, left]
                    * derivative[:, left]
                    * occupation_factor,
                    intermediate_index,
                    intermediate.dimension,
                    column,
                    amplitude_cutoff,
                )
            if state[left] == 0:
                continue
            for right in range(left + 1, basis.n_orbitals):
                if state[right] == 0:
                    continue
                updated = list(state)
                updated[left] -= 1
                updated[right] -= 1
                intermediate_index = intermediate.index[tuple(updated)]
                occupation_factor = sqrt(state[left] * state[right])
                _append_sparse_column_block(
                    rows,
                    columns,
                    data,
                    2.0
                    * prefactor
                    * (
                        derivative[:, left] * frame[:, right]
                        + frame[:, left] * derivative[:, right]
                    )
                    * occupation_factor,
                    intermediate_index,
                    intermediate.dimension,
                    column,
                    amplitude_cutoff,
                )
    tangent = sparse.coo_matrix(
        (np.asarray(data, dtype=complex), (rows, columns)),
        shape=(
            physical_sites * intermediate.dimension,
            basis.dimension,
        ),
    ).tocsr()
    tangent.sum_duplicates()
    return tangent


def _normalize_hermitian_generator(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=complex)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError("generator must be square")
    values = 0.5 * (values + values.conj().T)
    values -= np.trace(values) * np.eye(values.shape[0]) / values.shape[0]
    norm = float(np.linalg.norm(values))
    if norm <= 1e-14:
        raise ValueError("projected local generator is numerically null")
    return values / norm


def projected_local_generator_pair(
    system: KapitLaughlinParent,
) -> tuple[np.ndarray, np.ndarray]:
    """Return two deterministic noncommuting projected onsite generators.

    Each generator is the band projection of a strictly onsite physical
    potential.  Mixed harmonics avoid special translation-sector zeros while
    keeping the prescription fixed across particle number and lattice size.
    """

    length = int(system.length)
    coordinates = np.arange(length, dtype=float)
    x = np.tile(coordinates, length)
    y = np.repeat(coordinates, length)
    angle = 2.0 * np.pi / length
    field_x = np.cos(angle * x) + 0.37 * np.sin(angle * (x + y))
    field_y = np.cos(angle * y) + 0.41 * np.sin(angle * (x - 2.0 * y))
    field_x -= np.mean(field_x)
    field_y -= np.mean(field_y)
    return (
        projected_onsite_generator(system, field_x),
        projected_onsite_generator(system, field_y),
    )


def projected_onsite_generator(
    system: KapitLaughlinParent,
    potential: np.ndarray,
) -> np.ndarray:
    """Project and normalize one strictly onsite physical generator."""

    values = np.asarray(potential, dtype=float)
    physical_sites = system.orbitals.shape[0]
    if values.shape != (physical_sites,) or not np.all(np.isfinite(values)):
        raise ValueError("onsite generator has the wrong shape or values")
    values = values - np.mean(values)
    orbitals = np.asarray(system.orbitals, dtype=complex)
    projected = orbitals.conj().T @ (values[:, None] * orbitals)
    return _normalize_hermitian_generator(projected)


def protected_parent_point(
    system: KapitLaughlinParent,
    lambda_x: float,
    lambda_y: float,
    generators: tuple[np.ndarray, np.ndarray] | None = None,
) -> ProtectedParentPoint:
    """Construct one positive frustration-free protected parent."""

    generator_x, generator_y = (
        projected_local_generator_pair(system)
        if generators is None
        else generators
    )
    generator_x = np.asarray(generator_x, dtype=complex)
    generator_y = np.asarray(generator_y, dtype=complex)
    expected = (system.n_flux, system.n_flux)
    if generator_x.shape != expected or generator_y.shape != expected:
        raise ValueError("protected generators have the wrong shape")
    for generator in (generator_x, generator_y):
        if not np.allclose(generator, generator.conj().T, atol=1e-11):
            raise ValueError("protected generators must be Hermitian")
    exponent = float(lambda_x) * generator_x + float(lambda_y) * generator_y
    onebody_map = expm(exponent)
    inverse_map = expm(-exponent)
    inverse_error = float(
        np.linalg.norm(onebody_map @ inverse_map - np.eye(system.n_flux))
    )
    if inverse_error > 1e-10:
        raise RuntimeError("one-body deformation lost invertibility")
    coefficient_frame = np.asarray(system.orbitals) @ inverse_map
    constraints, _ = pair_annihilation_constraints(
        system.basis,
        coefficient_frame,
    )
    parent = (constraints.conj().T @ constraints).tocsr()
    parent.sum_duplicates()
    return ProtectedParentPoint(
        lambda_x=float(lambda_x),
        lambda_y=float(lambda_y),
        generator_x=generator_x,
        generator_y=generator_y,
        onebody_map=onebody_map,
        inverse_map=inverse_map,
        coefficient_frame=coefficient_frame,
        constraints=constraints,
        parent=parent,
    )


def transported_kernel_frame(
    basis: BosonBasis,
    base_frame: np.ndarray,
    generator: np.ndarray,
) -> np.ndarray:
    """Apply ``Gamma_N(exp(generator))`` and orthonormalize its image."""

    values = np.asarray(generator, dtype=complex)
    if not np.allclose(values, values.conj().T, atol=1e-11):
        raise ValueError("transport generator must be Hermitian")
    fock_generator = manybody_one_body_operator(basis, values)
    transported = expm_multiply(fock_generator, np.asarray(base_frame))
    frame, _ = np.linalg.qr(transported)
    return np.asarray(frame, dtype=complex)


def _projector_distance(left: np.ndarray, right: np.ndarray) -> float:
    rank = left.shape[1]
    overlap = left.conj().T @ right
    value = rank - float(np.linalg.norm(overlap) ** 2)
    return float(np.sqrt(max(value, 0.0) / rank))


def _locality_second_moment(
    system: KapitLaughlinParent,
    inverse_map: np.ndarray,
) -> float:
    """Return the mean-square torus range of the deformed projected field."""

    orbitals = np.asarray(system.orbitals, dtype=complex)
    physical_kernel = orbitals @ inverse_map @ orbitals.conj().T
    length = int(system.length)
    total = 0.0
    weighted = 0.0
    for left in range(length * length):
        x_left, y_left = left % length, left // length
        for right in range(length * length):
            x_right, y_right = right % length, right // length
            dx = min(abs(x_left - x_right), length - abs(x_left - x_right))
            dy = min(abs(y_left - y_right), length - abs(y_left - y_right))
            weight = float(abs(physical_kernel[left, right]) ** 2)
            total += weight
            weighted += weight * (dx * dx + dy * dy)
    if total <= 0.0:
        raise RuntimeError("deformed physical kernel has zero norm")
    return weighted / total


def _dense_or_sparse_low_spectrum(
    parent: sparse.csr_matrix,
    rank: int,
) -> np.ndarray:
    dimension = parent.shape[0]
    count = rank + 2
    if dimension <= 2_000:
        values = np.linalg.eigvalsh(parent.toarray())
        return np.asarray(values[:count], dtype=float)
    values = eigsh(
        parent,
        k=count,
        which="SM",
        return_eigenvectors=False,
        tol=1e-10,
        maxiter=20_000,
        ncv=min(dimension, max(2 * count + 1, 100)),
    )
    return np.sort(np.real(values))


def _point_audit(
    system: KapitLaughlinParent,
    point: ProtectedParentPoint,
    base_frame: np.ndarray,
    expected_rank: int,
) -> tuple[ProtectedPointAudit, np.ndarray]:
    exponent = (
        point.lambda_x * point.generator_x
        + point.lambda_y * point.generator_y
    )
    frame = transported_kernel_frame(system.basis, base_frame, exponent)
    constraint_residual = float(np.linalg.norm(point.constraints @ frame))
    rayleigh = frame.conj().T @ (point.parent @ frame)
    rayleigh = 0.5 * (rayleigh + rayleigh.conj().T)
    internal = np.linalg.eigvalsh(rayleigh)
    spectrum = _dense_or_sparse_low_spectrum(point.parent, expected_rank)
    tolerance = 1e-9 * max(float(np.max(np.abs(spectrum))), 1.0)
    observed = int(np.count_nonzero(np.abs(spectrum) < tolerance))
    if observed >= spectrum.size:
        gap = 0.0
    else:
        gap = float(spectrum[observed] - spectrum[observed - 1])
    audit = ProtectedPointAudit(
        lambda_x=point.lambda_x,
        lambda_y=point.lambda_y,
        observed_rank=observed,
        kernel_residual=constraint_residual,
        internal_bandwidth=float(np.ptp(internal)),
        external_gap=gap,
        projector_distance=_projector_distance(base_frame, frame),
        locality_second_moment=_locality_second_moment(
            system, point.inverse_map
        ),
        map_condition_number=float(np.linalg.cond(point.onebody_map)),
    )
    return audit, frame


def _traceless_fiber_tangent_norm(
    system: KapitLaughlinParent,
    frame: np.ndarray,
    lambda_x: float,
    lambda_y: float,
    direction: int,
    generators: tuple[np.ndarray, np.ndarray],
    epsilon: float,
) -> float:
    displacement = [0.0, 0.0]
    displacement[int(direction)] = float(epsilon)
    plus = protected_parent_point(
        system,
        lambda_x + displacement[0],
        lambda_y + displacement[1],
        generators,
    ).parent
    minus = protected_parent_point(
        system,
        lambda_x - displacement[0],
        lambda_y - displacement[1],
        generators,
    ).parent
    derivative = (plus - minus) * (0.5 / epsilon)
    fiber = frame.conj().T @ (derivative @ frame)
    fiber = 0.5 * (fiber + fiber.conj().T)
    rank = fiber.shape[0]
    traceless = fiber - np.trace(fiber) * np.eye(rank) / rank
    return float(np.linalg.norm(traceless, ord=2))


def audit_protected_family(
    system: KapitLaughlinParent,
    base_frame: np.ndarray,
    points: tuple[tuple[float, float], ...],
    expected_rank: int,
    tangent_epsilon: float = 1e-5,
) -> ProtectedFamilyAudit:
    """Audit the exact-degeneracy gates on a finite parameter stencil."""

    if not points:
        raise ValueError("protected-family audit needs at least one point")
    if base_frame.shape != (system.basis.dimension, expected_rank):
        raise ValueError("base kernel frame has the wrong shape")
    generators = projected_local_generator_pair(system)
    commutator = generators[0] @ generators[1] - generators[1] @ generators[0]
    point_audits: list[ProtectedPointAudit] = []
    tangent_norms: list[float] = []
    locality_base = _locality_second_moment(system, np.eye(system.n_flux))
    for lambda_x, lambda_y in points:
        point = protected_parent_point(
            system, lambda_x, lambda_y, generators
        )
        point_audit, frame = _point_audit(
            system, point, base_frame, expected_rank
        )
        point_audits.append(point_audit)
        tangent_norms.extend(
            _traceless_fiber_tangent_norm(
                system,
                frame,
                lambda_x,
                lambda_y,
                direction,
                generators,
                tangent_epsilon,
            )
            for direction in (0, 1)
        )
    ranks = {point.observed_rank for point in point_audits}
    return ProtectedFamilyAudit(
        points=tuple(point_audits),
        generator_commutator_norm=float(np.linalg.norm(commutator)),
        maximum_traceless_fiber_tangent_norm=max(tangent_norms),
        maximum_kernel_residual=max(
            point.kernel_residual for point in point_audits
        ),
        maximum_internal_bandwidth=max(
            point.internal_bandwidth for point in point_audits
        ),
        minimum_external_gap=min(
            point.external_gap for point in point_audits
        ),
        maximum_projector_distance=max(
            point.projector_distance for point in point_audits
        ),
        maximum_locality_ratio=max(
            point.locality_second_moment / locality_base
            for point in point_audits
        ),
        constant_nullity=(ranks == {int(expected_rank)}),
    )
