"""Staged bond-dimension growth with checkpointed parity-sector states."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import time
from typing import Any, Sequence

from tenpy.models.model import MPOModel
from tenpy.networks.mps import MPS

from .checkpoints import CheckpointProvenance, save_checkpoint
from .parity_dmrg import ParityStateResult, _run_sector


@dataclass(frozen=True)
class StageResult:
    requested_chi: int
    reached_chi: int
    energy: float
    variance: float
    discarded_weight: float
    sweeps: int
    wall_seconds: float
    checkpoint_path: str | None


@dataclass
class StagedStateResult:
    final: ParityStateResult
    stages: list[StageResult]


def _validate_schedule(chi_schedule: Sequence[int]) -> tuple[int, ...]:
    schedule = tuple(int(chi) for chi in chi_schedule)
    if (
        not schedule
        or schedule[-1] != 128
        or any(chi < 2 for chi in schedule)
        or any(right <= left for left, right in zip(schedule, schedule[1:]))
    ):
        raise ValueError(
            "chi schedule must be strictly increasing, positive, and end at 128"
        )
    return schedule


def run_staged_sector(
    model: MPOModel,
    sector: str,
    chi_schedule: Sequence[int],
    base_options: dict[str, Any],
    *,
    initial_psi: MPS | None = None,
    checkpoint_root: Path | None = None,
    provenance: CheckpointProvenance | None = None,
) -> StagedStateResult:
    """Run one parity sector through an increasing chi schedule."""
    schedule = _validate_schedule(chi_schedule)
    if checkpoint_root is not None and provenance is None:
        raise ValueError("checkpoint_root requires provenance")
    current = initial_psi
    stages = []
    final = None
    for chi in schedule:
        options = dict(base_options)
        options["trunc_params"] = dict(base_options.get("trunc_params", {}))
        options["trunc_params"]["chi_max"] = chi
        started = time.perf_counter()
        state = _run_sector(model, options, sector, current)
        elapsed = time.perf_counter() - started
        sweeps = int(state.sweep_statistics.get("sweep", [0])[-1])
        checkpoint_path = None
        if checkpoint_root is not None:
            checkpoint_directory = Path(checkpoint_root) / f"chi{chi}"
            stage_provenance = replace(
                provenance,
                requested_chi=chi,
                reached_chi=state.max_chi,
                sweep_statistics=state.sweep_statistics,
            )
            save_checkpoint(
                checkpoint_directory,
                state.psi,
                stage_provenance,
                {
                    "energy": state.energy,
                    "variance": state.variance,
                    "discarded_weight": state.max_discarded_weight,
                    "wall_seconds": elapsed,
                    "sweeps": sweeps,
                },
            )
            checkpoint_path = str(checkpoint_directory)
        stages.append(
            StageResult(
                requested_chi=chi,
                reached_chi=state.max_chi,
                energy=state.energy,
                variance=state.variance,
                discarded_weight=state.max_discarded_weight,
                sweeps=sweeps,
                wall_seconds=elapsed,
                checkpoint_path=checkpoint_path,
            )
        )
        current = state.psi
        final = state
    assert final is not None
    return StagedStateResult(final=final, stages=stages)
