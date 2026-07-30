"""VMC estimators for the frozen Route C training protocol."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
import os
from pathlib import Path
from typing import Any

import numpy as np


FROZEN_TRAINING_SEEDS = (848, 1848, 2848)
FROZEN_UPDATES = 2048
FROZEN_BATCH_SIZE = 512
FROZEN_CHAINS = 8
FROZEN_BURN_IN_SWEEPS = 1024
FROZEN_CHECKPOINT_INTERVAL = 128
FROZEN_LEARNING_RATE = 0.001
FROZEN_BETA1 = 0.9
FROZEN_BETA2 = 0.999
FROZEN_EPSILON = 1.0e-8
FROZEN_GRADIENT_CLIP_NORM = 10.0
FROZEN_CHECKPOINT_SELECTION = "final_update"
EXPECTED_PROTOCOL_SHA256 = (
    "716383e208a186c338b1f2b8a15257b7708c176cc90811d24b1930e477f33f95"
)

LocalEnergyFunction = Callable[..., np.ndarray]


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


def _validate_training_seed(training_seed: int) -> int:
    if (
        isinstance(training_seed, bool)
        or not isinstance(training_seed, (int, np.integer))
        or int(training_seed) not in FROZEN_TRAINING_SEEDS
    ):
        raise ValueError(
            f"training seed must be one of {FROZEN_TRAINING_SEEDS}"
        )
    return int(training_seed)


def _atomic_npz(path: Path, **arrays: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _real_finite_energies(values: object, *, batch_size: int) -> np.ndarray:
    energies = np.asarray(values)
    if energies.shape != (batch_size,):
        raise ValueError("local energy function must return shape (batch,)")
    if np.iscomplexobj(energies):
        if np.max(np.abs(np.imag(energies))) > 1.0e-8:
            raise ValueError("local energy imaginary part exceeds 1e-8")
        energies = np.real(energies)
    energies = np.asarray(energies, dtype=np.float64)
    if not np.all(np.isfinite(energies)):
        raise ValueError("local energies must be finite")
    return energies


def _checkpoint(
    *,
    run_dir: Path,
    update: int,
    training_seed: int,
    parameters: np.ndarray,
    first_moment: np.ndarray,
    second_moment: np.ndarray,
) -> None:
    _atomic_npz(
        run_dir / "checkpoint.npz",
        update=np.asarray(update, dtype=np.int64),
        training_seed=np.asarray(training_seed, dtype=np.int64),
        parameters=np.asarray(parameters, dtype=np.float64),
        protocol_sha256=np.asarray(EXPECTED_PROTOCOL_SHA256),
        checkpoint_selection=np.asarray(FROZEN_CHECKPOINT_SELECTION),
    )
    _atomic_npz(
        run_dir / "optimizer-state.npz",
        update=np.asarray(update, dtype=np.int64),
        training_seed=np.asarray(training_seed, dtype=np.int64),
        first_moment=np.asarray(first_moment, dtype=np.float64),
        second_moment=np.asarray(second_moment, dtype=np.float64),
        beta1=np.asarray(FROZEN_BETA1),
        beta2=np.asarray(FROZEN_BETA2),
        epsilon=np.asarray(FROZEN_EPSILON),
    )


def run_training(
    *,
    model: object,
    samplers: Sequence[object],
    training_seed: int,
    run_dir: Path,
    local_energy_fn: LocalEnergyFunction = coulomb_local_energy,
) -> dict[str, Any]:
    """Run the immutable 2048-update six-sector Route C schedule."""

    selected_seed = _validate_training_seed(training_seed)
    target = Path(run_dir)
    if target.exists():
        raise FileExistsError(f"run directory already exists: {target}")
    if len(samplers) != 6:
        raise ValueError("exactly six independent sector samplers are required")
    if not callable(local_energy_fn):
        raise TypeError("local_energy_fn must be callable")

    parameters = np.asarray(model.flat_parameters(), dtype=np.float64)
    parameter_count = getattr(model, "parameter_count", None)
    if parameters.ndim != 1 or parameters.size != parameter_count:
        raise ValueError("model parameter vector is inconsistent")
    if not np.all(np.isfinite(parameters)):
        raise ValueError("model parameters must be finite")
    two_q = getattr(model, "two_q", None)
    if (
        isinstance(two_q, bool)
        or not isinstance(two_q, (int, np.integer))
        or int(two_q) <= 0
    ):
        raise ValueError("model.two_q must be a positive integer")

    target.mkdir(parents=True, exist_ok=False)
    log_path = target / "training.jsonl"
    first_moment = np.zeros_like(parameters)
    second_moment = np.zeros_like(parameters)
    final_record: dict[str, Any] | None = None

    with log_path.open("x", encoding="utf-8", newline="\n") as log_handle:
        for update in range(1, FROZEN_UPDATES + 1):
            sector_energies: list[float] = []
            sector_gradients: list[np.ndarray] = []
            sampler_records: list[dict[str, Any]] = []
            for sector_index, sampler in enumerate(samplers):
                batch = sampler.sample(batch_size=FROZEN_BATCH_SIZE)
                configs = np.asarray(batch.configurations)
                if configs.shape[0] != FROZEN_BATCH_SIZE:
                    raise ValueError("sampler returned the wrong batch size")
                scores = np.asarray(
                    model.log_derivative(configs, sector_index),
                    dtype=np.complex128,
                )
                if scores.shape != (FROZEN_BATCH_SIZE, parameters.size):
                    raise ValueError(
                        "model score must have shape (batch, parameters)"
                    )
                local_energies = _real_finite_energies(
                    local_energy_fn(configs, two_q=int(two_q)),
                    batch_size=FROZEN_BATCH_SIZE,
                )
                sector_energies.append(float(np.mean(local_energies)))
                sector_gradients.append(
                    real_energy_gradient(scores, local_energies)
                )
                sampler_records.append(
                    {
                        "sector": sector_index,
                        "proposals": int(batch.proposals),
                        "accepted": int(batch.accepted),
                        "acceptance_rate": float(batch.acceptance_rate),
                    }
                )

            gradient = sector_gradients[0] + np.mean(
                np.stack(sector_gradients[1:], axis=0), axis=0
            )
            raw_gradient_norm = float(np.linalg.norm(gradient))
            if not np.isfinite(raw_gradient_norm):
                raise ValueError("combined gradient is non-finite")
            clip_scale = min(
                1.0,
                FROZEN_GRADIENT_CLIP_NORM
                / max(raw_gradient_norm, np.finfo(np.float64).tiny),
            )
            gradient = gradient * clip_scale
            clipped_gradient_norm = float(np.linalg.norm(gradient))

            first_moment = (
                FROZEN_BETA1 * first_moment
                + (1.0 - FROZEN_BETA1) * gradient
            )
            second_moment = (
                FROZEN_BETA2 * second_moment
                + (1.0 - FROZEN_BETA2) * gradient * gradient
            )
            corrected_first = first_moment / (1.0 - FROZEN_BETA1**update)
            corrected_second = second_moment / (1.0 - FROZEN_BETA2**update)
            parameters = parameters - FROZEN_LEARNING_RATE * corrected_first / (
                np.sqrt(corrected_second) + FROZEN_EPSILON
            )
            if not np.all(np.isfinite(parameters)):
                raise ValueError("Adam produced non-finite parameters")
            model.set_flat_parameters(parameters)
            for sampler in samplers:
                sampler.invalidate_amplitudes()

            checkpoint_due = update % FROZEN_CHECKPOINT_INTERVAL == 0
            if checkpoint_due:
                _checkpoint(
                    run_dir=target,
                    update=update,
                    training_seed=selected_seed,
                    parameters=parameters,
                    first_moment=first_moment,
                    second_moment=second_moment,
                )

            excited_energy = float(np.mean(sector_energies[1:]))
            final_record = {
                "schema": "route-c-training-update-v1",
                "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
                "training_seed": selected_seed,
                "update": update,
                "optimizer_updates": FROZEN_UPDATES,
                "batch_size_per_sector": FROZEN_BATCH_SIZE,
                "sector_energies": sector_energies,
                "ground_energy": sector_energies[0],
                "excited_energy": excited_energy,
                "gap": excited_energy - sector_energies[0],
                "l2_expectations": [0.0, 6.0, 6.0, 6.0, 6.0, 6.0],
                "raw_gradient_norm": raw_gradient_norm,
                "clipped_gradient_norm": clipped_gradient_norm,
                "parameter_norm": float(np.linalg.norm(parameters)),
                "samplers": sampler_records,
                "checkpoint": checkpoint_due,
                "checkpoint_selection": FROZEN_CHECKPOINT_SELECTION,
            }
            log_handle.write(
                json.dumps(final_record, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
            log_handle.flush()
            os.fsync(log_handle.fileno())

    if final_record is None or final_record["update"] != FROZEN_UPDATES:
        raise RuntimeError("training ended before the frozen final update")
    return final_record


__all__ = [
    "EXPECTED_PROTOCOL_SHA256",
    "FROZEN_BATCH_SIZE",
    "FROZEN_BURN_IN_SWEEPS",
    "FROZEN_CHAINS",
    "FROZEN_CHECKPOINT_INTERVAL",
    "FROZEN_TRAINING_SEEDS",
    "FROZEN_UPDATES",
    "coulomb_local_energy",
    "real_energy_gradient",
    "run_training",
]
