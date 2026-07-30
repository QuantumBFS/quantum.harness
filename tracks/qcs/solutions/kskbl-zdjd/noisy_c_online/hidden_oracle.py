"""Hidden online data stream and isolated clean evaluator for Task C+.

The learner imports only the ``sample`` method of ``FreshNoiseStream`` during
optimization.  The complete clean domain is owned by ``CleanDomainEvaluator``
and is used under ``torch.inference_mode`` after a checkpoint is frozen.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


INPUT_BITS = 12
OUTPUT_BITS = 12
DOMAIN_SIZE = 1 << INPUT_BITS


def _ids_to_inputs(ids: torch.Tensor) -> torch.Tensor:
    """Encode input IDs as x bits followed by y bits, both LSB-first."""

    shifts = torch.arange(INPUT_BITS, device=ids.device)
    return ((ids[:, None] >> shifts[None, :]) & 1).to(torch.float32)


def _hidden_clean_bits(ids: torch.Tensor) -> torch.Tensor:
    """Return the hidden clean map. This function is not called by the learner."""

    x = ids & 63
    y = (ids >> 6) & 63
    value = x * y
    shifts = torch.arange(OUTPUT_BITS, device=ids.device)
    return ((value[:, None] >> shifts[None, :]) & 1).to(torch.float32)


@dataclass
class FreshNoiseStream:
    """Generate a new random input batch and a new independent noise mask."""

    batch_size: int
    noise_rate: float
    seed: int
    device: torch.device

    def __post_init__(self) -> None:
        if not 0.0 <= self.noise_rate < 0.5:
            raise ValueError("noise_rate must satisfy 0 <= p < 0.5")
        self.generator = torch.Generator(device=self.device)
        self.generator.manual_seed(self.seed)

    def sample(self) -> tuple[torch.Tensor, torch.Tensor]:
        ids = torch.randint(
            0,
            DOMAIN_SIZE,
            (self.batch_size,),
            generator=self.generator,
            device=self.device,
        )
        inputs = _ids_to_inputs(ids)
        clean = _hidden_clean_bits(ids)
        flips = torch.rand(
            clean.shape,
            generator=self.generator,
            device=self.device,
        ) < self.noise_rate
        noisy = torch.logical_xor(clean.bool(), flips).to(torch.float32)
        return inputs, noisy


@dataclass
class ShuffledCycleFreshNoiseStream:
    """Randomly permute the domain each cycle while regenerating every flip."""

    batch_size: int
    noise_rate: float
    seed: int
    device: torch.device

    def __post_init__(self) -> None:
        if not 0.0 <= self.noise_rate < 0.5:
            raise ValueError("noise_rate must satisfy 0 <= p < 0.5")
        self.generator = torch.Generator(device=self.device)
        self.generator.manual_seed(self.seed)
        self.permutation = torch.empty(
            0,
            dtype=torch.int64,
            device=self.device,
        )
        self.offset = 0

    def _sample_ids(self) -> torch.Tensor:
        chunks: list[torch.Tensor] = []
        remaining = self.batch_size
        while remaining:
            if self.offset >= len(self.permutation):
                self.permutation = torch.randperm(
                    DOMAIN_SIZE,
                    generator=self.generator,
                    device=self.device,
                )
                self.offset = 0
            take = min(remaining, len(self.permutation) - self.offset)
            chunks.append(self.permutation[self.offset : self.offset + take])
            self.offset += take
            remaining -= take
        return torch.cat(chunks)

    def sample(self) -> tuple[torch.Tensor, torch.Tensor]:
        ids = self._sample_ids()
        inputs = _ids_to_inputs(ids)
        clean = _hidden_clean_bits(ids)
        flips = torch.rand(
            clean.shape,
            generator=self.generator,
            device=self.device,
        ) < self.noise_rate
        noisy = torch.logical_xor(clean.bool(), flips).to(torch.float32)
        return inputs, noisy


@dataclass
class FixedDesignFreshNoiseStream:
    """Cycle through a supplied label-blind design with fresh output noise."""

    batch_size: int
    noise_rate: float | torch.Tensor
    seed: int
    device: torch.device
    design_ids: torch.Tensor

    def __post_init__(self) -> None:
        if isinstance(self.noise_rate, torch.Tensor):
            rates = self.noise_rate.to(
                device=self.device,
                dtype=torch.float32,
            ).flatten()
            if len(rates) != OUTPUT_BITS:
                raise ValueError("per-bit noise must contain 12 rates")
            if bool(torch.any(rates < 0.0)) or bool(torch.any(rates >= 0.5)):
                raise ValueError("all per-bit rates must satisfy 0 <= p < 0.5")
            self.noise_rate = rates
        elif not 0.0 <= self.noise_rate < 0.5:
            raise ValueError("noise_rate must satisfy 0 <= p < 0.5")
        design = self.design_ids.to(device=self.device, dtype=torch.int64)
        if design.ndim != 1 or len(design) == 0:
            raise ValueError("design_ids must be a non-empty one-dimensional tensor")
        if int(design.min()) < 0 or int(design.max()) >= DOMAIN_SIZE:
            raise ValueError("design_ids lie outside the input domain")
        if len(torch.unique(design)) != len(design):
            raise ValueError("design_ids must be unique")
        self.design_ids = design
        self.generator = torch.Generator(device=self.device)
        self.generator.manual_seed(self.seed)
        self.permutation = torch.empty(
            0,
            dtype=torch.int64,
            device=self.device,
        )
        self.offset = 0

    def _sample_ids(self) -> torch.Tensor:
        chunks: list[torch.Tensor] = []
        remaining = self.batch_size
        while remaining:
            if self.offset >= len(self.permutation):
                order = torch.randperm(
                    len(self.design_ids),
                    generator=self.generator,
                    device=self.device,
                )
                self.permutation = self.design_ids[order]
                self.offset = 0
            take = min(remaining, len(self.permutation) - self.offset)
            chunks.append(self.permutation[self.offset : self.offset + take])
            self.offset += take
            remaining -= take
        return torch.cat(chunks)

    def sample(self) -> tuple[torch.Tensor, torch.Tensor]:
        ids = self._sample_ids()
        inputs = _ids_to_inputs(ids)
        clean = _hidden_clean_bits(ids)
        flips = torch.rand(
            clean.shape,
            generator=self.generator,
            device=self.device,
        ) < self.noise_rate
        noisy = torch.logical_xor(clean.bool(), flips).to(torch.float32)
        return inputs, noisy


class CleanDomainEvaluator:
    """Own the complete clean domain without exposing it to optimization."""

    def __init__(self, device: torch.device) -> None:
        ids = torch.arange(DOMAIN_SIZE, device=device)
        self.ids = ids
        self.inputs = _ids_to_inputs(ids)
        self.targets = _hidden_clean_bits(ids)
