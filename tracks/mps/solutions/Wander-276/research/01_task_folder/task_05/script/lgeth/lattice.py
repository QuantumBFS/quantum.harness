"""Independent Kapit--Mueller projected-contact lattice backend.

The algorithms are task-local rewrites of the prior ``qgeom/models.py``,
``qgeom/projected.py``, ``qgeom/softcore.py``, and ``qgeom/operators.py``
implementations at provenance commit ``e4ee4c9``.  This module imports no
code or data from that implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, sqrt

import numpy as np
from scipy import sparse

from .combinatorics import occupation_states


@dataclass(frozen=True)
class Bond:
    """Directed hopping record with integer torus windings."""

    destination: int
    source: int
    amplitude: complex
    winding_x: int
    winding_y: int


@dataclass(frozen=True)
class BosonBasis:
    """Normalized occupation basis at fixed boson number."""

    n_orbitals: int
    n_particles: int

    def __post_init__(self) -> None:
        if self.n_orbitals < 1:
            raise ValueError("n_orbitals must be positive")
        if self.n_particles < 0:
            raise ValueError("n_particles must be nonnegative")
        states = tuple(
            occupation_states(self.n_particles, self.n_orbitals)
        )
        object.__setattr__(self, "states", states)
        object.__setattr__(
            self,
            "index",
            {state: index for index, state in enumerate(states)},
        )

    @property
    def dimension(self) -> int:
        return len(self.states)


@dataclass(frozen=True)
class KapitLaughlinParent:
    """Lowest-band frame and factorized projected contact parent."""

    n_particles: int
    n_flux: int
    length: int
    theta_x: float
    theta_y: float
    basis: BosonBasis
    intermediate_basis: BosonBasis
    bonds: tuple[Bond, ...]
    onebody_energies: np.ndarray
    orbitals: np.ndarray
    constraints: sparse.csr_matrix
    parent: sparse.csr_matrix


def _kapit_mueller_sign(displacement: complex) -> int:
    x = int(round(displacement.real))
    y = int(round(displacement.imag))
    return -1 if (x + y + x * y) % 2 else 1


def kapit_mueller_bonds(
    length: int,
    flux_density: float | None = None,
    image_cutoff: int = 2,
    amplitude_cutoff: float = 1e-13,
) -> tuple[Bond, ...]:
    """Return magneto-periodic Kapit--Mueller hoppings on a square torus."""

    linear_size = int(length)
    density = (
        2.0 / linear_size
        if flux_density is None
        else float(flux_density)
    )
    if linear_size <= 2:
        raise ValueError("length must exceed two")
    if not 0.0 < density < 1.0:
        raise ValueError("flux_density must lie in (0,1)")
    if image_cutoff < 0:
        raise ValueError("image_cutoff must be nonnegative")
    positions = tuple(
        complex(x, y)
        for y in range(linear_size)
        for x in range(linear_size)
    )
    bonds: list[Bond] = []
    for destination, z_destination in enumerate(positions):
        for source in range(destination + 1, len(positions)):
            base = positions[source] - z_destination
            for winding_x in range(-image_cutoff, image_cutoff + 1):
                for winding_y in range(
                    -image_cutoff,
                    image_cutoff + 1,
                ):
                    image = complex(
                        winding_x * linear_size,
                        winding_y * linear_size,
                    )
                    displacement = base + image
                    if abs(displacement) < 1e-14:
                        continue
                    envelope = np.exp(
                        -0.5
                        * np.pi
                        * (1.0 - density)
                        * abs(displacement) ** 2
                    )
                    gauge_phase = np.exp(
                        0.5
                        * np.pi
                        * density
                        * (
                            z_destination
                            * np.conjugate(displacement)
                            - np.conjugate(z_destination)
                            * displacement
                        )
                    )
                    extension_phase = np.exp(
                        0.5
                        * np.pi
                        * density
                        * (
                            z_destination * np.conjugate(image)
                            - np.conjugate(z_destination) * image
                        )
                    )
                    amplitude = (
                        _kapit_mueller_sign(displacement)
                        * envelope
                        * gauge_phase
                        * extension_phase
                    )
                    if abs(amplitude) >= amplitude_cutoff:
                        bonds.append(
                            Bond(
                                destination=destination,
                                source=source,
                                amplitude=complex(amplitude),
                                winding_x=winding_x,
                                winding_y=winding_y,
                            )
                        )
    return tuple(bonds)


def one_body_hamiltonian(
    n_sites: int,
    bonds: tuple[Bond, ...],
    theta_x: float = 0.0,
    theta_y: float = 0.0,
) -> sparse.csr_matrix:
    """Assemble the twist-dependent Hermitian single-particle matrix."""

    sites = int(n_sites)
    if sites < 1:
        raise ValueError("n_sites must be positive")
    rows: list[int] = []
    columns: list[int] = []
    data: list[complex] = []
    for bond in bonds:
        if not (
            0 <= bond.destination < sites
            and 0 <= bond.source < sites
        ):
            raise IndexError("bond endpoint is outside the lattice")
        phase = np.exp(
            1j
            * (
                bond.winding_x * float(theta_x)
                + bond.winding_y * float(theta_y)
            )
        )
        amplitude = bond.amplitude * phase
        rows.extend((bond.destination, bond.source))
        columns.extend((bond.source, bond.destination))
        data.extend((amplitude, np.conjugate(amplitude)))
    matrix = sparse.coo_matrix(
        (np.asarray(data, dtype=complex), (rows, columns)),
        shape=(sites, sites),
    ).tocsr()
    matrix.sum_duplicates()
    return matrix


def lowest_band_frame(
    n_sites: int,
    bonds: tuple[Bond, ...],
    n_orbitals: int,
    theta_x: float,
    theta_y: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Diagonalize the one-body problem and return its lowest-band frame."""

    orbitals = int(n_orbitals)
    if not 0 < orbitals < n_sites:
        raise ValueError("require 0<n_orbitals<n_sites")
    matrix = one_body_hamiltonian(
        n_sites,
        bonds,
        theta_x,
        theta_y,
    ).toarray()
    energies, frame = np.linalg.eigh(matrix)
    return energies, frame[:, :orbitals]


def projected_contact_constraints(
    basis: BosonBasis,
    orbitals: np.ndarray,
    onsite_u: float = 1.0,
    amplitude_cutoff: float = 1e-14,
) -> tuple[sparse.csr_matrix, BosonBasis]:
    """Return ``C`` such that the projected contact parent is ``C^dagger C``."""

    frame = np.asarray(orbitals, dtype=complex)
    if basis.n_particles < 2:
        raise ValueError("contact constraints require at least two particles")
    if frame.ndim != 2 or frame.shape[1] != basis.n_orbitals:
        raise ValueError("orbital frame and basis disagree")
    if onsite_u <= 0.0:
        raise ValueError("onsite_u must be positive")
    if not np.allclose(
        frame.conj().T @ frame,
        np.eye(basis.n_orbitals),
        atol=1e-11,
    ):
        raise ValueError("orbitals must have orthonormal columns")
    intermediate = BosonBasis(
        basis.n_orbitals,
        basis.n_particles - 2,
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
                for physical in range(physical_sites):
                    coefficient = (
                        prefactor
                        * frame[physical, left] ** 2
                        * occupation_factor
                    )
                    if abs(coefficient) > amplitude_cutoff:
                        rows.append(
                            physical * intermediate.dimension
                            + intermediate_index
                        )
                        columns.append(column)
                        data.append(coefficient)
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
                for physical in range(physical_sites):
                    coefficient = (
                        2.0
                        * prefactor
                        * frame[physical, left]
                        * frame[physical, right]
                        * occupation_factor
                    )
                    if abs(coefficient) > amplitude_cutoff:
                        rows.append(
                            physical * intermediate.dimension
                            + intermediate_index
                        )
                        columns.append(column)
                        data.append(coefficient)
    constraints = sparse.coo_matrix(
        (
            np.asarray(data, dtype=complex),
            (rows, columns),
        ),
        shape=(
            physical_sites * intermediate.dimension,
            basis.dimension,
        ),
    ).tocsr()
    constraints.sum_duplicates()
    return constraints, intermediate


def projected_contact_parent(
    basis: BosonBasis,
    orbitals: np.ndarray,
) -> tuple[sparse.csr_matrix, sparse.csr_matrix, BosonBasis]:
    """Return the positive projected parent, its factor, and lower basis."""

    constraints, intermediate = projected_contact_constraints(
        basis,
        orbitals,
    )
    parent = (constraints.conj().T @ constraints).tocsr()
    parent.sum_duplicates()
    return parent, constraints, intermediate


def build_kapit_laughlin_parent(
    n_particles: int,
    n_flux: int,
    theta_x: float,
    theta_y: float,
) -> KapitLaughlinParent:
    """Build a commensurate Kapit--Mueller projected-contact parent."""

    flux = int(n_flux)
    if flux % 2:
        raise ValueError("the registered sequence requires even n_flux")
    length = flux // 2
    if length <= 2:
        raise ValueError("the registered sequence requires n_flux>=8")
    bonds = kapit_mueller_bonds(length)
    energies, orbitals = lowest_band_frame(
        length * length,
        bonds,
        flux,
        theta_x,
        theta_y,
    )
    basis = BosonBasis(flux, int(n_particles))
    parent, constraints, intermediate = projected_contact_parent(
        basis,
        orbitals,
    )
    return KapitLaughlinParent(
        n_particles=int(n_particles),
        n_flux=flux,
        length=length,
        theta_x=float(theta_x),
        theta_y=float(theta_y),
        basis=basis,
        intermediate_basis=intermediate,
        bonds=bonds,
        onebody_energies=energies,
        orbitals=orbitals,
        constraints=constraints,
        parent=parent,
    )


def projected_site_potential(
    orbitals: np.ndarray,
    potential: np.ndarray,
) -> np.ndarray:
    """Project a real physical-site potential into the Chern band."""

    frame = np.asarray(orbitals, dtype=complex)
    values = np.asarray(potential, dtype=float)
    if frame.ndim != 2 or values.shape != (frame.shape[0],):
        raise ValueError("potential and orbital frame disagree")
    projected = frame.conj().T @ (values[:, None] * frame)
    return 0.5 * (projected + projected.conj().T)


def manybody_one_body_operator(
    basis: BosonBasis,
    one_body: np.ndarray,
    amplitude_cutoff: float = 1e-14,
) -> sparse.csr_matrix:
    """Second-quantize a Hermitian one-body operator."""

    matrix = np.asarray(one_body, dtype=complex)
    if matrix.shape != (basis.n_orbitals, basis.n_orbitals):
        raise ValueError("one-body matrix has the wrong shape")
    if not np.allclose(matrix, matrix.conj().T, atol=1e-11):
        raise ValueError("one-body matrix must be Hermitian")
    rows: list[int] = []
    columns: list[int] = []
    data: list[complex] = []
    for column, state in enumerate(basis.states):
        for source, population in enumerate(state):
            if population == 0:
                continue
            for destination in range(basis.n_orbitals):
                coefficient = matrix[destination, source]
                if abs(coefficient) <= amplitude_cutoff:
                    continue
                if destination == source:
                    target = state
                    factor = float(population)
                else:
                    updated = list(state)
                    factor = sqrt(
                        population * (updated[destination] + 1)
                    )
                    updated[source] -= 1
                    updated[destination] += 1
                    target = tuple(updated)
                rows.append(basis.index[target])
                columns.append(column)
                data.append(coefficient * factor)
    operator = sparse.coo_matrix(
        (
            np.asarray(data, dtype=complex),
            (rows, columns),
        ),
        shape=(basis.dimension, basis.dimension),
    ).tocsr()
    operator.sum_duplicates()
    return operator


def channel_matrix(
    energies_p: np.ndarray,
    vectors_p: np.ndarray,
    energies_q: np.ndarray,
    vectors_q: np.ndarray,
    tangent: sparse.spmatrix,
) -> np.ndarray:
    """Return the external Kubo response channel of an isolated multiplet."""

    ep = np.asarray(energies_p, dtype=float)
    eq = np.asarray(energies_q, dtype=float)
    frame_p = np.asarray(vectors_p, dtype=complex)
    frame_q = np.asarray(vectors_q, dtype=complex)
    if ep.size == 0 or eq.size == 0:
        raise ValueError("both target and external sectors must be nonempty")
    reference = float(np.mean(ep))
    denominators = reference - eq
    scale = max(1.0, abs(reference), float(np.max(np.abs(eq))))
    if np.any(np.abs(denominators) <= 1e-12 * scale):
        raise ValueError("external denominator closes")
    applied = tangent @ frame_q
    elements = frame_p.conj().T @ np.asarray(applied)
    return np.asarray(elements / denominators[None, :], dtype=complex)


def random_local_potential(n_sites: int, seed: int) -> np.ndarray:
    """Return a deterministic normalized zero-mean local potential."""

    rng = np.random.default_rng(int(seed))
    values = rng.normal(size=int(n_sites))
    values -= np.mean(values)
    norm = np.linalg.norm(values)
    if norm <= 0.0:
        raise RuntimeError("random potential has zero norm")
    return values / norm


def numerical_rank(
    matrix: np.ndarray,
    rtol: float = 1e-10,
) -> int:
    """Return a scale-aware singular-value rank."""

    values = np.linalg.svd(
        np.asarray(matrix, dtype=complex),
        compute_uv=False,
    )
    if values.size == 0:
        return 0
    return int(np.count_nonzero(values > rtol * values[0]))
