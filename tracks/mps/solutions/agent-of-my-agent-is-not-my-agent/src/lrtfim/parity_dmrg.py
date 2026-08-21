"""Parity-resolved DMRG in the rotated physical-X basis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from tenpy.algorithms import dmrg
from tenpy.models.model import MPOModel
from tenpy.networks.mps import MPS


@dataclass
class ParityStateResult:
    energy: float
    variance: float
    max_chi: int
    max_discarded_weight: float
    sector: str
    psi: MPS
    sweep_statistics: dict[str, Any]


@dataclass
class ParitySpectrumResult:
    ground: ParityStateResult
    excited: ParityStateResult

    @property
    def gap(self) -> float:
        return self.excited.energy - self.ground.energy


def _initial_state(model: MPOModel, sector: str) -> MPS:
    labels = ["up"] * model.lat.N_sites
    if sector == "odd":
        labels[model.lat.N_sites // 2] = "down"
    elif sector != "even":
        raise ValueError("sector must be 'even' or 'odd'")
    return MPS.from_product_state(model.lat.mps_sites(), labels, bc="finite")


def _run_sector(
    model: MPOModel,
    options: dict[str, Any],
    sector: str,
    initial_psi: MPS | None = None,
) -> ParityStateResult:
    psi = _initial_state(model, sector) if initial_psi is None else initial_psi.copy()
    validate_initial_state(model, psi, sector)
    info = dmrg.run(psi, model, dict(options))
    statistics = info["sweep_statistics"]
    discarded = statistics.get("max_trunc_err", [0.0])
    reached_chi = statistics.get("max_chi", [max(psi.chi)])
    variance = max(0.0, float(np.real_if_close(model.H_MPO.variance(psi))))
    return ParityStateResult(
        energy=float(info["E"]),
        variance=variance,
        max_chi=int(max(reached_chi)),
        max_discarded_weight=float(max(discarded)),
        sector=sector,
        psi=psi,
        sweep_statistics=statistics,
    )


def run_parity_spectrum(
    model: MPOModel,
    options: dict[str, Any],
    even_initial: MPS | None = None,
    odd_initial: MPS | None = None,
) -> ParitySpectrumResult:
    """Target the even ground state and lowest odd state independently."""
    if model.lat.mps_sites()[0].conserve != "parity":
        raise ValueError("model sites must conserve parity")
    return ParitySpectrumResult(
        ground=_run_sector(model, options, "even", even_initial),
        excited=_run_sector(model, options, "odd", odd_initial),
    )


def run_parity_ground(
    model: MPOModel,
    options: dict[str, Any],
    initial_psi: MPS | None = None,
) -> ParityStateResult:
    """Target only the even-sector ground state for a scan cell."""
    if model.lat.mps_sites()[0].conserve != "parity":
        raise ValueError("model sites must conserve parity")
    return _run_sector(model, options, "even", initial_psi)


def validate_initial_state(model: MPOModel, psi: MPS, sector: str) -> None:
    """Reject warm starts that change geometry, charge structure, or sector."""
    if sector not in {"even", "odd"}:
        raise ValueError("sector must be 'even' or 'odd'")
    if psi.L != model.lat.N_sites:
        raise ValueError(
            f"initial-state length mismatch: {psi.L} != {model.lat.N_sites}"
        )
    if psi.bc != "finite":
        raise ValueError("initial-state boundary condition must be finite")
    target_sites = model.lat.mps_sites()
    if any(
        source.conserve != target.conserve
        or source.leg.chinfo != target.leg.chinfo
        for source, target in zip(psi.sites, target_sites, strict=True)
    ):
        raise ValueError("initial-state site charge structure mismatch")
    charge = np.asarray(psi.get_total_charge(only_physical_legs=True), dtype=int)
    expected = 0 if sector == "even" else 1
    if len(charge) != 1 or int(charge[0]) % 2 != expected:
        raise ValueError(f"initial-state sector mismatch for {sector}")


def physical_correlations_rotated(psi: MPS) -> np.ndarray:
    """Return full periodic C(r) for physical Z, represented by Sigmax."""
    correlations = np.ones(psi.L, dtype=float)
    for distance in range(1, psi.L):
        values = [
            psi.expectation_value_term(
                [
                    ("Sigmax", origin),
                    ("Sigmax", (origin + distance) % psi.L),
                ]
            )
            for origin in range(psi.L)
        ]
        correlations[distance] = float(np.real(np.mean(values)))
    return correlations
