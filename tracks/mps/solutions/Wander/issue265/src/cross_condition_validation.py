"""Shared-parameter, symmetry, and cross-condition Burgers tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np

from .analytic_mechanism import front_linear_response_diagnostics
from .research_dataset import ResearchDataset
from .synthetic_data import solve_burgers_spectral_rk4
from .tension_resolution import (
    WeakFit,
    _weak_design,
    fit_power_exponent,
    fit_profiled_weak,
    forecast_error,
    forecast_profile,
    front_width_series,
)


Array = np.ndarray


@dataclass(frozen=True)
class SharedBurgersFit:
    a: float
    D: float
    covariance: Array
    correlation: float
    condition_number: float
    mse: float
    n_obs: int
    condition_residual_mse: dict[str, float]
    included_condition_ids: tuple[str, ...]
    train_window: tuple[float, float]

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["covariance"] = self.covariance.tolist()
        return result


@dataclass(frozen=True)
class SectorAmplitudeFit:
    g: float
    D: float
    covariance: Array
    correlation: float
    condition_number: float
    mse: float
    n_obs: int
    condition_residual_mse: dict[str, float]
    included_condition_ids: tuple[str, ...]
    train_window: tuple[float, float]

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["covariance"] = self.covariance.tolist()
        return result


def relative_l2(observed: Array, reference: Array) -> float:
    observed = np.asarray(observed, dtype=float)
    reference = np.asarray(reference, dtype=float)
    if observed.shape != reference.shape:
        raise ValueError("relative_l2 arrays must have equal shape")
    return float(
        np.linalg.norm(observed - reference)
        / max(float(np.linalg.norm(reference)), 1e-30)
    )


def solve_scalar_forecast(
    x: Array,
    t: Array,
    u0: Array,
    *,
    a: float,
    D: float,
    dt_internal: float = 0.005,
) -> Array:
    """Solve the constant-coefficient scalar competitor."""

    if D <= 0:
        raise ValueError("D must be positive")
    return solve_burgers_spectral_rk4(
        x=np.asarray(x, dtype=float),
        t=np.asarray(t, dtype=float),
        a=float(a),
        D_of_t=lambda _: float(D),
        u0=np.asarray(u0, dtype=float),
        dt_internal=dt_internal,
    )


def _normalized_design(
    dataset: ResearchDataset,
    *,
    train_window: tuple[float, float],
    x_crop: tuple[float, float],
) -> tuple[Array, Array, Array]:
    response, nonlinear, diffusion, _ = _weak_design(
        dataset.x,
        dataset.t,
        dataset.u,
        t_window=train_window,
        x_crop=x_crop,
    )
    # Equalize conditions rather than raw rows.  Multiplication by sqrt(n)
    # makes the block response have unit RMS, so denser output grids do not
    # receive larger aggregate weight solely because they contain more rows.
    scale = np.sqrt(response.size) / max(float(np.linalg.norm(response)), 1e-30)
    return response * scale, nonlinear * scale, diffusion * scale


def _solve_joint(
    datasets: Sequence[ResearchDataset],
    *,
    train_window: tuple[float, float],
    x_crop: tuple[float, float],
    sector_law: bool,
) -> tuple[Array, Array, float, float, dict[str, float], int]:
    if len(datasets) < 2:
        raise ValueError("A shared fit requires at least two conditions")
    ids = [dataset.condition_id for dataset in datasets]
    if len(set(ids)) != len(ids):
        raise ValueError("condition_id values must be unique")
    blocks: list[tuple[str, Array, Array]] = []
    for dataset in datasets:
        response, nonlinear, diffusion = _normalized_design(
            dataset,
            train_window=train_window,
            x_crop=x_crop,
        )
        if sector_law:
            mu = float(dataset.metadata["mu"])
            orientation = int(dataset.metadata["orientation"])
            nonlinear = 2.0 * orientation * mu * nonlinear
        design = np.column_stack([nonlinear, diffusion])
        blocks.append((dataset.condition_id, response, design))

    y = np.concatenate([block[1] for block in blocks])
    X = np.vstack([block[2] for block in blocks])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    residual = y - X @ beta
    dof = max(y.size - 2, 1)
    covariance = float(residual @ residual / dof) * np.linalg.pinv(X.T @ X)
    denominator = np.sqrt(
        max(float(covariance[0, 0]), 0.0)
        * max(float(covariance[1, 1]), 0.0)
    )
    correlation = (
        float(covariance[0, 1] / denominator) if denominator > 0 else 0.0
    )
    condition_residuals: dict[str, float] = {}
    for condition_id, response, design in blocks:
        condition_residuals[condition_id] = float(
            np.mean((response - design @ beta) ** 2)
        )
    return (
        beta,
        covariance,
        correlation,
        float(np.linalg.cond(X)),
        condition_residuals,
        int(y.size),
    )


def fit_shared_burgers(
    datasets: Sequence[ResearchDataset],
    *,
    train_window: tuple[float, float],
    x_crop: tuple[float, float],
) -> SharedBurgersFit:
    """Fit one constant ``a,D`` to all conditions with equal condition weight."""

    beta, covariance, correlation, condition_number, residuals, n_obs = (
        _solve_joint(
            datasets,
            train_window=train_window,
            x_crop=x_crop,
            sector_law=False,
        )
    )
    return SharedBurgersFit(
        a=float(beta[0]),
        D=float(beta[1]),
        covariance=covariance,
        correlation=correlation,
        condition_number=condition_number,
        mse=float(np.mean(list(residuals.values()))),
        n_obs=n_obs,
        condition_residual_mse=residuals,
        included_condition_ids=tuple(
            dataset.condition_id for dataset in datasets
        ),
        train_window=(float(train_window[0]), float(train_window[1])),
    )


def fit_sector_amplitude_law(
    datasets: Sequence[ResearchDataset],
    *,
    train_window: tuple[float, float],
    x_crop: tuple[float, float],
) -> SectorAmplitudeFit:
    """Fit ``a_i=2 orientation_i g mu_i`` with one shared ``D``."""

    beta, covariance, correlation, condition_number, residuals, n_obs = (
        _solve_joint(
            datasets,
            train_window=train_window,
            x_crop=x_crop,
            sector_law=True,
        )
    )
    return SectorAmplitudeFit(
        g=float(beta[0]),
        D=float(beta[1]),
        covariance=covariance,
        correlation=correlation,
        condition_number=condition_number,
        mse=float(np.mean(list(residuals.values()))),
        n_obs=n_obs,
        condition_residual_mse=residuals,
        included_condition_ids=tuple(
            dataset.condition_id for dataset in datasets
        ),
        train_window=(float(train_window[0]), float(train_window[1])),
    )


def fit_condition_specific(
    datasets: Sequence[ResearchDataset],
    *,
    train_window: tuple[float, float],
    x_crop: tuple[float, float],
) -> dict[str, WeakFit]:
    """Fit independent local surrogates, which do not test universality."""

    return {
        dataset.condition_id: fit_profiled_weak(
            dataset.x,
            dataset.t,
            dataset.u,
            t_window=train_window,
            x_crop=x_crop,
            gamma=0.0,
        )
        for dataset in datasets
    }


def rolling_shared_fits(
    datasets: Sequence[ResearchDataset],
    *,
    windows: Sequence[tuple[float, float]],
    x_crop: tuple[float, float],
) -> list[dict[str, float | int]]:
    """Fit the shared scalar coefficients on every available rolling window."""

    rows: list[dict[str, float | int]] = []
    for window in windows:
        if any(
            dataset.t[0] > window[0] or dataset.t[-1] < window[1]
            for dataset in datasets
        ):
            continue
        fit = fit_shared_burgers(
            datasets,
            train_window=window,
            x_crop=x_crop,
        )
        rows.append(
            {
                "t_min": float(window[0]),
                "t_max": float(window[1]),
                "t_center": 0.5 * float(window[0] + window[1]),
                "a": fit.a,
                "D": fit.D,
                "mse": fit.mse,
                "condition_number": fit.condition_number,
                "n_obs": fit.n_obs,
            }
        )
    return rows


def _bootstrap_design_blocks(
    dataset: ResearchDataset,
    *,
    train_window: tuple[float, float],
    x_crop: tuple[float, float],
    block_duration: float,
) -> tuple[Array, Array, Array, Array]:
    response, nonlinear, diffusion, row_time = _weak_design(
        dataset.x,
        dataset.t,
        dataset.u,
        t_window=train_window,
        x_crop=x_crop,
    )
    block = np.floor(
        (row_time - float(train_window[0])) / float(block_duration)
    ).astype(int)
    return response, nonlinear, diffusion, block


def bootstrap_shared_burgers(
    datasets: Sequence[ResearchDataset],
    *,
    train_window: tuple[float, float],
    x_crop: tuple[float, float],
    block_duration: float,
    n_replicates: int,
    seed: int,
    sector_law: bool = False,
) -> dict[str, object]:
    """Synchronous physical-time block bootstrap across all conditions."""

    if block_duration <= 0 or n_replicates < 10:
        raise ValueError("Bootstrap duration must be positive and replicates >= 10")
    prepared = [
        (
            dataset,
            *_bootstrap_design_blocks(
                dataset,
                train_window=train_window,
                x_crop=x_crop,
                block_duration=block_duration,
            ),
        )
        for dataset in datasets
    ]
    rng = np.random.default_rng(int(seed))
    samples = np.empty((n_replicates, 2), dtype=float)
    for replicate in range(n_replicates):
        responses: list[Array] = []
        designs: list[Array] = []
        for dataset, response, nonlinear, diffusion, block in prepared:
            unique_blocks = np.unique(block)
            sampled_blocks = rng.choice(
                unique_blocks,
                size=unique_blocks.size,
                replace=True,
            )
            indices = np.concatenate(
                [np.flatnonzero(block == value) for value in sampled_blocks]
            )
            y = response[indices]
            nonlinear_column = nonlinear[indices]
            diffusion_column = diffusion[indices]
            scale = np.sqrt(y.size) / max(float(np.linalg.norm(y)), 1e-30)
            if sector_law:
                nonlinear_column = (
                    2.0
                    * int(dataset.metadata["orientation"])
                    * float(dataset.metadata["mu"])
                    * nonlinear_column
                )
            responses.append(y * scale)
            designs.append(
                np.column_stack(
                    [nonlinear_column * scale, diffusion_column * scale]
                )
            )
        y_all = np.concatenate(responses)
        X_all = np.vstack(designs)
        samples[replicate], *_ = np.linalg.lstsq(
            X_all, y_all, rcond=None
        )
    covariance = np.cov(samples, rowvar=False, ddof=1)
    low, high = np.quantile(samples, [0.025, 0.975], axis=0)
    denominator = np.sqrt(
        max(float(covariance[0, 0]), 0.0)
        * max(float(covariance[1, 1]), 0.0)
    )
    return {
        "parameter_names": ["g" if sector_law else "a", "D"],
        "n_replicates": int(n_replicates),
        "block_duration": float(block_duration),
        "seed": int(seed),
        "samples": samples,
        "covariance": covariance,
        "correlation": (
            float(covariance[0, 1] / denominator) if denominator > 0 else 0.0
        ),
        "interval_95": {
            ("g" if sector_law else "a"): [
                float(low[0]),
                float(high[0]),
            ],
            "D": [float(low[1]), float(high[1])],
        },
    }


def coefficient_heterogeneity(
    shared: SharedBurgersFit,
    specific: dict[str, WeakFit],
) -> dict[str, float | dict[str, float]]:
    """Summarize condition-to-condition coefficient dispersion."""

    if not specific:
        raise ValueError("At least one condition-specific fit is required")
    coefficients = np.array(
        [[fit.a, fit.D0] for fit in specific.values()], dtype=float
    )
    means = np.mean(coefficients, axis=0)
    relative_spreads = np.std(coefficients, axis=0) / np.maximum(
        np.abs(means), 1e-30
    )
    covariance = np.asarray(shared.covariance, dtype=float)
    inverse = np.linalg.pinv(covariance)
    distances: dict[str, float] = {}
    for condition_id, fit in specific.items():
        delta = np.array([fit.a - shared.a, fit.D0 - shared.D])
        distances[condition_id] = float(np.sqrt(max(delta @ inverse @ delta, 0.0)))
    return {
        "a_relative_spread": float(relative_spreads[0]),
        "D_relative_spread": float(relative_spreads[1]),
        "max_relative_spread": float(np.max(relative_spreads)),
        "a_D_across_condition_correlation": (
            float(np.corrcoef(coefficients.T)[0, 1])
            if coefficients.shape[0] > 1
            else 0.0
        ),
        "max_mahalanobis_to_shared": max(distances.values()),
        "mahalanobis_to_shared": distances,
    }


def superposition_power_law(
    triplets: Sequence[
        tuple[float, ResearchDataset, ResearchDataset, ResearchDataset]
    ],
    *,
    t_window: tuple[float, float],
) -> dict[str, object]:
    """Fit the physical-magnetization superposition defect versus ``mu``."""

    if len(triplets) < 2:
        raise ValueError("At least two amplitudes are needed for a power law")
    amplitudes: list[float] = []
    defects: list[float] = []
    for mu, combined, first, second in triplets:
        if mu <= 0:
            raise ValueError("mu must be positive")
        series = superposition_defect(combined, first, second)
        mask = (combined.t >= t_window[0]) & (combined.t <= t_window[1])
        if np.count_nonzero(mask) < 2:
            raise ValueError("Superposition window is too small")
        amplitudes.append(float(mu))
        defects.append(float(np.mean(series[mask])))
    design = np.column_stack(
        [np.ones(len(amplitudes)), np.log(np.asarray(amplitudes))]
    )
    beta, *_ = np.linalg.lstsq(design, np.log(np.asarray(defects)), rcond=None)
    return {
        "mu": amplitudes,
        "mean_defect": defects,
        "amplitude": float(np.exp(beta[0])),
        "exponent": float(beta[1]),
        "t_window": [float(t_window[0]), float(t_window[1])],
    }


def spin_flip_defect(up: ResearchDataset, down: ResearchDataset) -> Array:
    """Return the time-resolved microscopic spin-flip equivariance defect."""

    if up.u.shape != down.u.shape or not np.allclose(up.x, down.x) or not np.allclose(
        up.t, down.t
    ):
        raise ValueError("Spin-flip pair must share the same grid")
    numerator = np.linalg.norm(down.u + up.u, axis=1)
    denominator = np.maximum(np.linalg.norm(up.u, axis=1), 1e-30)
    return numerator / denominator


def parity_defect(dataset: ResearchDataset) -> Array:
    """Return the defect from antisymmetry under reflection about x=0."""

    if not np.allclose(dataset.x, -dataset.x[::-1]):
        raise ValueError("Parity audit requires a reflection-symmetric grid")
    numerator = np.linalg.norm(dataset.u + dataset.u[:, ::-1], axis=1)
    denominator = np.maximum(np.linalg.norm(dataset.u, axis=1), 1e-30)
    return numerator / denominator


def superposition_defect(
    combined: ResearchDataset,
    first: ResearchDataset,
    second: ResearchDataset,
) -> Array:
    """Return the time-resolved weak-amplitude superposition defect."""

    if (
        combined.u.shape != first.u.shape
        or combined.u.shape != second.u.shape
        or not np.allclose(combined.x, first.x)
        or not np.allclose(combined.x, second.x)
        or not np.allclose(combined.t, first.t)
        or not np.allclose(combined.t, second.t)
    ):
        raise ValueError("Superposition datasets must share one grid")
    numerator = np.linalg.norm(combined.u - first.u - second.u, axis=1)
    denominator = np.maximum(
        np.linalg.norm(first.u, axis=1) + np.linalg.norm(second.u, axis=1),
        1e-30,
    )
    return numerator / denominator


def _moment_forecast_errors(
    dataset: ResearchDataset,
    prediction: Array,
    *,
    start_index: int,
    x_crop: tuple[float, float],
) -> dict[str, float]:
    orientation = int(dataset.metadata.get("orientation", 1))
    truth = orientation * dataset.u[start_index:]
    predicted = orientation * prediction
    t = dataset.t[start_index:]
    truth_front = front_width_series(dataset.x, t, truth, x_crop=x_crop)
    predicted_front = front_width_series(
        dataset.x, t, predicted, x_crop=x_crop
    )
    width_error = relative_l2(
        predicted_front["width"], truth_front["width"]
    )
    center_error = relative_l2(
        predicted_front["center"], truth_front["center"]
    )
    truth_variance = np.asarray(truth_front["variance"], dtype=float)
    predicted_variance = np.asarray(predicted_front["variance"], dtype=float)
    truth_dm = 0.5 * np.gradient(truth_variance, t, edge_order=2)
    predicted_dm = 0.5 * np.gradient(predicted_variance, t, edge_order=2)
    dm_error = relative_l2(predicted_dm, truth_dm)
    positive_mask = t > 0
    if np.count_nonzero(positive_mask) >= 5:
        truth_exponent = fit_power_exponent(
            t,
            np.asarray(truth_front["width"]),
            t_min=float(t[positive_mask][0]),
            t_max=float(t[-1]),
        )["exponent"]
        predicted_exponent = fit_power_exponent(
            t,
            np.asarray(predicted_front["width"]),
            t_min=float(t[positive_mask][0]),
            t_max=float(t[-1]),
        )["exponent"]
        exponent_error = float(predicted_exponent - truth_exponent)
    else:
        truth_exponent = float("nan")
        predicted_exponent = float("nan")
        exponent_error = float("nan")
    try:
        truth_cf = np.asarray(
            front_linear_response_diagnostics(
                dataset.x, t, truth, moment_smooth_window=11
            )["shape_factor"]
        )
        pred_cf = np.asarray(
            front_linear_response_diagnostics(
                dataset.x, t, predicted, moment_smooth_window=11
            )["shape_factor"]
        )
        cf_error = relative_l2(pred_cf, truth_cf)
    except ValueError:
        cf_error = float("nan")
    return {
        "width_relative_l2": width_error,
        "center_relative_l2": center_error,
        "shape_factor_relative_l2": cf_error,
        "moment_diffusivity_relative_l2": dm_error,
        "truth_width_exponent": float(truth_exponent),
        "prediction_width_exponent": float(predicted_exponent),
        "late_width_exponent_error": exponent_error,
    }


def leave_one_condition_out(
    datasets: Sequence[ResearchDataset],
    *,
    train_window: tuple[float, float],
    forecast_window: tuple[float, float],
    x_crop: tuple[float, float],
    model: str = "shared_constant",
    dt_internal: float = 0.02,
) -> list[dict[str, object]]:
    """Forecast each condition without allowing its rows into its fit."""

    results: list[dict[str, object]] = []
    for held_out in datasets:
        training = [
            dataset
            for dataset in datasets
            if dataset.condition_id != held_out.condition_id
        ]
        if model == "shared_constant":
            shared = fit_shared_burgers(
                training,
                train_window=train_window,
                x_crop=x_crop,
            )
            a, diffusion = shared.a, shared.D
            fit_payload: dict[str, object] = shared.to_dict()
        elif model == "sector_amplitude_law":
            sector = fit_sector_amplitude_law(
                training,
                train_window=train_window,
                x_crop=x_crop,
            )
            a = (
                2.0
                * int(held_out.metadata["orientation"])
                * sector.g
                * float(held_out.metadata["mu"])
            )
            diffusion = sector.D
            fit_payload = sector.to_dict()
        else:
            raise ValueError("Unknown leave-one-condition-out model")
        if held_out.condition_id in fit_payload["included_condition_ids"]:
            raise RuntimeError("Held-out condition leaked into training")

        start_index = int(
            np.argmin(np.abs(held_out.t - float(forecast_window[0])))
        )
        stop_index = int(
            np.argmin(np.abs(held_out.t - float(forecast_window[1])))
        )
        stop_index = max(stop_index, start_index + 1)
        relative_t = (
            held_out.t[start_index : stop_index + 1] - held_out.t[start_index]
        )
        weak_fit = WeakFit(
            a=float(a),
            D0=float(diffusion),
            gamma=0.0,
            mse=float(fit_payload["mse"]),
            n_obs=int(fit_payload["n_obs"]),
            t_window=train_window,
            t_ref=max(float(forecast_window[0]), 1.0),
        )
        prediction = forecast_profile(
            held_out.x,
            relative_t,
            held_out.u[start_index],
            fit=weak_fit,
            absolute_start_time=float(held_out.t[start_index]),
            dt_internal=dt_internal,
        )
        truth = held_out.u[start_index : stop_index + 1]
        profile_metrics = forecast_error(
            prediction, truth, held_out.x, x_crop=x_crop
        )
        moment_metrics = _moment_forecast_errors(
            ResearchDataset(
                condition_id=held_out.condition_id,
                x=held_out.x,
                t=held_out.t[: stop_index + 1],
                u=held_out.u[: stop_index + 1],
                metadata=held_out.metadata,
            ),
            prediction,
            start_index=start_index,
            x_crop=x_crop,
        )
        results.append(
            {
                "held_out_condition_id": held_out.condition_id,
                "model": model,
                "a": float(a),
                "D": float(diffusion),
                "training_condition_ids": list(
                    fit_payload["included_condition_ids"]
                ),
                **profile_metrics,
                **moment_metrics,
            }
        )
    return results
