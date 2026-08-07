"""Stochastic VMCRG optimization for a centered local patch-MPS residual."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import os
import time
from typing import Callable

import numpy as np

from .ising import IsingLattice
from .mps_patch import MPSGradient, PatchMPS
from .mps_sampler import MPSBiasedMetropolis
from .observables import patch_distribution_distances
from .operators import OperatorBasis, OperatorShape
from .patch_table import PatchLookupTable, enumerate_patches


def _scaled_gradient(gradient: MPSGradient, scale: float) -> MPSGradient:
    return MPSGradient(tuple(core * scale for core in gradient.cores))


def residual_parameter_gradient(
    model: PatchMPS,
    alpha: float,
    mean_histogram: np.ndarray,
) -> tuple[float, MPSGradient]:
    """Derivative of mean residual energy per patch under a supplied histogram."""
    histogram = np.asarray(mean_histogram, dtype=np.float64)
    if histogram.shape != (512,) or np.any(histogram < 0.0) or histogram.sum() <= 0.0:
        raise ValueError("mean_histogram must be 512 nonnegative counts")
    count = float(histogram.sum())
    lookup = PatchLookupTable.from_model(model)
    derivative_alpha = float(histogram @ lookup.values) / count
    centered_weights = histogram - count / 512.0
    derivative_cores = _scaled_gradient(
        model.gradient(
            enumerate_patches(),
            weights=centered_weights,
            symmetrize=lookup.symmetrized,
        ),
        float(alpha) / count,
    )
    return derivative_alpha, derivative_cores


def _log_mean_exp(values: np.ndarray) -> float:
    supplied = np.asarray(values, dtype=np.float64)
    maximum = float(supplied.max())
    return maximum + float(np.log(np.mean(np.exp(supplied - maximum))))


@dataclass(frozen=True)
class MPSOptimizationRecord:
    step: int
    objective: float
    objective_change: float
    gradient_norm: float
    core_gradient_norm: float
    alpha_gradient: float
    linear_gradient_norm: float
    alpha: float
    parameter_norm: float
    output_min: float
    output_max: float
    acceptance_rate: float
    block_nn_correlation: float
    patch_total_variation: float
    patch_jensen_shannon: float
    patch_kl_smoothed: float
    sweep_seconds: float
    total_seconds: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


class _Adam:
    def __init__(
        self,
        model: PatchMPS,
        linear_bias: np.ndarray,
        alpha_learning_rate: float,
        core_learning_rate: float,
        linear_learning_rate: float,
    ) -> None:
        for value in (alpha_learning_rate, core_learning_rate, linear_learning_rate):
            if value < 0.0:
                raise ValueError("learning rates cannot be negative")
        if alpha_learning_rate == 0.0 or core_learning_rate == 0.0:
            raise ValueError("alpha and core learning rates must be positive")
        self.alpha_learning_rate = float(alpha_learning_rate)
        self.core_learning_rate = float(core_learning_rate)
        self.linear_learning_rate = float(linear_learning_rate)
        self.step = 0
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.epsilon = 1e-8
        self.alpha_m = 0.0
        self.alpha_v = 0.0
        self.core_m = tuple(np.zeros_like(core) for core in model.cores)
        self.core_v = tuple(np.zeros_like(core) for core in model.cores)
        self.linear_m = np.zeros_like(linear_bias)
        self.linear_v = np.zeros_like(linear_bias)

    def reset_core_moments(self) -> None:
        for first, second in zip(self.core_m, self.core_v):
            first.fill(0.0)
            second.fill(0.0)

    def update(
        self,
        model: PatchMPS,
        alpha: float,
        linear_bias: np.ndarray,
        alpha_gradient: float,
        core_gradient: MPSGradient,
        linear_gradient: np.ndarray,
    ) -> float:
        self.step += 1
        correction1 = 1.0 - self.beta1**self.step
        correction2 = 1.0 - self.beta2**self.step
        self.alpha_m = self.beta1 * self.alpha_m + (1.0 - self.beta1) * alpha_gradient
        self.alpha_v = self.beta2 * self.alpha_v + (1.0 - self.beta2) * alpha_gradient**2
        alpha -= self.alpha_learning_rate * (self.alpha_m / correction1) / (
            np.sqrt(self.alpha_v / correction2) + self.epsilon
        )
        for parameter, derivative, first, second in zip(
            model.cores, core_gradient.cores, self.core_m, self.core_v
        ):
            first *= self.beta1
            first += (1.0 - self.beta1) * derivative
            second *= self.beta2
            second += (1.0 - self.beta2) * derivative**2
            parameter -= self.core_learning_rate * (first / correction1) / (
                np.sqrt(second / correction2) + self.epsilon
            )
        if self.linear_learning_rate > 0.0:
            self.linear_m *= self.beta1
            self.linear_m += (1.0 - self.beta1) * linear_gradient
            self.linear_v *= self.beta2
            self.linear_v += (1.0 - self.beta2) * linear_gradient**2
            linear_bias -= self.linear_learning_rate * (self.linear_m / correction1) / (
                np.sqrt(self.linear_v / correction2) + self.epsilon
            )
        return float(alpha)


class MPSVMCRGOptimizer:
    """Multiple-walker Stage B residual training with optional Stage C J tuning."""

    def __init__(
        self,
        length: int,
        couplings: np.ndarray,
        linear_bias: np.ndarray,
        model: PatchMPS,
        shapes: tuple[OperatorShape, ...],
        walkers: int = 16,
        seed: int = 20260801,
        alpha: float = 0.0,
        block_size: int = 3,
        rg_levels: int = 1,
        compiled: bool = True,
        parallel_walkers: bool = True,
    ) -> None:
        if walkers < 2:
            raise ValueError("at least two walkers are required")
        self.length = int(length)
        self.couplings = np.asarray(couplings, dtype=np.float64).copy()
        self.linear_bias = np.asarray(linear_bias, dtype=np.float64).copy()
        self.model = model
        self.shapes = tuple(shapes)
        self.alpha = float(alpha)
        self.walker_count = int(walkers)
        self.block_size = int(block_size)
        self.rg_levels = int(rg_levels)
        self.parallel_walkers = bool(parallel_walkers)
        lookup = PatchLookupTable.from_model(model)
        coarse_length = length // (block_size**rg_levels)
        micro_basis = OperatorBasis(length, self.shapes)
        block_basis = OperatorBasis(coarse_length, self.shapes)
        sequences = np.random.SeedSequence(seed).spawn(walkers)
        self.samplers: list[MPSBiasedMetropolis] = []
        for sequence in sequences:
            rng = np.random.default_rng(sequence)
            self.samplers.append(
                MPSBiasedMetropolis(
                    IsingLattice.random(length, rng),
                    self.couplings,
                    self.linear_bias,
                    self.alpha,
                    lookup,
                    rng,
                    self.shapes,
                    block_size=block_size,
                    rg_levels=rg_levels,
                    compiled=compiled,
                    micro_basis=micro_basis,
                    block_basis=block_basis,
                )
            )
        self.lookup = lookup

    def run(
        self,
        steps: int,
        sweeps_per_step: int,
        alpha_learning_rate: float,
        core_learning_rate: float,
        linear_learning_rate: float = 0.0,
        gradient_clip: float = 10.0,
        canonicalize_every: int = 25,
        cache_check_every: int = 25,
        callback: Callable[[MPSOptimizationRecord], None] | None = None,
    ) -> list[MPSOptimizationRecord]:
        if steps <= 0 or sweeps_per_step <= 0:
            raise ValueError("steps and sweeps_per_step must be positive")
        if gradient_clip <= 0.0:
            raise ValueError("gradient_clip must be positive")
        optimizer = _Adam(
            self.model,
            self.linear_bias,
            alpha_learning_rate,
            core_learning_rate,
            linear_learning_rate,
        )
        n_sites = self.samplers[0].rg_state.coarse_spins.size
        objective = 0.0
        records: list[MPSOptimizationRecord] = []
        start = time.perf_counter()
        executor = (
            ThreadPoolExecutor(max_workers=min(self.walker_count, os.cpu_count() or 1))
            if self.parallel_walkers
            else None
        )
        try:
            for step in range(steps):
                attempted_before = sum(sampler.attempted for sampler in self.samplers)
                accepted_before = sum(sampler.accepted for sampler in self.samplers)
                sweep_start = time.perf_counter()
                if executor is None:
                    for sampler in self.samplers:
                        sampler.run_sweeps(sweeps_per_step)
                else:
                    list(
                        executor.map(
                            lambda sampler: sampler.run_sweeps(sweeps_per_step),
                            self.samplers,
                        )
                    )
                sweep_seconds = time.perf_counter() - sweep_start
                histograms = np.stack(
                    [sampler.patch_cache.histogram for sampler in self.samplers]
                ).astype(np.float64)
                mean_histogram = histograms.mean(axis=0)
                residual_alpha, residual_cores = residual_parameter_gradient(
                    self.model, self.alpha, mean_histogram
                )
                alpha_gradient = -residual_alpha
                core_gradient = _scaled_gradient(residual_cores, -1.0)
                block_samples = np.stack(
                    [sampler.block_values for sampler in self.samplers]
                ).astype(np.float64)
                linear_gradient = -block_samples.mean(axis=0) / n_sites

                combined_norm = float(
                    np.sqrt(
                        alpha_gradient**2
                        + core_gradient.norm() ** 2
                        + (
                            np.dot(linear_gradient, linear_gradient)
                            if linear_learning_rate > 0.0
                            else 0.0
                        )
                    )
                )
                if combined_norm > gradient_clip:
                    scale = gradient_clip / combined_norm
                    alpha_gradient *= scale
                    core_gradient = _scaled_gradient(core_gradient, scale)
                    linear_gradient *= scale

                old_lookup = self.lookup
                old_alpha = self.alpha
                old_linear = self.linear_bias.copy()
                self.alpha = optimizer.update(
                    self.model,
                    self.alpha,
                    self.linear_bias,
                    alpha_gradient,
                    core_gradient,
                    linear_gradient,
                )
                if canonicalize_every > 0 and (step + 1) % canonicalize_every == 0:
                    self.model.left_canonicalize()
                    optimizer.reset_core_moments()
                diagnostics = self.model.diagnostics()
                if not np.isfinite(self.alpha) or not np.isfinite(
                    diagnostics["parameter_norm"]
                ):
                    raise FloatingPointError("MPS optimizer produced a non-finite parameter")
                self.lookup = PatchLookupTable.from_model(self.model)

                delta_bias = np.empty(self.walker_count, dtype=np.float64)
                for index, (sampler, histogram) in enumerate(zip(self.samplers, histograms)):
                    old_residual = float(histogram @ old_lookup.values)
                    new_residual = float(histogram @ self.lookup.values)
                    delta_bias[index] = float(
                        (self.linear_bias - old_linear) @ sampler.block_values
                        + self.alpha * new_residual
                        - old_alpha * old_residual
                    )
                    sampler.set_bias(self.linear_bias, self.alpha, self.lookup)
                objective_change = _log_mean_exp(-delta_bias)
                objective += objective_change

                attempted = sum(sampler.attempted for sampler in self.samplers) - attempted_before
                accepted = sum(sampler.accepted for sampler in self.samplers) - accepted_before
                distances = patch_distribution_distances(mean_histogram)
                nn_count = self.samplers[0].block_basis.instance_counts[0]
                block_nn = -float(block_samples[:, 0].mean()) / nn_count
                record = MPSOptimizationRecord(
                    step=step,
                    objective=float(objective),
                    objective_change=float(objective_change),
                    gradient_norm=float(combined_norm),
                    core_gradient_norm=float(core_gradient.norm()),
                    alpha_gradient=float(alpha_gradient),
                    linear_gradient_norm=float(np.linalg.norm(linear_gradient)),
                    alpha=float(self.alpha),
                    parameter_norm=float(diagnostics["parameter_norm"]),
                    output_min=float(diagnostics["output_min"]),
                    output_max=float(diagnostics["output_max"]),
                    acceptance_rate=float(accepted / attempted),
                    block_nn_correlation=block_nn,
                    patch_total_variation=distances["total_variation"],
                    patch_jensen_shannon=distances["jensen_shannon"],
                    patch_kl_smoothed=distances["kl_smoothed"],
                    sweep_seconds=float(sweep_seconds),
                    total_seconds=float(time.perf_counter() - start),
                )
                records.append(record)
                if callback is not None:
                    callback(record)
                if cache_check_every > 0 and (step + 1) % cache_check_every == 0:
                    for sampler in self.samplers:
                        sampler.assert_cache_consistent()
        finally:
            if executor is not None:
                executor.shutdown(wait=True)
        return records
