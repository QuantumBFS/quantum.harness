from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from qcontrol.config import SystemConfig


ComplexMatrix = NDArray[np.complex128]


@dataclass(frozen=True)
class ControlSystem:
    drift: ComplexMatrix
    controls: tuple[ComplexMatrix, ...]
    target: ComplexMatrix
    amplitude_scales: tuple[float, ...]
    name: str

    @property
    def dimension(self) -> int:
        return self.drift.shape[0]


def _normalized_paulis() -> tuple[ComplexMatrix, ...]:
    scale = np.float64(1.0 / np.sqrt(2.0))
    identity = scale * np.eye(2, dtype=np.complex128)
    x = scale * np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
    y = scale * np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=np.complex128)
    z = scale * np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)
    return identity, x, y, z


def _validate_system(system: ControlSystem) -> None:
    dimension = system.dimension
    expected_shape = (dimension, dimension)
    if dimension < 2 or system.drift.shape != expected_shape:
        raise ValueError("drift must be a square matrix of dimension at least two")
    if not system.controls:
        raise ValueError("at least one control Hamiltonian is required")
    if len(system.controls) != len(system.amplitude_scales):
        raise ValueError("each control must have an amplitude scale")

    for matrix in (system.drift, *system.controls):
        if matrix.shape != expected_shape:
            raise ValueError("Hamiltonians must have matching square shapes")
        if not np.all(np.isfinite(matrix)):
            raise ValueError("Hamiltonians must contain only finite values")
        if not np.allclose(matrix, matrix.conj().T, rtol=0.0, atol=1e-12):
            raise ValueError("Hamiltonians must be Hermitian")

    if system.target.shape != expected_shape:
        raise ValueError("target must match the Hamiltonian dimension")
    identity = np.eye(dimension, dtype=np.complex128)
    if not np.allclose(system.target.conj().T @ system.target, identity, rtol=0.0, atol=1e-12):
        raise ValueError("target must be unitary")


def make_system(config: SystemConfig) -> ControlSystem:
    identity, x, y, z = _normalized_paulis()
    amplitude = float(config.amplitude_bound)

    if config.name == "one_qubit":
        drift = np.asarray(0.37 * z, dtype=np.complex128)
        controls = (x.copy(), y.copy())
        target = np.asarray(
            [[1.0, 1.0], [1.0, -1.0]],
            dtype=np.complex128,
        ) / np.sqrt(2.0)
    else:
        zi = np.kron(z, identity)
        iz = np.kron(identity, z)
        zz = np.kron(z, z)
        drift = np.asarray(0.31 * zi + 0.47 * iz + 0.23 * zz, dtype=np.complex128)
        controls = (
            np.asarray(np.kron(x, identity), dtype=np.complex128),
            np.asarray(np.kron(y, identity), dtype=np.complex128),
            np.asarray(np.kron(identity, x), dtype=np.complex128),
            np.asarray(np.kron(identity, y), dtype=np.complex128),
        )
        target = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
                [0.0, 0.0, 1.0, 0.0],
            ],
            dtype=np.complex128,
        )

    system = ControlSystem(
        drift=drift,
        controls=controls,
        target=target,
        amplitude_scales=(amplitude,) * len(controls),
        name=config.name,
    )
    _validate_system(system)
    return system


def _traceless(matrix: ComplexMatrix) -> ComplexMatrix:
    dimension = matrix.shape[0]
    trace_part = np.trace(matrix) / np.float64(dimension)
    return np.asarray(
        matrix - trace_part * np.eye(dimension, dtype=np.complex128),
        dtype=np.complex128,
    )


def _skew_vector(matrix: ComplexMatrix) -> NDArray[np.float64]:
    traceless = _traceless(matrix)
    skew = np.asarray(0.5 * (traceless - traceless.conj().T), dtype=np.complex128)
    return np.concatenate((skew.real.ravel(), skew.imag.ravel())).astype(np.float64)


def _vector_to_matrix(vector: NDArray[np.float64], dimension: int) -> ComplexMatrix:
    element_count = dimension * dimension
    matrix = vector[:element_count].reshape(dimension, dimension) + 1.0j * vector[
        element_count:
    ].reshape(dimension, dimension)
    return np.asarray(matrix, dtype=np.complex128)


def _orthogonal_residual(
    vector: NDArray[np.float64],
    basis: list[NDArray[np.float64]],
) -> NDArray[np.float64]:
    residual = vector.copy()
    for _ in range(2):
        for basis_vector in basis:
            residual -= np.dot(basis_vector, residual) * basis_vector
    return residual


def lie_algebra_dimension(system: ControlSystem, tolerance: float = 1e-10) -> int:
    if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool):
        raise ValueError("tolerance must be a positive finite number")
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be a positive finite number")
    _validate_system(system)

    dimension = system.dimension
    maximum_dimension = dimension**2 - 1
    basis_vectors: list[NDArray[np.float64]] = []
    basis_matrices: list[ComplexMatrix] = []

    def add_generator(matrix: ComplexMatrix) -> bool:
        vector = _skew_vector(matrix)
        residual = _orthogonal_residual(vector, basis_vectors)
        norm = float(np.linalg.norm(residual))
        if norm <= tolerance:
            return False
        normalized = residual / norm
        basis_vectors.append(normalized)
        basis_matrices.append(_vector_to_matrix(normalized, dimension))
        return True

    for hamiltonian in (system.drift, *system.controls):
        add_generator(np.asarray(-1.0j * hamiltonian, dtype=np.complex128))
        if len(basis_vectors) == maximum_dimension:
            return maximum_dimension

    while len(basis_vectors) < maximum_dimension:
        added = False
        current_count = len(basis_matrices)
        for left_index in range(current_count):
            for right_index in range(left_index + 1, current_count):
                left = basis_matrices[left_index]
                right = basis_matrices[right_index]
                commutator = left @ right - right @ left
                if add_generator(np.asarray(commutator, dtype=np.complex128)):
                    added = True
                    break
            if added:
                break
        if not added:
            break

    return len(basis_vectors)


def _random_traceless_hermitian(
    rng: np.random.Generator,
    dimension: int,
) -> ComplexMatrix:
    raw = rng.standard_normal((dimension, dimension)) + 1.0j * rng.standard_normal(
        (dimension, dimension)
    )
    hermitian = np.asarray(0.5 * (raw + raw.conj().T), dtype=np.complex128)
    traceless = _traceless(hermitian)
    norm = float(np.linalg.norm(traceless, "fro"))
    if norm == 0.0:
        raise RuntimeError("failed to generate a nonzero perturbation")
    return np.asarray(traceless / norm, dtype=np.complex128)


def perturb_system(system: ControlSystem, gap: float, seed: int) -> ControlSystem:
    if isinstance(gap, bool) or not isinstance(gap, (int, float)):
        raise ValueError("gap must be a finite nonnegative number")
    gap = float(gap)
    if not math.isfinite(gap) or gap < 0.0:
        raise ValueError("gap must be a finite nonnegative number")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    _validate_system(system)

    if gap == 0.0:
        return ControlSystem(
            drift=system.drift.copy(),
            controls=tuple(control.copy() for control in system.controls),
            target=system.target.copy(),
            amplitude_scales=system.amplitude_scales,
            name=system.name,
        )

    rng = np.random.default_rng(seed)
    drift_direction = _random_traceless_hermitian(rng, system.dimension)
    unmodeled_direction = _random_traceless_hermitian(rng, system.dimension)
    aggregate = np.asarray(drift_direction + unmodeled_direction, dtype=np.complex128)
    aggregate /= np.linalg.norm(aggregate, "fro")
    perturbation_norm = gap * float(np.linalg.norm(system.drift, "fro"))
    perturbed_drift = np.asarray(
        system.drift + perturbation_norm * aggregate,
        dtype=np.complex128,
    )

    gain_changes = 1.0 + gap * rng.standard_normal(len(system.controls))
    perturbed_controls = tuple(
        np.asarray(gain * control, dtype=np.complex128)
        for gain, control in zip(gain_changes, system.controls, strict=True)
    )
    truth = ControlSystem(
        drift=perturbed_drift,
        controls=perturbed_controls,
        target=system.target.copy(),
        amplitude_scales=system.amplitude_scales,
        name=system.name,
    )
    _validate_system(truth)
    return truth
