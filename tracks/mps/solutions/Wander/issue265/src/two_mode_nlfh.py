"""Conservative stochastic solver for the two-mode Heisenberg NLFH model."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

Array = np.ndarray


@dataclass(frozen=True)
class TwoModeParams:
    Dm: float
    Dphi: float
    lambda_m: float
    lambda_phi: float
    chi: float = 0.25

    def __post_init__(self) -> None:
        values = np.asarray(
            [self.Dm, self.Dphi, self.lambda_m, self.lambda_phi, self.chi],
            dtype=float,
        )
        if np.any(~np.isfinite(values)):
            raise ValueError("Two-mode parameters must be finite")
        if self.Dm <= 0 or self.Dphi <= 0 or self.chi <= 0:
            raise ValueError("Diffusions and chi must be positive")


@dataclass(frozen=True)
class TwoModeNoiseFaces:
    m: Array
    phi: Array


@dataclass(frozen=True)
class TwoModeNoisePanel:
    initial_m: Array
    initial_phi: Array
    face_m: Array
    face_phi: Array
    seed: int


@dataclass(frozen=True)
class LazyNoisePanel:
    seed: int
    n_ensemble: int
    n_steps: int
    n_cells: int
    spin_sign: int = 1

    def __post_init__(self) -> None:
        if (
            self.n_ensemble < 2
            or self.n_steps < 1
            or self.n_cells < 4
            or self.spin_sign not in (-1, 1)
        ):
            raise ValueError("invalid lazy noise-panel specification")


@dataclass(frozen=True)
class TwoModeState:
    m: Array
    phi: Array


@dataclass(frozen=True)
class TwoModeTrajectory:
    t: Array
    m: Array
    phi: Array
    jm_output: Array
    jphi_output: Array
    jm_origin: Array
    jphi_origin: Array
    integrated_jm_output: Array
    integrated_jphi_output: Array


@dataclass(frozen=True)
class TwoModeEnsemble:
    t: Array
    mean_m: Array
    mean_phi: Array
    mean_jm: Array
    mean_jphi: Array
    cmm_origin: Array
    czz_center: Array
    integrated_jm: Array
    integrated_jphi: Array
    integrated_jm_time: Array
    integrated_jphi_time: Array
    jm_cumulants: Array
    jphi_cumulants: Array
    jm_cumulants_time: Array
    jphi_cumulants_time: Array
    seed: int
    n_ensemble: int


def two_mode_flux(
    m: Array,
    phi: Array,
    *,
    lambda_m: float,
    lambda_phi: float,
) -> tuple[Array, Array]:
    """Evaluate the symmetry-allowed two-mode Euler currents."""

    m = np.asarray(m, dtype=float)
    phi = np.asarray(phi, dtype=float)
    if m.shape != phi.shape:
        raise ValueError("m and phi must have equal shape")
    jm = float(lambda_m) * m * phi
    jphi = 0.5 * float(lambda_m) * m**2 + 0.5 * float(lambda_phi) * phi**2
    return jm, jphi


def _entropy_conservative_burgers_face(
    left: Array,
    right: Array,
    coupling: float,
) -> Array:
    """Symmetric three-point flux for ``coupling*q**2/2``."""

    return (
        float(coupling)
        / 6.0
        * (left**2 + left * right + right**2)
    )


def _euler_face_fluxes(
    m: Array,
    phi: Array,
    params: TwoModeParams,
) -> tuple[Array, Array]:
    m_right = np.roll(m, -1, axis=-1)
    phi_right = np.roll(phi, -1, axis=-1)
    if np.isclose(params.lambda_m, params.lambda_phi, rtol=0.0, atol=1e-15):
        coupling = float(params.lambda_m)
        up_left, up_right = m + phi, m_right + phi_right
        um_left, um_right = m - phi, m_right - phi_right
        f_plus = _entropy_conservative_burgers_face(
            up_left, up_right, coupling
        )
        f_minus = _entropy_conservative_burgers_face(
            um_left, um_right, -coupling
        )
        return 0.5 * (f_plus + f_minus), 0.5 * (f_plus - f_minus)

    # Off the diagonal fixed-point manifold there is no unique invariant
    # split form.  Centered face evaluation preserves the exact parities and
    # conservation; refinement is therefore required before data comparison.
    m_face = 0.5 * (m + m_right)
    phi_face = 0.5 * (phi + phi_right)
    return two_mode_flux(
        m_face,
        phi_face,
        lambda_m=params.lambda_m,
        lambda_phi=params.lambda_phi,
    )


def _total_face_fluxes(
    state: TwoModeState,
    *,
    dx: float,
    dt: float,
    params: TwoModeParams,
    noise_faces: TwoModeNoiseFaces | None,
) -> tuple[Array, Array]:
    m = np.asarray(state.m, dtype=float)
    phi = np.asarray(state.phi, dtype=float)
    if m.shape != phi.shape or m.ndim < 1:
        raise ValueError("state fields must have equal non-scalar shape")
    jm, jphi = _euler_face_fluxes(m, phi, params)
    jm = jm - params.Dm * (np.roll(m, -1, axis=-1) - m) / dx
    jphi = (
        jphi
        - params.Dphi * (np.roll(phi, -1, axis=-1) - phi) / dx
    )
    if noise_faces is not None:
        noise_m = np.asarray(noise_faces.m, dtype=float)
        noise_phi = np.asarray(noise_faces.phi, dtype=float)
        if noise_m.shape != m.shape or noise_phi.shape != phi.shape:
            raise ValueError("One-step face noise must match the state shape")
        normalization = np.sqrt(dx * dt)
        jm = jm - np.sqrt(2.0 * params.Dm * params.chi) * noise_m / normalization
        jphi = (
            jphi
            - np.sqrt(2.0 * params.Dphi * params.chi)
            * noise_phi
            / normalization
        )
    return jm, jphi


def _validate_two_mode_stability(
    state: TwoModeState,
    *,
    dx: float,
    dt: float,
    params: TwoModeParams,
) -> None:
    """Reject diffusion or advective CFL violations before an explicit step."""

    diffusion_limit = dx**2 / (2.0 * max(params.Dm, params.Dphi))
    if dt > diffusion_limit:
        raise ValueError("dt violates the explicit diffusion stability limit")
    m = np.asarray(state.m, dtype=float)
    phi = np.asarray(state.phi, dtype=float)
    # Gershgorin bound for the spectral radius of
    # [[lambda_m*phi, lambda_m*m], [lambda_m*m, lambda_phi*phi]].
    speed_bound = np.maximum(
        abs(params.lambda_m) * (np.abs(phi) + np.abs(m)),
        abs(params.lambda_phi) * np.abs(phi)
        + abs(params.lambda_m) * np.abs(m),
    )
    courant = float(dt / dx * np.max(speed_bound))
    if not np.isfinite(courant) or courant > 0.9:
        raise ValueError("dt violates the explicit advective stability limit")


def _advance_two_mode_from_fluxes(
    state: TwoModeState,
    *,
    jm: Array,
    jphi: Array,
    dx: float,
    dt: float,
    params: TwoModeParams,
) -> TwoModeState:
    """Advance from already evaluated face fluxes without recomputing them."""

    _validate_two_mode_stability(
        state,
        dx=float(dx),
        dt=float(dt),
        params=params,
    )
    updated_m = np.asarray(state.m, dtype=float) - dt / dx * (
        np.asarray(jm, dtype=float) - np.roll(jm, 1, axis=-1)
    )
    updated_phi = np.asarray(state.phi, dtype=float) - dt / dx * (
        np.asarray(jphi, dtype=float) - np.roll(jphi, 1, axis=-1)
    )
    return TwoModeState(m=updated_m, phi=updated_phi)


def _deterministic_fluxes_from_total(
    jm: Array,
    jphi: Array,
    *,
    noise_faces: TwoModeNoiseFaces | None,
    dx: float,
    dt: float,
    params: TwoModeParams,
) -> tuple[Array, Array]:
    """Remove the sampled white-noise current for observable prediction."""

    if noise_faces is None:
        return np.asarray(jm, dtype=float), np.asarray(jphi, dtype=float)
    normalization = np.sqrt(float(dx) * float(dt))
    deterministic_jm = np.asarray(jm, dtype=float) + (
        np.sqrt(2.0 * params.Dm * params.chi)
        * np.asarray(noise_faces.m, dtype=float)
        / normalization
    )
    deterministic_jphi = np.asarray(jphi, dtype=float) + (
        np.sqrt(2.0 * params.Dphi * params.chi)
        * np.asarray(noise_faces.phi, dtype=float)
        / normalization
    )
    return deterministic_jm, deterministic_jphi


def conservative_two_mode_step(
    state: TwoModeState,
    *,
    dx: float,
    dt: float,
    params: TwoModeParams,
    noise_faces: TwoModeNoiseFaces | None,
) -> TwoModeState:
    """Advance one periodic finite-volume step using face-flux differences."""

    if dx <= 0 or dt <= 0:
        raise ValueError("dx and dt must be positive")
    jm, jphi = _total_face_fluxes(
        state,
        dx=float(dx),
        dt=float(dt),
        params=params,
        noise_faces=noise_faces,
    )
    return _advance_two_mode_from_fluxes(
        state,
        jm=jm,
        jphi=jphi,
        dx=float(dx),
        dt=float(dt),
        params=params,
    )


def simulate_two_mode(
    *,
    x: Array,
    t: Array,
    m0: Array,
    phi0: Array,
    params: TwoModeParams,
    dt_internal: float,
    noise_faces: TwoModeNoiseFaces | None,
) -> TwoModeTrajectory:
    """Simulate one periodic realization on an exactly aligned output grid."""

    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    m0 = np.asarray(m0, dtype=float)
    phi0 = np.asarray(phi0, dtype=float)
    if (
        x.ndim != 1
        or t.ndim != 1
        or m0.shape != x.shape
        or phi0.shape != x.shape
    ):
        raise ValueError("Expected x,t one-dimensional and initial fields on x")
    if x.size < 4 or t.size < 2 or np.any(np.diff(t) <= 0):
        raise ValueError("Simulation grids are too small or not increasing")
    dx_values = np.diff(x)
    dx = float(dx_values[0])
    if not np.allclose(dx_values, dx):
        raise ValueError("x must be a uniform periodic grid")
    if dt_internal <= 0:
        raise ValueError("dt_internal must be positive")
    step_positions = (t - t[0]) / float(dt_internal)
    rounded_positions = np.rint(step_positions).astype(int)
    if not np.allclose(step_positions, rounded_positions, atol=1e-10):
        raise ValueError("Output times must align with dt_internal")
    n_steps = int(rounded_positions[-1])

    if noise_faces is not None:
        noise_m = np.asarray(noise_faces.m, dtype=float)
        noise_phi = np.asarray(noise_faces.phi, dtype=float)
        expected = (n_steps, x.size)
        if noise_m.shape != expected or noise_phi.shape != expected:
            raise ValueError(f"noise face arrays must have shape {expected}")
    state = TwoModeState(m=m0.copy(), phi=phi0.copy())
    output_m = np.empty((t.size, x.size), dtype=float)
    output_phi = np.empty_like(output_m)
    output_jm = np.empty_like(output_m)
    output_jphi = np.empty_like(output_m)
    output_m[0] = state.m
    output_phi[0] = state.phi
    jm_origin = np.empty(n_steps, dtype=float)
    jphi_origin = np.empty(n_steps, dtype=float)
    integrated_jm_output = np.zeros(t.size, dtype=float)
    integrated_jphi_output = np.zeros(t.size, dtype=float)
    central_face = int(
        np.argmin(np.abs(0.5 * (x[:-1] + x[1:])))
    )
    cumulative_jm = 0.0
    cumulative_jphi = 0.0
    output_lookup = {
        int(step): index for index, step in enumerate(rounded_positions)
    }
    for step in range(n_steps):
        one_noise = (
            None
            if noise_faces is None
            else TwoModeNoiseFaces(
                m=np.asarray(noise_faces.m[step]),
                phi=np.asarray(noise_faces.phi[step]),
            )
        )
        jm, jphi = _total_face_fluxes(
            state,
            dx=dx,
            dt=float(dt_internal),
            params=params,
            noise_faces=one_noise,
        )
        if step in output_lookup:
            output_index = output_lookup[step]
            output_jm[output_index], output_jphi[output_index] = (
                _deterministic_fluxes_from_total(
                    jm,
                    jphi,
                    noise_faces=one_noise,
                    dx=dx,
                    dt=float(dt_internal),
                    params=params,
                )
            )
        jm_origin[step] = float(jm[central_face])
        jphi_origin[step] = float(jphi[central_face])
        cumulative_jm += float(dt_internal) * jm_origin[step]
        cumulative_jphi += float(dt_internal) * jphi_origin[step]
        state = _advance_two_mode_from_fluxes(
            state,
            jm=jm,
            jphi=jphi,
            dx=dx,
            dt=float(dt_internal),
            params=params,
        )
        completed_step = step + 1
        if completed_step in output_lookup:
            output_index = output_lookup[completed_step]
            output_m[output_index] = state.m
            output_phi[output_index] = state.phi
            integrated_jm_output[output_index] = cumulative_jm
            integrated_jphi_output[output_index] = cumulative_jphi
    final_index = output_lookup[n_steps]
    output_jm[final_index], output_jphi[final_index] = _total_face_fluxes(
        state,
        dx=dx,
        dt=float(dt_internal),
        params=params,
        noise_faces=None,
    )
    return TwoModeTrajectory(
        t=t.copy(),
        m=output_m,
        phi=output_phi,
        jm_output=output_jm,
        jphi_output=output_jphi,
        jm_origin=jm_origin,
        jphi_origin=jphi_origin,
        integrated_jm_output=integrated_jm_output,
        integrated_jphi_output=integrated_jphi_output,
    )


def equilibrium_variance_sanity(
    *,
    params: TwoModeParams,
    n_cells: int,
    n_ensemble: int,
    n_steps: int,
    dt: float,
    dx: float,
    seed: int,
) -> dict[str, float | int | dict[str, float]]:
    """Vectorized equilibrium ensemble check for variance and conservation."""

    if n_cells < 8 or n_ensemble < 32 or n_steps < 1:
        raise ValueError("Equilibrium sanity ensemble is too small")
    rng = np.random.default_rng(int(seed))
    target_variance = params.chi / float(dx)
    state = TwoModeState(
        m=rng.normal(scale=np.sqrt(target_variance), size=(n_ensemble, n_cells)),
        phi=rng.normal(
            scale=np.sqrt(target_variance), size=(n_ensemble, n_cells)
        ),
    )
    initial_m_sum = np.sum(state.m, axis=1)
    initial_phi_sum = np.sum(state.phi, axis=1)
    for _ in range(n_steps):
        state = conservative_two_mode_step(
            state,
            dx=dx,
            dt=dt,
            params=params,
            noise_faces=TwoModeNoiseFaces(
                m=rng.normal(size=(n_ensemble, n_cells)),
                phi=rng.normal(size=(n_ensemble, n_cells)),
            ),
        )
    m_variance = float(np.var(state.m))
    phi_variance = float(np.var(state.phi))
    jm, _ = two_mode_flux(
        state.m,
        state.phi,
        lambda_m=params.lambda_m,
        lambda_phi=params.lambda_phi,
    )
    centered_current = jm - np.mean(jm)
    current_variance = float(np.mean(centered_current**2))
    skewness = float(
        np.mean(centered_current**3) / max(current_variance**1.5, 1e-30)
    )
    max_conservation_error = max(
        float(np.max(np.abs(np.sum(state.m, axis=1) - initial_m_sum))),
        float(np.max(np.abs(np.sum(state.phi, axis=1) - initial_phi_sum))),
    )
    return {
        "seed": int(seed),
        "params": asdict(params),
        "target_variance": target_variance,
        "m_variance": m_variance,
        "phi_variance": phi_variance,
        "m_variance_relative_error": abs(m_variance - target_variance)
        / target_variance,
        "phi_variance_relative_error": abs(phi_variance - target_variance)
        / target_variance,
        "magnetization_current_skewness": skewness,
        "max_conservation_error": max_conservation_error,
    }


def _first_four_cumulants(samples: Array) -> Array:
    samples = np.asarray(samples, dtype=float)
    centered = samples - np.mean(samples)
    second = float(np.mean(centered**2))
    return np.array(
        [
            float(np.mean(samples)),
            second,
            float(np.mean(centered**3)),
            float(np.mean(centered**4) - 3.0 * second**2),
        ]
    )


def _first_four_cumulants_by_time(samples: Array) -> Array:
    samples = np.asarray(samples, dtype=float)
    if samples.ndim != 2:
        raise ValueError("time-resolved samples must have shape (ensemble, time)")
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


def ensemble_transfer_logz(
    ensemble: TwoModeEnsemble,
    gamma: Array,
    *,
    mode: str = "m",
) -> Array:
    """Return the empirical time-resolved transfer characteristic function."""

    gamma = np.asarray(gamma, dtype=float)
    if (
        gamma.ndim != 1
        or gamma.size < 3
        or np.any(~np.isfinite(gamma))
        or not np.allclose(gamma, -gamma[::-1], rtol=0.0, atol=1e-13)
        or not np.any(np.isclose(gamma, 0.0, rtol=0.0, atol=1e-13))
    ):
        raise ValueError("gamma must be finite, symmetric, and contain zero")
    if mode == "m":
        samples = np.asarray(ensemble.integrated_jm_time, dtype=float)
    elif mode == "phi":
        samples = np.asarray(ensemble.integrated_jphi_time, dtype=float)
    else:
        raise ValueError("mode must be m or phi")
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
    # Sampling noise need not satisfy conjugacy bitwise.  The two sides carry
    # the same information, so retain positive fields and enforce the exact
    # characteristic-function identity on their registered negative partners.
    for index, value in enumerate(gamma):
        if value < -1e-13:
            partner = int(np.argmin(np.abs(gamma + value)))
            result[:, index] = np.conj(result[:, partner])
    result[:, zero] = 0.0
    return result


def generate_noise_panel(
    *,
    seed: int,
    n_ensemble: int,
    n_steps: int,
    n_cells: int,
) -> TwoModeNoisePanel:
    """Generate standard-normal innovations for paired model comparisons."""

    if n_ensemble < 2 or n_steps < 1 or n_cells < 4:
        raise ValueError("noise panel dimensions are too small")
    rng = np.random.default_rng(int(seed))
    initial_m = rng.normal(size=(n_ensemble, n_cells))
    initial_phi = rng.normal(size=(n_ensemble, n_cells))
    face_m = rng.normal(size=(n_ensemble, n_steps, n_cells))
    face_phi = rng.normal(size=(n_ensemble, n_steps, n_cells))
    return TwoModeNoisePanel(
        initial_m=initial_m,
        initial_phi=initial_phi,
        face_m=face_m,
        face_phi=face_phi,
        seed=int(seed),
    )


def lazy_noise_panel(
    *,
    seed: int,
    n_ensemble: int,
    n_steps: int,
    n_cells: int,
    spin_sign: int = 1,
) -> LazyNoisePanel:
    """Describe replayable per-trajectory innovations without allocating them."""

    return LazyNoisePanel(
        seed=int(seed),
        n_ensemble=int(n_ensemble),
        n_steps=int(n_steps),
        n_cells=int(n_cells),
        spin_sign=int(spin_sign),
    )


def _lazy_trajectory_noise(
    panel: LazyNoisePanel,
    ensemble_index: int,
) -> tuple[Array, Array, Array, Array]:
    if not 0 <= ensemble_index < panel.n_ensemble:
        raise IndexError("lazy noise trajectory index is out of range")
    sequence = np.random.SeedSequence(
        [int(panel.seed), int(ensemble_index)]
    )
    rng = np.random.default_rng(sequence)
    initial_m = (
        panel.spin_sign * rng.normal(size=panel.n_cells)
    )
    initial_phi = rng.normal(size=panel.n_cells)
    face_m = panel.spin_sign * rng.normal(
        size=(panel.n_steps, panel.n_cells)
    )
    face_phi = rng.normal(size=(panel.n_steps, panel.n_cells))
    return initial_m, initial_phi, face_m, face_phi


def _simulate_two_mode_lazy_ensemble(
    *,
    x: Array,
    t: Array,
    m0: Array,
    phi0: Array,
    params: TwoModeParams,
    dt_internal: float,
    panel: LazyNoisePanel,
    equilibrium_fluctuations: bool,
) -> TwoModeEnsemble:
    """Vectorized replay of a lazy panel with memory O(ensemble*cells)."""

    n_ensemble = panel.n_ensemble
    n_steps = panel.n_steps
    n_cells = panel.n_cells
    dx = float(x[1] - x[0])
    positions = (t - t[0]) / float(dt_internal)
    rounded = np.rint(positions).astype(int)
    lookup = {int(step): index for index, step in enumerate(rounded)}
    rng = np.random.default_rng(int(panel.seed))
    standard_m = panel.spin_sign * rng.normal(
        size=(n_ensemble, n_cells)
    )
    standard_phi = rng.normal(size=(n_ensemble, n_cells))
    if equilibrium_fluctuations:
        scale = np.sqrt(params.chi / dx)
        delta_m = standard_m * scale
        delta_phi = standard_phi * scale
        delta_m -= np.mean(delta_m, axis=1, keepdims=True)
        delta_phi -= np.mean(delta_phi, axis=1, keepdims=True)
    else:
        delta_m = np.zeros_like(standard_m)
        delta_phi = np.zeros_like(standard_phi)
    state = TwoModeState(
        m=np.asarray(m0)[None, :] + delta_m,
        phi=np.asarray(phi0)[None, :] + delta_phi,
    )
    origin_cell = int(np.argmin(np.abs(x)))
    central_face = int(np.argmin(np.abs(0.5 * (x[:-1] + x[1:]))))
    reference = delta_m[:, origin_cell]
    mean_m = np.empty((t.size, n_cells), dtype=float)
    mean_phi = np.empty_like(mean_m)
    mean_jm = np.empty_like(mean_m)
    mean_jphi = np.empty_like(mean_m)
    cmm = np.empty_like(mean_m)
    czz = np.empty_like(mean_m)
    integrated_m = np.zeros((n_ensemble, t.size), dtype=float)
    integrated_phi = np.zeros_like(integrated_m)
    mean_m[0] = np.mean(state.m, axis=0)
    mean_phi[0] = np.mean(state.phi, axis=0)
    cmm[0] = np.mean(
        (state.m - mean_m[0][None, :]) * reference[:, None],
        axis=0,
    )
    centered_initial = state.m[:, origin_cell] - mean_m[0, origin_cell]
    czz[0] = np.mean(
        (state.m - mean_m[0][None, :]) * centered_initial[:, None],
        axis=0,
    )
    cumulative_m = np.zeros(n_ensemble, dtype=float)
    cumulative_phi = np.zeros(n_ensemble, dtype=float)
    for step in range(n_steps):
        noise = TwoModeNoiseFaces(
            m=panel.spin_sign
            * rng.normal(size=(n_ensemble, n_cells)),
            phi=rng.normal(size=(n_ensemble, n_cells)),
        )
        jm, jphi = _total_face_fluxes(
            state,
            dx=dx,
            dt=dt_internal,
            params=params,
            noise_faces=noise,
        )
        if step in lookup:
            index = lookup[step]
            deterministic_jm, deterministic_jphi = (
                _deterministic_fluxes_from_total(
                    jm,
                    jphi,
                    noise_faces=noise,
                    dx=dx,
                    dt=dt_internal,
                    params=params,
                )
            )
            mean_jm[index] = np.mean(deterministic_jm, axis=0)
            mean_jphi[index] = np.mean(deterministic_jphi, axis=0)
        cumulative_m += dt_internal * jm[:, central_face]
        cumulative_phi += dt_internal * jphi[:, central_face]
        state = _advance_two_mode_from_fluxes(
            state,
            jm=jm,
            jphi=jphi,
            dx=dx,
            dt=dt_internal,
            params=params,
        )
        completed = step + 1
        if completed in lookup:
            index = lookup[completed]
            mean_m[index] = np.mean(state.m, axis=0)
            mean_phi[index] = np.mean(state.phi, axis=0)
            cmm[index] = np.mean(
                (state.m - mean_m[index][None, :])
                * reference[:, None],
                axis=0,
            )
            centered_now = (
                state.m[:, origin_cell] - mean_m[index, origin_cell]
            )
            czz[index] = np.mean(
                (state.m - mean_m[index][None, :])
                * centered_now[:, None],
                axis=0,
            )
            integrated_m[:, index] = cumulative_m
            integrated_phi[:, index] = cumulative_phi
    final_index = lookup[n_steps]
    deterministic_jm, deterministic_jphi = _total_face_fluxes(
        state,
        dx=dx,
        dt=dt_internal,
        params=params,
        noise_faces=None,
    )
    mean_jm[final_index] = np.mean(deterministic_jm, axis=0)
    mean_jphi[final_index] = np.mean(deterministic_jphi, axis=0)
    jm_cumulants_time = _first_four_cumulants_by_time(integrated_m)
    jphi_cumulants_time = _first_four_cumulants_by_time(integrated_phi)
    return TwoModeEnsemble(
        t=t.copy(),
        mean_m=mean_m,
        mean_phi=mean_phi,
        mean_jm=mean_jm,
        mean_jphi=mean_jphi,
        cmm_origin=cmm,
        czz_center=czz,
        integrated_jm=integrated_m[:, -1].copy(),
        integrated_jphi=integrated_phi[:, -1].copy(),
        integrated_jm_time=integrated_m,
        integrated_jphi_time=integrated_phi,
        jm_cumulants=jm_cumulants_time[-1].copy(),
        jphi_cumulants=jphi_cumulants_time[-1].copy(),
        jm_cumulants_time=jm_cumulants_time,
        jphi_cumulants_time=jphi_cumulants_time,
        seed=int(panel.seed),
        n_ensemble=n_ensemble,
    )


def simulate_two_mode_ensemble(
    *,
    x: Array,
    t: Array,
    m0: Array,
    phi0: Array,
    params: TwoModeParams,
    dt_internal: float,
    n_ensemble: int,
    seed: int,
    equilibrium_fluctuations: bool = True,
    noise_panel: TwoModeNoisePanel | LazyNoisePanel | None = None,
) -> TwoModeEnsemble:
    """Simulate an ensemble with reproducible initial and face noise.

    The connected correlation uses the initial magnetization fluctuation at
    the cell closest to the origin as its reference.  Integrated-current
    cumulants are returned through fourth order.
    """

    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    m0 = np.asarray(m0, dtype=float)
    phi0 = np.asarray(phi0, dtype=float)
    if n_ensemble < 2:
        raise ValueError("n_ensemble must be at least two")
    if x.ndim != 1 or m0.shape != x.shape or phi0.shape != x.shape:
        raise ValueError("Initial ensemble means must match x")
    step_positions = (t - t[0]) / float(dt_internal)
    rounded_positions = np.rint(step_positions).astype(int)
    if not np.allclose(step_positions, rounded_positions, atol=1e-10):
        raise ValueError("Output times must align with dt_internal")
    n_steps = int(rounded_positions[-1])
    dx = float(x[1] - x[0])
    if noise_panel is None:
        noise_panel = lazy_noise_panel(
            seed=int(seed),
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
            raise ValueError("lazy noise panel dimensions do not match")
    elif (
        np.asarray(noise_panel.initial_m).shape != expected_initial
        or np.asarray(noise_panel.initial_phi).shape != expected_initial
        or np.asarray(noise_panel.face_m).shape != expected_faces
        or np.asarray(noise_panel.face_phi).shape != expected_faces
    ):
        raise ValueError("noise panel shapes must match ensemble, steps, and cells")
    if isinstance(noise_panel, LazyNoisePanel):
        return _simulate_two_mode_lazy_ensemble(
            x=x,
            t=t,
            m0=m0,
            phi0=phi0,
            params=params,
            dt_internal=dt_internal,
            panel=noise_panel,
            equilibrium_fluctuations=equilibrium_fluctuations,
        )

    sum_m = np.zeros((t.size, x.size), dtype=float)
    sum_phi = np.zeros_like(sum_m)
    sum_jm = np.zeros_like(sum_m)
    sum_jphi = np.zeros_like(sum_m)
    cross_m_reference = np.zeros_like(sum_m)
    cross_m_center = np.zeros_like(sum_m)
    center_sum = np.zeros(t.size, dtype=float)
    reference_sum = 0.0
    integrated_jm = np.empty(n_ensemble, dtype=float)
    integrated_jphi = np.empty(n_ensemble, dtype=float)
    integrated_jm_time = np.empty((n_ensemble, t.size), dtype=float)
    integrated_jphi_time = np.empty_like(integrated_jm_time)
    fluctuation_scale = np.sqrt(params.chi / dx)
    for ensemble_index in range(n_ensemble):
        if isinstance(noise_panel, LazyNoisePanel):
            (
                standard_initial_m,
                standard_initial_phi,
                standard_face_m,
                standard_face_phi,
            ) = _lazy_trajectory_noise(noise_panel, ensemble_index)
        else:
            standard_initial_m = np.asarray(
                noise_panel.initial_m[ensemble_index], dtype=float
            )
            standard_initial_phi = np.asarray(
                noise_panel.initial_phi[ensemble_index], dtype=float
            )
            standard_face_m = np.asarray(
                noise_panel.face_m[ensemble_index], dtype=float
            )
            standard_face_phi = np.asarray(
                noise_panel.face_phi[ensemble_index], dtype=float
            )
        if equilibrium_fluctuations:
            delta_m = standard_initial_m * fluctuation_scale
            delta_phi = standard_initial_phi * fluctuation_scale
            # Fix conserved zero modes so condition-to-condition mean offsets
            # do not masquerade as dynamics.
            delta_m -= np.mean(delta_m)
            delta_phi -= np.mean(delta_phi)
        else:
            delta_m = np.zeros(x.size)
            delta_phi = np.zeros(x.size)
        origin = int(np.argmin(np.abs(x)))
        reference = float(delta_m[origin])
        reference_sum += reference
        noise = TwoModeNoiseFaces(
            m=standard_face_m,
            phi=standard_face_phi,
        )
        trajectory = simulate_two_mode(
            x=x,
            t=t,
            m0=m0 + delta_m,
            phi0=phi0 + delta_phi,
            params=params,
            dt_internal=dt_internal,
            noise_faces=noise,
        )
        sum_m += trajectory.m
        sum_phi += trajectory.phi
        sum_jm += trajectory.jm_output
        sum_jphi += trajectory.jphi_output
        cross_m_reference += trajectory.m * reference
        center_values = trajectory.m[:, origin]
        cross_m_center += trajectory.m * center_values[:, None]
        center_sum += center_values
        integrated_jm_time[ensemble_index] = trajectory.integrated_jm_output
        integrated_jphi_time[ensemble_index] = trajectory.integrated_jphi_output
        integrated_jm[ensemble_index] = float(
            trajectory.integrated_jm_output[-1]
        )
        integrated_jphi[ensemble_index] = float(
            trajectory.integrated_jphi_output[-1]
        )

    mean_m = sum_m / float(n_ensemble)
    mean_phi = sum_phi / float(n_ensemble)
    mean_jm = sum_jm / float(n_ensemble)
    mean_jphi = sum_jphi / float(n_ensemble)
    mean_reference = reference_sum / float(n_ensemble)
    cmm_origin = (
        cross_m_reference / float(n_ensemble)
        - mean_m * mean_reference
    )
    czz_center = (
        cross_m_center / float(n_ensemble)
        - mean_m * (center_sum / float(n_ensemble))[:, None]
    )
    jm_cumulants_time = _first_four_cumulants_by_time(integrated_jm_time)
    jphi_cumulants_time = _first_four_cumulants_by_time(integrated_jphi_time)
    return TwoModeEnsemble(
        t=t.copy(),
        mean_m=mean_m,
        mean_phi=mean_phi,
        mean_jm=mean_jm,
        mean_jphi=mean_jphi,
        cmm_origin=cmm_origin,
        czz_center=czz_center,
        integrated_jm=integrated_jm,
        integrated_jphi=integrated_jphi,
        integrated_jm_time=integrated_jm_time,
        integrated_jphi_time=integrated_jphi_time,
        jm_cumulants=_first_four_cumulants(integrated_jm),
        jphi_cumulants=_first_four_cumulants(integrated_jphi),
        jm_cumulants_time=jm_cumulants_time,
        jphi_cumulants_time=jphi_cumulants_time,
        seed=int(noise_panel.seed),
        n_ensemble=int(n_ensemble),
    )


def paired_error_improvement(
    scalar_errors: Array,
    two_mode_errors: Array,
    *,
    n_replicates: int,
    confidence: float,
    seed: int,
) -> dict[str, float | int]:
    """Paired-bootstrap relative improvement of two-mode over scalar errors."""

    scalar_errors = np.asarray(scalar_errors, dtype=float)
    two_mode_errors = np.asarray(two_mode_errors, dtype=float)
    if (
        scalar_errors.ndim != 1
        or scalar_errors.shape != two_mode_errors.shape
        or scalar_errors.size < 3
        or np.any(~np.isfinite(scalar_errors))
        or np.any(~np.isfinite(two_mode_errors))
        or np.any(scalar_errors <= 0)
        or np.any(two_mode_errors < 0)
    ):
        raise ValueError("Paired finite nonnegative error arrays are required")
    if n_replicates < 100 or not 0 < confidence < 1:
        raise ValueError("Need at least 100 replicates and 0<confidence<1")
    point = 1.0 - float(np.mean(two_mode_errors)) / float(
        np.mean(scalar_errors)
    )
    rng = np.random.default_rng(int(seed))
    values = np.empty(n_replicates, dtype=float)
    for index in range(n_replicates):
        sample = rng.integers(0, scalar_errors.size, size=scalar_errors.size)
        values[index] = 1.0 - float(np.mean(two_mode_errors[sample])) / float(
            np.mean(scalar_errors[sample])
        )
    alpha = 0.5 * (1.0 - float(confidence))
    low, high = np.quantile(values, [alpha, 1.0 - alpha])
    return {
        "relative_improvement": point,
        "paired_ci_low": float(low),
        "paired_ci_high": float(high),
        "confidence": float(confidence),
        "n_replicates": int(n_replicates),
        "seed": int(seed),
    }
