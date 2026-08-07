"""Explicit common-bath normalization and counterterm model variants."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .config import BathConfig, ModelConfig, Normalization
from .models import coupling_operator, ising_hamiltonian
from .operators import ComplexMatrix


@dataclass(frozen=True)
class ModelVariant:
    name: str
    config: ModelConfig
    metadata: dict[str, Any]


def _variant(
    *,
    name: str,
    n: int,
    j: float,
    omega: float,
    drive_amplitude: float,
    drive_frequency: float,
    normalization: Normalization,
    counterterm: bool,
    bath: BathConfig,
) -> ModelVariant:
    strength = bath.alpha * bath.cutoff if counterterm else 0.0
    config = ModelConfig(
        n=n,
        j=j,
        omega=omega,
        drive_amplitude=drive_amplitude,
        drive_frequency=drive_frequency,
        normalization=normalization,
        counterterm=counterterm,
        counterterm_strength=strength,
    )
    return ModelVariant(
        name,
        config,
        {
            "normalization": normalization,
            "eta": config.eta,
            "counterterm": counterterm,
            "counterterm_strength": strength,
            "bath": asdict(bath),
        },
    )


def model_variants(
    *,
    n: int,
    j: float,
    bath: BathConfig,
    omega: float = 1.0,
    drive_amplitude: float = 0.2,
    drive_frequency: float = 1.0,
) -> tuple[ModelVariant, ...]:
    """Return the four predeclared bounded/Kac and counterterm choices."""
    return tuple(
        _variant(
            name=f"{normalization}_{'ct' if counterterm else 'no_ct'}",
            n=n,
            j=j,
            omega=omega,
            drive_amplitude=drive_amplitude,
            drive_frequency=drive_frequency,
            normalization=normalization,
            counterterm=counterterm,
            bath=bath,
        )
        for normalization in ("bounded", "kac")
        for counterterm in (False, True)
    )


def variant_operators(variant: ModelVariant) -> tuple[ComplexMatrix, ComplexMatrix]:
    return ising_hamiltonian(variant.config), coupling_operator(variant.config)


def diagnostic_heat_rescaling(
    heat: NDArray[np.float64], eta: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return raw heat and a separately labeled eta-squared diagnostic."""
    if eta <= 0:
        raise ValueError("eta must be positive")
    raw = np.array(heat, dtype=np.float64, copy=True)
    return raw, raw / eta**2
