from __future__ import annotations

from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True)
class ModelConfig:
    lx: int = 10
    ly: int = 10
    j: float = 1.0
    fields: tuple[float, ...] = (2.5, 3.0, 3.5)

    def __post_init__(self) -> None:
        if not isinstance(self.fields, tuple):
            raise TypeError("fields must be a tuple")
        if self.lx < 1 or self.ly < 1:
            raise ValueError("lattice extents must be positive")
        if self.j <= 0:
            raise ValueError("J must be positive")
        if not self.fields or any(h < 0 for h in self.fields):
            raise ValueError("fields must be a non-empty tuple of non-negative values")

    @property
    def nsites(self) -> int:
        return self.lx * self.ly


@dataclass(frozen=True)
class EvolutionConfig:
    beta_min: float = 0.1
    beta_max: float = 1.0
    output_step: float = 0.1
    delta_beta: float = 0.025
    bond_dims: tuple[int, ...] = (4, 6, 8)

    def __post_init__(self) -> None:
        if not isinstance(self.bond_dims, tuple):
            raise TypeError("bond_dims must be a tuple")
        if not 0 < self.delta_beta <= self.output_step:
            raise ValueError("delta_beta must lie in (0, output_step]")
        if self.beta_min <= 0 or self.beta_max < self.beta_min:
            raise ValueError("invalid beta interval")
        if not self.bond_dims or any(d < 1 for d in self.bond_dims):
            raise ValueError("bond dimensions must be positive")
        span = self.beta_max - self.beta_min
        intervals = round(span / self.output_step)
        if not isclose(
            intervals * self.output_step,
            span,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("beta interval must form an exact output grid")

    def output_betas(self) -> tuple[float, ...]:
        count = round((self.beta_max - self.beta_min) / self.output_step) + 1
        return tuple(round(self.beta_min + i * self.output_step, 12) for i in range(count))
