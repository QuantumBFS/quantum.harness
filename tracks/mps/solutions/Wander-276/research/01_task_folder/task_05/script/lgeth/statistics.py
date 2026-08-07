"""Controlled spectral estimators for active geometric statistics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.optimize import curve_fit, lsq_linear


@dataclass(frozen=True)
class BootstrapInterval:
    """Bootstrap summary of a scalar sample mean."""

    mean: float
    lower: float
    upper: float
    standard_error: float
    replicates: int


@dataclass(frozen=True)
class CurveBand:
    """Matrix- or block-level simultaneous confidence band."""

    mean: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    pointwise_lower: np.ndarray
    pointwise_upper: np.ndarray
    standard_error: np.ndarray
    critical_value: float
    replicates: int
    units: int
    method: str


def sample_poisson_spectra(
    samples: int,
    levels: int,
    seed: int,
) -> np.ndarray:
    """Sample independent exponential-spacing spectra."""

    rng = np.random.default_rng(int(seed))
    spacings = rng.exponential(size=(int(samples), int(levels)))
    spectra = np.cumsum(spacings, axis=1)
    spectra -= np.mean(spectra, axis=1, keepdims=True)
    return spectra


def sample_gue_spectra(
    samples: int,
    levels: int,
    seed: int,
) -> np.ndarray:
    """Sample finite complex Hermitian Gaussian spectra."""

    count = int(samples)
    dimension = int(levels)
    if count < 1 or dimension < 3:
        raise ValueError("require samples>=1 and levels>=3")
    rng = np.random.default_rng(int(seed))
    spectra = np.empty((count, dimension), dtype=float)
    for sample in range(count):
        gaussian = (
            rng.normal(size=(dimension, dimension))
            + 1j * rng.normal(size=(dimension, dimension))
        )
        matrix = (gaussian + gaussian.conj().T) / np.sqrt(
            4.0 * dimension
        )
        spectra[sample] = np.linalg.eigvalsh(matrix)
    return spectra


def bulk_gap_ratio_per_spectrum(
    spectra: np.ndarray,
    bulk_fraction: float = 0.7,
) -> np.ndarray:
    """Return one adjacent-gap-ratio mean per spectrum."""

    values = np.asarray(spectra, dtype=float)
    if values.ndim != 2 or values.shape[1] < 3:
        raise ValueError("spectra must have shape (samples, levels>=3)")
    fraction = float(bulk_fraction)
    if not 0.2 <= fraction <= 1.0:
        raise ValueError("bulk_fraction must lie in [0.2,1]")
    result = np.empty(values.shape[0], dtype=float)
    trim = int(np.floor(0.5 * (1.0 - fraction) * values.shape[1]))
    for sample, spectrum in enumerate(values):
        ordered = np.sort(spectrum)
        bulk = ordered[
            trim : values.shape[1] - trim if trim else values.shape[1]
        ]
        spacings = np.diff(bulk)
        if spacings.size < 2 or np.any(spacings <= 0.0):
            raise ValueError("bulk spectrum has degenerate or too few levels")
        ratios = np.minimum(spacings[:-1], spacings[1:]) / np.maximum(
            spacings[:-1],
            spacings[1:],
        )
        result[sample] = float(np.mean(ratios))
    return result


def unfold_spectra(
    spectra: np.ndarray,
    method: str,
) -> np.ndarray:
    """Unfold spectra by pooled CDF or per-spectrum polynomial counting."""

    values = np.asarray(spectra, dtype=float)
    if values.ndim != 2 or values.shape[1] < 4:
        raise ValueError("spectra must have shape (samples,levels>=4)")
    ordered = np.sort(values, axis=1)
    if method == "ensemble_cdf":
        pooled = np.sort(ordered.ravel())
        quantiles = np.linspace(
            0.0,
            float(values.shape[1]),
            pooled.size,
        )
        return np.asarray(
            [
                np.interp(spectrum, pooled, quantiles)
                for spectrum in ordered
            ]
        )
    if method == "polynomial":
        unfolded = np.empty_like(ordered)
        target = np.arange(values.shape[1], dtype=float)
        degree = min(5, values.shape[1] - 1)
        for sample, spectrum in enumerate(ordered):
            center = float(np.mean(spectrum))
            scale = float(np.std(spectrum))
            if scale <= 0.0:
                raise ValueError("cannot unfold a constant spectrum")
            standardized = (spectrum - center) / scale
            coefficients = np.polynomial.chebyshev.chebfit(
                standardized,
                target,
                degree,
            )
            mapped = np.polynomial.chebyshev.chebval(
                standardized,
                coefficients,
            )
            if np.any(np.diff(mapped) <= 0.0):
                raise ValueError("polynomial unfolding is not monotone")
            unfolded[sample] = mapped
        return unfolded
    raise ValueError("unknown unfolding method")


def number_variance(
    unfolded_spectra: np.ndarray,
    lengths: Iterable[float],
    windows_per_spectrum: int = 48,
) -> dict[str, float]:
    """Estimate number variance from sliding unfolded windows."""

    spectra = np.asarray(unfolded_spectra, dtype=float)
    if spectra.ndim != 2:
        raise ValueError("unfolded_spectra must be two-dimensional")
    result: dict[str, float] = {}
    for raw_length in lengths:
        length = float(raw_length)
        if length <= 0.0:
            raise ValueError("window lengths must be positive")
        counts: list[int] = []
        for spectrum in spectra:
            ordered = np.sort(spectrum)
            lower = float(ordered[1])
            upper = float(ordered[-2] - length)
            if upper <= lower:
                continue
            starts = np.linspace(
                lower,
                upper,
                int(windows_per_spectrum),
            )
            for start in starts:
                counts.append(
                    int(
                        np.count_nonzero(
                            (ordered >= start)
                            & (ordered < start + length)
                        )
                    )
                )
        if not counts:
            raise ValueError("no number-variance windows were available")
        result[str(length)] = float(np.var(counts, ddof=1))
    return result


def bootstrap_mean_interval(
    values: np.ndarray,
    replicates: int,
    seed: int,
) -> BootstrapInterval:
    """Return a percentile bootstrap interval for the mean."""

    sample = np.asarray(values, dtype=float).ravel()
    draws = int(replicates)
    if sample.size < 2 or draws < 100:
        raise ValueError("need at least two values and 100 replicates")
    rng = np.random.default_rng(int(seed))
    indices = rng.integers(
        0,
        sample.size,
        size=(draws, sample.size),
    )
    means = np.mean(sample[indices], axis=1)
    lower, upper = np.quantile(means, (0.025, 0.975))
    return BootstrapInterval(
        mean=float(np.mean(sample)),
        lower=float(lower),
        upper=float(upper),
        standard_error=float(np.std(means, ddof=1)),
        replicates=draws,
    )


def intervals_overlap(
    first: BootstrapInterval,
    second: BootstrapInterval,
) -> bool:
    """Return whether two closed bootstrap intervals overlap."""

    return bool(
        max(first.lower, second.lower)
        <= min(first.upper, second.upper)
    )


def remove_labeled_atoms(
    spectrum: np.ndarray,
    atom_labels: np.ndarray,
) -> np.ndarray:
    """Remove only levels carrying explicit algebraic atom labels."""

    values = np.asarray(spectrum)
    labels = np.asarray(atom_labels, dtype=bool)
    if values.shape != labels.shape:
        raise ValueError("spectrum and labels must have matching shapes")
    return values[~labels]


def histogram_l1(
    first: np.ndarray,
    second: np.ndarray,
    edges: np.ndarray,
) -> float:
    """Return the histogram probability-density L1 distance."""

    bins = np.asarray(edges, dtype=float)
    density_first, _ = np.histogram(
        np.asarray(first).ravel(),
        bins=bins,
        density=True,
    )
    density_second, _ = np.histogram(
        np.asarray(second).ravel(),
        bins=bins,
        density=True,
    )
    return float(
        np.sum(
            np.abs(density_first - density_second) * np.diff(bins)
        )
    )


def matrix_bootstrap_band(
    curves: np.ndarray,
    replicates: int,
    seed: int,
    groups: np.ndarray | None = None,
) -> CurveBand:
    """Return a simultaneous band using matrices or independent seed blocks.

    Exact resampling is used for at most 512 independent units.  Larger
    matrix ensembles use the Gaussian multiplier limit of the matrix-mean
    process, estimated from the full between-matrix covariance.
    """

    values = np.asarray(curves, dtype=float)
    draws = int(replicates)
    if values.ndim != 2 or values.shape[0] < 2 or draws < 100:
        raise ValueError("require curves=(units,grid), units>=2, draws>=100")
    if groups is not None:
        labels = np.asarray(groups)
        if labels.shape != (values.shape[0],):
            raise ValueError("groups must provide one label per curve")
        unique = np.unique(labels)
        units = np.asarray(
            [np.mean(values[labels == label], axis=0) for label in unique]
        )
        method = "hierarchical_seed_block_bootstrap"
    else:
        units = values
        method = "matrix_bootstrap"
    count, grid = units.shape
    rng = np.random.default_rng(int(seed))
    mean = np.mean(units, axis=0)
    if count <= 512:
        bootstrap = np.empty((draws, grid), dtype=float)
        batch = 256
        for start in range(0, draws, batch):
            stop = min(start + batch, draws)
            indices = rng.integers(
                0,
                count,
                size=(stop - start, count),
            )
            bootstrap[start:stop] = np.mean(units[indices], axis=1)
    else:
        centered = units - mean
        covariance_mean = (
            centered.T @ centered / (count * (count - 1))
        )
        eigenvalues, eigenvectors = np.linalg.eigh(
            0.5 * (covariance_mean + covariance_mean.T)
        )
        keep = eigenvalues > max(
            float(eigenvalues[-1]) * 1e-12,
            0.0,
        )
        factor = eigenvectors[:, keep] * np.sqrt(eigenvalues[keep])[None, :]
        bootstrap = mean + rng.normal(
            size=(draws, int(np.count_nonzero(keep)))
        ) @ factor.T
        method = "matrix_gaussian_multiplier_bootstrap"
    pointwise_lower, pointwise_upper = np.quantile(
        bootstrap,
        (0.025, 0.975),
        axis=0,
    )
    standard_error = np.std(bootstrap, axis=0, ddof=1)
    safe_error = np.maximum(standard_error, 1e-15)
    maximum = np.max(
        np.abs((bootstrap - mean) / safe_error),
        axis=1,
    )
    critical = float(np.quantile(maximum, 0.95))
    return CurveBand(
        mean=mean,
        lower=mean - critical * standard_error,
        upper=mean + critical * standard_error,
        pointwise_lower=pointwise_lower,
        pointwise_upper=pointwise_upper,
        standard_error=standard_error,
        critical_value=critical,
        replicates=draws,
        units=count,
        method=method,
    )


def _number_variance_matrix_curves(
    unfolded_spectra: np.ndarray,
    lengths: np.ndarray,
    windows_per_spectrum: int = 24,
) -> np.ndarray:
    spectra = np.sort(np.asarray(unfolded_spectra, dtype=float), axis=1)
    scales = np.asarray(lengths, dtype=float)
    if spectra.ndim != 2 or spectra.shape[1] < 8:
        raise ValueError("unfolded spectra require at least eight levels")
    if np.any(scales <= 0.0):
        raise ValueError("lengths must be positive")
    curves = np.empty((spectra.shape[0], scales.size), dtype=float)
    for matrix, levels in enumerate(spectra):
        for column, length in enumerate(scales):
            lower = float(levels[1])
            upper = float(levels[-2] - length)
            if upper <= lower:
                curves[matrix, column] = np.nan
                continue
            starts = np.linspace(lower, upper, int(windows_per_spectrum))
            left = np.searchsorted(levels, starts, side="left")
            right = np.searchsorted(
                levels,
                starts + length,
                side="left",
            )
            counts = right - left
            curves[matrix, column] = float(np.var(counts, ddof=1))
    if np.any(~np.isfinite(curves)):
        raise ValueError("requested length exceeds the usable bulk")
    return curves


def number_variance_matrix_curves(
    unfolded_spectra: np.ndarray,
    lengths: Iterable[float],
    windows_per_spectrum: int = 24,
) -> np.ndarray:
    """Return one number-variance curve per input matrix."""

    return _number_variance_matrix_curves(
        unfolded_spectra,
        np.asarray(tuple(float(value) for value in lengths)),
        windows_per_spectrum=windows_per_spectrum,
    )


def spectral_rigidity(
    unfolded_spectra: np.ndarray,
    lengths: Iterable[float],
) -> np.ndarray:
    """Estimate Dyson--Mehta rigidity from the number-variance identity."""

    scales = np.asarray(tuple(float(value) for value in lengths))
    sigma = np.mean(
        _number_variance_matrix_curves(unfolded_spectra, scales),
        axis=0,
    )
    result = np.empty_like(scales)
    extended_x = np.concatenate([[0.0], scales])
    extended_sigma = np.concatenate([[0.0], sigma])
    for index, length in enumerate(scales):
        mask = extended_x <= length
        x = extended_x[mask]
        values = extended_sigma[mask]
        kernel = length**3 - 2.0 * length * length * x + x**3
        result[index] = (
            2.0
            / length**4
            * np.trapezoid(kernel * values, x)
        )
    return result


def connected_form_factor(
    unfolded_spectra: np.ndarray,
    times: Iterable[float],
) -> np.ndarray:
    """Return the connected spectral form factor normalized by level count."""

    spectra = np.asarray(unfolded_spectra, dtype=float)
    time_grid = np.asarray(tuple(float(value) for value in times))
    if spectra.ndim != 2 or spectra.shape[1] < 2:
        raise ValueError("unfolded spectra must be two-dimensional")
    phases = np.exp(
        -2j
        * np.pi
        * spectra[:, :, None]
        * time_grid[None, None, :]
    )
    partition = np.sum(phases, axis=1)
    return (
        np.mean(np.abs(partition) ** 2, axis=0)
        - np.abs(np.mean(partition, axis=0)) ** 2
    ) / spectra.shape[1]


def fit_size_models(
    dimensions: np.ndarray,
    values: np.ndarray,
    sigma: np.ndarray,
) -> dict[str, dict[str, float | list[float]] | str]:
    """Fit offset power laws and compare them by leave-one-size-out error."""

    D = np.asarray(dimensions, dtype=float)
    y = np.asarray(values, dtype=float)
    uncertainty = np.asarray(sigma, dtype=float)
    if D.ndim != 1 or D.size < 5 or y.shape != D.shape:
        raise ValueError("at least five one-dimensional size points required")
    if uncertainty.shape != D.shape or np.any(uncertainty <= 0.0):
        raise ValueError("sigma must be positive and match dimensions")

    def fixed_fit(
        x: np.ndarray,
        target: np.ndarray,
        error: np.ndarray,
        exponent: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        design = np.column_stack([np.ones_like(x), x ** (-exponent)])
        weighted = design / error[:, None]
        rhs = target / error
        solution = lsq_linear(
            weighted,
            rhs,
            bounds=(0.0, np.inf),
        )
        if not solution.success:
            raise RuntimeError("bounded fixed-exponent fit failed")
        parameters = solution.x
        covariance = np.linalg.pinv(weighted.T @ weighted)
        return parameters, covariance

    models: dict[str, dict[str, float | list[float]]] = {}
    for label, exponent in (("D^-1/2", 0.5), ("D^-1", 1.0)):
        parameters, covariance = fixed_fit(D, y, uncertainty, exponent)
        prediction = parameters[0] + parameters[1] * D ** (-exponent)
        residual = (y - prediction) / uncertainty
        rss = float(np.sum(residual * residual))
        loo = []
        for held_out in range(D.size):
            keep = np.arange(D.size) != held_out
            local, _ = fixed_fit(
                D[keep],
                y[keep],
                uncertainty[keep],
                exponent,
            )
            loo.append(
                y[held_out]
                - (
                    local[0]
                    + local[1] * D[held_out] ** (-exponent)
                )
            )
        models[label] = {
            "offset": float(parameters[0]),
            "amplitude": float(parameters[1]),
            "exponent": exponent,
            "offset_standard_error": float(np.sqrt(covariance[0, 0])),
            "weighted_rss": rss,
            "loo_rmse": float(np.sqrt(np.mean(np.square(loo)))),
            "prediction": prediction.tolist(),
        }

    def free_model(x, offset, amplitude, exponent):
        return offset + amplitude * x ** (-exponent)

    parameters, covariance = curve_fit(
        free_model,
        D,
        y,
        sigma=uncertainty,
        absolute_sigma=True,
        p0=(max(0.0, float(np.min(y)) * 0.5), float(y[0]), 0.5),
        bounds=([0.0, 0.0, 0.1], [np.inf, np.inf, 3.0]),
        maxfev=50_000,
    )
    prediction = free_model(D, *parameters)
    residual = (y - prediction) / uncertainty
    loo = []
    for held_out in range(D.size):
        keep = np.arange(D.size) != held_out
        try:
            local, _ = curve_fit(
                free_model,
                D[keep],
                y[keep],
                sigma=uncertainty[keep],
                absolute_sigma=True,
                p0=parameters,
                bounds=([0.0, 0.0, 0.1], [np.inf, np.inf, 3.0]),
                maxfev=50_000,
            )
            loo.append(y[held_out] - free_model(D[held_out], *local))
        except RuntimeError:
            loo.append(np.nan)
    models["free"] = {
        "offset": float(parameters[0]),
        "amplitude": float(parameters[1]),
        "exponent": float(parameters[2]),
        "offset_standard_error": float(np.sqrt(covariance[0, 0])),
        "exponent_standard_error": float(np.sqrt(covariance[2, 2])),
        "weighted_rss": float(np.sum(residual * residual)),
        "loo_rmse": float(np.sqrt(np.nanmean(np.square(loo)))),
        "prediction": prediction.tolist(),
    }
    best = min(models, key=lambda key: float(models[key]["loo_rmse"]))
    return {"models": models, "best_by_loo": best}
