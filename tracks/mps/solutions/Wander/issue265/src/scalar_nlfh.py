"""Symmetry-sector scalar stochastic Burgers comparator.

The scalar comparator is not interpreted as a universal constitutive law for
physical magnetization.  Its orientation label is explicit, so the normalized
field coefficient obeys ``a_U = 2 * orientation * g * mu``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .two_mode_nlfh import (
    LazyNoisePanel,
    TwoModeNoisePanel,
    _lazy_trajectory_noise,
    lazy_noise_panel,
)

Array = np.ndarray


@dataclass(frozen=True)
class ScalarParams:
    D: float
    g: float
    chi: float = 0.25

    def __post_init__(self) -> None:
        values = np.asarray([self.D, self.g, self.chi], dtype=float)
        if np.any(~np.isfinite(values)):
            raise ValueError("scalar parameters must be finite")
        if self.D <= 0 or self.chi <= 0:
            raise ValueError("scalar D and chi must be positive")


@dataclass(frozen=True)
class ScalarTrajectory:
    t: Array
    m: Array
    current_output: Array
    current_origin: Array
    integrated_current_output: Array


@dataclass(frozen=True)
class ScalarEnsemble:
    t: Array
    mean_m: Array
    mean_current: Array
    cmm_origin: Array
    czz_center: Array
    integrated_current_time: Array
    current_cumulants_time: Array
    seed: int
    n_ensemble: int


def normalized_burgers_coefficient(
    *,
    g: float,
    mu: float,
    orientation: int,
) -> float:
    if mu <= 0 or orientation not in (-1, 1):
        raise ValueError("mu must be positive and orientation must be +/-1")
    return 2.0 * int(orientation) * float(g) * float(mu)


def _face_flux(
    m: Array,
    *,
    dx: float,
    dt: float,
    params: ScalarParams,
    orientation: int,
    noise: Array | None,
) -> Array:
    if orientation not in (-1, 1):
        raise ValueError("orientation must be +/-1")
    m = np.asarray(m, dtype=float)
    right = np.roll(m, -1, axis=-1)
    # Entropy-conservative face flux for j = orientation * g * m**2.
    flux = (
        int(orientation)
        * float(params.g)
        / 3.0
        * (m**2 + m * right + right**2)
    )
    flux -= params.D * (right - m) / float(dx)
    if noise is not None:
        noise = np.asarray(noise, dtype=float)
        if noise.shape != m.shape:
            raise ValueError("scalar face noise must match m")
        flux -= (
            np.sqrt(2.0 * params.D * params.chi)
            * noise
            / np.sqrt(float(dx) * float(dt))
        )
    return flux


def conservative_scalar_step(
    m: Array,
    *,
    dx: float,
    dt: float,
    params: ScalarParams,
    orientation: int,
    noise: Array | None,
) -> Array:
    if dx <= 0 or dt <= 0:
        raise ValueError("dx and dt must be positive")
    if dt > dx**2 / (2.0 * params.D):
        raise ValueError("dt violates the explicit diffusion stability limit")
    courant = float(
        dt / dx * np.max(2.0 * abs(params.g) * np.abs(m))
    )
    if not np.isfinite(courant) or courant > 0.9:
        raise ValueError("dt violates the explicit advective stability limit")
    flux = _face_flux(
        m,
        dx=dx,
        dt=dt,
        params=params,
        orientation=orientation,
        noise=noise,
    )
    return np.asarray(m, dtype=float) - dt / dx * (
        flux - np.roll(flux, 1, axis=-1)
    )


def _advance_scalar_from_flux(
    m: Array,
    *,
    flux: Array,
    dx: float,
    dt: float,
    params: ScalarParams,
) -> Array:
    """Advance from an already evaluated total current."""

    if dt > dx**2 / (2.0 * params.D):
        raise ValueError("dt violates the explicit diffusion stability limit")
    courant = float(
        dt / dx * np.max(2.0 * abs(params.g) * np.abs(m))
    )
    if not np.isfinite(courant) or courant > 0.9:
        raise ValueError("dt violates the explicit advective stability limit")
    return np.asarray(m, dtype=float) - dt / dx * (
        np.asarray(flux, dtype=float) - np.roll(flux, 1, axis=-1)
    )


def _deterministic_scalar_flux(
    flux: Array,
    *,
    noise: Array | None,
    dx: float,
    dt: float,
    params: ScalarParams,
) -> Array:
    """Remove the sampled white-noise current for observable prediction."""

    if noise is None:
        return np.asarray(flux, dtype=float)
    return np.asarray(flux, dtype=float) + (
        np.sqrt(2.0 * params.D * params.chi)
        * np.asarray(noise, dtype=float)
        / np.sqrt(float(dx) * float(dt))
    )


def simulate_scalar(
    *,
    x: Array,
    t: Array,
    m0: Array,
    params: ScalarParams,
    orientation: int,
    dt_internal: float,
    noise_faces: Array | None,
) -> ScalarTrajectory:
    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    m0 = np.asarray(m0, dtype=float)
    if x.ndim != 1 or t.ndim != 1 or m0.shape != x.shape:
        raise ValueError("scalar x,t,m0 shapes are incompatible")
    if x.size < 4 or t.size < 2 or np.any(np.diff(t) <= 0):
        raise ValueError("scalar grids are too small or not increasing")
    dx = float(x[1] - x[0])
    if not np.allclose(np.diff(x), dx):
        raise ValueError("scalar x grid must be uniform")
    positions = (t - t[0]) / float(dt_internal)
    steps = np.rint(positions).astype(int)
    if not np.allclose(positions, steps, atol=1e-10):
        raise ValueError("scalar output times must align with dt_internal")
    n_steps = int(steps[-1])
    if noise_faces is not None and np.asarray(noise_faces).shape != (
        n_steps,
        x.size,
    ):
        raise ValueError("scalar noise faces have the wrong shape")
    state = m0.copy()
    output_m = np.empty((t.size, x.size), dtype=float)
    output_current = np.empty_like(output_m)
    output_m[0] = state
    origin = int(np.argmin(np.abs(0.5 * (x[:-1] + x[1:]))))
    current_origin = np.empty(n_steps, dtype=float)
    integrated_output = np.zeros(t.size, dtype=float)
    cumulative = 0.0
    lookup = {int(step): index for index, step in enumerate(steps)}
    for step in range(n_steps):
        one_noise = (
            None
            if noise_faces is None
            else np.asarray(noise_faces[step], dtype=float)
        )
        flux = _face_flux(
            state,
            dx=dx,
            dt=dt_internal,
            params=params,
            orientation=orientation,
            noise=one_noise,
        )
        if step in lookup:
            output_current[lookup[step]] = _deterministic_scalar_flux(
                flux,
                noise=one_noise,
                dx=dx,
                dt=dt_internal,
                params=params,
            )
        current_origin[step] = float(flux[origin])
        cumulative += float(dt_internal) * current_origin[step]
        state = _advance_scalar_from_flux(
            state,
            flux=flux,
            dx=dx,
            dt=dt_internal,
            params=params,
        )
        completed = step + 1
        if completed in lookup:
            index = lookup[completed]
            output_m[index] = state
            integrated_output[index] = cumulative
    output_current[lookup[n_steps]] = _face_flux(
        state,
        dx=dx,
        dt=dt_internal,
        params=params,
        orientation=orientation,
        noise=None,
    )
    return ScalarTrajectory(
        t=t.copy(),
        m=output_m,
        current_output=output_current,
        current_origin=current_origin,
        integrated_current_output=integrated_output,
    )


def _cumulants_by_time(samples: Array) -> Array:
    mean = np.mean(samples, axis=0)
    centered = samples - mean[None, :]
    second = np.mean(centered**2, axis=0)
    return np.column_stack(
        [
            mean,
            second,
            np.mean(centered**3, axis=0),
            np.mean(centered**4, axis=0) - 3.0 * second**2,
        ]
    )


def simulate_scalar_ensemble(
    *,
    x: Array,
    t: Array,
    m0: Array,
    params: ScalarParams,
    orientation: int,
    dt_internal: float,
    n_ensemble: int,
    seed: int,
    equilibrium_fluctuations: bool = True,
    noise_panel: TwoModeNoisePanel | LazyNoisePanel | None = None,
) -> ScalarEnsemble:
    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    m0 = np.asarray(m0, dtype=float)
    positions = (t - t[0]) / float(dt_internal)
    steps = np.rint(positions).astype(int)
    if not np.allclose(positions, steps, atol=1e-10):
        raise ValueError("scalar output times must align with dt_internal")
    n_steps = int(steps[-1])
    if noise_panel is None:
        noise_panel = lazy_noise_panel(
            seed=seed,
            n_ensemble=n_ensemble,
            n_steps=n_steps,
            n_cells=x.size,
        )
    expected_initial = (n_ensemble, x.size)
    expected_faces = (n_ensemble, n_steps, x.size)
    if isinstance(noise_panel, LazyNoisePanel):
        if (
            noise_panel.n_ensemble != n_ensemble
            or noise_panel.n_steps != n_steps
            or noise_panel.n_cells != x.size
        ):
            raise ValueError("scalar lazy noise panel shape mismatch")
    elif (
        np.asarray(noise_panel.initial_m).shape != expected_initial
        or np.asarray(noise_panel.face_m).shape != expected_faces
    ):
        raise ValueError("scalar noise panel shape mismatch")
    dx = float(x[1] - x[0])
    fluctuation_scale = np.sqrt(params.chi / dx)
    if isinstance(noise_panel, LazyNoisePanel):
        rng = np.random.default_rng(int(noise_panel.seed))
        standard = noise_panel.spin_sign * rng.normal(
            size=(n_ensemble, x.size)
        )
        # Consume the phi initial panel so scalar and two-mode innovations
        # remain aligned under the common-random-number convention.
        rng.normal(size=(n_ensemble, x.size))
        if equilibrium_fluctuations:
            delta = standard * fluctuation_scale
            delta -= np.mean(delta, axis=1, keepdims=True)
        else:
            delta = np.zeros_like(standard)
        state = np.asarray(m0)[None, :] + delta
        origin_cell = int(np.argmin(np.abs(x)))
        origin_face = int(
            np.argmin(np.abs(0.5 * (x[:-1] + x[1:])))
        )
        reference = delta[:, origin_cell]
        mean_m = np.empty((t.size, x.size), dtype=float)
        mean_current = np.empty_like(mean_m)
        cmm = np.empty_like(mean_m)
        czz = np.empty_like(mean_m)
        integrated = np.zeros((n_ensemble, t.size), dtype=float)
        mean_m[0] = np.mean(state, axis=0)
        cmm[0] = np.mean(
            (state - mean_m[0][None, :]) * reference[:, None],
            axis=0,
        )
        centered_initial = state[:, origin_cell] - mean_m[0, origin_cell]
        czz[0] = np.mean(
            (state - mean_m[0][None, :]) * centered_initial[:, None],
            axis=0,
        )
        cumulative = np.zeros(n_ensemble, dtype=float)
        positions = (t - t[0]) / float(dt_internal)
        rounded = np.rint(positions).astype(int)
        lookup = {
            int(step): index for index, step in enumerate(rounded)
        }
        for step in range(n_steps):
            noise_m = noise_panel.spin_sign * rng.normal(
                size=(n_ensemble, x.size)
            )
            # Consume the unused phi face innovations for exact cross-model
            # stream alignment.
            rng.normal(size=(n_ensemble, x.size))
            flux = _face_flux(
                state,
                dx=dx,
                dt=dt_internal,
                params=params,
                orientation=orientation,
                noise=noise_m,
            )
            if step in lookup:
                deterministic = _deterministic_scalar_flux(
                    flux,
                    noise=noise_m,
                    dx=dx,
                    dt=dt_internal,
                    params=params,
                )
                mean_current[lookup[step]] = np.mean(
                    deterministic,
                    axis=0,
                )
            cumulative += dt_internal * flux[:, origin_face]
            state = _advance_scalar_from_flux(
                state,
                flux=flux,
                dx=dx,
                dt=dt_internal,
                params=params,
            )
            completed = step + 1
            if completed in lookup:
                index = lookup[completed]
                mean_m[index] = np.mean(state, axis=0)
                cmm[index] = np.mean(
                    (state - mean_m[index][None, :])
                    * reference[:, None],
                    axis=0,
                )
                centered_now = (
                    state[:, origin_cell] - mean_m[index, origin_cell]
                )
                czz[index] = np.mean(
                    (state - mean_m[index][None, :])
                    * centered_now[:, None],
                    axis=0,
                )
                integrated[:, index] = cumulative
        mean_current[lookup[n_steps]] = np.mean(
            _face_flux(
                state,
                dx=dx,
                dt=dt_internal,
                params=params,
                orientation=orientation,
                noise=None,
            ),
            axis=0,
        )
        return ScalarEnsemble(
            t=t.copy(),
            mean_m=mean_m,
            mean_current=mean_current,
            cmm_origin=cmm,
            czz_center=czz,
            integrated_current_time=integrated,
            current_cumulants_time=_cumulants_by_time(integrated),
            seed=int(noise_panel.seed),
            n_ensemble=n_ensemble,
        )
    sum_m = np.zeros((t.size, x.size), dtype=float)
    sum_current = np.zeros_like(sum_m)
    cross = np.zeros_like(sum_m)
    cross_center = np.zeros_like(sum_m)
    center_sum = np.zeros(t.size, dtype=float)
    reference_sum = 0.0
    integrated = np.empty((n_ensemble, t.size), dtype=float)
    origin = int(np.argmin(np.abs(x)))
    for ensemble_index in range(n_ensemble):
        if isinstance(noise_panel, LazyNoisePanel):
            (
                standard_initial,
                _,
                standard_faces,
                _,
            ) = _lazy_trajectory_noise(noise_panel, ensemble_index)
        else:
            standard_initial = np.asarray(
                noise_panel.initial_m[ensemble_index], dtype=float
            )
            standard_faces = np.asarray(
                noise_panel.face_m[ensemble_index], dtype=float
            )
        if equilibrium_fluctuations:
            delta = standard_initial * fluctuation_scale
            delta -= np.mean(delta)
        else:
            delta = np.zeros(x.size)
        reference = float(delta[origin])
        trajectory = simulate_scalar(
            x=x,
            t=t,
            m0=m0 + delta,
            params=params,
            orientation=orientation,
            dt_internal=dt_internal,
            noise_faces=standard_faces,
        )
        sum_m += trajectory.m
        sum_current += trajectory.current_output
        cross += trajectory.m * reference
        center_values = trajectory.m[:, origin]
        cross_center += trajectory.m * center_values[:, None]
        center_sum += center_values
        reference_sum += reference
        integrated[ensemble_index] = trajectory.integrated_current_output
    mean_m = sum_m / float(n_ensemble)
    return ScalarEnsemble(
        t=t.copy(),
        mean_m=mean_m,
        mean_current=sum_current / float(n_ensemble),
        cmm_origin=(
            cross / float(n_ensemble)
            - mean_m * reference_sum / float(n_ensemble)
        ),
        czz_center=(
            cross_center / float(n_ensemble)
            - mean_m * (center_sum / float(n_ensemble))[:, None]
        ),
        integrated_current_time=integrated,
        current_cumulants_time=_cumulants_by_time(integrated),
        seed=int(noise_panel.seed),
        n_ensemble=int(n_ensemble),
    )


def scalar_transfer_logz(ensemble: ScalarEnsemble, gamma: Array) -> Array:
    gamma = np.asarray(gamma, dtype=float)
    if (
        gamma.ndim != 1
        or not np.allclose(gamma, -gamma[::-1], rtol=0.0, atol=1e-13)
        or not np.any(np.isclose(gamma, 0.0, rtol=0.0, atol=1e-13))
    ):
        raise ValueError("gamma must be symmetric and contain zero")
    samples = np.asarray(ensemble.integrated_current_time)
    characteristic = np.mean(
        np.exp(1j * samples[:, :, None] * gamma[None, None, :]),
        axis=0,
    )
    if np.any(np.abs(characteristic) < 1e-14):
        raise ValueError("empirical characteristic function crosses zero")
    logz = np.log(characteristic)
    phase = np.unwrap(logz.imag, axis=0)
    zero = int(np.argmin(np.abs(gamma)))
    phase -= phase[:, zero, None]
    result = logz.real + 1j * phase
    for index, value in enumerate(gamma):
        if value < -1e-13:
            partner = int(np.argmin(np.abs(gamma + value)))
            result[:, index] = np.conj(result[:, partner])
    result[:, zero] = 0.0
    return result
