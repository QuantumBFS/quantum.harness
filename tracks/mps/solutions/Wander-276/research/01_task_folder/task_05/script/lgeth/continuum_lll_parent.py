"""Independent continuum-torus bosonic ``V_0`` parent.

This task-local implementation rewrites the guiding-center pair-factor
construction used in the torus pseudopotential literature.  It has no runtime
dependency on task_03 code or artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
from scipy import sparse

from .lattice import BosonBasis


@dataclass(frozen=True)
class ContinuumLLLParent:
    """Factor-only square-torus continuum LLL contact parent."""

    n_particles: int
    n_flux: int
    kappa: float
    image_cutoff: int
    basis: BosonBasis
    intermediate_basis: BosonBasis
    pair_coefficients: np.ndarray
    constraints: sparse.csr_matrix


def normalized_pair_modes(n_orbitals: int) -> tuple[tuple[int, int], ...]:
    """Return the deterministic normalized unordered two-boson basis."""

    orbitals = int(n_orbitals)
    if orbitals < 1:
        raise ValueError("n_orbitals must be positive")
    return tuple(
        (left, right)
        for left in range(orbitals)
        for right in range(left, orbitals)
    )


def _validate_parameters(
    n_flux: int,
    kappa: float,
    image_cutoff: int,
) -> tuple[int, float, int]:
    flux = int(n_flux)
    inverse_radius = float(kappa)
    images = int(image_cutoff)
    if flux < 2:
        raise ValueError("n_flux must be at least two")
    if not np.isfinite(inverse_radius) or inverse_radius <= 0.0:
        raise ValueError("kappa must be finite and positive")
    if images < 0:
        raise ValueError("image_cutoff must be nonnegative")
    return flux, inverse_radius, images


def torus_v0_pair_coefficients(
    n_flux: int,
    kappa: float,
    image_cutoff: int = 8,
) -> np.ndarray:
    """Return row-normalized magnetic-periodic ``V_0`` pair factors."""

    flux, inverse_radius, images_count = _validate_parameters(
        n_flux,
        kappa,
        image_cutoff,
    )
    pairs = normalized_pair_modes(flux)
    pair_index = {pair: index for index, pair in enumerate(pairs)}
    coefficients = np.zeros((2 * flux, len(pairs)), dtype=float)
    images = np.arange(-images_count, images_count + 1, dtype=float)
    for center_twice in range(2 * flux):
        for relative_twice in range(-flux, flux):
            if (center_twice - relative_twice) % 2:
                continue
            left = ((center_twice - relative_twice) // 2) % flux
            right = ((center_twice + relative_twice) // 2) % flux
            relative = 0.5 * relative_twice
            form_factor = float(
                np.sum(
                    np.exp(
                        -inverse_radius**2
                        * np.square(relative + images * flux)
                    )
                )
            )
            pair = (min(left, right), max(left, right))
            coefficients[center_twice, pair_index[pair]] += form_factor
        for index, (left, right) in enumerate(pairs):
            if left == right:
                coefficients[center_twice, index] *= sqrt(2.0)
    row_norms = np.linalg.norm(coefficients, axis=1)
    if np.any(row_norms <= np.finfo(float).tiny):
        raise RuntimeError("continuum V0 contains a zero pair-center factor")
    coefficients /= row_norms[:, None]
    return coefficients


def torus_v0_constraint_map(
    basis: BosonBasis,
    kappa: float,
    image_cutoff: int = 8,
    amplitude_cutoff: float = 1e-15,
) -> tuple[sparse.csr_matrix, BosonBasis, np.ndarray]:
    """Apply every pair-center factor to a fixed-number boson basis."""

    if basis.n_particles < 2:
        raise ValueError("continuum pair constraints require at least two particles")
    if amplitude_cutoff < 0.0:
        raise ValueError("amplitude_cutoff must be nonnegative")
    coefficients = torus_v0_pair_coefficients(
        basis.n_orbitals,
        kappa,
        image_cutoff=image_cutoff,
    )
    intermediate = BosonBasis(
        basis.n_orbitals,
        basis.n_particles - 2,
    )
    pairs = normalized_pair_modes(basis.n_orbitals)
    rows: list[int] = []
    columns: list[int] = []
    data: list[complex] = []
    for column, state in enumerate(basis.states):
        for pair_index, (left, right) in enumerate(pairs):
            if left == right:
                if state[left] < 2:
                    continue
                factor = sqrt(state[left] * (state[left] - 1) / 2.0)
                updated = list(state)
                updated[left] -= 2
            else:
                if state[left] == 0 or state[right] == 0:
                    continue
                factor = sqrt(state[left] * state[right])
                updated = list(state)
                updated[left] -= 1
                updated[right] -= 1
            intermediate_index = intermediate.index[tuple(updated)]
            active = np.flatnonzero(
                np.abs(coefficients[:, pair_index]) > float(amplitude_cutoff)
            )
            rows.extend(
                (active * intermediate.dimension + intermediate_index).tolist()
            )
            columns.extend([column] * int(active.size))
            data.extend((factor * coefficients[active, pair_index]).tolist())
    constraints = sparse.coo_matrix(
        (
            np.asarray(data, dtype=complex),
            (rows, columns),
        ),
        shape=(2 * basis.n_orbitals * intermediate.dimension, basis.dimension),
    ).tocsr()
    constraints.sum_duplicates()
    constraints.eliminate_zeros()
    return constraints, intermediate, coefficients


def build_continuum_lll_parent(
    n_particles: int,
    n_flux: int,
    *,
    image_cutoff: int = 8,
) -> ContinuumLLLParent:
    """Build the registered square-torus continuum LLL parent factor."""

    particles = int(n_particles)
    flux = int(n_flux)
    if particles < 2:
        raise ValueError("continuum LLL parent requires at least two particles")
    if flux < 2 * particles:
        raise ValueError("continuum Laughlin parent requires n_flux>=2N")
    kappa = float(np.sqrt(2.0 * np.pi / flux))
    basis = BosonBasis(flux, particles)
    constraints, intermediate, coefficients = torus_v0_constraint_map(
        basis,
        kappa,
        image_cutoff=int(image_cutoff),
    )
    return ContinuumLLLParent(
        n_particles=particles,
        n_flux=flux,
        kappa=kappa,
        image_cutoff=int(image_cutoff),
        basis=basis,
        intermediate_basis=intermediate,
        pair_coefficients=coefficients,
        constraints=constraints,
    )


def magnetic_translation_matrix(
    n_flux: int,
    shift: int,
    phase: int,
) -> np.ndarray:
    """Return one finite Heisenberg--Weyl translation in the LLL orbitals."""

    flux = int(n_flux)
    if flux < 2:
        raise ValueError("n_flux must be at least two")
    displacement = int(shift) % flux
    momentum = int(phase) % flux
    matrix = np.zeros((flux, flux), dtype=complex)
    for orbital in range(flux):
        target = (orbital + displacement) % flux
        matrix[target, orbital] = np.exp(
            2j
            * np.pi
            * momentum
            * (orbital + 0.5 * displacement)
            / flux
        )
    return matrix


def guiding_center_coherent_state(
    n_flux: int,
    shift: int,
    phase: int,
    *,
    image_cutoff: int = 8,
) -> np.ndarray:
    """Return one normalized magnetic translate of a periodic Gaussian."""

    flux = int(n_flux)
    images = int(image_cutoff)
    if flux < 2 or images < 0:
        raise ValueError("coherent-state flux and image cutoff are invalid")
    orbitals = np.arange(flux, dtype=float)
    windings = np.arange(-images, images + 1, dtype=float)
    fiducial = np.sum(
        np.exp(
            -np.pi
            * np.square(orbitals[:, None] + flux * windings[None, :])
            / flux
        ),
        axis=1,
    ).astype(complex)
    fiducial /= np.linalg.norm(fiducial)
    translated = magnetic_translation_matrix(flux, shift, phase) @ fiducial
    return np.asarray(translated / np.linalg.norm(translated), dtype=complex)


def _traceless_normalized(matrix: np.ndarray) -> np.ndarray:
    value = np.asarray(matrix, dtype=complex)
    if value.ndim != 2 or value.shape[0] != value.shape[1]:
        raise ValueError("generator must be a square matrix")
    value = 0.5 * (value + value.conj().T)
    value = value - np.trace(value) * np.eye(value.shape[0]) / value.shape[0]
    norm = float(np.linalg.norm(value))
    if norm <= 1e-12:
        raise ValueError("generator loses support after trace removal")
    return value / norm


def coherent_link_generator(
    state: np.ndarray,
    neighbor: np.ndarray,
    operator_class: str,
) -> np.ndarray:
    """Return an endpoint-gauge-invariant coherent-state bond or current."""

    left = np.asarray(state, dtype=complex)
    right = np.asarray(neighbor, dtype=complex)
    if left.ndim != 1 or right.shape != left.shape:
        raise ValueError("coherent link endpoints must be equal-length vectors")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise ValueError("coherent link endpoints must be finite")
    left = left / np.linalg.norm(left)
    right = right / np.linalg.norm(right)
    overlap = complex(np.vdot(right, left))
    if abs(overlap) <= 1e-12:
        raise ValueError("coherent link overlap is too small for phase dressing")
    dressing = overlap / abs(overlap)
    forward = dressing * np.outer(right, left.conj())
    if operator_class == "magnetic_bond":
        generator = forward + forward.conj().T
    elif operator_class == "magnetic_current":
        generator = 1j * (forward - forward.conj().T)
    else:
        raise ValueError("coherent link class must be magnetic_bond or magnetic_current")
    return _traceless_normalized(generator)


def phase_space_generator(
    n_flux: int,
    anchor: tuple[int, int],
    operator_class: str,
) -> np.ndarray:
    """Return one registered local guiding-center generator."""

    flux = int(n_flux)
    x, y = (int(value) % flux for value in anchor)
    state = guiding_center_coherent_state(flux, x, y)
    if operator_class == "guiding_density":
        return _traceless_normalized(np.outer(state, state.conj()))
    neighbor = guiding_center_coherent_state(flux, x + 1, y)
    return coherent_link_generator(state, neighbor, operator_class)


def continuum_operator_panels(
    n_flux: int,
    operator_class: str,
    *,
    panels: int = 24,
    panel_size: int = 8,
    seed: int = 2026080107,
) -> tuple[np.ndarray, np.ndarray]:
    """Return deterministic complete panels over the torus phase-space grid."""

    flux = int(n_flux)
    panel_count = int(panels)
    size = int(panel_size)
    if operator_class not in (
        "guiding_density",
        "magnetic_bond",
        "magnetic_current",
    ):
        raise ValueError("unknown continuum operator class")
    if panel_count < 1 or size < 1 or size > flux * flux:
        raise ValueError("continuum panel dimensions are invalid")
    anchors = np.asarray(
        [(x, y) for y in range(flux) for x in range(flux)],
        dtype=int,
    )
    rng = np.random.default_rng(int(seed))
    selected = np.empty((panel_count, size, 2), dtype=int)
    generators = np.empty((panel_count, size, flux, flux), dtype=complex)
    for panel in range(panel_count):
        indices = rng.choice(anchors.shape[0], size=size, replace=False)
        selected[panel] = anchors[indices]
        generators[panel] = np.asarray(
            [
                phase_space_generator(
                    flux,
                    tuple(anchor),
                    operator_class,
                )
                for anchor in selected[panel]
            ]
        )
    return selected, generators


def structured_continuum_operator_panel(
    n_flux: int,
    operator_class: str,
    *,
    panel_size: int = 8,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a line-ordered same-class structured control panel."""

    flux = int(n_flux)
    size = int(panel_size)
    anchors = np.asarray(
        [(index % flux, index // flux) for index in range(size)],
        dtype=int,
    )
    generators = np.asarray(
        [
            phase_space_generator(flux, tuple(anchor), operator_class)
            for anchor in anchors
        ]
    )
    return anchors, generators
