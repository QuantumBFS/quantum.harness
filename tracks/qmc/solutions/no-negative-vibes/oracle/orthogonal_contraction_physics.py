"""Group-algebra and exact-diagonalization audits for the R3b model."""

from __future__ import annotations

from dataclasses import dataclass
from math import comb
from typing import Sequence

import numpy as np

from oracle.orthogonal_contraction_candidate import (
    embed_orthogonal_plaquette_atoms,
)
from oracle.orthogonal_contraction_exclusion import (
    common_commutant_audit,
)
from oracle.semigroup_model_factory import (
    HermitianSemigroupModel,
    hermitian_semigroup_model,
)


@dataclass(frozen=True)
class SectorAlgebraAudit:
    """Commutant data for one fixed-particle-number representation."""

    particle_number: int
    dimension: int
    commutant_nullity: int
    smallest_nonzero_singular_value: float


@dataclass(frozen=True)
class GroupAlgebraAudit:
    """Finite-size obstruction to a small group-algebra closure."""

    modes: int
    one_particle_lie_dimension: int
    sectors: tuple[SectorAlgebraAudit, ...]
    middle_hodge_square_residual: float
    middle_hodge_commutator_residual: float
    middle_chiral_dimensions: tuple[int, int]
    middle_chiral_commutant_nullities: tuple[int, int]


@dataclass(frozen=True)
class ExactDiagonalizationAudit:
    """Half-filled ED observables on an open overlapping-plaquette chain."""

    modes: int
    plaquettes: tuple[tuple[int, int, int, int], ...]
    particle_number: int
    sector_dimension: int
    ground_energy: float
    ground_energy_per_plaquette: float
    sector_gap: float
    ground_multiplicity: int
    first_distinct_gap: float
    chiral_ground_energies: tuple[float, float]
    chiral_internal_gaps: tuple[float, float]
    chiral_ground_wick_residuals: tuple[float, float]
    plaquette_energy_profile: tuple[float, ...]
    density_profile: tuple[float, ...]
    staggered_density_structure_factor: float
    maximum_offdiagonal_coherence: float


def overlapping_plaquettes(
    modes: int,
) -> tuple[tuple[int, int, int, int], ...]:
    """Open chain of four-mode plaquettes overlapping by two modes."""

    if modes < 4 or modes % 2:
        raise ValueError("modes must be even and at least four")
    return tuple(
        (left, left + 1, left + 2, left + 3)
        for left in range(0, modes - 3, 2)
    )


def build_overlapping_plaquette_model(
    modes: int,
    *,
    scale: float = 0.6,
    coefficients: Sequence[float] = (1.0, 0.8),
) -> HermitianSemigroupModel:
    """Construct the translation-repeated open-chain R3b anchor."""

    plaquettes = overlapping_plaquettes(modes)
    local_coefficients = tuple(float(value) for value in coefficients)
    if len(local_coefficients) != 2:
        raise ValueError("exactly two atom coefficients are required")
    atoms = embed_orthogonal_plaquette_atoms(
        modes=modes,
        plaquettes=plaquettes,
        scale=scale,
    )
    return hermitian_semigroup_model(
        atoms,
        local_coefficients * len(plaquettes),
    )


def _sector_indices(modes: int, particles: int) -> np.ndarray:
    return np.asarray(
        [
            state
            for state in range(1 << modes)
            if state.bit_count() == particles
        ],
        dtype=int,
    )


def _commutant_audit(
    matrices: Sequence[np.ndarray],
    *,
    tolerance: float,
) -> tuple[int, float]:
    items = tuple(np.asarray(item, dtype=complex) for item in matrices)
    if not items:
        raise ValueError("at least one matrix is required")
    dimension = items[0].shape[0]
    identity = np.eye(dimension, dtype=complex)
    design = np.vstack(
        [
            np.kron(identity, item)
            - np.kron(item.T, identity)
            for item in items
        ]
    )
    singular_values = np.linalg.svd(design, compute_uv=False)
    rank = int(np.sum(singular_values > tolerance))
    nonzero = singular_values[singular_values > tolerance]
    return (
        dimension * dimension - rank,
        float(np.min(nonzero)) if len(nonzero) else 0.0,
    )


def _permutation_sign(sequence: Sequence[int]) -> int:
    inversions = sum(
        sequence[left] > sequence[right]
        for left in range(len(sequence))
        for right in range(left + 1, len(sequence))
    )
    return -1 if inversions % 2 else 1


def _middle_hodge_star(modes: int) -> tuple[np.ndarray, np.ndarray]:
    particles = modes // 2
    indices = _sector_indices(modes, particles)
    positions = {int(state): index for index, state in enumerate(indices)}
    full_mask = (1 << modes) - 1
    star = np.zeros((len(indices), len(indices)), dtype=complex)
    for column, state_value in enumerate(indices):
        state = int(state_value)
        complement = full_mask ^ state
        occupied = [
            mode for mode in range(modes) if state & (1 << mode)
        ]
        empty = [
            mode for mode in range(modes) if complement & (1 << mode)
        ]
        star[positions[complement], column] = _permutation_sign(
            occupied + empty
        )
    return indices, star


def group_algebra_audit(
    model: HermitianSemigroupModel,
    *,
    tolerance: float = 1e-9,
) -> GroupAlgebraAudit:
    """Audit irreducibility of the generated Fock *-algebra.

    A scalar common commutant implies, by Burnside's theorem, that the
    complex *-algebra generated in that particle sector is the full matrix
    algebra.  The six-mode middle exterior power has the expected Hodge
    split, so its two chiral blocks are checked separately.
    """

    modes = model.modes
    sector_results: list[SectorAlgebraAudit] = []
    for particles in range(modes + 1):
        indices = _sector_indices(modes, particles)
        restricted = tuple(
            atom[np.ix_(indices, indices)]
            for atom in model.fock_atoms
        )
        nullity, smallest = _commutant_audit(
            restricted,
            tolerance=tolerance,
        )
        sector_results.append(
            SectorAlgebraAudit(
                particle_number=particles,
                dimension=len(indices),
                commutant_nullity=nullity,
                smallest_nonzero_singular_value=smallest,
            )
        )

    square_residual = 0.0
    commutator_residual = 0.0
    chiral_dimensions = (0, 0)
    chiral_nullities = (0, 0)
    if modes % 2 == 0:
        indices, star = _middle_hodge_star(modes)
        identity = np.eye(len(indices), dtype=complex)
        square_sign = (-1) ** ((modes // 2) ** 2)
        square_residual = float(
            np.linalg.norm(star @ star - square_sign * identity)
        )
        restricted = tuple(
            atom[np.ix_(indices, indices)].astype(complex)
            for atom in model.fock_atoms
        )
        commutator_residual = max(
            float(np.linalg.norm(star @ atom - atom @ star))
            for atom in restricted
        )
        chirality = star if square_sign == 1 else -1j * star
        eigenvalues, eigenvectors = np.linalg.eigh(chirality)
        eigenspaces = [
            eigenvectors[:, eigenvalues > 0.0],
            eigenvectors[:, eigenvalues < 0.0],
        ]
        chiral_dimensions = tuple(
            space.shape[1] for space in eigenspaces
        )  # type: ignore[assignment]
        chiral_nullities = tuple(
            _commutant_audit(
                tuple(
                    space.conj().T @ atom @ space
                    for atom in restricted
                ),
                tolerance=tolerance,
            )[0]
            for space in eigenspaces
        )  # type: ignore[assignment]

    return GroupAlgebraAudit(
        modes=modes,
        one_particle_lie_dimension=common_commutant_audit(
            model.one_particle_atoms
        ).lie_closure_dimension,
        sectors=tuple(sector_results),
        middle_hodge_square_residual=square_residual,
        middle_hodge_commutator_residual=commutator_residual,
        middle_chiral_dimensions=chiral_dimensions,
        middle_chiral_commutant_nullities=chiral_nullities,
    )


def _one_body_density_matrix(
    state: np.ndarray,
    basis: np.ndarray,
    modes: int,
) -> np.ndarray:
    positions = {int(mask): index for index, mask in enumerate(basis)}
    result = np.zeros((modes, modes), dtype=complex)
    for column, mask_value in enumerate(basis):
        mask = int(mask_value)
        amplitude = state[column]
        for annihilate in range(modes):
            if not mask & (1 << annihilate):
                continue
            after = mask ^ (1 << annihilate)
            sign_annihilate = (-1) ** (
                mask & ((1 << annihilate) - 1)
            ).bit_count()
            for create in range(modes):
                if after & (1 << create):
                    continue
                target = after | (1 << create)
                sign_create = (-1) ** (
                    after & ((1 << create) - 1)
                ).bit_count()
                result[create, annihilate] += (
                    np.conj(state[positions[target]])
                    * amplitude
                    * sign_annihilate
                    * sign_create
                )
    return result


def _density_wick_residual(
    state: np.ndarray,
    basis: np.ndarray,
    modes: int,
) -> float:
    probabilities = np.abs(state) ** 2
    occupations = np.asarray(
        [
            [(int(mask) >> mode) & 1 for mode in range(modes)]
            for mask in basis
        ],
        dtype=float,
    )
    density = probabilities @ occupations
    density_products = np.einsum(
        "s,si,sj->ij",
        probabilities,
        occupations,
        occupations,
    )
    one_body = _one_body_density_matrix(state, basis, modes)
    return max(
        abs(
            density_products[left, right]
            - density[left] * density[right]
            + abs(one_body[left, right]) ** 2
        )
        for left in range(modes)
        for right in range(left + 1, modes)
    )


def exact_diagonalization_audit(
    modes: int,
    *,
    scale: float = 0.6,
) -> ExactDiagonalizationAudit:
    """Compute reproducible half-filled observables for a small open chain."""

    model = build_overlapping_plaquette_model(modes, scale=scale)
    particles = modes // 2
    basis = _sector_indices(modes, particles)
    sector = model.hamiltonian[np.ix_(basis, basis)]
    eigenvalues, eigenvectors = np.linalg.eigh(sector)
    ground_energy = float(eigenvalues[0])
    ground_mask = np.abs(eigenvalues - ground_energy) < 1e-10
    ground_space = eigenvectors[:, ground_mask]
    probabilities = np.mean(np.abs(ground_space) ** 2, axis=1)
    distinct = eigenvalues[~ground_mask]
    first_distinct_gap = float(distinct[0] - ground_energy)

    occupations = np.asarray(
        [
            [(int(mask) >> mode) & 1 for mode in range(modes)]
            for mask in basis
        ],
        dtype=float,
    )
    density = probabilities @ occupations
    density_products = np.einsum(
        "s,si,sj->ij",
        probabilities,
        occupations,
        occupations,
    )
    connected = density_products - np.outer(density, density)
    staggered = np.asarray(
        [(-1.0) ** mode for mode in range(modes)]
    )
    structure_factor = float(
        staggered @ connected @ staggered / modes
    )

    one_body = sum(
        (
            _one_body_density_matrix(ground_space[:, column], basis, modes)
            for column in range(ground_space.shape[1])
        ),
        np.zeros((modes, modes), dtype=complex),
    ) / ground_space.shape[1]
    offdiagonal = one_body - np.diag(np.diag(one_body))

    _, star = _middle_hodge_star(modes)
    square_sign = (-1) ** (particles**2)
    chirality = star if square_sign == 1 else -1j * star
    chiral_values, chiral_vectors = np.linalg.eigh(chirality)
    chiral_spaces = (
        chiral_vectors[:, chiral_values > 0.0],
        chiral_vectors[:, chiral_values < 0.0],
    )
    chiral_spectra: list[np.ndarray] = []
    chiral_ground_states: list[np.ndarray] = []
    for space in chiral_spaces:
        values, vectors = np.linalg.eigh(
            space.conj().T @ sector @ space
        )
        chiral_spectra.append(values)
        chiral_ground_states.append(space @ vectors[:, 0])
    wick_residuals = tuple(
        _density_wick_residual(state, basis, modes)
        for state in chiral_ground_states
    )

    plaquette_energies: list[float] = []
    for plaquette_index in range(len(overlapping_plaquettes(modes))):
        local_term = np.zeros_like(model.hamiltonian)
        for atom_offset, coefficient in enumerate((1.0, 0.8)):
            atom = model.fock_atoms[2 * plaquette_index + atom_offset]
            local_term -= coefficient * (atom + atom.T)
        restricted_term = local_term[np.ix_(basis, basis)]
        plaquette_energies.append(
            float(
                np.trace(
                    ground_space.conj().T
                    @ restricted_term
                    @ ground_space
                ).real
                / ground_space.shape[1]
            )
        )

    plaquettes = overlapping_plaquettes(modes)
    return ExactDiagonalizationAudit(
        modes=modes,
        plaquettes=plaquettes,
        particle_number=particles,
        sector_dimension=comb(modes, particles),
        ground_energy=ground_energy,
        ground_energy_per_plaquette=float(
            eigenvalues[0] / len(plaquettes)
        ),
        sector_gap=float(eigenvalues[1] - eigenvalues[0]),
        ground_multiplicity=int(np.sum(ground_mask)),
        first_distinct_gap=first_distinct_gap,
        chiral_ground_energies=tuple(
            float(spectrum[0]) for spectrum in chiral_spectra
        ),  # type: ignore[arg-type]
        chiral_internal_gaps=tuple(
            float(spectrum[1] - spectrum[0])
            for spectrum in chiral_spectra
        ),  # type: ignore[arg-type]
        chiral_ground_wick_residuals=wick_residuals,  # type: ignore[arg-type]
        plaquette_energy_profile=tuple(plaquette_energies),
        density_profile=tuple(float(value) for value in density),
        staggered_density_structure_factor=structure_factor,
        maximum_offdiagonal_coherence=float(
            np.max(np.abs(offdiagonal))
        ),
    )
