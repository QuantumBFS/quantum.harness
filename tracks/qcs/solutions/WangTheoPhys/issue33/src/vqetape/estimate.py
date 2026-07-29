"""Analytical upper bounds used for cheap candidate filtering."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil
from typing import Any

from vqetape.spec import ProgramConfig, TFIMVQESpec, dtype_bytes


@dataclass(frozen=True)
class StaticEstimate:
    parameter_count: int
    state_bytes: int
    saved_boundary_upper_bound_bytes: int
    estimated_forward_gate_applications: int
    estimated_recompute_gate_applications: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def estimate_program(
    spec: TFIMVQESpec,
    config: ProgramConfig,
) -> StaticEstimate:
    """Return conservative state/tape and gate-work estimates."""

    state_bytes = (1 << spec.nqubits) * dtype_bytes(spec.dtype)
    gates_per_layer = 2 * spec.nqubits - 1
    forward_gates = spec.depth * gates_per_layer

    if config.adjoint == "remat":
        saved_states = 3
        recompute_gates = forward_gates
    elif config.adjoint == "segmented":
        assert config.segment_length is not None
        saved_states = (
            ceil(spec.depth / config.segment_length)
            + config.segment_length
            + 2
        )
        recompute_gates = forward_gates
    else:
        saved_states = spec.depth + 1
        recompute_gates = 0

    return StaticEstimate(
        parameter_count=spec.active_parameter_count,
        state_bytes=state_bytes,
        saved_boundary_upper_bound_bytes=saved_states * state_bytes,
        estimated_forward_gate_applications=forward_gates,
        estimated_recompute_gate_applications=recompute_gates,
    )
