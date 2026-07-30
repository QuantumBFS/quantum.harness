"""VMC estimators for the frozen Route C training protocol."""

from __future__ import annotations

import numpy as np


def coulomb_local_energy(configs: object, *, two_q: int) -> np.ndarray:
    """Evaluate the chord-distance Coulomb potential for each configuration."""

    values = np.asarray(configs, dtype=np.complex128)
    if values.ndim != 3 or values.shape[2] != 2 or values.shape[1] < 2:
        raise ValueError("configs must have shape (batch, n_electrons, 2)")
    if values.shape[0] <= 0 or not np.all(np.isfinite(values)):
        raise ValueError("configs must be a non-empty finite batch")
    if isinstance(two_q, bool) or not isinstance(two_q, (int, np.integer)):
        raise ValueError("two_q must be a positive integer")
    if int(two_q) <= 0:
        raise ValueError("two_q must be a positive integer")

    q_value = int(two_q) / 2.0
    energy = np.zeros(values.shape[0], dtype=np.float64)
    for first in range(values.shape[1]):
        for second in range(first + 1, values.shape[1]):
            determinant = (
                values[:, first, 0] * values[:, second, 1]
                - values[:, first, 1] * values[:, second, 0]
            )
            with np.errstate(divide="ignore", invalid="ignore"):
                energy += 1.0 / (
                    2.0 * np.sqrt(q_value) * np.abs(determinant)
                )
    return energy


def real_energy_gradient(scores: object, local_energies: object) -> np.ndarray:
    """Return ``2 Re Cov(conj(score), local_energy)`` for real parameters."""

    score_values = np.asarray(scores, dtype=np.complex128)
    energy_values = np.asarray(local_energies)
    if score_values.ndim != 2:
        raise ValueError("scores must have shape (batch, parameters)")
    if energy_values.ndim != 1 or energy_values.shape[0] != score_values.shape[0]:
        raise ValueError("local_energies must have shape (batch,)")
    if score_values.shape[0] <= 0:
        raise ValueError("scores must contain at least one sample")
    if not np.all(np.isfinite(score_values)) or not np.all(
        np.isfinite(energy_values)
    ):
        raise ValueError("scores and local energies must be finite")

    centered_scores = score_values - np.mean(score_values, axis=0)
    centered_energy = energy_values - np.mean(energy_values)
    covariance = np.mean(
        np.conjugate(centered_scores) * centered_energy[:, None], axis=0
    )
    return 2.0 * np.real(covariance)
