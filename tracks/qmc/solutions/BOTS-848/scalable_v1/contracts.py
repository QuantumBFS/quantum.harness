from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class SampleBatch:
    configs: Any
    n_samples: int
    burn_in_steps: int
    seed: int

    def __post_init__(self) -> None:
        if len(self.configs) != self.n_samples:
            raise ValueError("n_samples does not match configuration batch")


@dataclass(frozen=True)
class ConstructionCertificate:
    strict_lll: bool
    antisymmetric: bool
    scalable: bool
    trainable_parameters: int
    statement: str

    def __post_init__(self) -> None:
        if self.trainable_parameters <= 0:
            raise ValueError("trainable_parameters must be positive")


@dataclass(frozen=True)
class ResourceMetrics:
    placement: str
    wall_seconds: float
    peak_rss_bytes: int
    peak_vram_bytes: int | None
    checkpoint_bytes: int
    estimator_evaluations: int
    effective_sample_size: float
    n8_smoke_complete: bool
    n8_to_n6_time_ratio: float
    n8_to_n6_memory_ratio: float
    device_fingerprint: str

    def __post_init__(self) -> None:
        if self.placement not in {"local", "remote"}:
            raise ValueError("placement must be local or remote")
        if not math.isfinite(self.wall_seconds) or self.wall_seconds <= 0.0:
            raise ValueError("wall_seconds must be finite and positive")
        if (
            not math.isfinite(self.effective_sample_size)
            or self.effective_sample_size < 0.0
        ):
            raise ValueError("effective_sample_size must be finite and nonnegative")
        if self.n8_smoke_complete and (
            not math.isfinite(self.n8_to_n6_time_ratio)
            or not math.isfinite(self.n8_to_n6_memory_ratio)
            or self.n8_to_n6_time_ratio <= 0.0
            or self.n8_to_n6_memory_ratio <= 0.0
        ):
            raise ValueError("completed N=8 smoke ratios must be finite and positive")

    @property
    def ess_per_second(self) -> float:
        return self.effective_sample_size / self.wall_seconds


@runtime_checkable
class StateHandle(Protocol):
    label: str
    l: int
    m: int

    def sample(self, n_samples: int, seed: int) -> SampleBatch: ...
    def logpsi(self, config_batch: Any) -> np.ndarray: ...
    def local_energy(self, config_batch: Any) -> np.ndarray: ...
    def local_l2(self, config_batch: Any) -> np.ndarray: ...


@runtime_checkable
class CandidateAdapter(Protocol):
    name: str
    family: str

    def ground_state(self) -> StateHandle: ...
    def generate_multiplet(self) -> Mapping[int, StateHandle]: ...
    def construction_certificate(self) -> ConstructionCertificate: ...
    def resource_metrics(self) -> ResourceMetrics: ...


@runtime_checkable
class DiagnosticProvider(Protocol):
    def evaluate(
        self,
        candidate: CandidateAdapter,
        *,
        seed: int,
        swap_probes: int,
        rotation_probes: int,
    ) -> Mapping[str, float]: ...
