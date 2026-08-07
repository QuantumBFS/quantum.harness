#!/usr/bin/env python3
"""Parse MATLAB v7 CPMC outputs using independent runs as error units."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy.io import loadmat

from cpmc_config import CpmcContract


@dataclass(frozen=True)
class RunEstimate:
    run_id: str
    seed: int
    energy: float
    terminal_weight: float
    strata_mass: dict[str, float]
    blocks: tuple[float, ...] = ()


@dataclass(frozen=True)
class Estimate:
    mean: float
    sigma_block: float
    sigma_run: float
    sigma: float
    independent_runs: int


def _scalar(data: dict, key: str):
    if key not in data:
        raise ValueError(f"CPMC output lacks {key}")
    value = np.asarray(data[key]).squeeze()
    if value.size != 1:
        raise ValueError(f"CPMC scalar {key} has wrong shape")
    return value.item()


def _text(data: dict, key: str) -> str:
    value = _scalar(data, key)
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def load_cpmc_run(path: Path, contract: CpmcContract) -> RunEstimate:
    data = loadmat(path, squeeze_me=True)
    if int(_scalar(data, "schema_version")) != 1:
        raise ValueError("unsupported CPMC result schema")
    mode = _text(data, "mode")
    if mode not in {"fixed_horizon", "proposal_only", "production"}:
        raise ValueError(f"unknown CPMC mode: {mode}")
    if int(_scalar(data, "ltrot")) != contract.ltrot:
        raise ValueError("CPMC Ltrot mismatch")
    selected_hash = _text(
        data, "contract_selected_projection_sha256"
    )
    if selected_hash != contract.input_sha256["selected_projection"]:
        raise ValueError("CPMC selected projection hash mismatch")
    weights = np.atleast_1d(
        np.asarray(data["terminal_weights_pre_pc"], dtype=float).squeeze()
    )
    energies = np.atleast_1d(
        np.asarray(data["terminal_energies"], dtype=float).squeeze()
    )
    if weights.shape != energies.shape or weights.size == 0:
        raise ValueError("terminal weights/energies have incompatible shapes")
    if not np.all(np.isfinite(weights)) or not np.all(np.isfinite(energies)):
        raise ValueError("non-finite terminal CPMC data")
    total_weight = math.fsum(float(value) for value in weights)
    if total_weight <= 0.0:
        raise ValueError("terminal CPMC weight vanishes")
    energy = math.fsum(
        float(weight * value) for weight, value in zip(weights, energies)
    ) / total_weight
    names_raw = np.atleast_1d(data.get("strata_names", np.array([])))
    mass_raw = np.atleast_1d(
        np.asarray(data.get("strata_mass", np.array([])), dtype=float)
    )
    names = [
        item.decode() if isinstance(item, bytes) else str(item)
        for item in names_raw.flat
    ]
    if len(names) != mass_raw.size:
        raise ValueError("strata names/masses have incompatible shapes")
    blocks = tuple(
        float(value)
        for value in np.atleast_1d(
            np.asarray(data.get("block_energies", np.array([])), dtype=float)
        ).flat
        if np.isfinite(value)
    )
    if mode == "production":
        if not blocks:
            raise ValueError("production CPMC output has no block energies")
        energy = math.fsum(blocks) / len(blocks)
    return RunEstimate(
        run_id=_text(data, "run_id"),
        seed=int(_scalar(data, "seed")),
        energy=energy,
        terminal_weight=total_weight,
        strata_mass={
            name: float(value) for name, value in zip(names, mass_raw.flat)
        },
        blocks=blocks,
    )


def _jackknife_error(values: Sequence[float]) -> float:
    if len(values) < 2:
        return math.inf
    total = math.fsum(values)
    leave = [
        (total - value) / (len(values) - 1) for value in values
    ]
    center = math.fsum(leave) / len(leave)
    return math.sqrt(
        (len(leave) - 1) / len(leave)
        * math.fsum((value - center) ** 2 for value in leave)
    )


def block_and_run_error(
    blocks_by_run: Sequence[Sequence[float]]
) -> float:
    if not blocks_by_run:
        return math.inf
    errors = []
    block_size = 1
    maximum = max((len(run) for run in blocks_by_run), default=0)
    while block_size <= maximum:
        blocks = []
        per_run_counts = []
        for run in blocks_by_run:
            count_before = len(blocks)
            for start in range(0, len(run) - block_size + 1, block_size):
                blocks.append(
                    math.fsum(run[start:start + block_size]) / block_size
                )
            per_run_counts.append(len(blocks) - count_before)
        participating = [count for count in per_run_counts if count > 0]
        if (
            len(blocks) >= 4
            and len(participating) == len(blocks_by_run)
            and min(participating) >= 2
        ):
            errors.append(_jackknife_error(blocks))
        block_size *= 2
    return max(errors) if errors else math.inf


def independent_run_estimate(runs: Sequence[RunEstimate]) -> Estimate:
    if len(runs) < 2:
        raise ValueError("at least two independent CPMC runs are required")
    ids = [run.run_id for run in runs]
    seeds = [run.seed for run in runs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate CPMC run_id")
    if len(seeds) != len(set(seeds)):
        raise ValueError("duplicate independent-run seed")
    energies = [run.energy for run in runs]
    mean = math.fsum(energies) / len(energies)
    sigma_run = _jackknife_error(energies)
    sigma_block = (
        block_and_run_error([run.blocks for run in runs])
        if any(run.blocks for run in runs)
        else 0.0
    )
    sigma = max(sigma_block, sigma_run)
    return Estimate(
        mean=mean,
        sigma_block=sigma_block,
        sigma_run=sigma_run,
        sigma=sigma,
        independent_runs=len(runs),
    )
