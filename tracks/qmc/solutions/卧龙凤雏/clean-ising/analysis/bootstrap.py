"""Hierarchical block bootstrap through integration and Casimir fitting."""

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Dict, List, Mapping

import numpy as np

from analysis.fitting import fit_draws


FIT_WINDOWS = (4, 6, 8)


@dataclass(frozen=True)
class BootstrapResult:
    widths: np.ndarray
    k_values: np.ndarray
    mean_energy: np.ndarray
    g_mean_primary: np.ndarray
    g_mean_nested: np.ndarray
    g_draws_primary: np.ndarray
    g_draws_nested: np.ndarray
    c_draws_primary: Dict[int, np.ndarray]
    c_draws_nested: Dict[int, np.ndarray]
    primary_grid_points: int
    nested_grid_points: int
    diagnostics: Dict[str, Any]
    seed: int

    @property
    def primary_standard_error(self) -> float:
        return float(np.std(self.c_draws_primary[6], ddof=1))

    @property
    def integration_shift(self) -> float:
        return abs(
            float(np.mean(self.c_draws_primary[6]))
            - float(np.mean(self.c_draws_nested[6]))
        )


def bootstrap_mc(
    blocks: List[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    draws: int = 2000,
    seed: int = 20260729,
) -> BootstrapResult:
    if draws < 2:
        raise ValueError("bootstrap requires at least two draws")
    config = manifest["config"]
    mc = config["mc"]
    widths = np.asarray(config["widths"], dtype=float)
    primary_grid_points = mc["grid_intervals"] + 1
    replicas = mc["replicas"]
    blocks_per_replica = mc["measurement_sweeps"] // mc["block_sweeps"]
    energies = np.full(
        (widths.size, primary_grid_points, replicas, blocks_per_replica),
        np.nan,
        dtype=float,
    )
    width_index = {int(width): index for index, width in enumerate(widths)}
    for record in blocks:
        energies[
            width_index[record["l"]],
            record["k_index"],
            record["replica"],
            record["block_index"],
        ] = record["energy_sum"] / record["measurement_count"]
    if not np.all(np.isfinite(energies)):
        raise ValueError("bootstrap input is missing blocks or contains non-finite values")

    rng = np.random.default_rng(seed)
    energy_draws = np.empty((draws, widths.size, primary_grid_points), dtype=float)
    for width_position in range(widths.size):
        for k_index in range(primary_grid_points):
            replica_means = np.empty((draws, replicas), dtype=float)
            for replica in range(replicas):
                values = energies[width_position, k_index, replica]
                indices = rng.integers(
                    0,
                    blocks_per_replica,
                    size=(draws, blocks_per_replica),
                )
                replica_means[:, replica] = values[indices].mean(axis=1)
            energy_draws[:, width_position, k_index] = replica_means.mean(axis=1)

    k_values = np.linspace(0.0, config["critical_k"], primary_grid_points)
    nested_indices = slice(None, None, 2)
    nested_grid_points = (primary_grid_points + 1) // 2
    g_draws_primary = _integrate_draws(
        energy_draws,
        k_values,
        widths,
        config["aspect_ratio"],
    )
    g_draws_nested = _integrate_draws(
        energy_draws[:, :, nested_indices],
        k_values[nested_indices],
        widths,
        config["aspect_ratio"],
    )
    c_draws_primary = {
        l_min: fit_draws(widths, g_draws_primary, l_min) for l_min in FIT_WINDOWS
    }
    c_draws_nested = {
        l_min: fit_draws(widths, g_draws_nested, l_min) for l_min in FIT_WINDOWS
    }
    diagnostics = _diagnostics(energies, c_draws_primary, c_draws_nested)
    return BootstrapResult(
        widths=widths,
        k_values=k_values,
        mean_energy=energies.mean(axis=(2, 3)),
        g_mean_primary=g_draws_primary.mean(axis=0),
        g_mean_nested=g_draws_nested.mean(axis=0),
        g_draws_primary=g_draws_primary,
        g_draws_nested=g_draws_nested,
        c_draws_primary=c_draws_primary,
        c_draws_nested=c_draws_nested,
        primary_grid_points=primary_grid_points,
        nested_grid_points=nested_grid_points,
        diagnostics=diagnostics,
        seed=seed,
    )


def _integrate_draws(
    energy_draws: np.ndarray,
    k_values: np.ndarray,
    widths: np.ndarray,
    aspect_ratio: int,
) -> np.ndarray:
    weights = _simpson_weights(k_values)
    integrated = np.tensordot(energy_draws, weights, axes=([2], [0]))
    lengths = aspect_ratio * widths
    sites = widths * lengths
    free_energy = integrated - sites[np.newaxis, :] * np.log(2.0)
    return free_energy / lengths[np.newaxis, :]


def _simpson_weights(x_values: np.ndarray) -> np.ndarray:
    if x_values.size < 3 or x_values.size % 2 == 0:
        raise ValueError("nested Simpson grids require an odd number of points")
    spacing = np.diff(x_values)
    if not np.allclose(spacing, spacing[0], rtol=1.0e-12, atol=1.0e-15):
        raise ValueError("nested Simpson grids must be uniform")
    weights = np.ones(x_values.size)
    weights[1:-1:2] = 4.0
    weights[2:-1:2] = 2.0
    return weights * spacing[0] / 3.0


def _diagnostics(
    energies: np.ndarray,
    c_draws_primary: Mapping[int, np.ndarray],
    c_draws_nested: Mapping[int, np.ndarray],
) -> Dict[str, Any]:
    half_z_scores = []
    replica_z_scores = []
    for width_position in range(energies.shape[0]):
        for k_index in range(energies.shape[1]):
            replica_blocks = energies[width_position, k_index]
            for values in replica_blocks:
                midpoint = values.size // 2
                half_z_scores.append(
                    _difference_z(values[:midpoint], values[midpoint:])
                )
            for left, right in combinations(replica_blocks, 2):
                replica_z_scores.append(_difference_z(left, right))

    primary = c_draws_primary[6]
    standard_error = float(np.std(primary, ddof=1))
    integration_shift = abs(
        float(np.mean(primary)) - float(np.mean(c_draws_nested[6]))
    )
    window_stability = {}
    for l_min in (4, 8):
        difference = abs(
            float(np.mean(c_draws_primary[l_min])) - float(np.mean(primary))
        )
        combined = float(
            np.sqrt(
                np.var(c_draws_primary[l_min], ddof=1)
                + np.var(primary, ddof=1)
            )
        )
        window_stability[l_min] = {
            "difference": difference,
            "combined_standard_error": combined,
            "passes": difference <= combined,
        }
    max_half_z = float(max(half_z_scores, default=0.0))
    max_replica_z = float(max(replica_z_scores, default=0.0))
    return {
        "max_half_z": max_half_z,
        "max_replica_z": max_replica_z,
        "thermalization_passes": max_half_z < 4.0,
        "replica_agreement_passes": max_replica_z < 4.0,
        "integration_shift": integration_shift,
        "primary_standard_error": standard_error,
        "integration_passes": integration_shift < standard_error,
        "window_stability": window_stability,
    }


def _difference_z(left: np.ndarray, right: np.ndarray) -> float:
    difference = abs(float(np.mean(left)) - float(np.mean(right)))
    if left.size < 2 or right.size < 2:
        return 0.0 if difference == 0.0 else float("inf")
    variance = float(np.var(left, ddof=1) / left.size + np.var(right, ddof=1) / right.size)
    if variance == 0.0:
        return 0.0 if difference == 0.0 else float("inf")
    return difference / np.sqrt(variance)
