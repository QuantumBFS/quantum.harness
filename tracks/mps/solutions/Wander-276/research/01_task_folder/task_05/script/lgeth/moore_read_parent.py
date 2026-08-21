"""Factorized continuum-LLL three-body Moore--Read parents."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
from scipy import sparse

from .continuum_lll_parent import guiding_center_coherent_state
from .lattice import BosonBasis


@dataclass(frozen=True)
class ContinuumMooreReadParent:
    """Continuum-LLL three-body parent stored through its factor ``C_3``."""

    n_particles: int
    n_flux: int
    length: int
    basis: BosonBasis
    intermediate_basis: BosonBasis
    orbitals: np.ndarray
    constraints: sparse.csr_matrix


def _append_column_block(
    rows: list[int],
    columns: list[int],
    data: list[complex],
    values: np.ndarray,
    intermediate_index: int,
    intermediate_dimension: int,
    column: int,
    amplitude_cutoff: float,
) -> None:
    coefficients = np.asarray(values, dtype=complex)
    active = np.flatnonzero(np.abs(coefficients) > float(amplitude_cutoff))
    rows.extend(
        (active * int(intermediate_dimension) + int(intermediate_index)).tolist()
    )
    columns.extend([int(column)] * int(active.size))
    data.extend(coefficients[active].tolist())


def three_body_annihilation_constraints(
    basis: BosonBasis,
    coefficient_frame: np.ndarray,
    onsite_u: float = 1.0,
    amplitude_cutoff: float = 1e-14,
) -> tuple[sparse.csr_matrix, BosonBasis]:
    """Return stacked normalized projected constraints ``b_x^3/sqrt(3!)``."""

    frame = np.asarray(coefficient_frame, dtype=complex)
    if basis.n_particles < 3:
        raise ValueError("three-body constraints require at least three particles")
    if frame.ndim != 2 or frame.shape[1] != basis.n_orbitals:
        raise ValueError("coefficient frame and basis disagree")
    if frame.shape[0] < basis.n_orbitals:
        raise ValueError("coefficient frame cannot have fewer rows than orbitals")
    if np.linalg.matrix_rank(frame) != basis.n_orbitals:
        raise ValueError("coefficient frame must have full column rank")
    if not np.isfinite(onsite_u) or float(onsite_u) <= 0.0:
        raise ValueError("onsite_u must be finite and positive")
    if not np.isfinite(amplitude_cutoff) or float(amplitude_cutoff) < 0.0:
        raise ValueError("amplitude_cutoff must be finite and nonnegative")

    intermediate = BosonBasis(basis.n_orbitals, basis.n_particles - 3)
    physical_sites = frame.shape[0]
    prefactor = sqrt(float(onsite_u) / 6.0)
    rows: list[int] = []
    columns: list[int] = []
    data: list[complex] = []

    for column, state in enumerate(basis.states):
        for first in range(basis.n_orbitals):
            population_first = state[first]
            if population_first >= 3:
                updated = list(state)
                updated[first] -= 3
                index = intermediate.index[tuple(updated)]
                factor = sqrt(
                    population_first
                    * (population_first - 1)
                    * (population_first - 2)
                )
                _append_column_block(
                    rows,
                    columns,
                    data,
                    prefactor * frame[:, first] ** 3 * factor,
                    index,
                    intermediate.dimension,
                    column,
                    amplitude_cutoff,
                )

            if population_first >= 2:
                for second in range(basis.n_orbitals):
                    if second == first or state[second] == 0:
                        continue
                    updated = list(state)
                    updated[first] -= 2
                    updated[second] -= 1
                    index = intermediate.index[tuple(updated)]
                    factor = sqrt(
                        population_first
                        * (population_first - 1)
                        * state[second]
                    )
                    _append_column_block(
                        rows,
                        columns,
                        data,
                        3.0
                        * prefactor
                        * frame[:, first] ** 2
                        * frame[:, second]
                        * factor,
                        index,
                        intermediate.dimension,
                        column,
                        amplitude_cutoff,
                    )

            if population_first == 0:
                continue
            for second in range(first + 1, basis.n_orbitals):
                if state[second] == 0:
                    continue
                for third in range(second + 1, basis.n_orbitals):
                    if state[third] == 0:
                        continue
                    updated = list(state)
                    updated[first] -= 1
                    updated[second] -= 1
                    updated[third] -= 1
                    index = intermediate.index[tuple(updated)]
                    factor = sqrt(
                        population_first * state[second] * state[third]
                    )
                    _append_column_block(
                        rows,
                        columns,
                        data,
                        6.0
                        * prefactor
                        * frame[:, first]
                        * frame[:, second]
                        * frame[:, third]
                        * factor,
                        index,
                        intermediate.dimension,
                        column,
                        amplitude_cutoff,
                    )

    constraints = sparse.coo_matrix(
        (np.asarray(data, dtype=complex), (rows, columns)),
        shape=(physical_sites * intermediate.dimension, basis.dimension),
        dtype=complex,
    ).tocsr()
    constraints.sum_duplicates()
    constraints.eliminate_zeros()
    return constraints, intermediate


def coherent_state_constraint_frame(
    n_flux: int,
    *,
    image_cutoff: int = 8,
) -> np.ndarray:
    """Return the complete magnetic-translation orbit of one LLL coherent state."""

    flux = int(n_flux)
    if flux < 2:
        raise ValueError("n_flux must be at least two")
    return np.asarray(
        [
            guiding_center_coherent_state(
                flux,
                shift,
                phase,
                image_cutoff=int(image_cutoff),
            )
            for phase in range(flux)
            for shift in range(flux)
        ],
        dtype=complex,
    )


def build_continuum_moore_read_parent(
    n_particles: int,
    n_flux: int,
    *,
    image_cutoff: int = 8,
) -> ContinuumMooreReadParent:
    """Build a coherent-state factorization of the bosonic three-body parent."""

    particles = int(n_particles)
    flux = int(n_flux)
    if particles < 3:
        raise ValueError("Moore--Read parent requires at least three particles")
    if flux < particles:
        raise ValueError("Moore--Read quasihole sequence requires n_flux>=N")
    length = flux
    orbitals = coherent_state_constraint_frame(
        flux,
        image_cutoff=int(image_cutoff),
    )
    basis = BosonBasis(flux, particles)
    constraints, intermediate = three_body_annihilation_constraints(
        basis,
        orbitals,
    )
    return ContinuumMooreReadParent(
        n_particles=particles,
        n_flux=flux,
        length=length,
        basis=basis,
        intermediate_basis=intermediate,
        orbitals=orbitals,
        constraints=constraints,
    )
