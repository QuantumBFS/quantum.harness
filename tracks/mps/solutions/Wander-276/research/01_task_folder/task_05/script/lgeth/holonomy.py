"""Periodic isospectral unitary orbits and Wilson-loop chaos statistics."""

from __future__ import annotations

import numpy as np
from scipy.linalg import expm

from .bundle_geometry import BundleGeometry


def _normalize_hermitian(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=complex)
    values = 0.5 * (values + values.conj().T)
    values -= np.trace(values) / values.shape[0] * np.eye(
        values.shape[0],
        dtype=complex,
    )
    norm = float(np.linalg.norm(values, 2))
    if norm <= 1e-12:
        raise RuntimeError("local generator has zero spectral norm")
    return values / norm


def _local_hopping_generator(
    length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    sites = length * length
    matrix = np.zeros((sites, sites), dtype=complex)
    for y in range(length):
        for x in range(length):
            source = y * length + x
            for nx, ny in (
                ((x + 1) % length, y),
                (x, (y + 1) % length),
            ):
                destination = ny * length + nx
                amplitude = (
                    rng.normal() + 1j * rng.normal()
                ) / np.sqrt(2.0)
                matrix[destination, source] += amplitude
                matrix[source, destination] += np.conjugate(amplitude)
    return _normalize_hermitian(matrix)


def local_generator_pair(
    length: int,
    seed: int,
    commuting: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Return deterministic local Hermitian generators on a square torus."""

    linear = int(length)
    if linear < 2:
        raise ValueError("generator lattice length must be at least two")
    rng = np.random.default_rng(int(seed))
    sites = linear * linear
    if commuting:
        first = np.diag(rng.normal(size=sites))
        second = np.diag(rng.normal(size=sites))
        return (
            _normalize_hermitian(first),
            _normalize_hermitian(second),
        )
    first = _local_hopping_generator(linear, rng)
    second = _local_hopping_generator(linear, rng)
    if float(np.linalg.norm(first @ second - second @ first)) <= 1e-3:
        raise RuntimeError("noncommuting generator seed is accidentally singular")
    return first, second


def ambient_unitary(
    theta_x: float,
    theta_y: float,
    g: float,
    generators: tuple[np.ndarray, np.ndarray],
) -> np.ndarray:
    """Return a smooth periodic physical-site unitary."""

    coupling = float(g)
    if coupling < 0.0 or not np.isfinite(coupling):
        raise ValueError("g must be finite and nonnegative")
    first, second = (
        np.asarray(generators[0], dtype=complex),
        np.asarray(generators[1], dtype=complex),
    )
    if (
        first.ndim != 2
        or first.shape[0] != first.shape[1]
        or second.shape != first.shape
    ):
        raise ValueError("ambient generators must be equal square matrices")
    return expm(
        1j * coupling * np.sin(float(theta_x)) * first
    ) @ expm(
        1j * coupling * np.sin(float(theta_y)) * second
    )


def deform_orbital_mesh(
    orbital_frames: np.ndarray,
    g: float,
    seed: int,
    commuting: bool,
) -> np.ndarray:
    """Apply the periodic ambient unitary orbit to physical orbital frames."""

    frames = np.asarray(orbital_frames, dtype=complex)
    if frames.ndim != 4 or frames.shape[0] != frames.shape[1]:
        raise ValueError(
            "orbital frames must have shape (mesh, mesh, sites, orbitals)"
        )
    sites = frames.shape[2]
    length = int(round(np.sqrt(sites)))
    if length * length != sites:
        raise ValueError("physical sites do not form a square lattice")
    generators = local_generator_pair(
        length,
        seed=int(seed),
        commuting=bool(commuting),
    )
    mesh = frames.shape[0]
    twists = 2.0 * np.pi * np.arange(mesh) / mesh
    result = np.empty_like(frames)
    for ix, theta_x in enumerate(twists):
        for iy, theta_y in enumerate(twists):
            result[ix, iy] = (
                ambient_unitary(
                    theta_x,
                    theta_y,
                    g,
                    generators,
                )
                @ frames[ix, iy]
            )
    return result


def _circular_gap_ratio(phases: np.ndarray) -> float:
    angles = np.sort(np.mod(np.asarray(phases, dtype=float), 2.0 * np.pi))
    if angles.size < 3:
        raise ValueError("circular gap ratio requires at least three phases")
    spacings = np.diff(np.concatenate([angles, angles[:1] + 2.0 * np.pi]))
    next_spacings = np.roll(spacings, -1)
    maximum = np.maximum(spacings, next_spacings)
    valid = maximum > 1e-14
    if not np.any(valid):
        return 0.0
    ratios = np.minimum(spacings[valid], next_spacings[valid]) / maximum[valid]
    return float(np.mean(ratios))


def _loop_statistics(
    loops: np.ndarray,
    k_values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(loops, dtype=complex)
    count, rank, second = values.shape
    if rank != second:
        raise ValueError("Wilson loops must be square")
    phases = np.empty((count, rank), dtype=float)
    gap_ratio = np.empty(count, dtype=float)
    form_factor = np.empty((count, k_values.size), dtype=float)
    determinant_phase = np.empty(count, dtype=float)
    for index, loop in enumerate(values):
        eigenphases = np.sort(np.angle(np.linalg.eigvals(loop)))
        phases[index] = eigenphases
        gap_ratio[index] = _circular_gap_ratio(eigenphases)
        determinant_phase[index] = float(
            np.angle(np.exp(1j * np.sum(eigenphases)))
        )
        form_factor[index] = [
            abs(np.sum(np.exp(1j * k * eigenphases))) ** 2 / rank
            for k in k_values
        ]
    return phases, gap_ratio, form_factor, determinant_phase


def wilson_statistics(
    geometry: BundleGeometry,
    wilson_x: np.ndarray | None = None,
    wilson_y: np.ndarray | None = None,
    k_values: np.ndarray | None = None,
) -> dict[str, np.ndarray | float]:
    """Return common-phase-invariant Wilson spectral statistics."""

    loops_x = geometry.wilson_x if wilson_x is None else wilson_x
    loops_y = geometry.wilson_y if wilson_y is None else wilson_y
    rank = loops_x.shape[-1]
    if loops_x.shape[-2:] != (rank, rank) or loops_y.shape[-2:] != (
        rank,
        rank,
    ):
        raise ValueError("Wilson loop dimensions disagree")
    ks = (
        np.arange(1, rank + 1, dtype=int)
        if k_values is None
        else np.asarray(k_values, dtype=int)
    )
    if ks.ndim != 1 or ks.size == 0 or np.any(ks < 1):
        raise ValueError("Wilson powers must be positive integers")
    phases_x, gaps_x, form_x, determinant_x = _loop_statistics(
        loops_x,
        ks,
    )
    phases_y, gaps_y, form_y, determinant_y = _loop_statistics(
        loops_y,
        ks,
    )
    return {
        "k_values": ks,
        "phases": np.concatenate([phases_x, phases_y], axis=0),
        "gap_ratio": np.concatenate([gaps_x, gaps_y]),
        "form_factor": np.concatenate([form_x, form_y], axis=0),
        "determinant_phase_x": determinant_x,
        "determinant_phase_y": determinant_y,
        "mean_gap_ratio": float(np.mean(np.concatenate([gaps_x, gaps_y]))),
        "mean_form_factor": np.mean(
            np.concatenate([form_x, form_y], axis=0),
            axis=0,
        ),
    }


def _haar_unitary(
    dimension: int,
    rng: np.random.Generator,
) -> np.ndarray:
    gaussian = (
        rng.normal(size=(dimension, dimension))
        + 1j * rng.normal(size=(dimension, dimension))
    ) / np.sqrt(2.0)
    q, r = np.linalg.qr(gaussian)
    phases = np.diag(r)
    phases = phases / np.abs(phases)
    return q * phases.conj()[None, :]


def cue_wilson_reference(
    D: int,
    samples: int,
    k_values: np.ndarray,
    seed: int,
) -> dict[str, np.ndarray]:
    """Return independent circular-unitary Wilson statistics."""

    rank = int(D)
    count = int(samples)
    ks = np.asarray(k_values, dtype=int)
    if rank < 3 or count < 1 or ks.ndim != 1 or np.any(ks < 1):
        raise ValueError("invalid CUE reference dimensions")
    rng = np.random.default_rng(int(seed))
    gaps = np.empty(count, dtype=float)
    form_factor = np.empty((count, ks.size), dtype=float)
    for sample in range(count):
        unitary = _haar_unitary(rank, rng)
        phases = np.angle(np.linalg.eigvals(unitary))
        gaps[sample] = _circular_gap_ratio(phases)
        form_factor[sample] = [
            abs(np.sum(np.exp(1j * k * phases))) ** 2 / rank
            for k in ks
        ]
    return {
        "k_values": ks,
        "gap_ratio": gaps,
        "form_factor": form_factor,
    }
