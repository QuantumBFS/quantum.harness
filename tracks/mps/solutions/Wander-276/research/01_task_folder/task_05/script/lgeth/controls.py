"""Independent interventions for spectral and projector-geometric chaos."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .form_factors import form_factor_parts
from .statistics import bulk_gap_ratio_per_spectrum


@dataclass(frozen=True)
class FourierTangentPair:
    """Momentum-resolved real quadratures on a square physical lattice."""

    length: int
    kx: int
    ky: int
    orbit_key: tuple[int, int]
    v: np.ndarray
    w: np.ndarray


@dataclass(frozen=True)
class FixedProjectorControl:
    """Energy statistics varied inside one exactly fixed target projector."""

    alphas: np.ndarray
    times: np.ndarray
    energy_spectra: np.ndarray
    mean_gap_ratio: np.ndarray
    energy_raw: np.ndarray
    energy_disconnected: np.ndarray
    energy_connected: np.ndarray
    projector_distance: np.ndarray
    curvature_spectrum_error: np.ndarray
    seed: int


def fourier_tangent_pairs(length: int) -> list[FourierTangentPair]:
    """Return every nonzero momentum cosine/sine pair exactly once."""

    linear_size = int(length)
    if linear_size < 3 or linear_size % 2 == 0:
        raise ValueError("length must be an odd integer at least three")
    coordinates = np.asarray(
        [
            (x, y)
            for y in range(linear_size)
            for x in range(linear_size)
        ],
        dtype=float,
    )
    pairs: list[FourierTangentPair] = []
    for ky in range(linear_size):
        for kx in range(linear_size):
            if (kx, ky) == (0, 0):
                continue
            phase = (
                2.0
                * np.pi
                * (
                    kx * coordinates[:, 0]
                    + ky * coordinates[:, 1]
                )
                / linear_size
            )
            v = np.cos(phase)
            w = np.sin(phase)
            v -= np.mean(v)
            w -= np.mean(w)
            norm_v = float(np.linalg.norm(v))
            norm_w = float(np.linalg.norm(w))
            if norm_v <= 1e-14 or norm_w <= 1e-14:
                raise RuntimeError("nonzero momentum has a null real quadrature")
            v /= norm_v
            w /= norm_w
            inverse = (
                (-kx) % linear_size,
                (-ky) % linear_size,
            )
            orbit_key = min((kx, ky), inverse)
            pairs.append(
                FourierTangentPair(
                    length=linear_size,
                    kx=kx,
                    ky=ky,
                    orbit_key=orbit_key,
                    v=v,
                    w=w,
                )
            )
    return pairs


def _validated_tangent_gram(
    tangent_gram: np.ndarray,
    dimension: int,
) -> np.ndarray:
    gram = np.asarray(tangent_gram, dtype=float)
    if gram.shape != (dimension, dimension):
        raise ValueError("tangent_gram has the wrong shape")
    if np.any(~np.isfinite(gram)):
        raise ValueError("tangent_gram must be finite")
    gram = 0.5 * (gram + gram.T)
    eigenvalues = np.linalg.eigvalsh(gram)
    if float(eigenvalues[0]) < -1e-10 * max(
        float(eigenvalues[-1]),
        1.0,
    ):
        raise ValueError("tangent_gram must be positive semidefinite")
    return gram


def gram_normalize(
    values: np.ndarray,
    tangent_gram: np.ndarray,
) -> np.ndarray:
    """Mean-center and normalize a coefficient vector in the tangent Gram."""

    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1 or vector.size < 2 or np.any(~np.isfinite(vector)):
        raise ValueError("tangent coefficients must be a finite vector")
    gram = _validated_tangent_gram(tangent_gram, vector.size)
    centered = vector - np.mean(vector)
    norm_squared = float(centered @ gram @ centered)
    if norm_squared <= 1e-24:
        raise ValueError("tangent coefficients have zero Gram norm")
    return centered / np.sqrt(norm_squared)


def scrambled_tangent_pair(
    pair: FourierTangentPair,
    random_v: np.ndarray,
    random_w: np.ndarray,
    g: float,
    tangent_gram: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate from a structured momentum pair to random local tangents."""

    coupling = float(g)
    if not 0.0 <= coupling <= 1.0:
        raise ValueError("g must lie in [0,1]")
    if pair.v.shape != pair.w.shape:
        raise ValueError("Fourier tangent pair has inconsistent shapes")
    gram = _validated_tangent_gram(tangent_gram, pair.v.size)
    structured_v = gram_normalize(pair.v, gram)
    structured_w = gram_normalize(pair.w, gram)
    residual_v = gram_normalize(random_v, gram)
    residual_w = gram_normalize(random_w, gram)
    mixed_v = (
        np.sqrt(1.0 - coupling) * structured_v
        + np.sqrt(coupling) * residual_v
    )
    mixed_w = (
        np.sqrt(1.0 - coupling) * structured_w
        + np.sqrt(coupling) * residual_w
    )
    return (
        gram_normalize(mixed_v, gram),
        gram_normalize(mixed_w, gram),
    )


def _center_and_normalize_hermitian(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=complex)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError("matrix must be square")
    values = 0.5 * (values + values.conj().T)
    values -= np.trace(values) / values.shape[0] * np.eye(
        values.shape[0],
        dtype=complex,
    )
    norm = float(np.linalg.norm(values))
    if norm <= 1e-14:
        raise RuntimeError("Hermitian control has zero norm")
    return values / norm


def _numerical_projector_distance(
    target_block: np.ndarray,
) -> float:
    dimension = int(target_block.shape[0])
    full = np.zeros((2 * dimension, 2 * dimension), dtype=complex)
    full[:dimension, :dimension] = 0.1 * target_block
    full[dimension:, dimension:] = np.diag(
        np.linspace(2.0, 3.0, dimension)
    )
    eigenvalues, eigenvectors = np.linalg.eigh(full)
    if float(eigenvalues[dimension - 1]) >= float(eigenvalues[dimension]):
        raise RuntimeError("fixed-projector control closed its external gap")
    observed = (
        eigenvectors[:, :dimension]
        @ eigenvectors[:, :dimension].conj().T
    )
    expected = np.zeros_like(full)
    expected[:dimension, :dimension] = np.eye(dimension)
    return float(np.linalg.norm(observed - expected))


def projector_curvature_invariance(
    reference_spectrum: np.ndarray,
    repeated_spectra: np.ndarray,
) -> dict[str, float]:
    """Return maximum absolute and relative errors of repeated curvature data."""

    reference = np.asarray(reference_spectrum, dtype=float)
    repeated = np.asarray(repeated_spectra, dtype=float)
    if reference.ndim != 1 or repeated.ndim != 2:
        raise ValueError("reference must be 1D and repeated_spectra must be 2D")
    if repeated.shape[1] != reference.size:
        raise ValueError("curvature spectra have incompatible dimensions")
    difference = repeated - reference[None, :]
    absolute = float(np.max(np.abs(difference)))
    scale = max(float(np.max(np.abs(reference))), 1e-15)
    return {
        "maximum_absolute_error": absolute,
        "maximum_relative_error": absolute / scale,
    }


def fixed_projector_spectral_ensemble(
    dimension: int,
    samples: int,
    alphas: np.ndarray,
    seed: int,
    reference_curvature_spectrum: np.ndarray | None = None,
    times: np.ndarray | None = None,
) -> FixedProjectorControl:
    """Generate a Poisson-to-GUE interpolation inside one fixed projector."""

    rank = int(dimension)
    count = int(samples)
    alpha_grid = np.asarray(alphas, dtype=float)
    time_grid = (
        np.linspace(0.0, 3.0, 61)
        if times is None
        else np.asarray(times, dtype=float)
    )
    if rank < 4 or count < 2:
        raise ValueError("require dimension>=4 and samples>=2")
    if (
        alpha_grid.ndim != 1
        or alpha_grid.size < 1
        or np.any(~np.isfinite(alpha_grid))
        or np.any((alpha_grid < 0.0) | (alpha_grid > 1.0))
    ):
        raise ValueError("alphas must be a finite one-dimensional grid in [0,1]")
    if (
        time_grid.ndim != 1
        or time_grid.size < 1
        or np.any(~np.isfinite(time_grid))
    ):
        raise ValueError("times must be a finite one-dimensional grid")
    if reference_curvature_spectrum is None:
        reference = np.linspace(-1.0, 1.0, rank)
    else:
        reference = np.asarray(
            reference_curvature_spectrum,
            dtype=float,
        )
    if reference.shape != (rank,) or np.any(~np.isfinite(reference)):
        raise ValueError("reference_curvature_spectrum must match dimension")
    rng = np.random.default_rng(int(seed))
    spectra = np.empty(
        (alpha_grid.size, count, rank),
        dtype=np.float32,
    )
    first_matrices = np.empty(
        (alpha_grid.size, rank, rank),
        dtype=complex,
    )
    for sample in range(count):
        spacings = rng.exponential(size=rank)
        levels = np.cumsum(spacings)
        poisson_matrix = _center_and_normalize_hermitian(
            np.diag(levels)
        )
        gaussian = (
            rng.normal(size=(rank, rank))
            + 1j * rng.normal(size=(rank, rank))
        )
        gue_matrix = _center_and_normalize_hermitian(
            gaussian + gaussian.conj().T
        )
        for index, alpha in enumerate(alpha_grid):
            matrix = (
                np.sqrt(1.0 - alpha * alpha) * poisson_matrix
                + alpha * gue_matrix
            )
            spectra[index, sample] = np.linalg.eigvalsh(matrix)
            if sample == 0:
                first_matrices[index] = matrix
    mean_gap_ratio = np.empty(alpha_grid.size, dtype=float)
    raw = np.empty((alpha_grid.size, time_grid.size), dtype=float)
    disconnected = np.empty_like(raw)
    connected = np.empty_like(raw)
    projector_distance = np.empty(alpha_grid.size, dtype=float)
    repeated_curvature = np.repeat(
        reference[None, :],
        alpha_grid.size,
        axis=0,
    )
    for index, alpha in enumerate(alpha_grid):
        mean_gap_ratio[index] = float(
            np.mean(
                bulk_gap_ratio_per_spectrum(
                    spectra[index],
                    bulk_fraction=0.7,
                )
            )
        )
        parts = form_factor_parts(spectra[index], time_grid)
        raw[index] = parts.raw
        disconnected[index] = parts.disconnected
        connected[index] = parts.connected
        projector_distance[index] = _numerical_projector_distance(
            first_matrices[index]
        )
    invariance = projector_curvature_invariance(
        reference,
        repeated_curvature,
    )
    curvature_error = np.full(
        alpha_grid.size,
        invariance["maximum_absolute_error"],
        dtype=float,
    )
    return FixedProjectorControl(
        alphas=alpha_grid,
        times=time_grid,
        energy_spectra=spectra,
        mean_gap_ratio=mean_gap_ratio,
        energy_raw=raw,
        energy_disconnected=disconnected,
        energy_connected=connected,
        projector_distance=projector_distance,
        curvature_spectrum_error=curvature_error,
        seed=int(seed),
    )
