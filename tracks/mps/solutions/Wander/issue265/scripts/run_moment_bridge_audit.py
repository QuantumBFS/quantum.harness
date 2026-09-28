#!/usr/bin/env python3
"""Run the Phase-0 microscopic-to-Burgers moment bridge audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analytic_mechanism import (
    front_linear_response_diagnostics,
    moment_power_summary,
)
from src.moment_bridge import (
    A_GHD_INFINITY_T,
    block_bootstrap_bridge,
    fit_burgers_width_ode,
    fit_micro_amplitude,
    fit_parameter_flow,
    rolling_moment_bridge,
    tangent_invariants,
)
from src.research_protocol import (
    load_decision_rules,
    load_research_matrix,
)
from src.synthetic_data import load_npz
from src.tension_resolution import fit_profiled_weak


BLUE = "#2463A6"
GOLD = "#C58A16"
GREEN = "#37825B"
RED = "#B4453F"
GREY = "#929BA2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _bootstrap_rows(summary: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key in ("A", "D", "v", "A_bridge_over_A", "W_star"):
        interval = summary[key]
        assert isinstance(interval, dict)
        rows.append(
            {
                "quantity": key,
                "median": interval["median"],
                "low": interval["low"],
                "high": interval["high"],
                "confidence": summary["confidence"],
                "accepted_replicates": summary["accepted_replicates"],
                "rejected_replicates": summary["rejected_replicates"],
            }
        )
    return rows


def _save_constitutive_plot(
    path: Path,
    diagnostics: dict,
    *,
    t_window: tuple[float, float],
    A_width: float,
    D: float,
    v: float,
) -> None:
    t = np.asarray(diagnostics["t"], dtype=float)
    width = np.asarray(diagnostics["width"], dtype=float)
    moment = np.asarray(diagnostics["moment_diffusivity"], dtype=float)
    mask = (t >= t_window[0]) & (t <= t_window[1])
    order = np.argsort(width[mask])
    width_window = width[mask][order]
    moment_window = moment[mask][order]

    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    ax.scatter(
        width_window,
        moment_window,
        s=14,
        alpha=0.58,
        color=BLUE,
        label=r"data: $\frac{1}{2}dW^2/dt$",
    )
    ax.plot(
        width_window,
        A_width * np.sqrt(width_window),
        color=GREEN,
        lw=2.2,
        label=rf"$A_W\sqrt{{W}}$, $A_W={A_width:.4f}$",
    )
    ax.plot(
        width_window,
        D + v * width_window,
        color=GOLD,
        lw=2.0,
        ls="--",
        label=rf"$D+vW$, $D={D:.3f}$, $v={v:.4f}$",
    )
    ax.plot(
        width_window,
        A_GHD_INFINITY_T * np.sqrt(width_window),
        color=RED,
        lw=1.5,
        ls=":",
        label=rf"GHD $A_\infty\sqrt{{W}}$, $A_\infty={A_GHD_INFINITY_T:.4f}$",
    )
    ax.set_xlabel("front width W")
    ax.set_ylabel(r"$D_{\rm moment}$")
    ax.set_title(
        f"Microscopic square-root law and finite-window tangent "
        f"(t={t_window[0]:.0f}–{t_window[1]:.0f})"
    )
    ax.grid(color="#E7EAED", lw=0.7)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _save_flow_plot(path: Path, rows: list[dict[str, float]]) -> None:
    t_star = np.asarray([row["t_star"] for row in rows], dtype=float)
    a = np.asarray([row["a_from_width_implicit"] for row in rows], dtype=float)
    diffusion = np.asarray([row["D_width_implicit"] for row in rows], dtype=float)
    ratio = np.asarray([row["A_bridge_over_A_width"] for row in rows], dtype=float)

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.3))
    ax = axes[0]
    compensated_a = a * t_star ** (1.0 / 3.0)
    compensated_D = diffusion * t_star ** (-1.0 / 3.0)
    ax.plot(
        t_star,
        compensated_a / compensated_a[0],
        "o-",
        color=BLUE,
        label=r"$a(t_*)t_*^{1/3}$ / first",
    )
    ax.plot(
        t_star,
        compensated_D / compensated_D[0],
        "s-",
        color=GOLD,
        label=r"$D(t_*)t_*^{-1/3}$ / first",
    )
    ax.axhline(1.0, color=GREY, lw=1.0, ls=":")
    ax.set_xlabel(r"window center $t_*$")
    ax.set_ylabel("compensated coefficient")
    ax.set_title("Finite-window tangent-flow compensation")
    ax.grid(color="#E7EAED", lw=0.7)
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1]
    ax.plot(t_star, ratio, "o-", color=GREEN, label=r"$A_B/A_W$")
    ax.axhline(1.0, color=GREY, lw=1.0, ls=":")
    ax.axhspan(0.95, 1.05, color=GREEN, alpha=0.10, label="preregistered ±5%")
    ax.set_xlabel(r"window center $t_*$")
    ax.set_ylabel("tangent amplitude ratio")
    ax.set_title("Local affine-vs-square-root consistency")
    ax.grid(color="#E7EAED", lw=0.7)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=str(ROOT / "data" / "kharkov_highT_delta1.npz"),
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional research manifest recorded for pipeline provenance.",
    )
    parser.add_argument(
        "--matrix",
        default=str(ROOT / "configs" / "burgers_research_matrix.json"),
    )
    parser.add_argument(
        "--rules",
        default=str(ROOT / "configs" / "burgers_decision_rules.json"),
    )
    parser.add_argument(
        "--outdir",
        default=str(ROOT / "results_research_program" / "moment_bridge"),
    )
    parser.add_argument(
        "--late-window",
        nargs=2,
        type=float,
        default=(120.0, 190.0),
        metavar=("T_MIN", "T_MAX"),
    )
    parser.add_argument("--bootstrap-replicates", type=int)
    parser.add_argument("--seed", type=int, default=20260729)
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    matrix_path = Path(args.matrix).resolve()
    rules_path = Path(args.rules).resolve()
    outdir = Path(args.outdir).resolve()
    plots = outdir / "plots"
    tables = outdir / "tables"
    plots.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    matrix = load_research_matrix(matrix_path)
    rules = load_decision_rules(rules_path)
    dataset = load_npz(str(input_path))
    diagnostics = front_linear_response_diagnostics(
        dataset.x,
        dataset.t,
        dataset.u,
    )
    t = np.asarray(diagnostics["t"], dtype=float)
    width = np.asarray(diagnostics["width"], dtype=float)
    shape_factor = np.asarray(diagnostics["shape_factor"], dtype=float)
    U0 = float(diagnostics["half_jump"])
    late_window = (float(args.late_window[0]), float(args.late_window[1]))

    available_windows = tuple(
        window
        for window in matrix.rolling_windows
        if window[0] >= float(t[0]) and window[1] <= float(t[-1])
    )
    rolling = rolling_moment_bridge(
        t,
        width,
        shape_factor,
        U0=U0,
        windows=available_windows,
    )
    if len(rolling) < 3:
        raise RuntimeError("At least three rolling windows are required")

    late_micro = fit_micro_amplitude(t, width, t_window=late_window)
    late_burgers = fit_burgers_width_ode(t, width, t_window=late_window)
    late_mask = (t >= late_window[0]) & (t <= late_window[1])
    late_c_f = float(np.mean(shape_factor[late_mask]))
    late_W_anchor = float(np.median(width[late_mask]))
    late_invariants = tangent_invariants(
        D=late_burgers.D,
        v=late_burgers.v,
        A_width=late_micro.A,
        W_anchor=late_W_anchor,
        U0=U0,
        c_f=late_c_f,
    )

    replicates = (
        int(args.bootstrap_replicates)
        if args.bootstrap_replicates is not None
        else int(rules.threshold("bootstrap_replicates"))
    )
    bootstrap = block_bootstrap_bridge(
        t,
        width,
        t_window=late_window,
        block_duration=rules.threshold("bootstrap_block_duration"),
        replicates=replicates,
        seed=int(args.seed),
        confidence=rules.threshold("bootstrap_confidence"),
    )
    flow_a = fit_parameter_flow(rolling, value_key="a_from_width_implicit")
    flow_D = fit_parameter_flow(rolling, value_key="D_width_implicit")
    flow_A = fit_parameter_flow(rolling, value_key="A_width")
    powers = moment_power_summary(diagnostics)
    profile_fit = fit_profiled_weak(
        dataset.x,
        dataset.t,
        dataset.u,
        t_window=(52.0, 198.0),
        x_crop=(-120.0, 120.0),
        gamma=0.0,
    )

    _write_csv(tables / "rolling_bridge.csv", rolling)
    _write_csv(tables / "bootstrap_intervals.csv", _bootstrap_rows(bootstrap))
    _save_constitutive_plot(
        plots / "moment_constitutive_law.png",
        diagnostics,
        t_window=late_window,
        A_width=late_micro.A,
        D=late_burgers.D,
        v=late_burgers.v,
    )
    _save_flow_plot(plots / "coefficient_flow.png", rolling)

    tangent_tolerance = rules.threshold("tangent_ratio_abs_error_max")
    summary = {
        "phase": "phase_0_public_single_trajectory_pilot",
        "input": str(input_path),
        "input_sha256": _sha256(input_path),
        "matrix": str(matrix_path),
        "matrix_sha256": _sha256(matrix_path),
        "rules": str(rules_path),
        "rules_sha256": _sha256(rules_path),
        "manifest": (
            str(Path(args.manifest).resolve()) if args.manifest else None
        ),
        "manifest_sha256": (
            _sha256(Path(args.manifest).resolve()) if args.manifest else None
        ),
        "source_meta": dataset.meta,
        "available_rolling_windows": [list(window) for window in available_windows],
        "baseline": {
            "profile_a": float(profile_fit.a),
            "profile_D": float(profile_fit.D0),
            "profile_mse": float(profile_fit.mse),
            **powers,
        },
        "late_window": {
            "t_min": late_window[0],
            "t_max": late_window[1],
            "A_width": late_micro.A,
            "A_width_stderr_naive": late_micro.stderr_A,
            "A_width_relative_l2": late_micro.relative_l2,
            "A_GHD": A_GHD_INFINITY_T,
            "D_width_implicit": late_burgers.D,
            "v_width_implicit": late_burgers.v,
            "a_width_implicit": late_invariants["a_from_v"],
            "width_implicit_relative_l2": late_burgers.relative_l2,
            "mean_shape_factor": late_c_f,
            "W_anchor": late_W_anchor,
            **late_invariants,
            "tangent_internal_pass": bool(
                abs(late_invariants["A_bridge_over_A_width"] - 1.0)
                < tangent_tolerance
            ),
        },
        "rolling": rolling,
        "parameter_flows": {
            "a": flow_a,
            "D": flow_D,
            "A_width": flow_A,
            "universal_target": {"a_exponent": 0.0, "D_exponent": 0.0},
            "finite_tangent_target": {
                "a_exponent": -1.0 / 3.0,
                "D_exponent": 1.0 / 3.0,
            },
        },
        "bootstrap": bootstrap,
        "scope_warning": (
            "The bridge and bootstrap use one public initial condition. "
            "They test internal moment-level consistency, not cross-condition "
            "universality or the two-mode hypothesis."
        ),
    }
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"[OK] wrote Phase-0 moment bridge audit to {outdir}")


if __name__ == "__main__":
    main()
