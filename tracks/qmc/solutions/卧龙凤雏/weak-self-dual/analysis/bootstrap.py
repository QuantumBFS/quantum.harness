import numpy as np

from analysis.fitting import fit_gamma


def hierarchical_mean_bootstrap(
    gamma_blocks: dict[int, np.ndarray],
    widths: np.ndarray,
    *,
    samples: int,
    seed: int,
    transform: str = "none",
) -> np.ndarray:
    if samples < 2:
        raise ValueError("at least two bootstrap samples are required")
    rng = np.random.default_rng(seed)
    means = np.empty((samples, len(widths)), dtype=float)
    for width_index, width in enumerate(widths):
        values = np.asarray(gamma_blocks[int(width)], dtype=float)
        if values.ndim != 2 or values.size == 0 or not np.all(np.isfinite(values)):
            raise ValueError("each width requires a finite streams-by-blocks array")
        values = _transform_blocks(values, transform)
        stream_count, block_count = values.shape
        for sample in range(samples):
            selected_streams = rng.integers(0, stream_count, size=stream_count)
            stream_means = []
            for selected in selected_streams:
                selected_blocks = rng.integers(0, block_count, size=block_count)
                stream_means.append(values[selected, selected_blocks].mean())
            means[sample, width_index] = np.mean(stream_means)
    return means


def bootstrap_fits(
    gamma_blocks: dict[int, np.ndarray],
    widths: np.ndarray,
    sigma: np.ndarray,
    *,
    samples: int,
    seed: int,
) -> dict[str, np.ndarray]:
    widths = np.asarray(widths, dtype=int)
    sigma = np.asarray(sigma, dtype=float)
    base = hierarchical_mean_bootstrap(
        gamma_blocks, widths, samples=samples, seed=seed
    )
    extra_burnin = hierarchical_mean_bootstrap(
        gamma_blocks, widths, samples=samples, seed=seed + 1, transform="extra_burnin"
    )
    double_block = hierarchical_mean_bootstrap(
        gamma_blocks, widths, samples=samples, seed=seed + 2, transform="double_block"
    )
    definitions = {
        "primary": (base, 6, "l3", widths != -1),
        "lmin8": (base, 8, "l3", widths != -1),
        "lmin10": (base, 10, "l3", widths != -1),
        "extra_burnin": (extra_burnin, 6, "l3", widths != -1),
        "double_block": (double_block, 6, "l3", widths != -1),
        "no_correction": (base, 6, "none", widths != -1),
        "extended_correction": (base, 6, "l3_l5", widths != -1),
        "drop_l30": (base, 6, "l3", widths != 30),
    }
    results = {}
    for name, (draws, minimum, correction, mask) in definitions.items():
        selected_widths = widths[mask]
        selected_sigma = sigma[mask]
        results[name] = np.asarray(
            [
                fit_gamma(
                    selected_widths,
                    draw[mask],
                    selected_sigma,
                    minimum,
                    correction,
                ).central_charge
                for draw in draws
            ]
        )
    return results


def _transform_blocks(values: np.ndarray, transform: str) -> np.ndarray:
    if transform == "none":
        return values
    if transform == "extra_burnin":
        start = values.shape[1] // 4
        return values[:, start:]
    if transform == "double_block":
        count = values.shape[1] // 2
        if count == 0:
            raise ValueError("double-block bootstrap requires at least two blocks")
        trimmed = values[:, : 2 * count]
        return trimmed.reshape(values.shape[0], count, 2).mean(axis=2)
    raise ValueError(f"unknown block transform: {transform}")
