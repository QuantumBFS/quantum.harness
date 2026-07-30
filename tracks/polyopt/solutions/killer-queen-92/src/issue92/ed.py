"""Number-sector exact diagonalization for finite rooted patches.

Nothing in this module is a thermodynamic-limit certificate.  It is an
independent finite-system baseline for signs, cutoff conventions, and local
observables.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from math import sqrt
from time import perf_counter

import networkx as nx
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh


@lru_cache(maxsize=None)
def sector_basis(sites: int, nmax: int, total_particles: int) -> tuple[tuple[int, ...], ...]:
    """Enumerate bounded weak compositions in deterministic lexicographic order."""
    if sites < 1 or nmax < 1 or total_particles < 0 or total_particles > sites * nmax:
        return ()

    states: list[tuple[int, ...]] = []

    def extend(prefix: tuple[int, ...], sites_left: int, particles_left: int) -> None:
        if sites_left == 1:
            if 0 <= particles_left <= nmax:
                states.append(prefix + (particles_left,))
            return
        minimum = max(0, particles_left - nmax * (sites_left - 1))
        maximum = min(nmax, particles_left)
        for occupation in range(minimum, maximum + 1):
            extend(prefix + (occupation,), sites_left - 1, particles_left - occupation)

    extend((), sites, total_particles)
    return tuple(states)


def sector_hamiltonian(
    graph: nx.Graph,
    basis: tuple[tuple[int, ...], ...],
    *,
    nmax: int,
    hopping: float,
    interaction: float,
    mu: float,
) -> sparse.csr_matrix:
    """Assemble the truncated Bose--Hubbard Hamiltonian in one number sector."""
    dimension = len(basis)
    if dimension == 0:
        return sparse.csr_matrix((0, 0), dtype=float)
    if set(graph.nodes) != set(range(graph.number_of_nodes())):
        raise ValueError("graph nodes must be consecutive integers starting at zero")

    lookup = {state: index for index, state in enumerate(basis)}
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    edges = [tuple(sorted(edge)) for edge in graph.edges]

    for column, state in enumerate(basis):
        occupation = np.asarray(state, dtype=float)
        diagonal = 0.5 * interaction * np.sum(occupation * (occupation - 1.0))
        diagonal -= mu * np.sum(occupation)
        rows.append(column)
        columns.append(column)
        values.append(float(diagonal))

        for first, second in edges:
            for source, target in ((first, second), (second, first)):
                if state[source] == 0 or state[target] == nmax:
                    continue
                moved = list(state)
                moved[source] -= 1
                moved[target] += 1
                row = lookup[tuple(moved)]
                amplitude = -hopping * sqrt(state[source] * (state[target] + 1))
                rows.append(row)
                columns.append(column)
                values.append(amplitude)

    matrix = sparse.coo_matrix((values, (rows, columns)), shape=(dimension, dimension))
    return matrix.tocsr()


def _lowest_pairs(
    matrix: sparse.csr_matrix, count: int = 2, dense_threshold: int = 4096
) -> tuple[np.ndarray, np.ndarray]:
    dimension = matrix.shape[0]
    if dimension == 0:
        return np.empty(0), np.empty((0, 0))
    if dimension <= dense_threshold or dimension <= count:
        values, vectors = np.linalg.eigh(matrix.toarray())
        return values[:count], vectors[:, :count]
    requested = min(count, dimension - 1)
    values, vectors = eigsh(matrix, k=requested, which="SA", tol=1e-11)
    order = np.argsort(values)
    return values[order], vectors[:, order]


def _root_observables(
    graph: nx.Graph,
    basis: tuple[tuple[int, ...], ...],
    state_vector: np.ndarray,
    coordination: int,
) -> tuple[float, float, float]:
    probabilities = np.abs(state_vector) ** 2
    root_occupations = np.asarray([state[0] for state in basis], dtype=float)
    rho0 = float(probabilities @ root_occupations)
    fluctuation = float(probabilities @ ((root_occupations - 1.0) ** 2))

    lookup = {state: index for index, state in enumerate(basis)}
    kinetic = 0.0 + 0.0j
    for neighbor in graph.neighbors(0):
        for column, state in enumerate(basis):
            for source, target in ((neighbor, 0), (0, neighbor)):
                if state[source] == 0:
                    continue
                # The cutoff is inferred from the maximum occupation represented
                # in the sector; a target at the sector's maximum may still be
                # below nmax, so membership in the fixed basis is the safe test.
                moved = list(state)
                moved[source] -= 1
                moved[target] += 1
                row = lookup.get(tuple(moved))
                if row is None:
                    continue
                amplitude = sqrt(state[source] * (state[target] + 1))
                kinetic += np.conjugate(state_vector[row]) * amplitude * state_vector[column]
    return rho0, fluctuation, float(np.real_if_close(kinetic / coordination))


@dataclass
class EDResult:
    claim_type: str
    geometry: str
    patch_source: str
    radius: int
    sites: int
    edges: int
    root_degree: int
    infinite_coordination: int
    nmax: int
    interaction: float
    hopping: float
    mu: float
    hilbert_dimension: int
    largest_sector_dimension: int
    ground_sector: int
    ground_sector_dimension: int
    ground_energy: float
    first_excited_energy: float
    finite_patch_gap: float
    ground_degeneracy: int
    rho0: float
    F0: float
    K0: float
    runtime_s: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def solve_finite_patch(
    graph: nx.Graph,
    *,
    nmax: int,
    hopping: float,
    interaction: float = 1.0,
    mu: float = 0.5,
    dense_threshold: int = 4096,
) -> EDResult:
    """Diagonalize all number sectors and return the two lowest grand-canonical levels."""
    start = perf_counter()
    sites = graph.number_of_nodes()
    coordination = int(graph.graph["infinite_coordination"])
    candidates: list[tuple[float, int, int, np.ndarray, tuple[tuple[int, ...], ...]]] = []
    largest_sector = 0

    for particle_number in range(sites * nmax + 1):
        basis = sector_basis(sites, nmax, particle_number)
        largest_sector = max(largest_sector, len(basis))
        matrix = sector_hamiltonian(
            graph,
            basis,
            nmax=nmax,
            hopping=hopping,
            interaction=interaction,
            mu=mu,
        )
        values, vectors = _lowest_pairs(matrix, count=2, dense_threshold=dense_threshold)
        for level, energy in enumerate(values):
            candidates.append((float(energy), particle_number, len(basis), vectors[:, level], basis))

    candidates.sort(key=lambda item: item[0])
    if len(candidates) < 2:
        raise RuntimeError("finite patch does not contain two energy levels")
    ground = candidates[0]
    first_excited = candidates[1]
    tolerance = 1e-9 * max(1.0, abs(ground[0]))
    degeneracy = sum(abs(candidate[0] - ground[0]) <= tolerance for candidate in candidates)
    rho0, fluctuation, kinetic = _root_observables(
        graph, ground[4], ground[3], coordination
    )
    elapsed = perf_counter() - start

    return EDResult(
        claim_type="FINITE_OPEN_PATCH_NOT_THERMODYNAMIC_CERTIFICATE",
        geometry=str(graph.graph["geometry"]),
        patch_source=str(graph.graph["source"]),
        radius=int(graph.graph["radius"]),
        sites=sites,
        edges=graph.number_of_edges(),
        root_degree=graph.degree[0],
        infinite_coordination=coordination,
        nmax=nmax,
        interaction=interaction,
        hopping=hopping,
        mu=mu,
        hilbert_dimension=(nmax + 1) ** sites,
        largest_sector_dimension=largest_sector,
        ground_sector=ground[1],
        ground_sector_dimension=ground[2],
        ground_energy=ground[0],
        first_excited_energy=first_excited[0],
        finite_patch_gap=max(0.0, first_excited[0] - ground[0]),
        ground_degeneracy=degeneracy,
        rho0=rho0,
        F0=fluctuation,
        K0=kinetic,
        runtime_s=elapsed,
    )
