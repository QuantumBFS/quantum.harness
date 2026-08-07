"""Public Delta=1 versus Delta=2 scalar-surrogate control comparison."""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from .synthetic_data import Dataset
from .tension_resolution import (
    WeakFit,
    fit_power_exponent,
    fit_profiled_weak,
    forecast_error,
    forecast_profile,
    front_width_series,
)


def _fit_and_self_forecast(
    dataset: Dataset,
    *,
    fit_window: tuple[float, float],
    x_crop: tuple[float, float],
    width_window: tuple[float, float],
    dt_internal: float,
) -> tuple[WeakFit, dict[str, float], dict[str, float]]:
    fit = fit_profiled_weak(
        dataset.x,
        dataset.t,
        dataset.u,
        t_window=fit_window,
        x_crop=x_crop,
        gamma=0.0,
    )
    relative_t = dataset.t - dataset.t[0]
    prediction = forecast_profile(
        dataset.x,
        relative_t,
        dataset.u[0],
        fit=fit,
        absolute_start_time=float(dataset.t[0]),
        dt_internal=dt_internal,
    )
    error = forecast_error(prediction, dataset.u, dataset.x, x_crop=x_crop)
    front = front_width_series(
        dataset.x,
        dataset.t,
        dataset.u,
        x_crop=x_crop,
    )
    width_fit = fit_power_exponent(
        dataset.t,
        front["width"],
        t_min=width_window[0],
        t_max=width_window[1],
    )
    return fit, error, width_fit


def _transfer(
    source_fit: WeakFit,
    target: Dataset,
    *,
    x_crop: tuple[float, float],
    dt_internal: float,
) -> dict[str, float]:
    prediction = forecast_profile(
        target.x,
        target.t - target.t[0],
        target.u[0],
        fit=source_fit,
        absolute_start_time=float(target.t[0]),
        dt_internal=dt_internal,
    )
    return forecast_error(prediction, target.u, target.x, x_crop=x_crop)


def compare_public_environment_controls(
    delta1: Dataset,
    delta2: Dataset,
    *,
    fit_window: tuple[float, float] = (52.0, 198.0),
    width_window: tuple[float, float] = (80.0, 190.0),
    x_crop: tuple[float, float] = (-120.0, 120.0),
    dt_internal: float = 0.02,
) -> dict[str, object]:
    """Fit each environment locally and exchange coefficients without refit."""

    fit1, self1, width1 = _fit_and_self_forecast(
        delta1,
        fit_window=fit_window,
        x_crop=x_crop,
        width_window=width_window,
        dt_internal=dt_internal,
    )
    fit2, self2, width2 = _fit_and_self_forecast(
        delta2,
        fit_window=fit_window,
        x_crop=x_crop,
        width_window=width_window,
        dt_internal=dt_internal,
    )
    one_to_two = _transfer(
        fit1,
        delta2,
        x_crop=x_crop,
        dt_internal=dt_internal,
    )
    two_to_one = _transfer(
        fit2,
        delta1,
        x_crop=x_crop,
        dt_internal=dt_internal,
    )
    return {
        "schema_version": 1,
        "fit_window": list(fit_window),
        "width_window": list(width_window),
        "x_crop": list(x_crop),
        "delta1": {
            "fit": asdict(fit1),
            "self_forecast": self1,
            "width_power": width1,
        },
        "delta2": {
            "fit": asdict(fit2),
            "self_forecast": self2,
            "width_power": width2,
        },
        "transfer": {
            "delta1_coefficients_on_delta2": one_to_two,
            "delta2_coefficients_on_delta1": two_to_one,
            "delta1_to_delta2_error_ratio": (
                one_to_two["integrated_relative_l2"]
                / max(self2["integrated_relative_l2"], 1e-30)
            ),
            "delta2_to_delta1_error_ratio": (
                two_to_one["integrated_relative_l2"]
                / max(self1["integrated_relative_l2"], 1e-30)
            ),
        },
        "coefficient_ratios": {
            "a_delta1_over_delta2": fit1.a / fit2.a,
            "D_delta1_over_delta2": fit1.D0 / fit2.D0,
        },
        "interpretation": (
            "A constant Burgers surrogate can be locally accurate in both "
            "environments while its coefficients and width exponent are not "
            "transferable. Local fit quality alone is therefore not evidence "
            "for a microscopic universal scalar law or for KPZ scaling."
        ),
    }
