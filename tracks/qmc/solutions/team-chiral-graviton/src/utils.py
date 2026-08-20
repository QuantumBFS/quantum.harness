"""
Utility functions.
"""

import torch
import math
import numpy as np


def print_header(title: str, width: int = 60):
    """Print a formatted header."""
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_results(results: dict, width: int = 60):
    """Print results dictionary in a formatted way."""
    print("-" * width)
    print(f"{'Quantity':<30} {'Value':<20}")
    print("-" * width)
    for key, value in results.items():
        if isinstance(value, float):
            print(f"{key:<30} {value:<20.8f}")
        elif isinstance(value, int):
            print(f"{key:<30} {value:<20}")
        else:
            print(f"{key:<30} {str(value):<20}")
    print("-" * width)


def save_checkpoint(wf, optimizer, energy_history, filepath: str):
    """Save model checkpoint."""
    checkpoint = {
        'model_state': {name: param.data.clone()
                        for name, param in wf.named_parameters()
                        if param.requires_grad},
        'energy_history': energy_history,
    }
    torch.save(checkpoint, filepath)
    print(f"  Checkpoint saved to {filepath}")


def load_checkpoint(wf, filepath: str, device='cuda'):
    """Load model checkpoint."""
    checkpoint = torch.load(filepath, map_location=device, weights_only=True)
    for name, param in wf.named_parameters():
        if name in checkpoint['model_state'] and param.requires_grad:
            param.data.copy_(checkpoint['model_state'][name])
    print(f"  Checkpoint loaded from {filepath}")
    return checkpoint.get('energy_history', [])


def bootstrap_error(data: torch.Tensor, n_resamples: int = 200) -> tuple:
    """Compute mean and bootstrap error bar."""
    n = data.shape[0]
    means = []
    for _ in range(n_resamples):
        idx = torch.randint(0, n, (n,))
        means.append(data[idx].mean().item())
    means = np.array(means)
    return means.mean(), means.std()


def measure_pair_correlation(theta, phi, xyz):
    """
    Compute the pair correlation function g(r) from samples.

    g(r) = (1/(2*pi*N*rho)) * sum_{i!=j} delta(r - r_ij)

    Args:
        theta: [batch, N]
        phi:   [batch, N]
        xyz:   [batch, N, 3]

    Returns:
        (r_bins, g_r) pair correlation function
    """
    from .haldane_sphere import chord_distance_matrix

    chord = chord_distance_matrix(xyz)  # [batch, N, N]

    n_bins = 50
    r_max = 2.0
    bins = torch.linspace(0.01, r_max, n_bins, device=chord.device)

    # Count pairs in each distance bin
    triu = torch.triu_indices(xyz.shape[-2], xyz.shape[-2], offset=1)
    pairs = chord[:, triu[0], triu[1]]  # [batch, n_pairs]

    hist = torch.zeros(n_bins - 1, device=chord.device)
    for b in range(n_bins - 1):
        mask = (pairs >= bins[b]) & (pairs < bins[b + 1])
        hist[b] = mask.sum().float()

    # Normalize: average over batch, per-particle, per-area
    batch = xyz.shape[0]
    N = xyz.shape[-2]
    hist = hist / batch / N

    # Area normalization (spherical surface)
    r_center = (bins[:-1] + bins[1:]) / 2
    area_bin = 2 * math.pi * r_center * (bins[1] - bins[0])

    g_r = hist / (area_bin + 1e-10)

    return r_center.cpu().numpy(), g_r.cpu().numpy()
