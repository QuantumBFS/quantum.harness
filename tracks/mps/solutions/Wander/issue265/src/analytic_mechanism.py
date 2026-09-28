"""Analytic diagnostics for why a single domain wall looks like Burgers.

The high-temperature domain wall used by Kharkov et al. is a linear-response
experiment in the bias ``mu``.  To leading order,

    U_i(t) = <S_i^z(t)> / mu
           = 2 sum_j s_j <S_i^z(t) S_j^z(0)>_infinity,

where ``s_j`` is the initial step.  Consequently the normalized front
gradient is the equilibrium spin structure factor divided by the static
susceptibility.  A nonlinear scalar PDE inferred from one such trajectory is
therefore not automatically a microscopic nonlinear evolution law.

This module implements data diagnostics implied by that observation:

* the moment diffusivity ``D_moment = 0.5 d Var(front) / dt``;
* the exact second-moment balance of a viscous Burgers closure;
* spin-flip and amplitude-equivariance checks on inferred coefficients; and
* the scaling dimensions of instantaneous Burgers surrogate coefficients for
  an arbitrary self-similar front.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.signal import savgol_filter
from scipy.special import erf

from .tension_resolution import (
    fit_power_exponent,
    fit_profiled_weak,
    front_width_series,
)


Array = np.ndarray


def _validated_profile_arrays(x: Array, t: Array, u: Array) -> tuple[Array, Array, Array]:
    x = np.asarray(x, dtype=float)
    t = np.asarray(t, dtype=float)
    u = np.asarray(u, dtype=float)
    if x.ndim != 1 or t.ndim != 1 or u.shape != (t.size, x.size):
        raise ValueError("Expected x:(Nx,), t:(Nt,), u:(Nt,Nx)")
    if x.size < 20 or t.size < 11:
        raise ValueError("Profile diagnostics need at least 20 sites and 11 times")
    if np.any(np.diff(x) <= 0) or np.any(np.diff(t) <= 0):
        raise ValueError("x and t must be strictly increasing")
    if not np.all(np.isfinite(u)):
        raise ValueError("u contains non-finite values")
    return x, t, u


def _smooth_series(values: Array, requested_window: int, polyorder: int = 3) -> Array:
    values = np.asarray(values, dtype=float)
    window = min(int(requested_window), values.size - (1 - values.size % 2))
    if window % 2 == 0:
        window -= 1
    if window < polyorder + 2:
        return values.copy()
    return savgol_filter(values, window_length=window, polyorder=polyorder, mode="interp")


def front_linear_response_diagnostics(
    x: Array,
    t: Array,
    u: Array,
    *,
    moment_smooth_window: int = 101,
) -> dict[str, Array | float]:
    """Return structure-factor and moment diagnostics for a rising wall.

    The plateau midpoint is removed before evaluating spin-flip symmetry and
    the Burgers moment integral.  For a front with plateaus ``-U`` and ``+U``,
    the normalized gradient ``p = u_x / integral(u_x dx)`` has unit mass.  In
    linear response it equals ``C(x,t)/chi``.
    """

    x, t, u = _validated_profile_arrays(x, t, u)
    edge_n = min(10, max(2, x.size // 20))
    left = np.mean(u[:, :edge_n], axis=1)
    right = np.mean(u[:, -edge_n:], axis=1)
    midpoint_t = 0.5 * (left + right)
    half_jump_t = 0.5 * (right - left)
    half_jump = float(np.median(half_jump_t))
    if half_jump <= 0:
        raise ValueError("Expected a rising wall with positive plateau jump")

    centered = u - midpoint_t[:, None]
    symmetry_denominator = max(float(np.linalg.norm(centered)), 1e-30)
    spin_flip_antisymmetry_error = float(
        np.linalg.norm(centered + centered[:, ::-1]) / symmetry_denominator
    )

    ux = np.gradient(centered, x, axis=1, edge_order=2)
    gradient_symmetry_error = float(
        np.linalg.norm(ux - ux[:, ::-1]) / max(float(np.linalg.norm(ux)), 1e-30)
    )

    front = front_width_series(x, t, centered)
    variance = _smooth_series(front["variance"], moment_smooth_window)
    width = np.sqrt(np.maximum(variance, 0.0))
    moment_diffusivity = 0.5 * np.gradient(variance, t, edge_order=2)

    # For exact plateaus this is finite even on the infinite line.
    shape_integral = np.trapezoid(
        half_jump**2 - centered**2,
        x=x,
        axis=1,
    )
    shape_factor = shape_integral / np.maximum(half_jump**2 * width, 1e-30)

    return {
        "t": t.copy(),
        "width": width,
        "variance": variance,
        "moment_diffusivity": moment_diffusivity,
        "shape_integral": shape_integral,
        "shape_factor": shape_factor,
        "center": front["center"],
        "gradient_mass": front["gradient_mass"],
        "half_jump": half_jump,
        "plateau_midpoint_median": float(np.median(midpoint_t)),
        "spin_flip_antisymmetry_error": spin_flip_antisymmetry_error,
        "gradient_symmetry_error": gradient_symmetry_error,
    }


def moment_power_summary(
    diagnostics: dict[str, Array | float],
    *,
    t_window: tuple[float, float] = (80.0, 190.0),
) -> dict[str, float]:
    """Fit width, variance and moment-diffusivity powers on one time window."""

    t = np.asarray(diagnostics["t"], dtype=float)
    width = np.asarray(diagnostics["width"], dtype=float)
    variance = np.asarray(diagnostics["variance"], dtype=float)
    moment_diffusivity = np.asarray(diagnostics["moment_diffusivity"], dtype=float)
    t_min, t_max = map(float, t_window)
    width_fit = fit_power_exponent(t, width, t_min=t_min, t_max=t_max)
    variance_fit = fit_power_exponent(t, variance, t_min=t_min, t_max=t_max)
    mask = (
        (t >= t_min)
        & (t <= t_max)
        & (moment_diffusivity > 0)
        & np.isfinite(moment_diffusivity)
    )
    if np.count_nonzero(mask) < 5:
        raise ValueError("Not enough positive moment-diffusivity values")
    direct_gamma = float(
        np.polyfit(np.log(t[mask]), np.log(moment_diffusivity[mask]), 1)[0]
    )
    return {
        "t_min": t_min,
        "t_max": t_max,
        "width_exponent": float(width_fit["exponent"]),
        "variance_exponent": float(variance_fit["exponent"]),
        "moment_diffusivity_exponent_direct": direct_gamma,
        "moment_diffusivity_exponent_from_variance": float(
            variance_fit["exponent"] - 1.0
        ),
    }


def fit_burgers_moment_balance(
    diagnostics: dict[str, Array | float],
    *,
    t_mins: Sequence[float] = (50.0, 60.0, 80.0, 100.0, 120.0),
    t_max: float = 190.0,
) -> list[dict[str, float]]:
    """Fit the exact Burgers second-moment balance on several windows.

    For plateaus ``-U`` and ``+U``, differentiation of Burgers gives a
    Fokker-Planck equation for the normalized front gradient.  Its variance
    satisfies

        D_moment(t) = 0.5 dV/dt
                    = D + a/(4U) integral (U^2 - u^2) dx.

    If the front shape is self-similar, the integral equals
    ``c_shape * U^2 * W`` and the same identity becomes

        dW/dt = D/W + a*c_shape*U/4,

    explicitly showing the diffusion-to-rarefaction crossover.
    """

    t = np.asarray(diagnostics["t"], dtype=float)
    width = np.asarray(diagnostics["width"], dtype=float)
    moment_diffusivity = np.asarray(diagnostics["moment_diffusivity"], dtype=float)
    shape_integral = np.asarray(diagnostics["shape_integral"], dtype=float)
    shape_factor = np.asarray(diagnostics["shape_factor"], dtype=float)
    half_jump = float(diagnostics["half_jump"])
    width_rate = np.gradient(width, t, edge_order=2)

    rows: list[dict[str, float]] = []
    for t_min in t_mins:
        mask = (t >= float(t_min)) & (t <= float(t_max))
        if np.count_nonzero(mask) < 5:
            raise ValueError("Moment-balance window contains too few points")

        design = np.column_stack(
            [
                np.ones(np.count_nonzero(mask)),
                shape_integral[mask] / (4.0 * half_jump),
            ]
        )
        D_fit, a_fit = np.linalg.lstsq(
            design, moment_diffusivity[mask], rcond=None
        )[0]
        prediction = design @ np.array([D_fit, a_fit])
        relative_error = float(
            np.linalg.norm(moment_diffusivity[mask] - prediction)
            / max(float(np.linalg.norm(moment_diffusivity[mask])), 1e-30)
        )

        width_design = np.column_stack(
            [1.0 / width[mask], np.ones(np.count_nonzero(mask))]
        )
        D_width, ballistic_speed = np.linalg.lstsq(
            width_design, width_rate[mask], rcond=None
        )[0]
        mean_shape_factor = float(np.mean(shape_factor[mask]))
        a_from_width = float(
            4.0 * ballistic_speed / (mean_shape_factor * half_jump)
        )
        width_prediction = width_design @ np.array([D_width, ballistic_speed])
        width_relative_error = float(
            np.linalg.norm(width_rate[mask] - width_prediction)
            / max(float(np.linalg.norm(width_rate[mask])), 1e-30)
        )

        rows.append(
            {
                "t_min": float(t_min),
                "t_max": float(t_max),
                "D_from_moment_balance": float(D_fit),
                "a_from_moment_balance": float(a_fit),
                "moment_balance_relative_l2": relative_error,
                "mean_shape_factor": mean_shape_factor,
                "shape_factor_relative_std": float(
                    np.std(shape_factor[mask]) / max(abs(mean_shape_factor), 1e-30)
                ),
                "D_from_width_ode": float(D_width),
                "ballistic_speed_from_width_ode": float(ballistic_speed),
                "a_from_width_ode": a_from_width,
                "width_ode_relative_l2": width_relative_error,
            }
        )
    return rows


def amplitude_and_spin_flip_audit(
    x: Array,
    t: Array,
    u: Array,
    *,
    scales: Sequence[float] = (-2.0, -1.0, -0.5, 0.5, 1.0, 2.0),
    t_window: tuple[float, float] = (52.0, 198.0),
    x_crop: tuple[float, float] = (-120.0, 120.0),
) -> list[dict[str, float]]:
    """Refit rescaled copies of one trajectory.

    If ``v=c*u`` is only an amplitude rescaling of the same trajectory, the
    Burgers design transforms exactly as

        a_fit[v] = a_fit[u]/c,   D_fit[v] = D_fit[u].

    In linear response this amplitude dependence is incompatible with treating
    ``a_fit`` as a state-independent microscopic transport coefficient.
    Negative ``c`` is the spin-flipped wall.
    """

    x, t, u = _validated_profile_arrays(x, t, u)
    rows: list[dict[str, float]] = []
    for scale in scales:
        scale = float(scale)
        if scale == 0:
            raise ValueError("Amplitude scale cannot be zero")
        fit = fit_profiled_weak(
            x,
            t,
            scale * u,
            t_window=t_window,
            x_crop=x_crop,
            gamma=0.0,
        )
        rows.append(
            {
                "amplitude_scale": scale,
                "a_fit": float(fit.a),
                "D_fit": float(fit.D0),
                "scale_times_a_fit": float(scale * fit.a),
                "mse": float(fit.mse),
            }
        )
    return rows


def similarity_surrogate_scaling(
    *,
    beta: float = 2.0 / 3.0,
    half_jump: float = 0.5,
    times: Array | None = None,
    n_y: int = 4001,
) -> dict[str, Array | float]:
    """Fit Burgers features to an exact self-similar error-function front.

    For ``u=F(x/t^beta)``, dimensional analysis of the instantaneous least
    squares problem gives

        a_fit(t) proportional to t^(beta-1),
        D_fit(t) proportional to t^(2*beta-1).

    The calculation here verifies the powers without assuming that the front
    actually obeys Burgers.
    """

    beta = float(beta)
    if not 0 < beta < 1:
        raise ValueError("beta must lie between zero and one")
    if times is None:
        times = np.geomspace(10.0, 1000.0, 41)
    times = np.asarray(times, dtype=float)
    if np.any(times <= 0):
        raise ValueError("times must be positive")

    y = np.linspace(-6.0, 6.0, int(n_y))
    # A two-scale monotone sigmoid avoids the accidental special case in which
    # a single error function is generated exactly by diffusion alone.  The
    # dimensional powers below do not depend on this particular shape.
    mixture = 0.25
    broadening = 2.0
    narrow = erf(y)
    broad = erf(y / broadening)
    narrow_prime = 2.0 * np.exp(-(y**2)) / np.sqrt(np.pi)
    broad_prime = (
        2.0
        * np.exp(-((y / broadening) ** 2))
        / (np.sqrt(np.pi) * broadening)
    )
    narrow_second = -2.0 * y * narrow_prime
    broad_second = -2.0 * y * broad_prime / (broadening**2)
    F = float(half_jump) * ((1.0 - mixture) * narrow + mixture * broad)
    F_prime = float(half_jump) * (
        (1.0 - mixture) * narrow_prime + mixture * broad_prime
    )
    F_second = float(half_jump) * (
        (1.0 - mixture) * narrow_second + mixture * broad_second
    )

    a_values = []
    D_values = []
    correlations = []
    for time in times:
        response = -beta * y * F_prime / time
        nonlinear = -(time ** (-beta)) * F * F_prime
        diffusion = (time ** (-2.0 * beta)) * F_second
        design = np.column_stack([nonlinear, diffusion])
        fit, *_ = np.linalg.lstsq(design, response, rcond=None)
        a_values.append(float(fit[0]))
        D_values.append(float(fit[1]))
        correlations.append(float(np.corrcoef(nonlinear, diffusion)[0, 1]))

    a_values = np.asarray(a_values)
    D_values = np.asarray(D_values)
    a_exponent = float(
        np.polyfit(np.log(times), np.log(np.abs(a_values)), 1)[0]
    )
    D_exponent = float(
        np.polyfit(np.log(times), np.log(np.abs(D_values)), 1)[0]
    )
    return {
        "t": times,
        "a_fit": a_values,
        "D_fit": D_values,
        "feature_correlation": np.asarray(correlations),
        "a_exponent_fitted": a_exponent,
        "D_exponent_fitted": D_exponent,
        "a_exponent_expected": beta - 1.0,
        "D_exponent_expected": 2.0 * beta - 1.0,
        "beta": beta,
    }
