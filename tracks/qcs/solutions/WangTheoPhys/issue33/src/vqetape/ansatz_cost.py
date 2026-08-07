"""Spatial-contraction cost model for adaptive ansatz growth."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isfinite, log
from typing import Any

import jax

from vqetape.ansatz import (
    AnsatzOperator,
    AnsatzStructure,
)
from vqetape.ansatz_signals import AnsatzSignal
from vqetape.spec import TFIMVQESpec


@dataclass(frozen=True)
class AnsatzCostWeights:
    """Nonnegative weights for contraction-aware gate selection."""

    boundary: float = 1.0
    compile: float = 0.25
    warm: float = 0.25
    memory: float = 0.25

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if value < 0 or not isfinite(value):
                raise ValueError(
                    f"{name} weight must be finite and "
                    "nonnegative"
                )


@dataclass(frozen=True)
class AnsatzCostDelta:
    """Predicted structural cost change for one appended gate."""

    boundary_before: int
    boundary_after: int
    delta_log_boundary: float
    delta_compile_proxy: float
    delta_warm_proxy: float
    delta_memory_relative: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> AnsatzCostDelta:
        return cls(**payload)


def cut_entangler_counts(
    structure: AnsatzStructure,
) -> tuple[int, ...]:
    """Count RZZ Schmidt bonds crossing each chain cut."""

    counts = [0] * (structure.nqubits - 1)
    for operator in structure.operators:
        if operator.kind != "rx":
            counts[operator.wire] += 1
    return tuple(counts)


def spatial_boundary_dimension(
    structure: AnsatzStructure,
    *,
    mpo_bond_dimension: int = 3,
) -> int:
    """Return exact uncompressed bra-MPO-ket cut dimension."""

    if mpo_bond_dimension < 1:
        raise ValueError(
            "mpo_bond_dimension must be positive"
        )
    counts = cut_entangler_counts(structure)
    return mpo_bond_dimension * 4 ** max(counts, default=0)


def _compiler_weight(
    operator: AnsatzOperator,
) -> float:
    return 2.0 if operator.kind != "rx" else 1.0


def _warm_weight(operator: AnsatzOperator) -> float:
    return 1.5 if operator.kind != "rx" else 1.0


def candidate_cost_delta(
    structure: AnsatzStructure,
    operator: AnsatzOperator,
) -> AnsatzCostDelta:
    """Predict normalized cost increments for one gate."""

    extended = structure.append(operator)
    before = spatial_boundary_dimension(structure)
    after = spatial_boundary_dimension(extended)
    current_compile = sum(
        _compiler_weight(item)
        for item in structure.operators
    )
    current_warm = sum(
        _warm_weight(item)
        for item in structure.operators
    )
    return AnsatzCostDelta(
        boundary_before=before,
        boundary_after=after,
        delta_log_boundary=log(after / before),
        delta_compile_proxy=(
            _compiler_weight(operator)
            / max(1.0, current_compile)
        ),
        delta_warm_proxy=(
            _warm_weight(operator)
            / max(1.0, current_warm)
        ),
        delta_memory_relative=(after - before) / before,
    )


def contraction_aware_score(
    signal: AnsatzSignal,
    cost: AnsatzCostDelta,
    weights: AnsatzCostWeights,
) -> float:
    """Apply the approved signal-over-contraction-cost score."""

    denominator = (
        1.0
        + weights.boundary * cost.delta_log_boundary
        + weights.compile * cost.delta_compile_proxy
        + weights.warm * cost.delta_warm_proxy
        + weights.memory * cost.delta_memory_relative
    )
    if denominator <= 0 or not isfinite(denominator):
        raise ValueError(
            "contraction score denominator is invalid"
        )
    return signal.normalized_signal / denominator


def device_signature() -> tuple[str, ...]:
    """Return a stable description of the active JAX devices."""

    return tuple(
        (
            f"{device.platform}:{device.id}:"
            f"{device.device_kind}"
        )
        for device in jax.devices()
    )


def ansatz_cache_key(
    structure: AnsatzStructure,
    spec: TFIMVQESpec,
    *,
    jax_version: str | None = None,
    devices: tuple[str, ...] | None = None,
) -> str:
    """Hash all structure-dependent executable compatibility fields."""

    payload = {
        "structure": structure.to_dict(),
        "spec": spec.to_dict(),
        "jax_version": (
            jax.__version__
            if jax_version is None
            else jax_version
        ),
        "devices": (
            device_signature()
            if devices is None
            else devices
        ),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
