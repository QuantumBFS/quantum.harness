"""Gauge-covariant geometry of a degenerate bundle over a periodic mesh."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import factorial, prod, sqrt

import numpy as np
from scipy.linalg import schur

from .lattice import BosonBasis


@dataclass(frozen=True)
class BundleGeometry:
    """Discrete links, curvature, topology, and noncontractible holonomy."""

    link_x: np.ndarray
    link_y: np.ndarray
    plaquette: np.ndarray
    plaquette_curvature: np.ndarray
    wilson_x: np.ndarray
    wilson_y: np.ndarray
    wilson_x_phases: np.ndarray
    wilson_y_phases: np.ndarray
    chern_determinant: float
    chern_trace_log: float
    determinant_branch_margin: float
    minimum_overlap_singular_value: float
    maximum_link_unitarity_error: float
    maximum_plaquette_unitarity_error: float


def polar_unitary(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return the polar unitary and singular values of a square overlap."""

    values = np.asarray(matrix, dtype=complex)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError("overlap matrix must be square")
    left, singular_values, right_h = np.linalg.svd(
        values,
        full_matrices=False,
    )
    return left @ right_h, singular_values


@lru_cache(maxsize=None)
def _ordered_particle_indices(
    state: tuple[int, ...],
) -> tuple[tuple[int, ...], ...]:
    particles = sum(state)
    if particles == 0:
        return ((),)
    occupations = list(state)
    result: list[tuple[int, ...]] = []

    def visit(prefix: tuple[int, ...]) -> None:
        if len(prefix) == particles:
            result.append(prefix)
            return
        for orbital, population in enumerate(occupations):
            if population == 0:
                continue
            occupations[orbital] -= 1
            visit((*prefix, orbital))
            occupations[orbital] += 1

    visit(())
    return tuple(result)


def _occupation_tensor_amplitude(state: tuple[int, ...]) -> float:
    return sqrt(
        prod(factorial(population) for population in state)
        / factorial(sum(state))
    )


def apply_bosonic_fock_lift(
    basis: BosonBasis,
    single_particle_overlap: np.ndarray,
    frames: np.ndarray,
) -> np.ndarray:
    """Apply the symmetric bosonic lift of a one-particle overlap."""

    overlap = np.asarray(single_particle_overlap, dtype=complex)
    if overlap.shape != (basis.n_orbitals, basis.n_orbitals):
        raise ValueError("single-particle overlap has the wrong shape")
    coefficient_frames = np.asarray(frames, dtype=complex)
    if coefficient_frames.ndim == 1:
        coefficient_frames = coefficient_frames[:, None]
    if (
        coefficient_frames.ndim != 2
        or coefficient_frames.shape[0] != basis.dimension
    ):
        raise ValueError("coefficient frames have the wrong shape")
    particles = basis.n_particles
    vectors = coefficient_frames.shape[1]
    if particles == 0:
        return coefficient_frames.copy()
    tensor = np.zeros(
        (basis.n_orbitals,) * particles + (vectors,),
        dtype=complex,
    )
    for state_index, state in enumerate(basis.states):
        ordered = _ordered_particle_indices(state)
        indices = tuple(
            np.asarray(
                [entry[axis] for entry in ordered],
                dtype=int,
            )
            for axis in range(particles)
        )
        tensor[indices + (slice(None),)] = (
            _occupation_tensor_amplitude(state)
            * coefficient_frames[state_index]
        )
    transformed = tensor
    for axis in range(particles):
        transformed = np.tensordot(
            overlap,
            transformed,
            axes=(1, axis),
        )
        transformed = np.moveaxis(transformed, 0, axis)
    result = np.empty(
        (basis.dimension, vectors),
        dtype=complex,
    )
    for state_index, state in enumerate(basis.states):
        ordered = _ordered_particle_indices(state)
        indices = tuple(
            np.asarray(
                [entry[axis] for entry in ordered],
                dtype=int,
            )
            for axis in range(particles)
        )
        result[state_index] = (
            _occupation_tensor_amplitude(state)
            * np.sum(
                transformed[indices + (slice(None),)],
                axis=0,
            )
        )
    return result


def manybody_frame_overlap(
    basis: BosonBasis,
    left_frame: np.ndarray,
    right_frame: np.ndarray,
    left_orbitals: np.ndarray,
    right_orbitals: np.ndarray,
) -> np.ndarray:
    """Return the physical overlap of two projected many-body frames."""

    left_orbitals = np.asarray(left_orbitals, dtype=complex)
    right_orbitals = np.asarray(right_orbitals, dtype=complex)
    if left_orbitals.shape != right_orbitals.shape:
        raise ValueError("orbital frames must have equal shape")
    single_overlap = left_orbitals.conj().T @ right_orbitals
    lifted_right = apply_bosonic_fock_lift(
        basis,
        single_overlap,
        right_frame,
    )
    return np.asarray(left_frame, dtype=complex).conj().T @ lifted_right


def _orthonormal_frame(frame: np.ndarray) -> np.ndarray:
    values = np.asarray(frame, dtype=complex)
    if values.ndim != 2 or values.shape[0] < values.shape[1]:
        raise ValueError("frame must be a tall two-dimensional matrix")
    orthonormal, _ = np.linalg.qr(values)
    return orthonormal


def _curvature_from_unitary(
    unitary: np.ndarray,
    area: float,
) -> tuple[np.ndarray, np.ndarray]:
    triangular, vectors = schur(unitary, output="complex")
    phases = np.angle(np.diag(triangular))
    curvature = (
        vectors
        @ np.diag(phases / area)
        @ vectors.conj().T
    )
    return 0.5 * (curvature + curvature.conj().T), phases


def _analyze_overlap_links(
    overlaps_x: np.ndarray,
    overlaps_y: np.ndarray,
    delta_x: float,
    delta_y: float,
) -> BundleGeometry:
    if (
        overlaps_x.ndim != 4
        or overlaps_x.shape != overlaps_y.shape
        or overlaps_x.shape[-1] != overlaps_x.shape[-2]
    ):
        raise ValueError("overlap arrays must have shape (nx, ny, D, D)")
    nx, ny, rank, _ = overlaps_x.shape
    link_x = np.empty_like(overlaps_x, dtype=complex)
    link_y = np.empty_like(overlaps_y, dtype=complex)
    minimum_singular = np.inf
    maximum_link_error = 0.0
    identity = np.eye(rank, dtype=complex)
    for ix in range(nx):
        for iy in range(ny):
            link_x[ix, iy], singular_x = polar_unitary(
                overlaps_x[ix, iy]
            )
            link_y[ix, iy], singular_y = polar_unitary(
                overlaps_y[ix, iy]
            )
            minimum_singular = min(
                minimum_singular,
                float(np.min(singular_x)),
                float(np.min(singular_y)),
            )
            maximum_link_error = max(
                maximum_link_error,
                float(
                    np.linalg.norm(
                        link_x[ix, iy].conj().T
                        @ link_x[ix, iy]
                        - identity
                    )
                ),
                float(
                    np.linalg.norm(
                        link_y[ix, iy].conj().T
                        @ link_y[ix, iy]
                        - identity
                    )
                ),
            )
    plaquette = np.empty_like(link_x)
    curvature = np.empty_like(link_x)
    determinant_flux = 0.0
    trace_log_flux = 0.0
    maximum_plaquette_error = 0.0
    maximum_trace_phase = 0.0
    area = float(delta_x * delta_y)
    for ix in range(nx):
        for iy in range(ny):
            loop = (
                link_x[ix, iy]
                @ link_y[(ix + 1) % nx, iy]
                @ link_x[ix, (iy + 1) % ny].conj().T
                @ link_y[ix, iy].conj().T
            )
            loop, _ = polar_unitary(loop)
            plaquette[ix, iy] = loop
            maximum_plaquette_error = max(
                maximum_plaquette_error,
                float(
                    np.linalg.norm(
                        loop.conj().T @ loop - identity
                    )
                ),
            )
            curvature[ix, iy], phases = _curvature_from_unitary(
                loop,
                area,
            )
            trace_phase = float(np.sum(phases))
            determinant_phase = float(
                np.angle(np.exp(1j * trace_phase))
            )
            determinant_flux += determinant_phase
            trace_log_flux += trace_phase
            maximum_trace_phase = max(
                maximum_trace_phase,
                abs(trace_phase),
            )
    wilson_x = np.empty((ny, rank, rank), dtype=complex)
    wilson_y = np.empty((nx, rank, rank), dtype=complex)
    wilson_x_phases = np.empty((ny, rank), dtype=float)
    wilson_y_phases = np.empty((nx, rank), dtype=float)
    for iy in range(ny):
        loop = identity.copy()
        for ix in range(nx):
            loop = loop @ link_x[ix, iy]
        loop, _ = polar_unitary(loop)
        wilson_x[iy] = loop
        wilson_x_phases[iy] = np.sort(np.angle(np.linalg.eigvals(loop)))
    for ix in range(nx):
        loop = identity.copy()
        for iy in range(ny):
            loop = loop @ link_y[ix, iy]
        loop, _ = polar_unitary(loop)
        wilson_y[ix] = loop
        wilson_y_phases[ix] = np.sort(np.angle(np.linalg.eigvals(loop)))
    return BundleGeometry(
        link_x=link_x,
        link_y=link_y,
        plaquette=plaquette,
        plaquette_curvature=curvature,
        wilson_x=wilson_x,
        wilson_y=wilson_y,
        wilson_x_phases=wilson_x_phases,
        wilson_y_phases=wilson_y_phases,
        chern_determinant=determinant_flux / (2.0 * np.pi),
        chern_trace_log=trace_log_flux / (2.0 * np.pi),
        determinant_branch_margin=float(np.pi - maximum_trace_phase),
        minimum_overlap_singular_value=float(minimum_singular),
        maximum_link_unitarity_error=maximum_link_error,
        maximum_plaquette_unitarity_error=maximum_plaquette_error,
    )


def analyze_ambient_frame_mesh(
    frames: np.ndarray,
) -> BundleGeometry:
    """Analyze a periodic ambient-frame mesh."""

    values = np.asarray(frames, dtype=complex)
    if values.ndim != 4:
        raise ValueError("frames must have shape (nx, ny, ambient, rank)")
    nx, ny, _, rank = values.shape
    normalized = np.empty_like(values)
    for ix in range(nx):
        for iy in range(ny):
            normalized[ix, iy] = _orthonormal_frame(values[ix, iy])
    overlaps_x = np.empty((nx, ny, rank, rank), dtype=complex)
    overlaps_y = np.empty_like(overlaps_x)
    for ix in range(nx):
        for iy in range(ny):
            frame = normalized[ix, iy]
            overlaps_x[ix, iy] = (
                frame.conj().T @ normalized[(ix + 1) % nx, iy]
            )
            overlaps_y[ix, iy] = (
                frame.conj().T @ normalized[ix, (iy + 1) % ny]
            )
    return _analyze_overlap_links(
        overlaps_x,
        overlaps_y,
        2.0 * np.pi / nx,
        2.0 * np.pi / ny,
    )


def analyze_frame_bundle(
    coefficient_frames: np.ndarray,
    orbital_frames: np.ndarray,
    basis: BosonBasis,
) -> BundleGeometry:
    """Analyze physical many-body frames whose orbital bases vary on a mesh."""

    coefficients = np.asarray(coefficient_frames, dtype=complex)
    orbitals = np.asarray(orbital_frames, dtype=complex)
    if (
        coefficients.ndim != 4
        or orbitals.ndim != 4
        or coefficients.shape[:2] != orbitals.shape[:2]
        or coefficients.shape[2] != basis.dimension
        or orbitals.shape[-1] != basis.n_orbitals
    ):
        raise ValueError("coefficient/orbital frame meshes are incompatible")
    nx, ny, _, rank = coefficients.shape
    overlaps_x = np.empty((nx, ny, rank, rank), dtype=complex)
    overlaps_y = np.empty_like(overlaps_x)
    for ix in range(nx):
        for iy in range(ny):
            overlaps_x[ix, iy] = manybody_frame_overlap(
                basis,
                coefficients[ix, iy],
                coefficients[(ix + 1) % nx, iy],
                orbitals[ix, iy],
                orbitals[(ix + 1) % nx, iy],
            )
            overlaps_y[ix, iy] = manybody_frame_overlap(
                basis,
                coefficients[ix, iy],
                coefficients[ix, (iy + 1) % ny],
                orbitals[ix, iy],
                orbitals[ix, (iy + 1) % ny],
            )
    return _analyze_overlap_links(
        overlaps_x,
        overlaps_y,
        2.0 * np.pi / nx,
        2.0 * np.pi / ny,
    )


def random_local_gauge(
    frames: np.ndarray,
    seed: int,
) -> np.ndarray:
    """Apply independent local frame gauges on a periodic mesh."""

    values = np.asarray(frames, dtype=complex)
    if values.ndim != 4:
        raise ValueError("frames must have shape (nx, ny, ambient, rank)")
    rng = np.random.default_rng(int(seed))
    result = np.empty_like(values)
    rank = values.shape[-1]
    for ix in range(values.shape[0]):
        for iy in range(values.shape[1]):
            matrix = rng.normal(size=(rank, rank))
            matrix = matrix + 1j * rng.normal(size=matrix.shape)
            unitary, _ = np.linalg.qr(matrix)
            result[ix, iy] = values[ix, iy] @ unitary
    return result


def sorted_wilson_eigenphases(
    geometry: BundleGeometry,
) -> np.ndarray:
    """Return both noncontractible Wilson-loop phase spectra."""

    return np.concatenate(
        [geometry.wilson_x_phases, geometry.wilson_y_phases],
        axis=0,
    )
