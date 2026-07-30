from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import time
from typing import Callable

import numpy as np

from .ising import IsingLattice
from .fast import FastMultiOperatorBiasedMetropolis
from .local_execution import resolve_worker_limit
from .multi import MultiOperatorBiasedMetropolis
from .operators import OperatorBasis, OperatorShape


@dataclass(frozen=True)
class MultiOptimizationRecord:
    step: int
    instantaneous_bias: np.ndarray
    running_bias: np.ndarray
    mean_operators: np.ndarray
    covariance: np.ndarray
    gradient: np.ndarray
    update: np.ndarray
    gradient_norm: float
    covariance_condition_number: float
    acceptance_rates: np.ndarray
    elapsed_seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "step": int(self.step),
            "instantaneous_bias": self.instantaneous_bias.tolist(),
            "running_bias": self.running_bias.tolist(),
            "mean_operators": self.mean_operators.tolist(),
            "covariance": self.covariance.tolist(),
            "gradient": self.gradient.tolist(),
            "update": self.update.tolist(),
            "gradient_norm": float(self.gradient_norm),
            "covariance_condition_number": float(
                self.covariance_condition_number
            ),
            "acceptance_rates": self.acceptance_rates.tolist(),
            "elapsed_seconds": float(self.elapsed_seconds),
        }


def _finite_covariance_condition(covariance: np.ndarray) -> float:
    eigenvalues = np.linalg.eigvalsh(np.asarray(covariance, dtype=np.float64))
    largest = max(0.0, float(eigenvalues[-1]))
    if largest == 0.0:
        return 1.0
    threshold = largest * np.finfo(np.float64).eps * max(1, eigenvalues.size)
    positive = eigenvalues[eigenvalues > threshold]
    if positive.size == 0:
        return 1.0
    return max(1.0, largest / float(positive[0]))


class MultiOperatorOptimizer:
    """Vector implementation of Supplementary Eqs. S1-S3."""

    def __init__(
        self,
        length: int,
        couplings: np.ndarray,
        shapes: tuple[OperatorShape, ...],
        walkers: int = 16,
        seed: int = 20260715,
        initial_bias: np.ndarray | None = None,
        block_size: int = 3,
        compiled: bool = True,
        parallel_walkers: bool = True,
        max_workers: int | None = None,
        initial_spins: np.ndarray | None = None,
    ) -> None:
        self.shapes = tuple(shapes)
        self.couplings = np.asarray(couplings, dtype=float).copy()
        if self.couplings.shape != (len(self.shapes),):
            raise ValueError("couplings have the wrong shape")
        if walkers < 2:
            raise ValueError("at least two walkers are required")
        bias = (
            np.zeros(len(self.shapes), dtype=float)
            if initial_bias is None
            else np.asarray(initial_bias, dtype=float).copy()
        )
        if bias.shape != self.couplings.shape:
            raise ValueError("initial_bias has the wrong shape")

        micro_basis = OperatorBasis(length, self.shapes)
        block_basis = OperatorBasis(length // block_size, self.shapes)
        child_sequences = np.random.SeedSequence(seed).spawn(walkers)
        initial_values: np.ndarray | None = None
        if initial_spins is not None:
            initial_values = np.asarray(initial_spins, dtype=np.int8)
            if initial_values.shape != (walkers, length, length):
                raise ValueError(
                    "initial spins must have shape (walkers, length, length)"
                )
            if not np.all((initial_values == -1) | (initial_values == 1)):
                raise ValueError("initial spins must contain only -1 and +1")
        sampler_class = (
            FastMultiOperatorBiasedMetropolis
            if compiled
            else MultiOperatorBiasedMetropolis
        )
        self.parallel_walkers = bool(parallel_walkers)
        self.max_workers = resolve_worker_limit(max_workers, walkers)
        self.samplers: list[
            FastMultiOperatorBiasedMetropolis | MultiOperatorBiasedMetropolis
        ] = []
        for walker, child in enumerate(child_sequences):
            rng = np.random.default_rng(child)
            lattice = (
                IsingLattice.random(length, rng)
                if initial_values is None
                else IsingLattice(initial_values[walker].copy())
            )
            self.samplers.append(
                sampler_class(
                    lattice=lattice,
                    couplings=self.couplings,
                    bias=bias,
                    rng=rng,
                    shapes=self.shapes,
                    block_size=block_size,
                    micro_basis=micro_basis,
                    block_basis=block_basis,
                )
            )
        self.instantaneous_bias = bias.copy()
        self.running_bias = bias.copy()

    def run(
        self,
        steps: int,
        sweeps_per_step: int,
        learning_rate: float,
        reset_fractions: tuple[float, ...] = (0.1, 0.2),
        callback: Callable[[MultiOptimizationRecord], None] | None = None,
    ) -> list[MultiOptimizationRecord]:
        if steps <= 0 or sweeps_per_step <= 0 or learning_rate <= 0.0:
            raise ValueError("steps, sweeps_per_step and learning_rate must be positive")
        if any(fraction <= 0.0 or fraction >= 1.0 for fraction in reset_fractions):
            raise ValueError("reset fractions must lie strictly between 0 and 1")
        reset_steps = {max(1, int(round(steps * fraction))) for fraction in reset_fractions}

        average_sum = self.running_bias.copy()
        average_count = 1
        records: list[MultiOptimizationRecord] = []
        started = time.perf_counter()
        executor = (
            ThreadPoolExecutor(max_workers=self.max_workers)
            if self.parallel_walkers and len(self.samplers) > 1
            else None
        )
        try:
            for step in range(steps):
                for sampler in self.samplers:
                    sampler.bias = self.running_bias.copy()
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

                samples = np.stack(
                    [sampler.block_values for sampler in self.samplers]
                ).astype(float)
                mean = samples.mean(axis=0)
                centered = samples - mean
                covariance = centered.T @ centered / samples.shape[0]
                gradient = -mean
                correction = gradient + covariance @ (
                    self.instantaneous_bias - self.running_bias
                )
                update = -learning_rate * correction
                self.instantaneous_bias = self.instantaneous_bias + update

                completed_step = step + 1
                if completed_step in reset_steps:
                    average_sum = self.instantaneous_bias.copy()
                    average_count = 1
                else:
                    average_sum = average_sum + self.instantaneous_bias
                    average_count += 1
                self.running_bias = average_sum / average_count
                record = MultiOptimizationRecord(
                    step=step,
                    instantaneous_bias=self.instantaneous_bias.copy(),
                    running_bias=self.running_bias.copy(),
                    mean_operators=mean.copy(),
                    covariance=covariance.copy(),
                    gradient=gradient.copy(),
                    update=update.copy(),
                    gradient_norm=float(np.linalg.norm(gradient)),
                    covariance_condition_number=_finite_covariance_condition(
                        covariance
                    ),
                    acceptance_rates=np.asarray(
                        [sampler.acceptance_rate for sampler in self.samplers],
                        dtype=np.float64,
                    ),
                    elapsed_seconds=time.perf_counter() - started,
                )
                records.append(record)
                if callback is not None:
                    callback(record)
        finally:
            if executor is not None:
                executor.shutdown(wait=True)
        return records
