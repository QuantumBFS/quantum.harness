from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm
from scipy.sparse import bmat, csr_matrix
from scipy.sparse.linalg import expm_multiply

from .fock_ed import fixed_m_basis, l_plus_matrix, l_squared_matrix


@dataclass(frozen=True)
class ProjectedState:
    energy: float
    coefficients: np.ndarray
    head_weights: np.ndarray
    projected_rank: int


@dataclass(frozen=True)
class TowerComponent:
    magnetic_number: int
    basis: tuple[int, ...]
    coefficients: np.ndarray


@dataclass(frozen=True)
class VMCResult:
    mean: float
    standard_error: float
    total_uncertainty: float
    variance: float
    effective_sample_size: int
    sampling: str
    maximum_local_energy_imaginary_part: float


def angular_momentum_subspace(
    basis: tuple[int, ...],
    *,
    two_q: int,
    target_m: float,
    target_l: int,
) -> np.ndarray:
    """Return an orthonormal basis for one exact total-L subspace."""

    l_squared = l_squared_matrix(
        basis,
        two_q=two_q,
        target_m=target_m,
    )
    eigenvalues, eigenvectors = np.linalg.eigh(l_squared)
    target = target_l * (target_l + 1.0)
    selected = np.isclose(eigenvalues, target, rtol=0.0, atol=1.0e-9)
    if not np.any(selected):
        raise ValueError(f"no L={target_l} subspace in M={target_m}")
    return eigenvectors[:, selected]


def shared_random_features(
    basis: tuple[int, ...],
    *,
    n_orbitals: int,
    width: int,
    seed: int,
) -> np.ndarray:
    """Evaluate a seeded shared tanh trunk on occupation bitstrings."""

    occupations = np.array(
        [
            [1.0 if state & (1 << orbital) else -1.0 for orbital in range(n_orbitals)]
            for state in basis
        ]
    )
    random = np.random.default_rng(seed)
    weights = random.normal(
        scale=1.0 / np.sqrt(n_orbitals),
        size=(n_orbitals, width),
    )
    biases = random.uniform(-np.pi, np.pi, size=width)
    hidden = np.tanh(occupations @ weights + biases)
    return np.column_stack((np.ones(len(basis)), hidden))


def projected_ritz_state(
    hamiltonian: np.ndarray,
    features: np.ndarray,
    angular_momentum_subspace: np.ndarray,
) -> ProjectedState:
    """Optimize a linear neural head inside an exact angular-momentum sector."""

    projected_features = angular_momentum_subspace @ (
        angular_momentum_subspace.T.conj() @ features
    )
    left_vectors, singular_values, _ = np.linalg.svd(
        projected_features,
        full_matrices=False,
    )
    threshold = singular_values[0] * 1.0e-12
    rank = int(np.count_nonzero(singular_values > threshold))
    variational_basis = left_vectors[:, :rank]
    effective_hamiltonian = (
        variational_basis.T.conj() @ hamiltonian @ variational_basis
    )
    energies, head_vectors = np.linalg.eigh(effective_hamiltonian)
    coefficients = variational_basis @ head_vectors[:, 0]
    coefficients /= np.linalg.norm(coefficients)
    head_weights = np.linalg.lstsq(
        projected_features,
        coefficients,
        rcond=1.0e-12,
    )[0]
    energy = float(np.real(coefficients.conj() @ hamiltonian @ coefficients))
    return ProjectedState(
        energy=energy,
        coefficients=coefficients,
        head_weights=head_weights,
        projected_rank=rank,
    )


def generate_l2_tower(
    m0_coefficients: np.ndarray,
    *,
    n_electrons: int,
    two_q: int,
) -> dict[int, TowerComponent]:
    """Generate all five components of one normalized L=2 irrep."""

    target_l = 2
    m0_basis = fixed_m_basis(n_electrons, two_q, 0.0)
    tower = {
        0: TowerComponent(
            magnetic_number=0,
            basis=m0_basis,
            coefficients=m0_coefficients / np.linalg.norm(m0_coefficients),
        )
    }

    for magnetic_number in (0, 1):
        source = tower[magnetic_number]
        target_basis = fixed_m_basis(
            n_electrons,
            two_q,
            float(magnetic_number + 1),
        )
        raised = l_plus_matrix(
            source.basis,
            target_basis,
            two_q=two_q,
        ) @ source.coefficients
        normalization = np.sqrt(
            (target_l - magnetic_number) * (target_l + magnetic_number + 1)
        )
        tower[magnetic_number + 1] = TowerComponent(
            magnetic_number=magnetic_number + 1,
            basis=target_basis,
            coefficients=raised / normalization,
        )

    for magnetic_number in (0, -1):
        source = tower[magnetic_number]
        target_basis = fixed_m_basis(
            n_electrons,
            two_q,
            float(magnetic_number - 1),
        )
        raising_from_target = l_plus_matrix(
            target_basis,
            source.basis,
            two_q=two_q,
        )
        lowered = raising_from_target.T.conj() @ source.coefficients
        normalization = np.sqrt(
            (target_l + magnetic_number) * (target_l - magnetic_number + 1)
        )
        tower[magnetic_number - 1] = TowerComponent(
            magnetic_number=magnetic_number - 1,
            basis=target_basis,
            coefficients=lowered / normalization,
        )

    return dict(sorted(tower.items()))


def tower_ladder_residual(
    tower: dict[int, TowerComponent],
    *,
    two_q: int,
    target_l: int,
) -> float:
    """Maximum residual of the exact angular-momentum ladder relations."""

    residuals = []
    for magnetic_number in range(-target_l, target_l):
        source = tower[magnetic_number]
        target = tower[magnetic_number + 1]
        raised = l_plus_matrix(
            source.basis,
            target.basis,
            two_q=two_q,
        ) @ source.coefficients
        coefficient = np.sqrt(
            (target_l - magnetic_number) * (target_l + magnetic_number + 1)
        )
        residuals.append(
            np.linalg.norm(raised - coefficient * target.coefficients)
        )
    return float(max(residuals))


def vmc_energy(
    coefficients: np.ndarray,
    hamiltonian: np.ndarray,
    *,
    n_samples: int,
    seed: int,
    numerical_floor: float,
) -> VMCResult:
    """Estimate energy from independent samples of determinant probabilities."""

    probabilities = np.abs(coefficients) ** 2
    probabilities /= probabilities.sum()
    random = np.random.default_rng(seed)
    sampled_indices = random.choice(
        len(coefficients),
        size=n_samples,
        replace=True,
        p=probabilities,
    )
    h_psi = hamiltonian @ coefficients
    sampled_local_energies = (
        h_psi[sampled_indices] / coefficients[sampled_indices]
    )
    real_samples = np.real(sampled_local_energies)
    variance = float(np.var(real_samples, ddof=1))
    standard_error = math.sqrt(variance / n_samples)
    return VMCResult(
        mean=float(np.mean(real_samples)),
        standard_error=standard_error,
        total_uncertainty=math.hypot(standard_error, numerical_floor),
        variance=variance,
        effective_sample_size=n_samples,
        sampling="independent categorical determinant samples",
        maximum_local_energy_imaginary_part=float(
            np.max(np.abs(np.imag(sampled_local_energies)))
        ),
    )


def _monopole_orbital_values(
    theta: np.ndarray,
    phi: np.ndarray,
    *,
    two_q: int,
) -> np.ndarray:
    x = np.cos(theta)
    u = np.sqrt((1.0 + x) / 2.0) * np.exp(0.5j * phi)
    v = np.sqrt((1.0 - x) / 2.0) * np.exp(-0.5j * phi)
    values = np.empty((theta.size, two_q + 1), dtype=np.complex128)
    for orbital in range(two_q + 1):
        v_power = two_q - orbital
        normalization = math.sqrt(
            (two_q + 1) * math.comb(two_q, orbital) / (4.0 * math.pi)
        )
        gauge_sign = -1.0 if v_power % 2 else 1.0
        values[:, orbital] = (
            gauge_sign
            * normalization
            * u**orbital
            * v**v_power
        )
    return values


def _continuous_state_value(
    theta: np.ndarray,
    phi: np.ndarray,
    basis: tuple[int, ...],
    coefficients: np.ndarray,
    *,
    two_q: int,
) -> complex:
    orbital_values = _monopole_orbital_values(theta, phi, two_q=two_q)
    value = 0.0j
    for state, coefficient in zip(basis, coefficients, strict=True):
        occupied = [
            orbital
            for orbital in range(two_q + 1)
            if state & (1 << orbital)
        ]
        value += coefficient * np.linalg.det(orbital_values[:, occupied])
    return value / math.sqrt(math.factorial(theta.size))


def particle_swap_residual(
    basis: tuple[int, ...],
    coefficients: np.ndarray,
    *,
    two_q: int,
    seed: int,
    n_trials: int = 3,
) -> float:
    """Numerically test exchange antisymmetry in continuous coordinates."""

    random = np.random.default_rng(seed)
    n_electrons = basis[0].bit_count()
    residuals = []
    for _ in range(n_trials):
        theta = np.arccos(random.uniform(-1.0, 1.0, size=n_electrons))
        phi = random.uniform(0.0, 2.0 * np.pi, size=n_electrons)
        original = _continuous_state_value(
            theta,
            phi,
            basis,
            coefficients,
            two_q=two_q,
        )
        swapped_theta = theta.copy()
        swapped_phi = phi.copy()
        swapped_theta[[0, 1]] = swapped_theta[[1, 0]]
        swapped_phi[[0, 1]] = swapped_phi[[1, 0]]
        swapped = _continuous_state_value(
            swapped_theta,
            swapped_phi,
            basis,
            coefficients,
            two_q=two_q,
        )
        scale = max(abs(original), abs(swapped), 1.0e-14)
        residuals.append(abs(swapped + original) / scale)
    return float(max(residuals))


def finite_rotation_residual(
    tower: dict[int, TowerComponent],
    *,
    two_q: int,
    seed: int,
) -> float:
    """Compare a finite many-body rotation with the spin-2 representation."""

    magnetic_numbers = list(tower)
    dimensions = [len(tower[m].basis) for m in magnetic_numbers]
    offsets = np.cumsum([0, *dimensions])
    blocks = [
        [csr_matrix((dimensions[row], dimensions[column])) for column in range(5)]
        for row in range(5)
    ]
    for column, magnetic_number in enumerate(magnetic_numbers[:-1]):
        blocks[column + 1][column] = csr_matrix(
            l_plus_matrix(
                tower[magnetic_number].basis,
                tower[magnetic_number + 1].basis,
                two_q=two_q,
            )
        )
    j_plus = bmat(blocks, format="csr")
    j_y = (j_plus - j_plus.getH()) / (2.0j)
    magnetic_diagonal = np.concatenate(
        [np.full(dimension, magnetic_number) for dimension, magnetic_number in zip(dimensions, magnetic_numbers, strict=True)]
    )

    tower_embedding = np.zeros((int(offsets[-1]), 5), dtype=np.complex128)
    for column, magnetic_number in enumerate(magnetic_numbers):
        tower_embedding[offsets[column] : offsets[column + 1], column] = tower[
            magnetic_number
        ].coefficients

    spin2_j_plus = np.zeros((5, 5), dtype=np.complex128)
    for column, magnetic_number in enumerate(magnetic_numbers[:-1]):
        spin2_j_plus[column + 1, column] = np.sqrt(
            (2 - magnetic_number) * (2 + magnetic_number + 1)
        )
    spin2_j_y = (spin2_j_plus - spin2_j_plus.T.conj()) / (2.0j)

    random = np.random.default_rng(seed)
    alpha, gamma = random.uniform(0.0, 2.0 * np.pi, size=2)
    beta = math.acos(random.uniform(-1.0, 1.0))
    amplitudes = random.normal(size=5) + 1.0j * random.normal(size=5)
    amplitudes /= np.linalg.norm(amplitudes)

    rotated_full = tower_embedding @ amplitudes
    rotated_full *= np.exp(-1.0j * gamma * magnetic_diagonal)
    rotated_full = expm_multiply(
        -1.0j * beta * j_y,
        rotated_full,
        traceA=0.0,
    )
    rotated_full *= np.exp(-1.0j * alpha * magnetic_diagonal)

    rotated_spin2 = amplitudes * np.exp(
        -1.0j * gamma * np.asarray(magnetic_numbers)
    )
    rotated_spin2 = expm(-1.0j * beta * spin2_j_y) @ rotated_spin2
    rotated_spin2 *= np.exp(
        -1.0j * alpha * np.asarray(magnetic_numbers)
    )
    expected_full = tower_embedding @ rotated_spin2
    return float(np.linalg.norm(rotated_full - expected_full))
