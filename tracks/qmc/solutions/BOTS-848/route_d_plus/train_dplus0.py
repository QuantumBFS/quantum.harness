"""Blind N=6 D+0 training with exact delayed-acceptance SR chains."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from route_d_plus.coordinate import (
    scalar_laughlin_amplitudes,
    scalar_tower_amplitudes,
)
from route_d_plus.vmc import (
    block_estimate,
    center_whiten_channels,
    coulomb_potential,
    delayed_acceptance_chain,
    energy_gradient_metric,
    linear_log_derivatives,
    metropolis_chain,
    multiplet_log_derivatives,
    sr_update,
)

N_ELECTRONS = 6
TWO_Q = 15
RAW_RANKS = (2, 3, 4)


def ground_mother_channels(configuration: np.ndarray) -> np.ndarray:
    return scalar_laughlin_amplitudes(configuration, ranks=())


def tower_mother_channels(configuration: np.ndarray) -> np.ndarray:
    return scalar_tower_amplitudes(configuration, ranks=())


def ground_raw_channels(configuration: np.ndarray) -> np.ndarray:
    return scalar_laughlin_amplitudes(configuration, ranks=RAW_RANKS)


def tower_raw_channels(configuration: np.ndarray) -> np.ndarray:
    return scalar_tower_amplitudes(configuration, ranks=RAW_RANKS)


def raw_local_generators(channels: np.ndarray) -> np.ndarray:
    values = np.asarray(channels, dtype=np.complex128)
    if values.ndim == 2:
        return values[:, 1:] / values[:, :1]
    if values.ndim == 3:
        denominator = np.sum(np.abs(values[..., 0]) ** 2, axis=1)
        return np.einsum(
            "sm,sma->sa",
            values[..., 0].conj(),
            values[..., 1:],
            optimize=True,
        ) / denominator[:, None]
    raise ValueError("channels must describe scalar or multiplet samples")


def estimate_centering_whitening(
    ground_channels: np.ndarray,
    tower_channels: np.ndarray,
    *,
    relative_cutoff: float = 1.0e-12,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ground_local = raw_local_generators(ground_channels)
    tower_local = raw_local_generators(tower_channels)
    ground_mean = np.mean(ground_local, axis=0).real
    tower_mean = np.mean(tower_local, axis=0).real
    mean = 0.5 * (ground_mean + tower_mean)
    ground_centered = ground_local - ground_mean
    tower_centered = tower_local - tower_mean
    covariance = 0.5 * np.real(
        ground_centered.conj().T @ ground_centered
        / ground_centered.shape[0]
        + tower_centered.conj().T @ tower_centered
        / tower_centered.shape[0]
    )
    covariance = 0.5 * (covariance + covariance.T)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    retained = eigenvalues > relative_cutoff * np.max(eigenvalues)
    whitening = (
        eigenvectors[:, retained] / np.sqrt(eigenvalues[retained])
    ).T
    return mean, covariance, whitening


def _stack_chain_results(results: list[Any]) -> tuple[np.ndarray, np.ndarray]:
    samples = np.concatenate([result.samples for result in results], axis=0)
    channels = np.concatenate(
        [result.channel_values for result in results], axis=0
    )
    return samples, channels


def _make_whitened_evaluator(
    raw_evaluator: Callable[[np.ndarray], np.ndarray],
    mean: np.ndarray,
    whitening: np.ndarray,
) -> Callable[[np.ndarray], np.ndarray]:
    def evaluate(configuration: np.ndarray) -> np.ndarray:
        return center_whiten_channels(
            raw_evaluator(configuration), mean, whitening
        )

    return evaluate


def _complex_update(coefficients: np.ndarray, step: np.ndarray) -> np.ndarray:
    count = coefficients.size
    return coefficients + step[:count] + 1.0j * step[count:]


def _run_sector_update(
    *,
    mother_evaluator: Callable[[np.ndarray], np.ndarray],
    full_evaluator: Callable[[np.ndarray], np.ndarray],
    coefficients: np.ndarray,
    configurations: list[np.ndarray],
    seed: int,
    multiplet: bool,
    sample_steps: int,
    proposal_sweeps: int,
) -> tuple[np.ndarray, list[np.ndarray], dict[str, float]]:
    results = [
        delayed_acceptance_chain(
            mother_evaluator,
            full_evaluator,
            n_particles=N_ELECTRONS,
            coefficients=coefficients,
            seed=seed + chain,
            sample_steps=sample_steps,
            proposal_sweeps=proposal_sweeps,
            delta_max=0.35,
            initial_configuration=configurations[chain],
            global_rotation_interval=4,
        )
        for chain in range(len(configurations))
    ]
    samples, channels = _stack_chain_results(results)
    energy = coulomb_potential(samples, TWO_Q)
    derivatives = (
        multiplet_log_derivatives(channels, coefficients)
        if multiplet
        else linear_log_derivatives(channels, coefficients)
    )
    estimate, gradient, metric = energy_gradient_metric(
        energy, derivatives
    )
    step = sr_update(
        metric,
        gradient,
        learning_rate=0.1,
        diagonal_shift=1.0e-2,
        trust_radius=0.05,
    )
    updated = _complex_update(coefficients, step)
    next_configurations = [
        result.final_configuration for result in results
    ]
    diagnostics = {
        "energy": estimate,
        "step_norm": float(np.linalg.norm(step)),
        "gradient_norm": float(np.linalg.norm(gradient)),
        "correction_acceptance": float(
            np.mean([result.correction_acceptance for result in results])
        ),
        "mother_acceptance": float(
            np.mean([result.mother_acceptance for result in results])
        ),
        "global_rotation_residual": float(
            max(result.global_rotation_residual for result in results)
        ),
    }
    return updated, next_configurations, diagnostics


def _pilot_samples(seed: int, chains: int, samples_per_chain: int) -> tuple[
    np.ndarray, np.ndarray, list[np.ndarray], list[np.ndarray]
]:
    ground_results = [
        metropolis_chain(
            ground_mother_channels,
            n_particles=N_ELECTRONS,
            coefficients=np.empty(0, dtype=np.complex128),
            seed=seed + chain,
            burn_in_sweeps=16,
            sample_sweeps=samples_per_chain,
            delta_max=0.35,
            global_rotation_interval=4,
        )
        for chain in range(chains)
    ]
    tower_results = [
        metropolis_chain(
            tower_mother_channels,
            n_particles=N_ELECTRONS,
            coefficients=np.empty(0, dtype=np.complex128),
            seed=seed + 100 + chain,
            burn_in_sweeps=16,
            sample_sweeps=samples_per_chain,
            delta_max=0.35,
            global_rotation_interval=4,
        )
        for chain in range(chains)
    ]
    ground_samples = np.concatenate(
        [result.samples for result in ground_results], axis=0
    )
    tower_samples = np.concatenate(
        [result.samples for result in tower_results], axis=0
    )
    return (
        np.asarray([ground_raw_channels(item) for item in ground_samples]),
        np.asarray([tower_raw_channels(item) for item in tower_samples]),
        [result.samples[-1] for result in ground_results],
        [result.samples[-1] for result in tower_results],
    )


def _final_sector_diagnostics(
    results: list[Any],
) -> dict[str, Any]:
    chain_energies = np.stack(
        [
            coulomb_potential(result.samples, TWO_Q)
            for result in results
        ]
    )
    block_size = 2 if chain_energies.shape[1] % 2 == 0 else 1
    statistics = block_estimate(chain_energies, block_size=block_size)
    statistics.update(
        {
            "correction_acceptance": float(
                np.mean(
                    [result.correction_acceptance for result in results]
                )
            ),
            "mother_acceptance": float(
                np.mean([result.mother_acceptance for result in results])
            ),
            "global_rotation_residual": float(
                max(
                    result.global_rotation_residual for result in results
                )
            ),
        }
    )
    return statistics


def train_seed(
    seed: int,
    *,
    chains: int = 2,
    pilot_samples_per_chain: int = 8,
    updates: int = 12,
    samples_per_update: int = 2,
    proposal_sweeps: int = 2,
    final_samples_per_chain: int = 8,
) -> tuple[dict[str, Any], dict[str, Any]]:
    (
        pilot_ground,
        pilot_tower,
        ground_configurations,
        tower_configurations,
    ) = _pilot_samples(seed, chains, pilot_samples_per_chain)
    mean, covariance, whitening = estimate_centering_whitening(
        pilot_ground, pilot_tower
    )
    ground_evaluator = _make_whitened_evaluator(
        ground_raw_channels, mean, whitening
    )
    tower_evaluator = _make_whitened_evaluator(
        tower_raw_channels, mean, whitening
    )
    rng = np.random.default_rng(seed + 10_000)
    ground_coefficients = 1.0e-3 * (
        rng.normal(size=whitening.shape[0])
        + 1.0j * rng.normal(size=whitening.shape[0])
    )
    tower_coefficients = 1.0e-3 * (
        rng.normal(size=whitening.shape[0])
        + 1.0j * rng.normal(size=whitening.shape[0])
    )
    initialization_norm = float(
        np.sqrt(
            np.vdot(ground_coefficients, ground_coefficients).real
            + np.vdot(tower_coefficients, tower_coefficients).real
        )
    )
    trace = []
    for update in range(updates):
        ground_coefficients, ground_configurations, ground_record = (
            _run_sector_update(
                mother_evaluator=ground_mother_channels,
                full_evaluator=ground_evaluator,
                coefficients=ground_coefficients,
                configurations=ground_configurations,
                seed=seed + 1_000 * update,
                multiplet=False,
                sample_steps=samples_per_update,
                proposal_sweeps=proposal_sweeps,
            )
        )
        tower_coefficients, tower_configurations, tower_record = (
            _run_sector_update(
                mother_evaluator=tower_mother_channels,
                full_evaluator=tower_evaluator,
                coefficients=tower_coefficients,
                configurations=tower_configurations,
                seed=seed + 1_000 * update + 100,
                multiplet=True,
                sample_steps=samples_per_update,
                proposal_sweeps=proposal_sweeps,
            )
        )
        trace.append(
            {
                "update": update + 1,
                "ground": ground_record,
                "tower": tower_record,
                "objective": 0.5
                * (ground_record["energy"] + tower_record["energy"]),
            }
        )

    final_ground = [
        delayed_acceptance_chain(
            ground_mother_channels,
            ground_evaluator,
            n_particles=N_ELECTRONS,
            coefficients=ground_coefficients,
            seed=seed + 20_000 + chain,
            sample_steps=final_samples_per_chain,
            proposal_sweeps=proposal_sweeps,
            delta_max=0.35,
            initial_configuration=ground_configurations[chain],
            global_rotation_interval=4,
        )
        for chain in range(chains)
    ]
    final_tower = [
        delayed_acceptance_chain(
            tower_mother_channels,
            tower_evaluator,
            n_particles=N_ELECTRONS,
            coefficients=tower_coefficients,
            seed=seed + 21_000 + chain,
            sample_steps=final_samples_per_chain,
            proposal_sweeps=proposal_sweeps,
            delta_max=0.35,
            initial_configuration=tower_configurations[chain],
            global_rotation_interval=4,
        )
        for chain in range(chains)
    ]
    final_ground_statistics = _final_sector_diagnostics(final_ground)
    final_tower_statistics = _final_sector_diagnostics(final_tower)
    checkpoint = {
        "seed": seed,
        "n_electrons": N_ELECTRONS,
        "two_q": TWO_Q,
        "raw_generator_ranks": list(RAW_RANKS),
        "centering_mean": mean.tolist(),
        "covariance": covariance.tolist(),
        "whitening": whitening.tolist(),
        "ground_coefficients": {
            "real": ground_coefficients.real.tolist(),
            "imag": ground_coefficients.imag.tolist(),
        },
        "tower_coefficients": {
            "real": tower_coefficients.real.tolist(),
            "imag": tower_coefficients.imag.tolist(),
        },
        "initialization_norm": initialization_norm,
        "updates": updates,
        "checkpoint_selection": "final_update",
    }
    result = {
        "seed": seed,
        "initialization_norm": initialization_norm,
        "retained_generators": whitening.shape[0],
        "covariance_eigenvalues": np.linalg.eigvalsh(covariance).tolist(),
        "trace": trace,
        "initial_objective": trace[0]["objective"],
        "final_training_objective": trace[-1]["objective"],
        "final_ground": final_ground_statistics,
        "final_tower": final_tower_statistics,
        "final_gap": (
            final_tower_statistics["mean"]
            - final_ground_statistics["mean"]
        ),
    }
    return checkpoint, result


def write_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


__all__ = [
    "N_ELECTRONS",
    "RAW_RANKS",
    "TWO_Q",
    "estimate_centering_whitening",
    "ground_mother_channels",
    "ground_raw_channels",
    "raw_local_generators",
    "tower_mother_channels",
    "tower_raw_channels",
    "train_seed",
    "write_checkpoint",
]
