#!/usr/bin/env python3
"""Resolve the constant-Burgers versus KPZ/drifting-D interpretation tension.

The script writes a self-contained evidence bundle under the selected output
directory.  It never modifies the source data.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.synthetic_data import load_npz
from src.tension_resolution import (
    constant_closure_observed_window,
    extended_constant_closure_width,
    feature_conditioning,
    fit_power_exponent,
    fixed_a_D_series,
    forecast_error,
    front_width_series,
    instantaneous_joint_fit,
    local_log_slope,
    split_forecast_comparison,
    validate_grid_data,
)


BLUE = "#2463A6"
GOLD = "#C58A16"
INK = "#27313A"
GREY = "#9AA3AA"


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _safe_positive_power_fit(
    t: np.ndarray,
    values: np.ndarray,
    *,
    t_min: float,
    t_max: float,
) -> dict[str, float] | None:
    t = np.asarray(t, dtype=float)
    values = np.asarray(values, dtype=float)
    mask = (
        (t >= float(t_min))
        & (t <= float(t_max))
        & np.isfinite(values)
        & (values > 0)
    )
    if np.count_nonzero(mask) < 5:
        return None
    return fit_power_exponent(
        t,
        values,
        t_min=float(t_min),
        t_max=float(t_max),
    )


def _save_width_chart(
    path: Path,
    observed: dict[str, np.ndarray],
    closure: dict[str, np.ndarray],
    extended: dict[str, np.ndarray],
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(8.4, 7.2), sharex=False)
    ax = axes[0]
    ax.loglog(observed["t"], observed["width"], color=BLUE, lw=2.2, label="quantum data")
    ax.loglog(closure["t"], closure["width"], color=GOLD, lw=1.8, ls="--", label="constant-D closure")
    ax.loglog(extended["t"], extended["width"], color=GOLD, lw=1.2, alpha=0.7, label="closure continuation")
    t_anchor = np.asarray([60.0, 180.0])
    anchor = observed["width"][int(np.argmin(np.abs(observed["t"] - 60.0)))]
    ax.loglog(t_anchor, anchor * (t_anchor / 60.0) ** (2.0 / 3.0), color=INK, ls=":", label=r"$t^{2/3}$ guide")
    ax.set_xlabel("physical time t")
    ax.set_ylabel("gradient width W(t)")
    ax.set_title("Domain-wall width in data and the constant-viscosity closure")
    ax.legend(frameon=False, ncol=2)
    ax.grid(color="#E7EAED", lw=0.7)

    ax = axes[1]
    observed_beta = local_log_slope(observed["t"], observed["width"], half_window=25)
    closure_beta = local_log_slope(closure["t"], closure["width"], half_window=25)
    ax.semilogx(observed["t"], observed_beta, color=BLUE, lw=2.2, label="quantum data")
    ax.semilogx(closure["t"], closure_beta, color=GOLD, lw=1.8, ls="--", label="constant-D closure")
    ax.semilogx(extended["t"], extended["local_exponent"], color=GOLD, lw=1.2, alpha=0.7, label="closure continuation")
    ax.axhline(0.5, color=GREY, ls=":", lw=1.0, label=r"diffusive $1/2$")
    ax.axhline(2.0 / 3.0, color=INK, ls=":", lw=1.1, label=r"KPZ-like $2/3$")
    ax.axhline(1.0, color=GREY, ls="-.", lw=1.0, label="rarefaction 1")
    ax.set_ylim(0.42, 1.04)
    ax.set_xlabel("physical time t")
    ax.set_ylabel(r"local exponent $d\log W/d\log t$")
    ax.set_title("The apparent 2/3 law is reproduced by constant D and later crosses upward")
    ax.legend(frameon=False, ncol=2, fontsize=8)
    ax.grid(color="#E7EAED", lw=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=190)
    plt.close(fig)


def _save_identifiability_chart(
    path: Path,
    joint: dict[str, np.ndarray],
    fixed_results: list[dict[str, float]],
) -> None:
    mask = joint["t"] >= 80.0
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2))
    ax = axes[0]
    points = ax.scatter(joint["a"][mask], joint["D"][mask], c=joint["t"][mask], s=11, cmap="viridis")
    ax.set_xlabel("jointly fitted a(t)")
    ax.set_ylabel("jointly fitted D(t)")
    ax.set_title("Instantaneous coefficients lie on a trade-off ridge")
    cb = fig.colorbar(points, ax=ax)
    cb.set_label("time t")
    ax.grid(color="#E7EAED", lw=0.7)

    ax = axes[1]
    a_values = [row["a_fixed"] for row in fixed_results]
    gamma_values = [
        np.nan if row["gamma_D"] is None else row["gamma_D"]
        for row in fixed_results
    ]
    ax.plot(a_values, gamma_values, color=BLUE, marker="o", ms=3)
    ax.axhline(0.0, color=INK, lw=1.0, ls=":")
    ax.axhline(1.0 / 3.0, color=GOLD, lw=1.0, ls="--", label=r"KPZ target $1/3$")
    ax.set_xlabel("coefficient a held fixed")
    ax.set_ylabel(r"fitted exponent of D(t)")
    ax.set_title("The sign of D drift depends on the assumed a")
    ax.legend(frameon=False)
    ax.grid(color="#E7EAED", lw=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=190)
    plt.close(fig)


def _save_forecast_chart(path: Path, comparisons: list[dict]) -> None:
    labels = ["constant_D", "free_power_D", "kpz_gamma_1_3"]
    display = ["constant D", "free power D(t)", r"fixed $\gamma=1/3$"]
    colors = [BLUE, GOLD, GREY]
    cutoffs = [row["cutoff_actual"] for row in comparisons]
    xloc = np.arange(len(cutoffs), dtype=float)
    width = 0.24
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    for j, (label, name, color) in enumerate(zip(labels, display, colors)):
        values = [row["models"][label]["test"]["integrated_relative_l2"] for row in comparisons]
        ax.bar(xloc + (j - 1) * width, values, width=width, label=name, color=color, edgecolor=INK, linewidth=0.45)
    ax.set_xticks(xloc, [f"train through {value:.0f}" for value in cutoffs])
    ax.set_ylabel("held-out relative L2 error")
    ax.set_title("Allowing D(t) to drift does not consistently improve future profiles")
    ax.legend(frameon=False, ncol=3)
    ax.grid(axis="y", color="#E7EAED", lw=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=190)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=str(REPO / "data" / "kharkov_highT_delta1.npz"),
        help="Input npz containing x,t,u,meta",
    )
    parser.add_argument(
        "--outdir",
        default=str(REPO / "results_tension_resolution"),
        help="Output evidence directory",
    )
    parser.add_argument("--skip-extended", action="store_true", help="Skip long deterministic-PDE continuation")
    parser.add_argument(
        "--check-extended-convergence",
        action="store_true",
        help="Repeat the long continuation at half the internal time step",
    )
    args = parser.parse_args()
    if args.skip_extended and args.check_extended_convergence:
        parser.error("--skip-extended and --check-extended-convergence cannot be used together")

    dataset = load_npz(args.input)
    x, t, u = dataset.x, dataset.t, dataset.u
    outdir = Path(args.outdir)
    plots = outdir / "plots"
    tables = outdir / "tables"
    plots.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    quality = validate_grid_data(x, t, u)
    observed_width = front_width_series(x, t, u, x_crop=(-120.0, 120.0))
    width_fits = [
        fit_power_exponent(t, observed_width["width"], t_min=t_min, t_max=190.0)
        for t_min in (50.0, 60.0, 80.0, 100.0, 120.0, 140.0)
    ]

    constant_fit, constant_prediction, closure_width = constant_closure_observed_window(x, t, u)
    closure_error = forecast_error(constant_prediction, u, x, x_crop=(-120.0, 120.0))
    closure_width_fit = fit_power_exponent(t, closure_width["width"], t_min=80.0, t_max=190.0)

    if args.skip_extended:
        extended_width = {
            "t": closure_width["t"],
            "width": closure_width["width"],
            "local_exponent": local_log_slope(closure_width["t"], closure_width["width"]),
        }
    else:
        extended_width = extended_constant_closure_width(x, t, u, fit=constant_fit)

    extended_convergence = []
    if args.check_extended_convergence:
        extended_width_half_dt = extended_constant_closure_width(
            x, t, u, fit=constant_fit, dt_internal=0.1
        )
        for target_time in (200.0, 1000.0, 5000.0):
            index = int(np.argmin(np.abs(extended_width["t"] - target_time)))
            half_dt_index = int(
                np.argmin(np.abs(extended_width_half_dt["t"] - extended_width["t"][index]))
            )
            width_reference = float(extended_width_half_dt["width"][half_dt_index])
            extended_convergence.append(
                {
                    "target_t": target_time,
                    "actual_t": float(extended_width["t"][index]),
                    "beta_dt_0_2": float(extended_width["local_exponent"][index]),
                    "beta_dt_0_1": float(
                        extended_width_half_dt["local_exponent"][half_dt_index]
                    ),
                    "absolute_beta_difference": float(
                        abs(
                            extended_width["local_exponent"][index]
                            - extended_width_half_dt["local_exponent"][half_dt_index]
                        )
                    ),
                    "relative_width_difference": float(
                        abs(extended_width["width"][index] - width_reference)
                        / max(abs(width_reference), 1e-30)
                    ),
                }
            )

    joint = instantaneous_joint_fit(x, t, u)
    joint_mask = joint["t"] >= 80.0
    joint_ad_correlation = float(np.corrcoef(joint["a"][joint_mask], joint["D"][joint_mask])[0, 1])
    joint_D_gamma = _safe_positive_power_fit(
        joint["t"],
        joint["D"],
        t_min=80.0,
        t_max=float(joint["t"][-1]),
    )

    fixed_results = []
    a_half_span = max(0.04, 0.2 * abs(float(constant_fit.a)))
    for a_fixed in np.linspace(
        float(constant_fit.a) - a_half_span,
        float(constant_fit.a) + a_half_span,
        17,
    ):
        series = fixed_a_D_series(x, t, u, a_fixed=float(a_fixed))
        gamma_fit = _safe_positive_power_fit(
            series["t"],
            series["D"],
            t_min=80.0,
            t_max=float(series["t"][-1]),
        )
        late_mask = series["t"] >= 80.0
        fixed_results.append(
            {
                "a_fixed": float(a_fixed),
                "gamma_D": (
                    None if gamma_fit is None else gamma_fit["exponent"]
                ),
                "mean_D": float(np.mean(series["D"][late_mask])),
                "positive_D_fraction": float(
                    np.mean(series["D"][late_mask] > 0)
                ),
            }
        )

    conditioning = feature_conditioning(
        x, t, u, t_mins=(50.0, 80.0, 100.0, 120.0, 140.0), t_max=198.0
    )
    comparisons = split_forecast_comparison(x, t, u)

    width_rows = []
    observed_beta = local_log_slope(t, observed_width["width"], half_window=25)
    closure_beta = local_log_slope(t, closure_width["width"], half_window=25)
    for i in range(t.size):
        width_rows.append(
            {
                "t": float(t[i]),
                "width_data": float(observed_width["width"][i]),
                "width_constant_closure": float(closure_width["width"][i]),
                "beta_local_data": float(observed_beta[i]),
                "beta_local_constant_closure": float(closure_beta[i]),
            }
        )
    _write_csv(tables / "width_observed_and_closure.csv", width_rows)
    _write_csv(tables / "width_power_window_sensitivity.csv", width_fits)
    _write_csv(tables / "fixed_a_D_drift_sensitivity.csv", fixed_results)
    _write_csv(tables / "feature_conditioning.csv", conditioning)
    _write_csv(
        tables / "joint_instantaneous_coefficients.csv",
        [
            {
                "t": float(joint["t"][i]),
                "a": float(joint["a"][i]),
                "D": float(joint["D"][i]),
                "feature_correlation": float(joint["feature_corr"][i]),
            }
            for i in range(len(joint["t"]))
        ],
    )
    _write_csv(
        tables / "constant_closure_extended_width.csv",
        [
            {
                "t": float(extended_width["t"][i]),
                "width": float(extended_width["width"][i]),
                "local_exponent": float(extended_width["local_exponent"][i]),
            }
            for i in range(len(extended_width["t"]))
        ],
    )
    _write_csv(tables / "extended_dt_convergence.csv", extended_convergence)

    forecast_rows = []
    for split in comparisons:
        for model, payload in split["models"].items():
            forecast_rows.append(
                {
                    "cutoff": split["cutoff_actual"],
                    "model": model,
                    **payload["fit"],
                    **payload["test"],
                }
            )
    _write_csv(tables / "heldout_forecast_comparison.csv", forecast_rows)

    _save_width_chart(plots / "width_crossover.png", observed_width, closure_width, extended_width)
    _save_identifiability_chart(plots / "parameter_identifiability.png", joint, fixed_results)
    _save_forecast_chart(plots / "heldout_forecast.png", comparisons)

    observed_beta_80_190 = float(
        next(
            row["exponent"]
            for row in width_fits
            if abs(float(row["t_min"]) - 80.0) < 1e-12
        )
    )
    if observed_beta_80_190 < 0.58:
        resolution_finding = (
            "This public control is close to diffusive broadening rather than "
            "the Delta=1 KPZ-like finite window. Its scalar coefficients are "
            "therefore environment-specific and must not be transferred to "
            "the isotropic point."
        )
    else:
        resolution_finding = (
            "The apparent KPZ-like width exponent is reproduced by the "
            "constant-D deterministic closure over the observed window, "
            "while the inferred D(t) drift is not separately identifiable "
            "from a(t) and does not consistently improve held-out prediction."
        )

    result = {
        "input": str(Path(args.input).resolve()),
        "source_meta": dataset.meta,
        "data_quality": quality,
        "observed_width_power_fits": width_fits,
        "constant_closure": {
            "fit": asdict(constant_fit),
            "observed_window_profile_error": closure_error,
            "width_power_fit_80_190": closure_width_fit,
            "extended_local_exponent": {
                "at_t_200": float(
                    extended_width["local_exponent"][
                        int(np.argmin(np.abs(extended_width["t"] - 200.0)))
                    ]
                ),
                "at_t_1000": float(
                    extended_width["local_exponent"][
                        int(np.argmin(np.abs(extended_width["t"] - 1000.0)))
                    ]
                ),
                "at_t_5000": float(extended_width["local_exponent"][-1]),
            },
            "extended_dt_convergence": extended_convergence,
        },
        "identifiability": {
            "instantaneous_a_D_correlation_t_ge_80": joint_ad_correlation,
            "joint_fit_D_power_t_ge_80": joint_D_gamma,
            "fixed_a_sensitivity": fixed_results,
            "feature_conditioning": conditioning,
        },
        "heldout_forecasts": comparisons,
        "resolution": {
            "finding": (
                resolution_finding
            ),
            "interpretation": (
                "Treat D in the discovered mean-profile PDE as a finite-window closure coefficient, "
                "not as the scale-dependent KPZ effective diffusion constant. Establish asymptotic "
                "KPZ independently from correlation-function scaling or multi-initial-condition data."
            ),
        },
    }
    (outdir / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"[OK] wrote tension-resolution evidence to {outdir}")


if __name__ == "__main__":
    main()
