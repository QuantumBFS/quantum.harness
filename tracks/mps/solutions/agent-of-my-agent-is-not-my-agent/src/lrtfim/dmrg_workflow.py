"""Shared TeNPy DMRG workflow for the benchmark and long-range models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from tenpy.algorithms import dmrg
from tenpy.models.lattice import Chain
from tenpy.models.model import MPOModel
from tenpy.networks.mps import MPS
from tenpy.networks.mpo import MPO


@dataclass
class StateResult:
    """Numerical diagnostics for one targeted eigenstate."""

    energy: float
    variance: float
    max_chi: int
    max_discarded_weight: float
    psi: MPS
    sweep_statistics: dict[str, Any]


@dataclass
class SpectrumResult:
    """Ground and first-excited state result from a common DMRG protocol."""

    ground: StateResult
    excited: StateResult
    overlap: float

    @property
    def gap(self) -> float:
        return self.excited.energy - self.ground.energy


def build_mpo_model(mpo: MPO) -> MPOModel:
    """Wrap a validated finite MPO in the minimal TeNPy model interface."""
    lattice = Chain(mpo.L, mpo.sites[0], bc="open", bc_MPS="finite")
    return MPOModel(lattice, mpo)


def default_dmrg_options(chi_max: int = 128) -> dict[str, Any]:
    """Return the common two-site DMRG settings used by both TFIM models."""
    if chi_max < 2:
        raise ValueError("chi_max must be >= 2")
    return {
        "active_sites": 2,
        "mixer": True,
        "min_sweeps": 6,
        "max_sweeps": 30,
        "max_E_err": 1.0e-10,
        "max_S_err": 1.0e-8,
        "trunc_params": {
            "chi_max": int(chi_max),
            "svd_min": 1.0e-12,
        },
    }


def _product_state(model: MPOModel, direction: str) -> MPS:
    sites = model.lat.mps_sites()
    length = len(sites)
    if direction == "z":
        state: list[Any] = ["up"] * length
    elif direction == "x+":
        local = np.array([1.0, 1.0]) / np.sqrt(2.0)
        state = [local.copy() for _ in range(length)]
    elif direction == "x-":
        local = np.array([1.0, -1.0]) / np.sqrt(2.0)
        state = [local.copy() for _ in range(length)]
    else:
        raise ValueError(f"unknown product-state direction: {direction}")
    return MPS.from_product_state(sites, state, bc="finite")


def _run_state(
    model: MPOModel,
    psi: MPS,
    options: dict[str, Any],
    orthogonal_to: list[MPS] | None = None,
) -> StateResult:
    info = dmrg.run(
        psi,
        model,
        dict(options),
        orthogonal_to=orthogonal_to,
    )
    statistics = info["sweep_statistics"]
    discarded = statistics.get("max_trunc_err", [0.0])
    max_chi = statistics.get("max_chi", [max(psi.chi)])
    # Exact eigenstates can produce a tiny negative value from cancellation in
    # <H^2>-<H>^2; variance is non-negative by definition.
    variance = max(0.0, float(np.real_if_close(model.H_MPO.variance(psi))))
    return StateResult(
        energy=float(info["E"]),
        variance=variance,
        max_chi=int(max(max_chi)),
        max_discarded_weight=float(max(discarded)),
        psi=psi,
        sweep_statistics=statistics,
    )


def run_ground_and_first_excited(
    model: MPOModel,
    options: dict[str, Any] | None = None,
) -> SpectrumResult:
    """Target E0 and E1, validating E1 by explicit orthogonality to E0."""
    settings = default_dmrg_options() if options is None else dict(options)
    ground_candidates = [
        _run_state(model, _product_state(model, direction), settings)
        for direction in ("z", "x+")
    ]
    ground = min(ground_candidates, key=lambda result: result.energy)
    excited = _run_state(
        model,
        _product_state(model, "x-"),
        settings,
        orthogonal_to=[ground.psi],
    )
    overlap = float(abs(ground.psi.overlap(excited.psi)))
    return SpectrumResult(ground=ground, excited=excited, overlap=overlap)
