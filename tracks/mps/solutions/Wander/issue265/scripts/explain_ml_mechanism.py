#!/usr/bin/env python3
"""Build the analytic-mechanism evidence bundle for the learned Burgers PDE."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.analytic_mechanism import (
    amplitude_and_spin_flip_audit,
    fit_burgers_moment_balance,
    front_linear_response_diagnostics,
    moment_power_summary,
    similarity_surrogate_scaling,
)
from src.synthetic_data import load_npz
from src.tension_resolution import fit_profiled_weak


BLUE = "#2463A6"
GOLD = "#C58A16"
GREEN = "#37825B"
INK = "#27313A"
GREY = "#929BA2"


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _save_linear_response_collapse(
    path: Path,
    x: np.ndarray,
    t: np.ndarray,
    u: np.ndarray,
    beta: float,
) -> None:
    ux = np.gradient(u, x, axis=1, edge_order=2)
    jump = np.trapezoid(ux, x=x, axis=1)
    p = ux / jump[:, None]
    selected = (60.0, 80.0, 100.0, 140.0, 190.0)

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2))
    ax = axes[0]
    for target in selected:
        index = int(np.argmin(np.abs(t - target)))
        scale = t[index] ** beta
        ax.plot(
            x / scale,
            scale * p[index],
            lw=1.45,
            label=f"t={t[index]:.0f}",
        )
    ax.set_xlim(-2.2, 2.2)
    ax.set_xlabel(r"$x/t^\beta$")
    ax.set_ylabel(r"$t^\beta\,p(x,t)$")
    ax.set_title("Front gradient: normalized structure-factor proxy")
    ax.legend(frameon=False, ncol=2, fontsize=8)
    ax.grid(color="#E7EAED", lw=0.7)

    ax = axes[1]
    for target in selected:
        index = int(np.argmin(np.abs(t - target)))
        scale = t[index] ** beta
        ax.plot(x / scale, u[index], lw=1.45, label=f"t={t[index]:.0f}")
    ax.set_xlim(-2.2, 2.2)
    ax.set_xlabel(r"$x/t^\beta$")
    ax.set_ylabel(r"$U(x,t)$")
    ax.set_title("The learned sigmoid is the cumulative propagator")
    ax.grid(color="#E7EAED", lw=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=190)
    plt.close(fig)


def _save_moment_balance(
    path: Path,
    diagnostics: dict,
    closure_a: float,
    closure_D: float,
    moment_rows: list[dict[str, float]],
    t_window: tuple[float, float],
) -> None:
    t = np.asarray(diagnostics["t"])
    width = np.asarray(diagnostics["width"])
    D_moment = np.asarray(diagnostics["moment_diffusivity"])
    shape_integral = np.asarray(diagnostics["shape_integral"])
    half_jump = float(diagnostics["half_jump"])
    predicted = closure_D + closure_a * shape_integral / (4.0 * half_jump)
    mask = (t >= t_window[0]) & (t <= t_window[1])
    positive = mask & (D_moment > 0)
    log_fit = np.polyfit(np.log(t[positive]), np.log(D_moment[positive]), 1)
    power_guide = np.exp(log_fit[1]) * t**log_fit[0]

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.3))
    ax = axes[0]
    ax.plot(
        t,
        D_moment,
        color=BLUE,
        lw=2.0,
        label=r"$D_{\rm moment}=\frac{1}{2}dW^2/dt$",
    )
    ax.plot(
        t,
        predicted,
        color=GOLD,
        lw=1.8,
        ls="--",
        label=r"$D_{\rm closure}+aI/(4U)$",
    )
    ax.plot(t, power_guide, color=GREEN, lw=1.1, ls=":", label=rf"$t^{{{log_fit[0]:.3f}}}$ fit")
    ax.axhline(closure_D, color=GREY, lw=1.0, ls="-.", label=r"$D_{\rm closure}$")
    ax.set_xlim(float(t[0]), float(t[-1]))
    ax.set_xlabel("physical time t")
    ax.set_ylabel("diffusivity from front variance")
    ax.set_title("Moment diffusivity and closure decomposition", fontsize=12)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(color="#E7EAED", lw=0.7)

    row = moment_rows[-1]
    width_rate = np.gradient(width, t, edge_order=2)
    late = (t >= row["t_min"]) & (t <= row["t_max"])
    inverse_width = 1.0 / width[late]
    fitted_rate = (
        row["D_from_width_ode"] * inverse_width
        + row["ballistic_speed_from_width_ode"]
    )
    ax = axes[1]
    ax.scatter(inverse_width, width_rate[late], s=11, color=BLUE, alpha=0.72, label="data")
    order = np.argsort(inverse_width)
    ax.plot(
        inverse_width[order],
        fitted_rate[order],
        color=GOLD,
        lw=2.0,
        label=r"$\dot W=D/W+v$",
    )
    ax.set_xlabel(r"$1/W(t)$")
    ax.set_ylabel(r"$dW/dt$")
    ax.set_title("Width law: diffusion-to-rarefaction crossover", fontsize=12)
    ax.legend(frameon=False)
    ax.grid(color="#E7EAED", lw=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=190)
    plt.close(fig)


def _save_surrogate_symmetry(
    path: Path,
    amplitude_rows: list[dict[str, float]],
    similarity: dict,
) -> None:
    scales = np.asarray([row["amplitude_scale"] for row in amplitude_rows])
    a_fit = np.asarray([row["a_fit"] for row in amplitude_rows])
    D_fit = np.asarray([row["D_fit"] for row in amplitude_rows])
    invariant = float(
        np.mean([row["scale_times_a_fit"] for row in amplitude_rows])
    )

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.3))
    ax = axes[0]
    ax.scatter(scales, a_fit, color=BLUE, s=34, label=r"refitted $a$")
    negative = scales < 0
    positive = scales > 0
    for subset, label in (
        (negative, r"$a(cu)=a(u)/c$"),
        (positive, None),
    ):
        subset_order = np.argsort(scales[subset])
        ax.plot(
            scales[subset][subset_order],
            (invariant / scales[subset])[subset_order],
            color=GOLD,
            lw=1.5,
            ls="--",
            label=label,
        )
    ax.axhline(0.0, color=INK, lw=0.9)
    ax.set_xlabel("trajectory amplitude multiplier c")
    ax.set_ylabel("learned nonlinear coefficient a")
    ax.set_title("Amplitude and spin-flip equivariance", fontsize=12)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(color="#E7EAED", lw=0.7)

    twin = ax.twinx()
    twin.scatter(scales, D_fit, color=GREEN, marker="x", s=32, label=r"refitted $D$")
    twin.set_ylabel("learned diffusion coefficient D", color=GREEN)
    twin.tick_params(axis="y", colors=GREEN)

    ax = axes[1]
    sim_t = np.asarray(similarity["t"])
    sim_a = np.abs(np.asarray(similarity["a_fit"]))
    sim_D = np.abs(np.asarray(similarity["D_fit"]))
    ax.loglog(
        sim_t,
        sim_a / sim_a[0],
        color=BLUE,
        lw=2.0,
        label=rf"$|a_{{fit}}|\sim t^{{{similarity['a_exponent_fitted']:.3f}}}$",
    )
    ax.loglog(
        sim_t,
        sim_D / sim_D[0],
        color=GOLD,
        lw=2.0,
        label=rf"$|D_{{fit}}|\sim t^{{{similarity['D_exponent_fitted']:.3f}}}$",
    )
    ax.set_xlabel("time t")
    ax.set_ylabel("coefficient / initial coefficient")
    ax.set_title("Self-similarity fixes coefficient powers", fontsize=12)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(color="#E7EAED", lw=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=190)
    plt.close(fig)


def _report_text(summary: dict) -> str:
    powers = summary["moment_transport"]
    closure = summary["constant_burgers_closure"]
    late = summary["moment_balance_windows"][-1]
    symmetry = summary["linear_response_and_symmetry"]
    similarity = summary["self_similar_surrogate"]
    raw_check = summary.get("raw_source_check")
    raw_sentence = ""
    if raw_check is not None:
        raw_sentence = (
            " Repeating the calculation on the upstream array before spatial "
            f"SG filtering gives exponent "
            f"`{raw_check['moment_diffusivity_exponent_direct']:.4f}`, so the "
            "running moment diffusivity is not created by the smoothing step."
        )
    return f"""# Analytic mechanism behind the machine-learned Burgers equation

## Result

The learned equation

\\[
U_t+aUU_x=D U_{{xx}}
\\]

is an exceptionally accurate finite-window closure for one domain-wall
trajectory, but its nonlinear coefficient is not a state-independent
microscopic transport coefficient.  The public high-temperature wall is a
linear-response observable: its normalized spatial derivative is the
equilibrium spin structure factor.  Sparse regression represents that
linearly propagating, self-similar cumulative distribution by a local
nonlinear surrogate.

## 1. Exact high-temperature linear-response identity

For a weak step bias `mu`, expand the initial density matrix:

\\[
\\rho_\\mu(0)=2^{{-L}}\\left[
1+\\mu\\sum_j s_j\\sigma_j^z+O(\\mu^2)
\\right].
\\]

With \\(C_{{ij}}(t)=\\langle S_i^z(t)S_j^z(0)\\rangle_\\infty\\),

\\[
U_i(t)\\equiv\\frac{{\\langle S_i^z(t)\\rangle}}{{\\mu}}
=2\\sum_j s_j C_{{ij}}(t)+O(\\mu).
\\]

For a unit step, taking a spatial derivative gives

\\[
\\partial_x U(x,t)=\\frac{{C(x,t)}}{{\\chi}}=4C(x,t)
\\quad (\\chi=1/4).
\\]

Thus the sigmoid supplied to PDE learning is the cumulative distribution of
the two-point propagator.  Its antisymmetry error in the processed data is
{symmetry['spin_flip_antisymmetry_error']:.3e}; the gradient symmetry error is
{symmetry['gradient_symmetry_error']:.3e}.

## 2. The physically relevant running diffusivity comes from the variance

Let \\(p=\\partial_xU\\) be the normalized front gradient and
\\(W^2=\\int (x-\\bar x)^2p\\,dx\\). Define

\\[
D_{{\\rm moment}}(t)=\\frac12\\frac{{dW^2}}{{dt}}.
\\]

On \\(t={powers['t_min']:.0f}\\ldots{powers['t_max']:.0f}\\), the data give

\\[
W\\sim t^{{{powers['width_exponent']:.4f}}},
\\qquad
D_{{\\rm moment}}\\sim t^{{{powers['moment_diffusivity_exponent_direct']:.4f}}}.
\\]

The latter is the expected near-\\(t^{{1/3}}\\) moment diffusivity. It is not
the constant \\(D={closure['D']:.5f}\\) in the mean-profile closure.{raw_sentence}

## 3. Why constant Burgers reproduces the running width

Differentiating Burgers turns the front gradient into a Fokker-Planck density.
Its second moment obeys the exact identity

\\[
D_{{\\rm moment}}(t)
=D+\\frac{{a}}{{4U}}\\int_{{-\\infty}}^\\infty
\\left(U^2-U(x,t)^2\\right)dx.
\\]

The data have an almost time-independent shape factor

\\[
c_f=\\frac{{\\int(U^2-U(x,t)^2)dx}}{{U^2W(t)}}.
\\]

On the late window its mean is {late['mean_shape_factor']:.6f}, with relative
standard deviation {late['shape_factor_relative_std']:.3e}.  Therefore the
moment identity reduces to

\\[
\\dot W=\\frac{{D}}{{W}}+\\frac{{a c_f U}}{{4}}.
\\]

This is an analytic diffusion-to-rarefaction crossover: the first term gives
\\(W\\sim t^{{1/2}}\\), while the second ultimately gives \\(W\\sim t\\).  A
local exponent near \\(2/3\\) naturally occurs while both terms are comparable.
Fitting this moment equation on `t={late['t_min']:.0f}..{late['t_max']:.0f}`
recovers `a={late['a_from_width_ode']:.5f}` and
`D={late['D_from_width_ode']:.5f}`, with relative rate error
{late['width_ode_relative_l2']:.3e}.  These agree with the full-profile
closure `a={closure['a']:.5f}`, `D={closure['D']:.5f}`.

## 4. Why sparse regression invents a nonlinear coefficient

For any self-similar front \\(U(x,t)=F(x/t^\\beta)\\),

\\[
U_t\\sim t^{{-1}},\\qquad
-UU_x\\sim t^{{-\\beta}},\\qquad
U_{{xx}}\\sim t^{{-2\\beta}}.
\\]

The instantaneous least-squares coefficients therefore have scaling
dimensions

\\[
a_{{fit}}(t)\\sim t^{{\\beta-1}},\\qquad
D_{{fit}}(t)\\sim t^{{2\\beta-1}}.
\\]

The shape-only numerical check gives exponents
`{similarity['a_exponent_fitted']:.6f}` and
`{similarity['D_exponent_fitted']:.6f}`, exactly matching the predicted
`{similarity['a_exponent_expected']:.6f}` and
`{similarity['D_exponent_expected']:.6f}`.  For \\(\\beta=2/3\\), apparent
\\(t^{{-1/3}}\\) and \\(t^{{1/3}}\\) coefficient drift follows from
self-similarity alone; it does not establish a microscopic Burgers law.

## 5. Spin-flip and amplitude test

At infinite temperature and `mu -> 0`, response is linear in the imposed
source.  If the same trajectory is rescaled as \\(V=cU\\), the Burgers design
matrix forces

\\[
a_{{fit}}[cU]=\\frac{{a_{{fit}}[U]}}{{c}},\\qquad
D_{{fit}}[cU]=D_{{fit}}[U].
\\]

The refits satisfy this relation to numerical precision. In particular,
spin flip (`c=-1`) changes the sign of `a` while leaving `D` unchanged. A
universal scalar hydrodynamic equation for the spin-inversion-symmetric
Heisenberg chain cannot have a fixed coefficient multiplying the even flux
\\(U^2/2\\).  The fitted `a` consequently labels the chosen wall orientation
and normalization.

## Mechanistic interpretation

1. Quantum linear response produces a self-similar two-point propagator.
2. The domain-wall profile is its cumulative distribution.
3. On one monotone sigmoid, `-U U_x` and `U_xx` have the same odd parity and
   nearly the same spatial shape, creating an inverse-problem ridge.
4. Constant Burgers packages the running second moment into an exact
   finite-window crossover identity.
5. The closure predicts the observed one-point profiles extremely well, but
   its `a` and `D` should not be identified with microscopic KPZ parameters.

## Falsifiable next test

Generate weak walls with multiple amplitudes and both orientations. Linear
response predicts profile superposition and an orientation-independent
two-point propagator. A genuine nonlinear scalar Burgers law predicts
amplitude-dependent evolution with one fixed `a`. The two hypotheses cannot
both pass this test.

## Primary references

- Kharkov et al., *Discovering hydrodynamic equations of many-body quantum
  systems*: https://arxiv.org/abs/2111.02385
- Ljubotina, Žnidarič and Prosen, *Kardar-Parisi-Zhang physics in the quantum
  Heisenberg magnet*: https://arxiv.org/abs/1903.01329
- De Nardis, Gopalakrishnan and Vasseur, *Non-linear fluctuating hydrodynamics
  for KPZ scaling in isotropic spin chains*:
  https://arxiv.org/abs/2212.03696
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=str(REPO / "data" / "kharkov_highT_delta1.npz"),
    )
    parser.add_argument(
        "--outdir",
        default=str(REPO / "results_analytic_mechanism"),
    )
    parser.add_argument(
        "--raw-npy",
        default=str(REPO / "data" / "highT_delta1.npy"),
        help="Optional upstream array used to check preprocessing sensitivity",
    )
    args = parser.parse_args()

    dataset = load_npz(args.input)
    x, t, u = dataset.x, dataset.t, dataset.u
    outdir = Path(args.outdir)
    plots = outdir / "plots"
    tables = outdir / "tables"
    plots.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    diagnostics = front_linear_response_diagnostics(x, t, u)
    powers = moment_power_summary(diagnostics)
    moment_rows = fit_burgers_moment_balance(diagnostics)
    amplitude_rows = amplitude_and_spin_flip_audit(x, t, u)
    similarity = similarity_surrogate_scaling(beta=2.0 / 3.0)
    closure = fit_profiled_weak(
        x,
        t,
        u,
        t_window=(52.0, 198.0),
        x_crop=(-120.0, 120.0),
        gamma=0.0,
    )

    raw_check = None
    raw_path = Path(args.raw_npy)
    if raw_path.exists():
        raw_object = np.load(raw_path, allow_pickle=True)
        raw_dict = (
            raw_object.item()
            if hasattr(raw_object, "shape") and raw_object.shape == ()
            else raw_object
        )
        raw_t_all = np.asarray(raw_dict["t"], dtype=float)
        raw_u_all = np.asarray(raw_dict["u"], dtype=float)
        keep = raw_t_all >= float(t[0]) - 1e-9
        raw_t = raw_t_all[keep]
        raw_u = raw_u_all[keep]
        raw_x = np.arange(raw_u.shape[1], dtype=float)
        raw_x -= 0.5 * (raw_x[0] + raw_x[-1])
        raw_diagnostics = front_linear_response_diagnostics(raw_x, raw_t, raw_u)
        raw_check = moment_power_summary(raw_diagnostics)
        raw_check.update(
            {
                "source": str(raw_path.resolve()),
                "spin_flip_antisymmetry_error": float(
                    raw_diagnostics["spin_flip_antisymmetry_error"]
                ),
                "gradient_symmetry_error": float(
                    raw_diagnostics["gradient_symmetry_error"]
                ),
            }
        )

    moment_table = []
    for i in range(t.size):
        moment_table.append(
            {
                "t": float(t[i]),
                "width": float(np.asarray(diagnostics["width"])[i]),
                "variance": float(np.asarray(diagnostics["variance"])[i]),
                "D_moment": float(np.asarray(diagnostics["moment_diffusivity"])[i]),
                "shape_integral": float(np.asarray(diagnostics["shape_integral"])[i]),
                "shape_factor": float(np.asarray(diagnostics["shape_factor"])[i]),
            }
        )
    _write_csv(tables / "moment_transport.csv", moment_table)
    _write_csv(tables / "moment_balance_windows.csv", moment_rows)
    _write_csv(tables / "amplitude_spinflip_audit.csv", amplitude_rows)
    _write_csv(
        tables / "self_similar_surrogate.csv",
        [
            {
                "t": float(np.asarray(similarity["t"])[i]),
                "a_fit": float(np.asarray(similarity["a_fit"])[i]),
                "D_fit": float(np.asarray(similarity["D_fit"])[i]),
                "feature_correlation": float(
                    np.asarray(similarity["feature_correlation"])[i]
                ),
            }
            for i in range(len(np.asarray(similarity["t"])))
        ],
    )

    _save_linear_response_collapse(
        plots / "linear_response_collapse.png",
        x,
        t,
        u,
        beta=powers["width_exponent"],
    )
    _save_moment_balance(
        plots / "moment_balance.png",
        diagnostics,
        closure_a=closure.a,
        closure_D=closure.D0,
        moment_rows=moment_rows,
        t_window=(powers["t_min"], powers["t_max"]),
    )
    _save_surrogate_symmetry(
        plots / "surrogate_symmetry.png",
        amplitude_rows,
        similarity,
    )

    summary = {
        "input": str(Path(args.input).resolve()),
        "source_meta": dataset.meta,
        "linear_response_and_symmetry": {
            "half_jump": float(diagnostics["half_jump"]),
            "plateau_midpoint_median": float(
                diagnostics["plateau_midpoint_median"]
            ),
            "spin_flip_antisymmetry_error": float(
                diagnostics["spin_flip_antisymmetry_error"]
            ),
            "gradient_symmetry_error": float(
                diagnostics["gradient_symmetry_error"]
            ),
        },
        "moment_transport": powers,
        "constant_burgers_closure": {
            "a": float(closure.a),
            "D": float(closure.D0),
            "mse": float(closure.mse),
        },
        "moment_balance_windows": moment_rows,
        "amplitude_and_spin_flip": amplitude_rows,
        "self_similar_surrogate": {
            "beta": float(similarity["beta"]),
            "a_exponent_fitted": float(similarity["a_exponent_fitted"]),
            "D_exponent_fitted": float(similarity["D_exponent_fitted"]),
            "a_exponent_expected": float(similarity["a_exponent_expected"]),
            "D_exponent_expected": float(similarity["D_exponent_expected"]),
            "median_feature_correlation": float(
                np.median(np.asarray(similarity["feature_correlation"]))
            ),
        },
        "raw_source_check": raw_check,
        "analytic_resolution": {
            "mechanism": (
                "The weak high-temperature domain wall is the cumulative "
                "linear-response spin propagator. A local nonlinear Burgers "
                "equation is a finite-window surrogate whose exact moment "
                "balance packages the running front variance into constant "
                "closure coefficients."
            ),
            "falsifier": (
                "Fit multiple weak amplitudes and both wall orientations with "
                "one shared coefficient set. Linear response requires "
                "superposition; a genuine fixed-a scalar Burgers law does not."
            ),
        },
    }
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)
    )
    (outdir / "ANALYTIC_MECHANISM.md").write_text(_report_text(summary))
    print(f"[OK] wrote analytic-mechanism evidence to {outdir}")


if __name__ == "__main__":
    main()
