"""Registered nested model hierarchy for the joint two-mode audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .two_mode_nlfh import TwoModeParams


Array = np.ndarray
ModelName = Literal[
    "gaussian_diffusion",
    "scalar_surrogate",
    "independent_two_burgers",
    "coupled_two_mode",
]
MODEL_NAMES: tuple[ModelName, ...] = (
    "gaussian_diffusion",
    "scalar_surrogate",
    "independent_two_burgers",
    "coupled_two_mode",
)
PARAMETER_BOUNDS = {
    "Dm": (0.05, 10.0),
    "Dphi": (0.05, 10.0),
    "lambda_m": (-2.0, 2.0),
    "lambda_phi": (-2.0, 2.0),
    "alpha": (-10.0, 10.0),
}


@dataclass(frozen=True)
class ModelParameters:
    Dm: float
    Dphi: float
    lambda_m: float
    lambda_phi: float
    alpha: float

    def to_solver_params(self, *, chi: float = 0.25) -> TwoModeParams:
        return TwoModeParams(
            Dm=self.Dm,
            Dphi=self.Dphi,
            lambda_m=self.lambda_m,
            lambda_phi=self.lambda_phi,
            chi=chi,
        )


def free_parameter_names(name: ModelName) -> tuple[str, ...]:
    if name == "gaussian_diffusion":
        return ("Dm",)
    if name == "scalar_surrogate":
        return ("Dm", "lambda_m")
    if name == "independent_two_burgers":
        return ("Dm", "lambda_m")
    if name == "coupled_two_mode":
        return ("Dm", "Dphi", "lambda_m", "lambda_phi", "alpha")
    raise ValueError(f"unknown registered model {name}")


def parameters_for_model(name: ModelName, free: Array) -> ModelParameters:
    """Map a model's free vector onto the common five-parameter structure."""

    values = np.asarray(free, dtype=float)
    names = free_parameter_names(name)
    if values.shape != (len(names),) or np.any(~np.isfinite(values)):
        raise ValueError(f"{name} requires finite free vector {names}")
    for parameter, value in zip(names, values):
        low, high = PARAMETER_BOUNDS[parameter]
        if not low <= float(value) <= high:
            raise ValueError(f"{parameter} is outside its registered bounds")
    if name == "gaussian_diffusion":
        diffusion = float(values[0])
        return ModelParameters(diffusion, diffusion, 0.0, 0.0, 0.0)
    if name == "scalar_surrogate":
        diffusion, coupling = map(float, values)
        return ModelParameters(diffusion, diffusion, coupling, 0.0, 0.0)
    if name == "independent_two_burgers":
        diffusion, coupling = map(float, values)
        return ModelParameters(
            diffusion, diffusion, coupling, coupling, 0.0
        )
    if name == "coupled_two_mode":
        return ModelParameters(*map(float, values))
    raise ValueError(f"unknown registered model {name}")


def hidden_mode_initial_condition(m0: Array, alpha: float) -> Array:
    """Return the global spin-flip-even hidden-field initial condition."""

    m0 = np.asarray(m0, dtype=float)
    if m0.ndim != 1 or np.any(~np.isfinite(m0)) or not np.isfinite(alpha):
        raise ValueError("finite one-dimensional m0 and alpha are required")
    squared = m0**2
    return float(alpha) * (squared - np.mean(squared))


def initial_hidden_field(
    m0: Array,
    *,
    alpha: float,
    role: str,
) -> Array:
    """Force zero hidden response at equilibrium and retained linear order."""

    if role in {"two_mode_response", "two_mode_equilibrium"}:
        return np.zeros_like(np.asarray(m0, dtype=float))
    return hidden_mode_initial_condition(m0, alpha)
