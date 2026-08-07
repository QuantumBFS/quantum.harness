from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .ising import IsingLattice
from .sampler import BiasedMetropolis


@dataclass(frozen=True)
class OptimizationRecord:
    step: int
    instantaneous_bias: float
    running_bias: float
    mean_s_block: float
    variance_s_block: float
    gradient: float
    update: float

    @property
    def bias(self) -> float:
        """Final variational result is the running average, per Supplement Eq. S1-S3."""
        return self.running_bias


class SingleOperatorOptimizer:
    """One-operator implementation of Supplementary Eqs. S1-S3."""

    def __init__(
        self,
        length: int,
        coupling: float,
        walkers: int = 16,
        seed: int = 20260714,
        initial_bias: float = 0.0,
        block_size: int = 3,
    ) -> None:
        if walkers < 2:
            raise ValueError("at least two walkers are required to estimate variance")
        seed_sequence = np.random.SeedSequence(seed)
        child_sequences = seed_sequence.spawn(walkers)
        self.samplers: list[BiasedMetropolis] = []
        for child in child_sequences:
            rng = np.random.default_rng(child)
            lattice = IsingLattice.random(length, rng)
            self.samplers.append(
                BiasedMetropolis(lattice, coupling, initial_bias, rng, block_size)
            )
        self.instantaneous_bias = float(initial_bias)
        self.running_bias = float(initial_bias)
        self.bias = float(initial_bias)

    def run(
        self,
        steps: int,
        sweeps_per_step: int,
        learning_rate: float,
        reset_fractions: tuple[float, ...] = (0.1, 0.2),
    ) -> list[OptimizationRecord]:
        if steps <= 0 or sweeps_per_step <= 0:
            raise ValueError("steps and sweeps_per_step must be positive")
        if learning_rate <= 0.0:
            raise ValueError("learning_rate must be positive")
        reset_steps = {max(1, int(round(steps * fraction))) for fraction in reset_fractions}
        if any(fraction <= 0.0 or fraction >= 1.0 for fraction in reset_fractions):
            raise ValueError("reset fractions must lie strictly between 0 and 1")

        records: list[OptimizationRecord] = []
        average_sum = self.running_bias
        average_count = 1
        for step in range(steps):
            for sampler in self.samplers:
                sampler.bias = self.running_bias
                for _ in range(sweeps_per_step):
                    sampler.sweep()

            values = np.asarray([sampler.s_block for sampler in self.samplers], dtype=float)
            mean = float(values.mean())
            variance = float(values.var(ddof=0))
            gradient = -mean
            correction = gradient + variance * (
                self.instantaneous_bias - self.running_bias
            )
            update = -learning_rate * correction
            self.instantaneous_bias += update

            completed_step = step + 1
            if completed_step in reset_steps:
                average_sum = self.instantaneous_bias
                average_count = 1
            else:
                average_sum += self.instantaneous_bias
                average_count += 1
            self.running_bias = average_sum / average_count
            self.bias = self.running_bias
            records.append(
                OptimizationRecord(
                    step=step,
                    instantaneous_bias=self.instantaneous_bias,
                    running_bias=self.running_bias,
                    mean_s_block=mean,
                    variance_s_block=variance,
                    gradient=gradient,
                    update=update,
                )
            )
        return records
