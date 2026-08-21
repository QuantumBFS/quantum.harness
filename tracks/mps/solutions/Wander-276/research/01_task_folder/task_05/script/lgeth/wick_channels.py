"""Gauge-invariant covariance-matched four-channel Wick statistics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .manybody_response import SiteResponseCache


@dataclass(frozen=True)
class WhitenedChannels:
    """Channel tensor after exact whitening on its label support."""

    channels: np.ndarray
    covariance: np.ndarray
    covariance_eigenvalues: np.ndarray
    inverse_sqrt: np.ndarray


@dataclass(frozen=True)
class WickResult:
    """Four-channel tensor, separable Wick prediction, and residual."""

    tensor: np.ndarray
    wick_tensor: np.ndarray
    connected: np.ndarray
    R4: float
    A_left: float
    B_right: float
    left_eigenvalues: np.ndarray
    right_eigenvalues: np.ndarray
    channel_covariance_eigenvalues: np.ndarray


def _toroidal_distance_squared(
    first: int,
    second: int,
    length: int,
) -> float:
    ax, ay = first % length, first // length
    bx, by = second % length, second // length
    dx = min(abs(ax - bx), length - abs(ax - bx))
    dy = min(abs(ay - by), length - abs(ay - by))
    return float(dx * dx + dy * dy)


def _farthest_site_subset(
    length: int,
    count: int,
    start: int,
    tie_order: np.ndarray,
) -> tuple[int, ...]:
    sites = length * length
    chosen = [int(start)]
    priority = {int(site): index for index, site in enumerate(tie_order)}
    while len(chosen) < count:
        candidates = [site for site in range(sites) if site not in chosen]
        scores = {
            site: min(
                _toroidal_distance_squared(site, selected, length)
                for selected in chosen
            )
            for site in candidates
        }
        best_score = max(scores.values())
        best = [site for site in candidates if scores[site] == best_score]
        chosen.append(min(best, key=priority.__getitem__))
    return tuple(chosen)


def local_density_panels(
    length: int,
    panel_size: int,
    panels: int,
    seed: int,
) -> np.ndarray:
    """Return deterministic balanced panels of mean-zero site densities."""

    linear = int(length)
    size = int(panel_size)
    count = int(panels)
    sites = linear * linear
    if linear < 2 or not 1 <= size < sites or count < 1:
        raise ValueError("invalid local-density panel dimensions")
    rng = np.random.default_rng(int(seed))
    result = np.empty((count, size, sites), dtype=float)
    starts = np.resize(rng.permutation(sites), count)
    for panel in range(count):
        tie_order = rng.permutation(sites)
        chosen = _farthest_site_subset(
            linear,
            size,
            int(starts[panel]),
            tie_order,
        )
        for row, site in enumerate(chosen):
            result[panel, row] = -np.ones(sites, dtype=float) / sites
            result[panel, row, site] += 1.0
    return result


def fourier_density_panel(
    length: int,
    panel_size: int,
) -> np.ndarray:
    """Return a deterministic real low-momentum density panel."""

    linear = int(length)
    size = int(panel_size)
    sites = linear * linear
    if linear < 2 or not 1 <= size < sites:
        raise ValueError("invalid Fourier-panel dimensions")
    coordinates = np.asarray(
        [(x, y) for y in range(linear) for x in range(linear)],
        dtype=float,
    )
    momenta = [
        (kx, ky)
        for ky in range(linear)
        for kx in range(linear)
        if (kx, ky) != (0, 0)
    ]
    momenta.sort(
        key=lambda momentum: (
            min(momentum[0], linear - momentum[0]) ** 2
            + min(momentum[1], linear - momentum[1]) ** 2,
            momentum[1],
            momentum[0],
        )
    )
    selected: list[np.ndarray] = []
    for kx, ky in momenta:
        phase = (
            2.0
            * np.pi
            * (kx * coordinates[:, 0] + ky * coordinates[:, 1])
            / linear
        )
        for candidate in (np.cos(phase), np.sin(phase)):
            vector = candidate - np.mean(candidate)
            for existing in selected:
                vector = vector - (existing @ vector) * existing
            norm = float(np.linalg.norm(vector))
            if norm <= 1e-10:
                continue
            selected.append(vector / norm)
            if len(selected) == size:
                return np.asarray(selected)
    raise RuntimeError("Fourier panel did not reach the requested rank")


def assemble_channels(
    cache: SiteResponseCache,
    coefficients: np.ndarray,
) -> np.ndarray:
    """Combine and tangent-normalize cached site responses."""

    values = np.asarray(coefficients, dtype=complex)
    sites = cache.solutions.shape[0]
    if values.ndim != 2 or values.shape[1] != sites:
        raise ValueError("coefficients and site-response cache disagree")
    gram = np.asarray(cache.tangent_gram, dtype=complex)
    if gram.shape != (sites, sites):
        raise ValueError("tangent Gram matrix has the wrong shape")
    channels = np.empty(
        (values.shape[0], cache.solutions.shape[1], cache.solutions.shape[2]),
        dtype=complex,
    )
    for index, vector in enumerate(values):
        norm_squared = float(np.real(vector.conj() @ gram @ vector))
        if norm_squared <= 1e-20:
            raise ValueError("operator panel contains a null tangent")
        channels[index] = np.tensordot(
            vector,
            cache.solutions,
            axes=(0, 0),
        ) / np.sqrt(norm_squared)
    return channels


def channel_covariance(channels: np.ndarray) -> np.ndarray:
    """Return ``Tr(A_mu A_nu^dagger)/D`` on channel-label space."""

    values = np.asarray(channels, dtype=complex)
    if values.ndim != 3 or min(values.shape) < 1:
        raise ValueError("channels must have shape (label, ambient, rank)")
    rank = values.shape[-1]
    covariance = np.einsum(
        "mai,nai->mn",
        values,
        values.conj(),
        optimize=True,
    ) / rank
    return 0.5 * (covariance + covariance.conj().T)


def whiten_channel_labels(
    channels: np.ndarray,
    rtol: float = 1e-10,
) -> WhitenedChannels:
    """Whiten the complete numerically supported channel-label covariance."""

    values = np.asarray(channels, dtype=complex)
    covariance = channel_covariance(values)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    largest = float(eigenvalues[-1])
    if largest <= 0.0:
        raise ValueError("channel-label covariance has no positive support")
    if float(eigenvalues[0]) <= float(rtol) * largest:
        raise ValueError("channel-label support is singular")
    inverse_sqrt = (
        eigenvectors * (eigenvalues ** -0.5)[None, :]
    ) @ eigenvectors.conj().T
    whitened = np.einsum(
        "mn,nai->mai",
        inverse_sqrt,
        values,
        optimize=True,
    )
    observed = channel_covariance(whitened)
    if not np.allclose(
        observed,
        np.eye(values.shape[0]),
        atol=2e-9,
        rtol=2e-9,
    ):
        raise RuntimeError("channel-label whitening failed")
    return WhitenedChannels(
        channels=whitened,
        covariance=covariance,
        covariance_eigenvalues=eigenvalues,
        inverse_sqrt=inverse_sqrt,
    )


def target_covariance(channels: np.ndarray) -> np.ndarray:
    """Return the mean target-space covariance ``A_mu^dagger A_mu``."""

    values = np.asarray(channels, dtype=complex)
    covariance = np.mean(
        np.einsum(
            "mai,maj->mij",
            values.conj(),
            values,
            optimize=True,
        ),
        axis=0,
    )
    return 0.5 * (covariance + covariance.conj().T)


def external_covariance_eigenvalues(
    channels: np.ndarray,
    rtol: float = 1e-12,
) -> np.ndarray:
    """Return nonzero eigenvalues of the mean external covariance by Gram reduction."""

    values = np.asarray(channels, dtype=complex)
    if values.ndim != 3:
        raise ValueError("channels must have shape (label, ambient, rank)")
    labels, ambient, rank = values.shape
    stacked = values.transpose(1, 0, 2).reshape(ambient, labels * rank)
    gram = stacked.conj().T @ stacked / labels
    eigenvalues = np.linalg.eigvalsh(0.5 * (gram + gram.conj().T))
    largest = max(float(eigenvalues[-1]), 0.0)
    if largest <= 0.0:
        raise ValueError("external covariance has no positive support")
    return eigenvalues[eigenvalues > float(rtol) * largest]


def four_channel_tensor(channels: np.ndarray) -> np.ndarray:
    """Return ``Tr(X_mu X_nu^dagger X_rho X_sigma^dagger)/D``."""

    values = np.asarray(channels, dtype=complex)
    if values.ndim != 3:
        raise ValueError("channels must have shape (label, ambient, rank)")
    rank = values.shape[-1]
    pair_grams = np.einsum(
        "mai,naj->mnij",
        values.conj(),
        values,
        optimize=True,
    )
    return np.einsum(
        "mnij,rsji->mnrs",
        pair_grams,
        pair_grams,
        optimize=True,
    ) / rank


def covariance_matched_wick(
    channels: np.ndarray,
    rtol: float = 1e-10,
) -> WickResult:
    """Return the separable covariance-matched Wick residual."""

    whitened = whiten_channel_labels(channels, rtol=rtol)
    values = whitened.channels
    rank = values.shape[-1]
    left = target_covariance(values)
    left_eigenvalues = np.linalg.eigvalsh(left)
    right_eigenvalues = external_covariance_eigenvalues(values)
    left_trace = float(np.sum(left_eigenvalues))
    right_trace = float(np.sum(right_eigenvalues))
    A_left = (
        rank
        * float(np.sum(left_eigenvalues**2))
        / (left_trace * left_trace)
    )
    B_right = (
        rank
        * float(np.sum(right_eigenvalues**2))
        / (right_trace * right_trace)
    )
    tensor = four_channel_tensor(values)
    identity = np.eye(values.shape[0])
    wick = (
        A_left * np.einsum("mn,rs->mnrs", identity, identity)
        + B_right * np.einsum("ms,rn->mnrs", identity, identity)
    )
    connected = tensor - wick
    denominator = float(np.linalg.norm(wick))
    if denominator <= 0.0:
        raise RuntimeError("Wick tensor has zero norm")
    return WickResult(
        tensor=tensor,
        wick_tensor=wick,
        connected=connected,
        R4=float(np.linalg.norm(connected) / denominator),
        A_left=A_left,
        B_right=B_right,
        left_eigenvalues=left_eigenvalues,
        right_eigenvalues=right_eigenvalues,
        channel_covariance_eigenvalues=whitened.covariance_eigenvalues,
    )


def sample_matched_gaussian_channels(
    left_eigenvalues: np.ndarray,
    right_eigenvalues: np.ndarray,
    channel_count: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw a separable complex Gaussian response tensor."""

    left = np.asarray(left_eigenvalues, dtype=float)
    right = np.asarray(right_eigenvalues, dtype=float)
    labels = int(channel_count)
    if (
        left.ndim != 1
        or right.ndim != 1
        or left.size == 0
        or right.size == 0
        or labels < 1
        or np.any(left <= 0.0)
        or np.any(right <= 0.0)
    ):
        raise ValueError("Gaussian covariance spectra must be positive vectors")
    left = left / np.sum(left)
    right = right / np.sum(right)
    gaussian = (
        rng.normal(size=(labels, right.size, left.size))
        + 1j * rng.normal(size=(labels, right.size, left.size))
    ) / np.sqrt(2.0)
    return (
        np.sqrt(right)[None, :, None]
        * gaussian
        * np.sqrt(left)[None, None, :]
    )


def _fast_covariance_matched_r4(
    channels: np.ndarray,
) -> float:
    """Return ``R4`` without diagonalizing the external covariance."""

    values = whiten_channel_labels(channels).channels
    labels = values.shape[0]
    rank = values.shape[-1]
    pair_grams = np.einsum(
        "mai,naj->mnij",
        values.conj(),
        values,
        optimize=True,
    )
    left = np.mean(
        pair_grams[np.arange(labels), np.arange(labels)],
        axis=0,
    )
    left_trace = float(np.trace(left).real)
    A_left = (
        rank
        * float(np.trace(left @ left).real)
        / (left_trace * left_trace)
    )
    right_trace = left_trace
    right_trace_square = (
        float(np.sum(np.abs(pair_grams) ** 2)) / (labels * labels)
    )
    B_right = (
        rank * right_trace_square / (right_trace * right_trace)
    )
    tensor = np.einsum(
        "mnij,rsji->mnrs",
        pair_grams,
        pair_grams,
        optimize=True,
    ) / rank
    identity = np.eye(labels)
    wick = (
        A_left * np.einsum("mn,rs->mnrs", identity, identity)
        + B_right * np.einsum("ms,rn->mnrs", identity, identity)
    )
    return float(np.linalg.norm(tensor - wick) / np.linalg.norm(wick))


def gaussian_r4_reference(
    left_eigenvalues: np.ndarray,
    right_eigenvalues: np.ndarray,
    channel_count: int,
    samples: int,
    seed: int,
) -> np.ndarray:
    """Return finite-size covariance-matched Gaussian ``R4`` samples."""

    count = int(samples)
    if count < 1:
        raise ValueError("Gaussian reference requires at least one sample")
    rng = np.random.default_rng(int(seed))
    result = np.empty(count, dtype=float)
    for sample in range(count):
        channels = sample_matched_gaussian_channels(
            left_eigenvalues,
            right_eigenvalues,
            channel_count,
            rng,
        )
        result[sample] = _fast_covariance_matched_r4(channels)
    return result
