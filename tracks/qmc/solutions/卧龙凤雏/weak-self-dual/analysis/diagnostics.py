import numpy as np


def effective_sample_size(series: np.ndarray) -> float:
    values = np.asarray(series, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.all(np.isfinite(values)):
        raise ValueError("ESS input must be a nonempty finite vector")
    centered = values - values.mean()
    variance = float(np.dot(centered, centered) / len(values))
    if variance == 0.0:
        return float(len(values))
    correlations = []
    for lag in range(1, len(values)):
        covariance = float(np.dot(centered[:-lag], centered[lag:]) / (len(values) - lag))
        correlations.append(covariance / variance)
    positive_pair_sum = 0.0
    for start in range(0, len(correlations), 2):
        pair = sum(correlations[start : start + 2])
        if pair <= 0.0:
            break
        positive_pair_sum += pair
    tau = max(1.0, 1.0 + 2.0 * positive_pair_sum)
    return float(min(len(values), len(values) / tau))


def width_sampling_diagnostics(
    gamma_blocks: dict[int, np.ndarray],
) -> dict[int, dict[str, float]]:
    result = {}
    for width, block_array in gamma_blocks.items():
        values = np.asarray(block_array, dtype=float)
        stream_ess = [effective_sample_size(stream) for stream in values]
        lag_one = []
        for stream in values:
            if len(stream) < 2 or np.var(stream) == 0.0:
                lag_one.append(0.0)
            else:
                lag_one.append(float(np.corrcoef(stream[:-1], stream[1:])[0, 1]))
        result[int(width)] = {
            "effective_sample_size": float(sum(stream_ess)),
            "maximum_absolute_lag_one": float(max(abs(value) for value in lag_one)),
        }
    return result


def self_duality_diagnostic(
    electric_counts: dict[int, np.ndarray],
    magnetic_counts: dict[int, np.ndarray],
    face_counts: dict[int, np.ndarray],
) -> dict:
    stream_means = []
    electric_total = 0.0
    magnetic_total = 0.0
    faces_total = 0.0
    for width in sorted(electric_counts):
        electric = np.asarray(electric_counts[width], dtype=float)
        magnetic = np.asarray(magnetic_counts[width], dtype=float)
        faces = np.asarray(face_counts[width], dtype=float)
        if electric.shape != magnetic.shape or electric.shape != faces.shape:
            raise ValueError("vortex count arrays must have identical shapes")
        differences = (electric - magnetic) / faces
        stream_means.extend(differences.mean(axis=1))
        electric_total += electric.sum()
        magnetic_total += magnetic.sum()
        faces_total += faces.sum()
    values = np.asarray(stream_means, dtype=float)
    standard_error = (
        float(values.std(ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0
    )
    mean_difference = float(values.mean())
    z_score = mean_difference / standard_error if standard_error > 0.0 else 0.0
    return {
        "electric_density": float(electric_total / faces_total),
        "magnetic_density": float(magnetic_total / faces_total),
        "mean_difference": mean_difference,
        "standard_error": standard_error,
        "z_score": float(z_score),
    }


def fit_stability(fit_samples: dict[str, np.ndarray]) -> dict:
    primary = np.asarray(fit_samples["primary"], dtype=float)
    required = ["lmin8", "lmin10", "extra_burnin", "double_block", "drop_l30"]
    shifts = {}
    maximum_z = 0.0
    centers = [float(np.mean(primary))]
    for name in required:
        values = np.asarray(fit_samples[name], dtype=float)
        difference = values - primary
        error = float(np.std(difference, ddof=1))
        shift = float(np.mean(difference))
        z = abs(shift) / error if error > 0.0 else (0.0 if shift == 0.0 else float("inf"))
        shifts[name] = {"shift": shift, "paired_standard_error": error, "z": z}
        maximum_z = max(maximum_z, z)
        centers.append(float(np.mean(values)))
    return {
        "variants": shifts,
        "maximum_shift_z": maximum_z,
        "systematic_spread": max(centers) - min(centers),
    }
