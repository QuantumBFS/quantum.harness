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


class CleanDomainEvaluator:
    """Own the complete clean domain without exposing it to optimization."""

    def __init__(self, device: torch.device) -> None:
        ids = torch.arange(DOMAIN_SIZE, device=device)
        self.ids = ids
        self.inputs = _ids_to_inputs(ids)
        self.targets = _hidden_clean_bits(ids)
