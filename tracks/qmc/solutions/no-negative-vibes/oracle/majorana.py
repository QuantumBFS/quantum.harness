"""Small-system Majorana trace oracle and reflection-positive generators."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.linalg import expm


@dataclass(frozen=True)
class TraceWeightResult:
    classification: str
    value: complex
    phase: complex
    log_abs: float
    cancellation_ratio: float
    determinant_square: complex
    determinant_phase: complex
    log_abs_determinant: float
    square_identity_residual: float
    determinant_condition_number: float
    determinant_check_reliable: bool


_I2 = np.eye(2, dtype=complex)
_X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
_Y = np.array([[0.0, -1j], [1j, 0.0]], dtype=complex)
_Z = np.diag([1.0, -1.0]).astype(complex)


def _kron_all(factors: list[np.ndarray]) -> np.ndarray:
    result = np.array([[1.0]], dtype=complex)
    for factor in factors:
        result = np.kron(result, factor)
    return result


def majorana_operators(n_modes: int) -> tuple[np.ndarray, ...]:
    """Return a Jordan-Wigner representation with {gamma_i,gamma_j}=2 delta_ij."""
    if n_modes < 1:
        raise ValueError("n_modes must be positive")

    operators: list[np.ndarray] = []
    for mode in range(n_modes):
        prefix = [_Z] * mode
        suffix = [_I2] * (n_modes - mode - 1)
        operators.append(_kron_all([*prefix, _X, *suffix]))
        operators.append(_kron_all([*prefix, _Y, *suffix]))
    return tuple(operators)


def quadratic_operator(
    generator: np.ndarray,
    *,
    operators: tuple[np.ndarray, ...] | None = None,
) -> np.ndarray:
    """Represent h(A)=gamma^T A gamma / 4 on the fermionic Fock space."""
    matrix = np.asarray(generator, dtype=complex)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("generator must be square")
    if matrix.shape[0] % 2:
        raise ValueError("a Majorana generator must have even dimension")
    scale = max(1.0, float(np.linalg.norm(matrix)))
    if np.linalg.norm(matrix + matrix.T) > 1e-10 * scale:
        raise ValueError("a Majorana generator must be complex skew-symmetric")

    n_modes = matrix.shape[0] // 2
    gamma = operators or majorana_operators(n_modes)
    if len(gamma) != matrix.shape[0]:
        raise ValueError("operator count does not match generator dimension")

    dimension = gamma[0].shape[0]
    result = np.zeros((dimension, dimension), dtype=complex)
    for left in range(matrix.shape[0]):
        for right in range(left + 1, matrix.shape[0]):
            result += 0.5 * matrix[left, right] * gamma[left] @ gamma[right]
    return result


def spin_trace_weight(
    generators: list[np.ndarray],
    *,
    phase_tolerance: float = 1e-10,
    zero_tolerance: float = 1e-12,
) -> TraceWeightResult:
    """Evaluate the continuous Spin trace, including its square-root branch."""
    if not generators:
        raise ValueError("at least one generator is required")
    matrices = [np.asarray(generator, dtype=complex) for generator in generators]
    shape = matrices[0].shape
    if any(matrix.shape != shape for matrix in matrices):
        raise ValueError("all generators must have the same shape")

    gamma = majorana_operators(shape[0] // 2)
    fock_dimension = gamma[0].shape[0]
    fock_product = np.eye(fock_dimension, dtype=complex)
    fock_log_scale = 0.0
    one_particle_product = np.eye(shape[0], dtype=complex)
    for matrix in matrices:
        fock_product = fock_product @ expm(
            quadratic_operator(matrix, operators=gamma)
        )
        product_norm = float(np.linalg.norm(fock_product))
        if not math.isfinite(product_norm) or product_norm == 0.0:
            raise FloatingPointError("non-finite Fock-space product")
        fock_product /= product_norm
        fock_log_scale += math.log(product_norm)
        one_particle_product = one_particle_product @ expm(matrix)

    scaled_trace = complex(np.trace(fock_product))
    cancellation_ratio = abs(scaled_trace) / math.sqrt(fock_dimension)
    if scaled_trace == 0.0:
        phase = 0.0j
        log_abs = -math.inf
        value = 0.0j
    else:
        phase = scaled_trace / abs(scaled_trace)
        log_abs = fock_log_scale + math.log(abs(scaled_trace))
        if log_abs > math.log(np.finfo(float).max):
            value = complex(
                math.copysign(math.inf, phase.real) if phase.real else 0.0,
                math.copysign(math.inf, phase.imag) if phase.imag else 0.0,
            )
        else:
            value = phase * math.exp(log_abs)

    shifted = np.eye(shape[0], dtype=complex) + one_particle_product
    singular_values = np.linalg.svd(shifted, compute_uv=False)
    sigma_max = float(singular_values[0])
    sigma_min = float(singular_values[-1])
    determinant_condition_number = (
        math.inf if sigma_min == 0.0 else sigma_max / sigma_min
    )
    determinant_phase_raw, log_abs_determinant = np.linalg.slogdet(shifted)
    determinant_phase = complex(determinant_phase_raw)
    if determinant_phase == 0.0:
        determinant_square = 0.0j
    elif log_abs_determinant > math.log(np.finfo(float).max):
        determinant_square = complex(
            math.copysign(math.inf, determinant_phase.real)
            if determinant_phase.real
            else 0.0,
            math.copysign(math.inf, determinant_phase.imag)
            if determinant_phase.imag
            else 0.0,
        )
    else:
        determinant_square = determinant_phase * math.exp(log_abs_determinant)

    if scaled_trace == 0.0 or determinant_phase == 0.0:
        square_identity_residual = (
            0.0 if scaled_trace == 0.0 and determinant_phase == 0.0 else math.inf
        )
    else:
        phase_residual = abs(phase * phase - determinant_phase)
        log_difference = 2.0 * log_abs - float(log_abs_determinant)
        magnitude_residual = (
            abs(math.expm1(log_difference))
            if abs(log_difference) < 50.0
            else math.inf
        )
        square_identity_residual = max(phase_residual, magnitude_residual)
    determinant_check_reliable = (
        math.isfinite(determinant_condition_number)
        and determinant_condition_number <= 1e6
        and cancellation_ratio > zero_tolerance
        and math.isfinite(square_identity_residual)
        and square_identity_residual <= 1e-8
    )

    if cancellation_ratio <= zero_tolerance:
        classification = "uncertain"
    elif abs(phase.imag) > phase_tolerance:
        classification = "complex"
    elif phase.real > 0.0:
        classification = "positive"
    else:
        classification = "negative"

    return TraceWeightResult(
        classification=classification,
        value=value,
        phase=complex(phase),
        log_abs=float(log_abs),
        cancellation_ratio=float(cancellation_ratio),
        determinant_square=determinant_square,
        determinant_phase=determinant_phase,
        log_abs_determinant=float(log_abs_determinant),
        square_identity_residual=float(square_identity_residual),
        determinant_condition_number=determinant_condition_number,
        determinant_check_reliable=determinant_check_reliable,
    )


def canonical_reflection_structures(
    block_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return anticommuting J1^2=+1 and J2^2=-1 reflection structures."""
    if block_size < 1:
        raise ValueError("block_size must be positive")
    identity = np.eye(block_size)
    zero = np.zeros_like(identity)
    j1 = np.block([[zero, identity], [identity, zero]])
    j2 = np.block([[zero, -identity], [identity, zero]])
    return j1, j2


def random_reflection_generator(
    rng: np.random.Generator,
    *,
    block_size: int,
    scale: float,
    cone: str = "positive",
) -> np.ndarray:
    """Sample the complex Majorana block class with a PSD or indefinite C block."""
    if block_size < 2 and cone == "indefinite":
        raise ValueError("an indefinite cone control needs block_size >= 2")
    raw_b = (
        rng.standard_normal((block_size, block_size))
        + 1j * rng.standard_normal((block_size, block_size))
    ) / math.sqrt(2.0 * block_size)
    block_b = 0.5 * (raw_b - raw_b.T)

    raw_c = (
        rng.standard_normal((block_size, block_size))
        + 1j * rng.standard_normal((block_size, block_size))
    ) / math.sqrt(2.0 * block_size)
    if cone == "positive":
        block_c = raw_c @ raw_c.conj().T
    elif cone == "indefinite":
        hermitian = 0.5 * (raw_c + raw_c.conj().T)
        eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
        magnitudes = np.abs(eigenvalues) + 0.25
        signs = np.ones(block_size)
        signs[1::2] = -1.0
        block_c = (
            eigenvectors
            @ np.diag(signs * magnitudes)
            @ eigenvectors.conj().T
        )
    else:
        raise ValueError(f"unknown cone: {cone}")

    generator = np.block(
        [
            [block_b, 1j * block_c],
            [-1j * block_c.T, block_b.conj()],
        ]
    )
    norm = float(np.linalg.norm(generator))
    if norm == 0.0:
        raise RuntimeError("Majorana projection produced a zero generator")
    size = 2 * block_size
    return generator * (scale * math.sqrt(size) / norm)


def reflection_structure_residual(
    generator: np.ndarray,
    *,
    j1: np.ndarray,
    j2: np.ndarray,
    require_cone: bool,
) -> float:
    """Measure skewness, reflection reality, and (optionally) cone violation."""
    matrix = np.asarray(generator, dtype=complex)
    scale = max(1.0, float(np.linalg.norm(matrix)))
    reflection = j1.T @ matrix @ j1 - matrix.conj()
    cone_matrix = 1j * (j2 @ matrix - matrix.conj() @ j2)
    cone_matrix = 0.5 * (cone_matrix + cone_matrix.conj().T)
    residuals = [
        float(np.linalg.norm(matrix + matrix.T)),
        float(np.linalg.norm(reflection)),
        float(np.linalg.norm(cone_matrix - cone_matrix.conj().T)),
    ]
    if require_cone:
        largest_eigenvalue = float(np.linalg.eigvalsh(cone_matrix)[-1])
        residuals.append(max(0.0, largest_eigenvalue))
    return max(residuals) / scale


def plane_rotation(size: int, *, angle: float) -> np.ndarray:
    """Rotate the first two Majorana axes, changing the reflection structure."""
    if size < 2:
        raise ValueError("size must be at least two")
    rotation = np.eye(size)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    rotation[:2, :2] = [[cosine, -sine], [sine, cosine]]
    return rotation


def shared_reality_rotation(block_size: int, *, angle: float) -> np.ndarray:
    """Rotate J2 while commuting with J1, so the common reality condition remains."""
    if block_size < 2:
        raise ValueError("block_size must be at least two")
    identity = np.eye(block_size)
    hadamard = np.block([[identity, identity], [identity, -identity]]) / math.sqrt(2.0)
    plus_rotation = plane_rotation(block_size, angle=angle)
    eigenbasis_rotation = np.block(
        [
            [plus_rotation, np.zeros_like(identity)],
            [np.zeros_like(identity), identity],
        ]
    )
    return hadamard @ eigenbasis_rotation @ hadamard.T
