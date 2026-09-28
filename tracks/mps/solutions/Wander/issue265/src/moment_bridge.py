"""Moment-level bridge between microscopic GHD and finite-window Burgers.

The microscopic Heisenberg prediction is most cleanly tested without taking a
time derivative:

    W(t)**(3/2) = intercept + (3 A / 2) t.

The finite-window Burgers surrogate is likewise fit without differentiating
the data, using the exact implicit solution of

    dW/dt = D/W + v.

Their local tangent relation is

    A = 2 sqrt(D v),  W_star = D/v.

This module keeps the moment-level comparison separate from any claim that
the full deterministic scalar PDE is a universal physical-magnetization law.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import least_squares


Array = np.ndarray
A_GHD_INFINITY_T = 20.0 * np.pi / 81.0


@dataclass(frozen=True)
class MicroAmplitudeFit:
    """Derivative-free fit of ``W**(3/2) = b + 3*A*t/2``."""

    A: float
    intercept: float
    relative_l2: float
    stderr_A: float
    t_window: tuple[float, float]
    n_obs: int


@dataclass(frozen=True)
class BurgersWidthFit:
    """Positive-parameter fit of the exact Burgers moment-width ODE."""

    D: float
    v: float
    relative_l2: float
    stderr_D: float
    stderr_v: float
    log_parameter_correlation: float
    t_window: tuple[float, float]
    n_obs: int
    success: bool


def _validated_series(t: Array, width: Array) -> tuple[Array, Array]:
    t = np.asarray(t, dtype=float)
    width = np.asarray(width, dtype=float)
    if t.ndim != 1 or width.ndim != 1 or t.shape != width.shape:
        raise ValueError("t and width must be one-dimensional arrays of equal size")
    if t.size < 5:
        raise ValueError("At least five width observations are required")
    if np.any(~np.isfinite(t)) or np.any(~np.isfinite(width)):
        raise ValueError("t and width must be finite")
    if np.any(np.diff(t) < 0):
        raise ValueError("t must be non-decreasing")
    if np.any(width <= 0):
        raise ValueError("width must be positive")
    return t, width


def _windowed(
    t: Array,
    width: Array,
    t_window: tuple[float, float],
) -> tuple[Array, Array]:
    t, width = _validated_series(t, width)
    start, stop = map(float, t_window)
    if not start < stop:
        raise ValueError("t_window must be strictly increasing")
    mask = (t >= start) & (t <= stop)
    if np.count_nonzero(mask) < 5:
        raise ValueError("t_window contains fewer than five observations")
    return t[mask], width[mask]


def fit_micro_amplitude(
    t: Array,
    width: Array,
    *,
    t_window: tuple[float, float],
) -> MicroAmplitudeFit:
    """Fit the microscopic square-root constitutive amplitude without d/dt."""

    tw, ww = _windowed(t, width, t_window)
    y = ww**1.5
    design = np.column_stack([np.ones(tw.size), tw])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    prediction = design @ beta
    residual = y - prediction
    relative_l2 = float(
        np.linalg.norm(residual) / max(float(np.linalg.norm(y)), 1e-30)
    )
    dof = max(tw.size - 2, 1)
    sigma2 = float(residual @ residual / dof)
    covariance = sigma2 * np.linalg.pinv(design.T @ design)
    stderr_slope = float(np.sqrt(max(covariance[1, 1], 0.0)))
    return MicroAmplitudeFit(
        A=float(2.0 * beta[1] / 3.0),
        intercept=float(beta[0]),
        relative_l2=relative_l2,
        stderr_A=float(2.0 * stderr_slope / 3.0),
        t_window=(float(t_window[0]), float(t_window[1])),
        n_obs=int(tw.size),
    )


def burgers_elapsed_time(
    width: Array,
    *,
    W0: float,
    D: float,
    v: float,
    t0: float = 0.0,
) -> Array:
    """Evaluate the exact implicit solution of ``dW/dt=D/W+v``.

    The returned value is physical time as a function of width.  ``log1p`` is
    used to reduce cancellation when the width increment is small.
    """

    width = np.asarray(width, dtype=float)
    W0 = float(W0)
    D = float(D)
    v = float(v)
    if W0 <= 0 or D <= 0 or v <= 0:
        raise ValueError("W0, D and v must be positive")
    if np.any(width <= 0):
        raise ValueError("width must be positive")
    delta = width - W0
    log_ratio = np.log1p(v * delta / (D + v * W0))
    elapsed = delta / v - (D / v**2) * log_ratio
    return float(t0) + elapsed


def _initial_width_parameters(t: Array, width: Array) -> tuple[float, float]:
    unique_t, inverse = np.unique(t, return_inverse=True)
    if unique_t.size < 5:
        return 2.0, 0.05
    counts = np.bincount(inverse)
    unique_width = np.bincount(inverse, weights=width) / counts
    rate = np.gradient(unique_width, unique_t, edge_order=2)
    design = np.column_stack([1.0 / unique_width, np.ones(unique_width.size)])
    estimate, *_ = np.linalg.lstsq(design, rate, rcond=None)
    diffusion = max(float(estimate[0]), 1e-4)
    speed = max(float(estimate[1]), 1e-5)
    return diffusion, speed


def fit_burgers_width_ode(
    t: Array,
    width: Array,
    *,
    t_window: tuple[float, float],
    initial: tuple[float, float] | None = None,
) -> BurgersWidthFit:
    """Fit ``D,v`` from the exact implicit width law without estimating dW/dt."""

    tw, ww = _windowed(t, width, t_window)
    order = np.argsort(tw, kind="stable")
    tw = tw[order]
    ww = ww[order]
    if np.any(np.diff(ww) < -1e-10):
        raise ValueError("Burgers width fit requires a monotone front width")

    t0 = float(tw[0])
    W0 = float(ww[0])
    duration = max(float(np.ptp(tw)), 1.0)
    if initial is None:
        initial = _initial_width_parameters(tw, ww)
    D0 = max(float(initial[0]), 1e-8)
    v0 = max(float(initial[1]), 1e-8)

    def residual(log_parameters: Array) -> Array:
        diffusion, speed = np.exp(log_parameters)
        prediction = burgers_elapsed_time(
            ww,
            W0=W0,
            D=float(diffusion),
            v=float(speed),
            t0=t0,
        )
        return (prediction - tw) / duration

    result = least_squares(
        residual,
        np.log(np.array([D0, v0], dtype=float)),
        bounds=(np.log([1e-10, 1e-10]), np.log([1e5, 1e3])),
        xtol=1e-13,
        ftol=1e-13,
        gtol=1e-13,
        max_nfev=3000,
    )
    diffusion, speed = np.exp(result.x)
    prediction = burgers_elapsed_time(
        ww,
        W0=W0,
        D=float(diffusion),
        v=float(speed),
        t0=t0,
    )
    relative_l2 = float(
        np.linalg.norm(prediction - tw)
        / max(float(np.linalg.norm(tw - t0)), 1e-30)
    )

    dof = max(tw.size - 2, 1)
    sigma2 = float(np.sum(result.fun**2) / dof)
    covariance_log = sigma2 * np.linalg.pinv(result.jac.T @ result.jac)
    stderr_D = float(diffusion * np.sqrt(max(covariance_log[0, 0], 0.0)))
    stderr_v = float(speed * np.sqrt(max(covariance_log[1, 1], 0.0)))
    denominator = np.sqrt(
        max(covariance_log[0, 0], 0.0) * max(covariance_log[1, 1], 0.0)
    )
    correlation = (
        float(covariance_log[0, 1] / denominator) if denominator > 0 else 0.0
    )
    return BurgersWidthFit(
        D=float(diffusion),
        v=float(speed),
        relative_l2=relative_l2,
        stderr_D=stderr_D,
        stderr_v=stderr_v,
        log_parameter_correlation=correlation,
        t_window=(float(t_window[0]), float(t_window[1])),
        n_obs=int(tw.size),
        success=bool(result.success),
    )


def tangent_invariants(
    *,
    D: float,
    v: float,
    A_width: float,
    W_anchor: float,
    U0: float,
    c_f: float,
) -> dict[str, float]:
    """Return coefficient-level tests of the local square-root tangent."""

    values = np.asarray([D, v, A_width, W_anchor, U0, c_f], dtype=float)
    if np.any(values <= 0) or np.any(~np.isfinite(values)):
        raise ValueError("All tangent inputs must be positive and finite")
    A_bridge = 2.0 * np.sqrt(float(D) * float(v))
    W_star = float(D) / float(v)
    a_from_v = 4.0 * float(v) / (float(U0) * float(c_f))
    return {
        "W_star": W_star,
        "A_bridge": A_bridge,
        "A_bridge_over_A_width": A_bridge / float(A_width),
        "D_over_vW_anchor": float(D) / (float(v) * float(W_anchor)),
        "a_from_v": a_from_v,
        "A_GHD": A_GHD_INFINITY_T,
        "A_width_over_A_GHD": float(A_width) / A_GHD_INFINITY_T,
        "A_bridge_over_A_GHD": A_bridge / A_GHD_INFINITY_T,
    }


def rolling_moment_bridge(
    t: Array,
    width: Array,
    shape_factor: Array,
    *,
    U0: float,
    windows: Sequence[tuple[float, float]],
) -> list[dict[str, float]]:
    """Fit microscopic and Burgers moment laws on registered rolling windows."""

    t, width = _validated_series(t, width)
    shape_factor = np.asarray(shape_factor, dtype=float)
    if shape_factor.shape != t.shape or np.any(shape_factor <= 0):
        raise ValueError("shape_factor must be positive and match t")
    rows: list[dict[str, float]] = []
    for start, stop in windows:
        mask = (t >= float(start)) & (t <= float(stop))
        if np.count_nonzero(mask) < 5:
            continue
        micro = fit_micro_amplitude(
            t,
            width,
            t_window=(float(start), float(stop)),
        )
        burgers = fit_burgers_width_ode(
            t,
            width,
            t_window=(float(start), float(stop)),
        )
        c_f = float(np.mean(shape_factor[mask]))
        c_f_relative_std = float(
            np.std(shape_factor[mask]) / max(abs(c_f), 1e-30)
        )
        W_anchor = float(np.median(width[mask]))
        invariant = tangent_invariants(
            D=burgers.D,
            v=burgers.v,
            A_width=micro.A,
            W_anchor=W_anchor,
            U0=float(U0),
            c_f=c_f,
        )
        rows.append(
            {
                "t_min": float(start),
                "t_max": float(stop),
                "t_star": float(np.sqrt(float(start) * float(stop))),
                "W_anchor": W_anchor,
                "A_width": micro.A,
                "A_width_stderr_naive": micro.stderr_A,
                "A_width_relative_l2": micro.relative_l2,
                "D_width_implicit": burgers.D,
                "D_width_stderr_naive": burgers.stderr_D,
                "v_width_implicit": burgers.v,
                "v_width_stderr_naive": burgers.stderr_v,
                "a_from_width_implicit": invariant["a_from_v"],
                "width_implicit_relative_l2": burgers.relative_l2,
                "log_D_v_correlation": burgers.log_parameter_correlation,
                "mean_shape_factor": c_f,
                "shape_factor_relative_std": c_f_relative_std,
                **invariant,
            }
        )
    return rows


def fit_parameter_flow(
    rows: Sequence[dict[str, float]],
    *,
    value_key: str,
) -> dict[str, float]:
    """Fit a rolling parameter to ``value = amplitude * t_star**exponent``."""

    if len(rows) < 3:
        return {
            "amplitude": float("nan"),
            "exponent": float("nan"),
            "relative_l2_log": float("nan"),
            "n_windows": int(len(rows)),
        }
    t_star = np.asarray([row["t_star"] for row in rows], dtype=float)
    values = np.asarray([row[value_key] for row in rows], dtype=float)
    valid = np.isfinite(t_star) & np.isfinite(values) & (t_star > 0) & (values > 0)
    if np.count_nonzero(valid) < 3:
        raise ValueError(f"Not enough positive rolling values for {value_key}")
    design = np.column_stack([np.ones(np.count_nonzero(valid)), np.log(t_star[valid])])
    response = np.log(values[valid])
    beta, *_ = np.linalg.lstsq(design, response, rcond=None)
    residual = response - design @ beta
    return {
        "amplitude": float(np.exp(beta[0])),
        "exponent": float(beta[1]),
        "relative_l2_log": float(
            np.linalg.norm(residual) / max(float(np.linalg.norm(response)), 1e-30)
        ),
        "n_windows": int(np.count_nonzero(valid)),
    }


def _percentile_interval(values: Sequence[float], confidence: float) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    alpha = 100.0 * (1.0 - float(confidence)) / 2.0
    return {
        "median": float(np.median(array)),
        "low": float(np.percentile(array, alpha)),
        "high": float(np.percentile(array, 100.0 - alpha)),
    }


def block_bootstrap_bridge(
    t: Array,
    width: Array,
    *,
    t_window: tuple[float, float],
    block_duration: float,
    replicates: int,
    seed: int,
    confidence: float = 0.95,
) -> dict[str, object]:
    """Moving physical-time block bootstrap for the moment bridge.

    Entire observed ``(t,W)`` pairs are resampled in contiguous blocks.  The
    relation fits are order-independent; sorting the sampled pairs restores a
    valid anchor for the implicit Burgers law while repeated blocks retain
    their bootstrap multiplicity.
    """

    if block_duration <= 0 or replicates <= 0:
        raise ValueError("block_duration and replicates must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must lie between zero and one")
    tw, ww = _windowed(t, width, t_window)
    original_micro = fit_micro_amplitude(tw, ww, t_window=t_window)
    original_burgers = fit_burgers_width_ode(tw, ww, t_window=t_window)
    median_dt = float(np.median(np.diff(np.unique(tw))))
    if median_dt <= 0:
        raise ValueError("Bootstrap requires at least two unique times")
    block_size = max(2, int(round(float(block_duration) / median_dt)))
    n = tw.size
    starts = np.arange(0, n, block_size, dtype=int)
    blocks = [np.arange(start, min(start + block_size, n)) for start in starts]
    blocks_needed = int(np.ceil(n / block_size))
    rng = np.random.default_rng(int(seed))

    collected: dict[str, list[float]] = {
        "A": [],
        "D": [],
        "v": [],
        "A_bridge_over_A": [],
        "W_star": [],
    }
    rejected = 0
    for _ in range(int(replicates)):
        chosen = rng.integers(0, len(blocks), size=blocks_needed)
        indices = np.concatenate([blocks[index] for index in chosen])[:n]
        order = np.argsort(tw[indices], kind="stable")
        sampled_t = tw[indices][order]
        sampled_width = ww[indices][order]
        try:
            micro = fit_micro_amplitude(
                sampled_t,
                sampled_width,
                t_window=(float(sampled_t[0]), float(sampled_t[-1])),
            )
            burgers = fit_burgers_width_ode(
                sampled_t,
                sampled_width,
                t_window=(float(sampled_t[0]), float(sampled_t[-1])),
                initial=(original_burgers.D, original_burgers.v),
            )
            A_bridge = 2.0 * np.sqrt(burgers.D * burgers.v)
            collected["A"].append(micro.A)
            collected["D"].append(burgers.D)
            collected["v"].append(burgers.v)
            collected["A_bridge_over_A"].append(A_bridge / micro.A)
            collected["W_star"].append(burgers.D / burgers.v)
        except (ValueError, FloatingPointError):
            rejected += 1

    accepted = int(replicates) - rejected
    if accepted < max(10, int(0.5 * replicates)):
        raise RuntimeError("Too few accepted bridge bootstrap replicates")
    return {
        "confidence": float(confidence),
        "block_duration": float(block_duration),
        "block_size_observations": int(block_size),
        "requested_replicates": int(replicates),
        "accepted_replicates": accepted,
        "rejected_replicates": int(rejected),
        **{
            key: _percentile_interval(values, confidence)
            for key, values in collected.items()
        },
    }
