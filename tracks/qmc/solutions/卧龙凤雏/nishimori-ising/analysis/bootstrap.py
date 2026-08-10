import numpy as np

from analysis.fitting import fit_free_energy


def hierarchical_central_charge_bootstrap(
    block_tensor: np.ndarray,
    widths: np.ndarray,
    minimum_width: int,
    samples: int,
    seed: int,
) -> np.ndarray:
    widths = np.asarray(widths, dtype=float)
    tensor = np.asarray(block_tensor, dtype=float)
    if tensor.ndim != 3 or tensor.shape[2] != len(widths):
        raise ValueError("block tensor width axis must match widths")
    phi_samples = hierarchical_mean_bootstrap(block_tensor, samples=samples, seed=seed)
    central_charges = np.empty(samples, dtype=float)
    for sample_index, phi in enumerate(phi_samples):
        central_charges[sample_index] = fit_free_energy(
            widths, phi, minimum_width
        ).central_charge
    return central_charges


def hierarchical_mean_bootstrap(
    block_tensor: np.ndarray,
    *,
    samples: int,
    seed: int,
) -> np.ndarray:
    """Resample replicas, then joint-width block vectors within each replica."""
    tensor = np.asarray(block_tensor, dtype=float)
    if tensor.ndim != 3:
        raise ValueError("block tensor must have replica, block, and width axes")
    replicas, blocks, width_count = tensor.shape
    if replicas == 0 or blocks == 0 or width_count == 0:
        raise ValueError("block tensor dimensions must be nonempty")
    if samples < 2:
        raise ValueError("at least two bootstrap samples are required")
    if not np.all(np.isfinite(tensor)):
        raise ValueError("block tensor must be finite")

    rng = np.random.default_rng(seed)
    means = np.empty((samples, width_count), dtype=float)
    for sample_index in range(samples):
        replica_indices = rng.integers(0, replicas, size=replicas)
        replica_means = np.empty((replicas, width_count), dtype=float)
        for destination, source in enumerate(replica_indices):
            block_indices = rng.integers(0, blocks, size=blocks)
            replica_means[destination] = tensor[source, block_indices].mean(axis=0)
        means[sample_index] = replica_means.mean(axis=0)
    return means
