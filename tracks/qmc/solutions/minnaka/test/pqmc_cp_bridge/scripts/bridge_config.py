#!/usr/bin/env python3
"""Immutable model and projection contract for the PQMC/CP bridge."""

from __future__ import annotations

from dataclasses import dataclass
import math


_THETA_CANDIDATES = (10, 12, 14, 16, 18, 20)
_ENERGY_TOLERANCE = 0.005


@dataclass(frozen=True)
class PhysicalConfig:
    lx: int
    ly: int
    hopping: float
    interaction: float
    n_up: int
    n_down: int
    dt: float
    beta: float
    exact_energy: float
    pbc_x: bool
    pbc_y: bool
    hs_transform: str


def approved_config() -> PhysicalConfig:
    return PhysicalConfig(
        lx=4,
        ly=4,
        hopping=1.0,
        interaction=4.0,
        n_up=8,
        n_down=8,
        dt=0.05,
        beta=1.0,
        exact_energy=-13.62192,
        pbc_x=True,
        pbc_y=True,
        hs_transform="binary_hirsch_spin",
    )


def theta_candidates() -> tuple[int, ...]:
    return _THETA_CANDIDATES


def validate_config(config: PhysicalConfig) -> None:
    if config.lx != 4 or config.ly != 4:
        raise ValueError("approved lattice is 4x4")
    if not config.pbc_x or not config.pbc_y:
        raise ValueError("both lattice directions must use PBC")
    nsites = config.lx * config.ly
    if config.n_up != nsites // 2 or config.n_down != nsites // 2:
        raise ValueError("approved sector is half-filled with N_up=N_down=8")
    if config.hopping != 1.0 or config.interaction != 4.0:
        raise ValueError("approved couplings are t=1 and U=4")
    if not math.isfinite(config.dt) or config.dt <= 0.0:
        raise ValueError("dt must be finite and positive")
    if not math.isfinite(config.beta) or config.beta <= 0.0:
        raise ValueError("beta must be finite and positive")
    if config.hs_transform != "binary_hirsch_spin":
        raise ValueError("approved HS transform is real binary Hirsch spin")


def ltrot(theta: float, config: PhysicalConfig) -> int:
    validate_config(config)
    raw = (2.0 * theta + config.beta) / config.dt
    rounded = round(raw)
    if abs(raw - rounded) >= 1.0e-12:
        raise ValueError("(2*theta+beta)/dt is not an integer")
    return int(rounded)


def energy_ok(energy: float, config: PhysicalConfig) -> bool:
    validate_config(config)
    if not math.isfinite(energy):
        return False
    difference = abs(energy - config.exact_energy)
    return difference < _ENERGY_TOLERANCE or math.isclose(
        difference, _ENERGY_TOLERANCE, rel_tol=0.0, abs_tol=1.0e-14
    )
