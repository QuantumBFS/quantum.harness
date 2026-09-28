"""Registered stochastic forward operator for the joint observable panel."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from .scalar_nlfh import (
    ScalarParams,
    scalar_transfer_logz,
    simulate_scalar_ensemble,
)
from .two_mode_models import (
    ModelName,
    ModelParameters,
    initial_hidden_field,
)
from .two_mode_nlfh import (
    LazyNoisePanel,
    TwoModeNoisePanel,
    ensemble_transfer_logz,
    lazy_noise_panel,
    simulate_two_mode_ensemble,
)
from .two_mode_observables import (
    EQUILIBRIUM,
    PULSE_NEG,
    PULSE_POS,
    JointObservablePanel,
)

Array = np.ndarray


@dataclass(frozen=True)
class ForwardFidelity:
    spatial_stride: int
    dt_internal: float
    n_ensemble: int
    seed: int

    def __post_init__(self) -> None:
        if (
            self.spatial_stride < 1
            or self.dt_internal <= 0
            or self.n_ensemble < 2
        ):
            raise ValueError("invalid forward-model fidelity")


def fidelity_from_rules(
    rules: Mapping[str, Any],
    *,
    final: bool = False,
) -> ForwardFidelity:
    raw = rules["forward_model"]
    prefix = "final" if final else "screening"
    return ForwardFidelity(
        spatial_stride=int(
            raw.get(f"{prefix}_spatial_stride", raw.get("spatial_stride"))
        ),
        dt_internal=float(
            raw.get(f"{prefix}_dt_internal", raw.get("dt_internal"))
        ),
        n_ensemble=int(
            raw["final_ensemble"] if final else raw["screening_ensemble"]
        ),
        seed=int(raw["seed"]),
    )


def _block_average(values: Array, stride: int) -> Array:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or values.size % stride:
        raise ValueError("spatial grid size must be divisible by spatial_stride")
    return values.reshape(values.size // stride, stride).mean(axis=1)


def _coarse_grid(x: Array, stride: int) -> Array:
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or x.size % stride:
        raise ValueError("simulation x grid is incompatible with spatial_stride")
    if not np.allclose(np.diff(x), np.diff(x)[0]):
        raise ValueError("simulation x grid must be uniform")
    return _block_average(x, stride)


def _transformed_noise(
    base: TwoModeNoisePanel | LazyNoisePanel,
    *,
    spin_sign: int,
) -> TwoModeNoisePanel | LazyNoisePanel:
    if spin_sign not in (-1, 1):
        raise ValueError("spin_sign must be +/-1")
    if isinstance(base, LazyNoisePanel):
        return LazyNoisePanel(
            seed=base.seed,
            n_ensemble=base.n_ensemble,
            n_steps=base.n_steps,
            n_cells=base.n_cells,
            spin_sign=spin_sign,
        )
    return TwoModeNoisePanel(
        initial_m=spin_sign * np.asarray(base.initial_m),
        initial_phi=np.asarray(base.initial_phi),
        face_m=spin_sign * np.asarray(base.face_m),
        face_phi=np.asarray(base.face_phi),
        seed=int(base.seed),
    )


def _interpolate_profiles(
    coarse_x: Array,
    values: Array,
    target_x: Array,
) -> Array:
    return np.stack(
        [np.interp(target_x, coarse_x, row) for row in np.asarray(values)]
    )


def _interpolate_currents(
    coarse_x: Array,
    values: Array,
    target_x: Array,
) -> Array:
    coarse_faces = 0.5 * (coarse_x[:-1] + coarse_x[1:])
    return np.stack(
        [
            np.interp(target_x, coarse_faces, row[:-1])
            for row in np.asarray(values)
        ]
    )


class RegisteredForwardPredictor:
    """Map registered parameters to every block using one frozen noise panel."""

    def __init__(self, fidelity: ForwardFidelity):
        self.fidelity = fidelity
        self._noise_cache: dict[
            tuple[int, int], TwoModeNoisePanel | LazyNoisePanel
        ] = {}

    def _noise(
        self,
        *,
        n_steps: int,
        n_cells: int,
        supplied: Any,
    ) -> TwoModeNoisePanel | LazyNoisePanel:
        if isinstance(supplied, (TwoModeNoisePanel, LazyNoisePanel)):
            return supplied
        key = (n_steps, n_cells)
        if key not in self._noise_cache:
            self._noise_cache[key] = lazy_noise_panel(
                seed=self.fidelity.seed,
                n_ensemble=self.fidelity.n_ensemble,
                n_steps=n_steps,
                n_cells=n_cells,
            )
        return self._noise_cache[key]

    def __call__(
        self,
        name: ModelName,
        parameters: ModelParameters,
        panel: JointObservablePanel,
        noise_panel: Any,
    ) -> Mapping[str, Array]:
        if panel.simulation_x is None or panel.profile_mask is None:
            simulation_x = np.asarray(panel.x, dtype=float)
            profile_target_x = simulation_x
        else:
            simulation_x = np.asarray(panel.simulation_x, dtype=float)
            profile_target_x = simulation_x[
                np.asarray(panel.profile_mask, dtype=bool)
            ]
        coarse_x = _coarse_grid(
            simulation_x, self.fidelity.spatial_stride
        )
        positions = (panel.t - panel.t[0]) / self.fidelity.dt_internal
        rounded = np.rint(positions).astype(int)
        if (
            not np.isclose(float(panel.t[0]), 0.0)
            or not np.allclose(positions, rounded, atol=1e-10)
        ):
            raise ValueError("forward panel times must start at zero and align")
        base_noise = self._noise(
            n_steps=int(rounded[-1]),
            n_cells=coarse_x.size,
            supplied=noise_panel,
        )

        predicted_u: dict[str, Array] = {}
        predicted_m: dict[str, Array] = {}
        predicted_current: dict[str, Array] = {}
        predicted_czz: dict[str, Array] = {}
        predicted_logz: dict[str, Array] = {}
        for condition_id in sorted(panel.profile):
            metadata = dict(panel.metadata.get(condition_id, {}))
            orientation = int(metadata.get("orientation", 1))
            if orientation not in (-1, 1):
                raise ValueError(f"missing orientation for {condition_id}")
            role = str(metadata.get("role", ""))
            if not role:
                if condition_id in {PULSE_POS, PULSE_NEG}:
                    role = "two_mode_response"
                elif condition_id == EQUILIBRIUM:
                    role = "two_mode_equilibrium"
                else:
                    role = "primary_amplitude"
            mu = float(metadata.get("mu", 0.0))
            if mu <= 0:
                raise ValueError(f"missing positive mu for {condition_id}")
            background = float(metadata.get("background_m", 0.0))
            if condition_id not in panel.physical_initial:
                raise ValueError(f"missing physical initial state for {condition_id}")
            m0 = _block_average(
                panel.physical_initial[condition_id],
                self.fidelity.spatial_stride,
            )
            condition_noise = _transformed_noise(
                base_noise,
                spin_sign=orientation,
            )
            if name in {"gaussian_diffusion", "scalar_surrogate"}:
                scalar = ScalarParams(
                    D=parameters.Dm,
                    g=(
                        0.0
                        if name == "gaussian_diffusion"
                        else parameters.lambda_m
                    ),
                    chi=0.25,
                )
                ensemble = simulate_scalar_ensemble(
                    x=coarse_x,
                    t=panel.t,
                    # This comparator is a sector law for the deviation from
                    # the condition's background:
                    # j = sigma*g*(m-m_bg)^2.  Consequently the normalized
                    # field U=(m-m_bg)/mu has a_U=2*sigma*g*mu.
                    m0=m0 - background,
                    params=scalar,
                    orientation=orientation,
                    dt_internal=self.fidelity.dt_internal,
                    n_ensemble=self.fidelity.n_ensemble,
                    seed=self.fidelity.seed,
                    noise_panel=condition_noise,
                )
                mean_m = ensemble.mean_m + background
                mean_current = ensemble.mean_current
                czz_center = ensemble.czz_center
                logz = (
                    scalar_transfer_logz(
                        ensemble, panel.fcs_gamma[condition_id]
                    )
                    if condition_id in panel.fcs_logz
                    else None
                )
            else:
                phi0 = initial_hidden_field(
                    m0,
                    alpha=parameters.alpha,
                    role=role,
                )
                ensemble = simulate_two_mode_ensemble(
                    x=coarse_x,
                    t=panel.t,
                    m0=m0,
                    phi0=phi0,
                    params=parameters.to_solver_params(chi=0.25),
                    dt_internal=self.fidelity.dt_internal,
                    n_ensemble=self.fidelity.n_ensemble,
                    seed=self.fidelity.seed,
                    noise_panel=condition_noise,
                )
                mean_m = ensemble.mean_m
                mean_current = ensemble.mean_jm
                czz_center = ensemble.czz_center
                logz = (
                    ensemble_transfer_logz(
                        ensemble, panel.fcs_gamma[condition_id], mode="m"
                    )
                    if condition_id in panel.fcs_logz
                    else None
                )
            physical = _interpolate_profiles(
                coarse_x, mean_m, profile_target_x
            )
            predicted_m[condition_id] = physical
            predicted_u[condition_id] = (physical - background) / mu
            if condition_id in panel.current:
                if (
                    panel.simulation_x is not None
                    and condition_id in panel.current_masks
                ):
                    full_bonds = 0.5 * (
                        simulation_x[:-1] + simulation_x[1:]
                    )
                    current_target = full_bonds[
                        np.asarray(
                            panel.current_masks[condition_id], dtype=bool
                        )
                    ]
                elif panel.current[condition_id].shape[1] == panel.x.size - 1:
                    current_target = 0.5 * (panel.x[:-1] + panel.x[1:])
                else:
                    current_target = panel.x
                predicted_current[condition_id] = _interpolate_currents(
                    coarse_x, mean_current, current_target
                )
            if condition_id in panel.czz:
                predicted_czz[condition_id] = _interpolate_profiles(
                    coarse_x,
                    czz_center,
                    profile_target_x,
                )
            if logz is not None:
                predicted_logz[condition_id] = logz

        result: dict[str, Array] = {}
        for condition_id, values in predicted_u.items():
            result[f"profile:{condition_id}"] = values
        for condition_id, values in predicted_current.items():
            result[f"current:{condition_id}"] = values
        for condition_id, values in predicted_czz.items():
            result[f"czz:{condition_id}"] = values
        if panel.response_cmm or panel.response_cjm:
            if not {PULSE_POS, PULSE_NEG} <= set(predicted_m):
                raise ValueError(
                    "registered response blocks require the complete pulse pair"
                )
            epsilon = float(panel.metadata[PULSE_POS]["mu"])
            response_cmm = (
                predicted_m[PULSE_POS] - predicted_m[PULSE_NEG]
            ) / (2.0 * epsilon)
            for key in panel.response_cmm:
                result[f"response_cmm:{key}"] = response_cmm
            if panel.response_cjm:
                if not {PULSE_POS, PULSE_NEG} <= set(predicted_current):
                    raise ValueError(
                        "registered current response requires pulse currents"
                    )
                response_cjm = (
                    predicted_current[PULSE_POS]
                    - predicted_current[PULSE_NEG]
                ) / (2.0 * epsilon)
                for key in panel.response_cjm:
                    result[f"response_cjm:{key}"] = response_cjm
        for condition_id, values in predicted_logz.items():
            result[f"fcs_logz:{condition_id}"] = values
        return result
