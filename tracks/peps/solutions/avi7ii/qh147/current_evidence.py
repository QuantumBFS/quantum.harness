"""Render the evidence currently available for challenge issue #147."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np


PEPO_BETAS = (0.025, 0.05)
QMC_M_VALUES = (32, 64, 128)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite(value, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def load_pepo_probe(run_dir: Path) -> dict:
    """Load the completed two-step thermodynamic PEPO probe."""
    root = Path(run_dir) / "thermodynamic"
    manifest = _read_json(root / "manifest.json")
    if manifest.get("status") != "complete" or manifest.get("mode") != "thermodynamic":
        raise ValueError("PEPO thermodynamic manifest must be complete")
    accepted = tuple(float(value) for value in manifest.get("accepted_betas", []))
    if accepted != PEPO_BETAS:
        raise ValueError("PEPO probe must contain exactly the two accepted beta points")

    points = []
    config_hash = manifest.get("config_sha256")
    for beta in PEPO_BETAS:
        metadata = _read_json(
            root / "checkpoints" / f"beta-{beta:.6f}" / "metadata.json"
        )
        diagnostics = metadata.get("diagnostics", {})
        budget = diagnostics.get("budget", {})
        final = diagnostics.get("final", {})
        if _finite(metadata.get("beta"), "PEPO beta") != beta:
            raise ValueError("PEPO checkpoint beta does not match its path")
        if metadata.get("mode") != "thermodynamic":
            raise ValueError("PEPO checkpoint is not thermodynamic mode")
        if metadata.get("config_sha256") != config_hash:
            raise ValueError("PEPO checkpoint config hash mismatch")
        if metadata.get("lattice") != {"lx": 10, "ly": 10}:
            raise ValueError("PEPO probe must use the 10x10 lattice")
        if int(budget.get("requested_bond", -1)) != 4 or int(budget.get("chi", -1)) != 16:
            raise ValueError("PEPO probe must use D=4 and chi=16")
        points.append(
            {
                "beta": beta,
                "u": _finite(diagnostics.get("u"), "PEPO u"),
                "log_z_per_site": _finite(diagnostics.get("z"), "PEPO z"),
                "objective": _finite(final.get("total"), "PEPO objective"),
                "frobenius": _finite(final.get("frobenius"), "PEPO Frobenius term"),
                "u_difference": _finite(
                    final.get("u_difference"), "PEPO u difference"
                ),
                "z_difference": _finite(
                    final.get("z_difference"), "PEPO z difference"
                ),
                "u_penalty": _finite(final.get("u_penalty"), "PEPO u penalty"),
                "z_penalty": _finite(final.get("z_penalty"), "PEPO z penalty"),
                "hermiticity_penalty": _finite(
                    final.get("hermiticity_penalty"),
                    "PEPO Hermiticity penalty",
                ),
                "hermiticity_residual": _finite(
                    diagnostics.get("hermiticity_residual"),
                    "PEPO Hermiticity residual",
                ),
                "iterations": int(diagnostics.get("iterations", -1)),
                "max_bond": int(diagnostics.get("max_bond", -1)),
                "peak_memory_bytes": int(
                    diagnostics.get("peak_memory_bytes", -1)
                ),
                "wall_seconds": _finite(
                    diagnostics.get("wall_seconds"), "PEPO wall time"
                ),
            }
        )
    return {
        "status": "two-step-probe",
        "lattice": "10x10 open",
        "J": 1.0,
        "h": 3.0,
        "D": 4,
        "chi": 16,
        "delta_beta": 0.025,
        "points": points,
    }


def load_qmc_validation(run_dir: Path) -> dict:
    """Load an accepted three-point QMC Trotter analysis."""
    result = _read_json(Path(run_dir) / "analysis.json")
    if result.get("accepted") is not True:
        raise ValueError("QMC analysis must pass all acceptance gates")
    rows = result.get("finite_m", [])
    diagnostics = result.get("diagnostics", [])
    if tuple(int(row.get("M", -1)) for row in rows) != QMC_M_VALUES:
        raise ValueError("QMC analysis must contain M=32,64,128 in order")
    if tuple(int(row.get("M", -1)) for row in diagnostics) != QMC_M_VALUES:
        raise ValueError("QMC diagnostics must match the finite-M grid")
    for row in rows:
        for name in ("x", "u", "bootstrap_se", "residual_sigma"):
            _finite(row.get(name), f"QMC {name}")
        if float(row["bootstrap_se"]) <= 0:
            raise ValueError("QMC bootstrap errors must be positive")
    fit = result.get("fit", {})
    for name in ("u_infinity", "bootstrap_se", "slope", "reduced_chi2"):
        _finite(fit.get(name), f"QMC fit {name}")
    ci95 = fit.get("ci95", [])
    if len(ci95) != 2 or not all(math.isfinite(float(value)) for value in ci95):
        raise ValueError("QMC fit must contain a finite 95% confidence interval")
    return result


def _style() -> None:
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 8,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.4,
            "lines.markersize": 5,
            "savefig.bbox": "tight",
        }
    )


def _despine(axes) -> None:
    for axis in np.atleast_1d(axes).flat:
        axis.spines[["top", "right"]].set_visible(False)


def plot_pepo_probe(pepo: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _style()
    points = pepo["points"]
    beta = np.asarray([point["beta"] for point in points])
    energy = np.asarray([point["u"] for point in points])
    log_z = np.asarray([point["log_z_per_site"] for point in points])
    objective = np.abs([point["objective"] for point in points])

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.55), constrained_layout=True)
    axes[0].plot(beta, energy, color="#0072B2", marker="o", linestyle="-")
    axes[0].set_xlabel("Inverse temperature beta J")
    axes[0].set_ylabel("Internal energy u/J per site")
    axes[0].set_title("Two accepted checkpoints")

    axes[1].plot(beta, log_z, color="#D55E00", marker="s", linestyle="--")
    axes[1].set_xlabel("Inverse temperature beta J")
    axes[1].set_ylabel("Log-partition density (ln Z)/N")
    axes[1].set_title("Thermodynamic representation")

    axes[2].plot(beta, objective, color="#009E73", marker="^", linestyle="-.")
    axes[2].set_yscale("log")
    axes[2].set_xlabel("Inverse temperature beta J")
    axes[2].set_ylabel("Absolute final objective")
    axes[2].set_title("Compression diagnostic")
    axes[2].text(
        0.03,
        0.96,
        "Hermiticity residual = 0\nAccepted optimizer updates = 0",
        transform=axes[2].transAxes,
        va="top",
        fontsize=7,
    )
    for index, axis in enumerate(axes):
        axis.text(-0.18, 1.05, chr(ord("A") + index), transform=axis.transAxes,
                  fontweight="bold", fontsize=10, va="top")
    _despine(axes)
    fig.suptitle(
        "Thermodynamic PEPO feasibility probe (10x10 open TFIM, h/J=3, D=4, chi=16)",
        fontsize=10,
    )
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "pepo-two-step-diagnostics.png", dpi=300)
    fig.savefig(output / "pepo-two-step-diagnostics.pdf")
    plt.close(fig)


def plot_qmc_validation(qmc: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _style()
    rows = qmc["finite_m"]
    diagnostics = qmc["diagnostics"]
    fit = qmc["fit"]
    thresholds = qmc["thresholds"]
    x_values = np.asarray([row["x"] for row in rows])
    values = np.asarray([row["u"] for row in rows])
    errors = np.asarray([row["bootstrap_se"] for row in rows])
    m_values = np.asarray([row["M"] for row in rows])
    x_line = np.linspace(0.0, 1.05 * np.max(x_values), 200)
    y_line = fit["u_infinity"] + fit["slope"] * x_line

    fig = plt.figure(figsize=(7.2, 3.0), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, width_ratios=(1.8, 1.0))
    fit_axis = fig.add_subplot(grid[:, 0])
    rhat_axis = fig.add_subplot(grid[0, 1])
    split_axis = fig.add_subplot(grid[1, 1], sharex=rhat_axis)

    fit_axis.plot(x_line, y_line, color="#0072B2", linestyle="-", label="weighted fit")
    fit_axis.errorbar(
        x_values,
        values,
        yerr=errors,
        fmt="o",
        color="#D55E00",
        ecolor="#D55E00",
        capsize=3,
        label="finite M (block-bootstrap SE)",
    )
    fit_axis.errorbar(
        [0.0],
        [fit["u_infinity"]],
        yerr=[fit["bootstrap_se"]],
        fmt="*",
        ms=9,
        color="#009E73",
        capsize=3,
        label="zero-step estimate (bootstrap SE)",
    )
    fit_axis.vlines(
        0.0,
        fit["ci95"][0],
        fit["ci95"][1],
        color="#009E73",
        linewidth=4,
        alpha=0.28,
        label="zero-step 95% CI",
    )
    for row in rows:
        fit_axis.annotate(
            f"M={row['M']}",
            (row["x"], row["u"]),
            xytext=(4, 5),
            textcoords="offset points",
            fontsize=7,
        )
    fit_axis.set_xlabel("Squared Trotter step (beta/M)^2")
    fit_axis.set_ylabel("Internal energy u/J per site")
    fit_axis.set_title(
        f"QMC Trotter extrapolation, beta J=0.5 (reduced chi-square={fit['reduced_chi2']:.3f})"
    )
    fit_axis.legend(frameon=False, loc="best")

    rhat = np.asarray([row["rhat"] for row in diagnostics])
    split_z = np.asarray([row["max_split_half_z"] for row in diagnostics])
    rhat_axis.plot(m_values, rhat, color="#CC79A7", marker="s", linestyle="--")
    rhat_axis.axhline(
        thresholds["rhat_max"], color="#000000", linestyle=":", linewidth=1,
        label=f"limit {thresholds['rhat_max']:.2f}"
    )
    rhat_axis.set_ylabel("R-hat")
    rhat_axis.set_title("Chain diagnostics")
    rhat_axis.legend(frameon=False, loc="upper right")
    rhat_axis.tick_params(labelbottom=False)

    split_axis.plot(m_values, split_z, color="#E69F00", marker="^", linestyle="-.")
    split_axis.axhline(
        thresholds["split_half_z_max"], color="#000000", linestyle=":", linewidth=1,
        label=f"limit {thresholds['split_half_z_max']:.1f}"
    )
    split_axis.set_xlabel("Trotter slices M")
    split_axis.set_ylabel("Max split-half |z|")
    split_axis.set_xticks(m_values)
    split_axis.legend(frameon=False, loc="upper right")

    fit_axis.text(-0.12, 1.03, "A", transform=fit_axis.transAxes,
                  fontweight="bold", fontsize=10, va="top")
    rhat_axis.text(-0.20, 1.06, "B", transform=rhat_axis.transAxes,
                   fontweight="bold", fontsize=10, va="top")
    split_axis.text(-0.20, 1.06, "C", transform=split_axis.transAxes,
                    fontweight="bold", fontsize=10, va="top")
    _despine([fit_axis, rhat_axis, split_axis])
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "qmc-trotter-and-chain-diagnostics.png", dpi=300)
    fig.savefig(output / "qmc-trotter-and-chain-diagnostics.pdf")
    plt.close(fig)


def write_summary(pepo: dict, qmc: dict, output: Path) -> None:
    summary = {
        "scope": "current validated evidence only",
        "pepo": pepo,
        "qmc": {
            "status": "accepted",
            "beta": 0.5,
            "M": list(QMC_M_VALUES),
            "u_infinity": qmc["fit"]["u_infinity"],
            "bootstrap_se": qmc["fit"]["bootstrap_se"],
            "ci95": qmc["fit"]["ci95"],
            "max_rhat": max(row["rhat"] for row in qmc["diagnostics"]),
            "max_split_half_z": max(
                row["max_split_half_z"] for row in qmc["diagnostics"]
            ),
        },
        "not_assessed": [
            "ordinary PEPO comparison",
            "specific heat C(beta)",
            "full-beta thermodynamic curve",
            "PEPO boundary-dimension chi convergence",
            "PEPO bond-dimension D convergence",
            "imaginary-time step delta_beta convergence",
        ],
        "interpretation": (
            "The PEPO result is a two-step feasibility probe, not a thermodynamic "
            "curve or convergence study. The QMC result supports only the beta=0.5 "
            "Trotter extrapolation and its chain diagnostics."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / "evidence-summary.json.tmp"
    temporary.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output / "evidence-summary.json")

    lines = [
        "# Issue #147 Current Evidence Figures",
        "",
        "The figures use completed, validated outputs only.",
        "",
        "## PEPO",
        "",
        "The 10x10 open-boundary thermodynamic PEPO uses J=1, h=3, D=4, "
        "chi=16, and delta_beta=0.025. Only beta=0.025 and 0.05 are available; "
        "both have zero Hermiticity residual and zero accepted optimizer updates.",
        "",
        "## QMC",
        "",
        f"At beta=0.5, the M=32,64,128 extrapolation gives u_infinity="
        f"{qmc['fit']['u_infinity']:.10f} +/- {qmc['fit']['bootstrap_se']:.10f} "
        "(bootstrap SE). The 95% bootstrap interval is "
        f"[{qmc['fit']['ci95'][0]:.10f}, {qmc['fit']['ci95'][1]:.10f}].",
        "",
        "## Not assessed",
        "",
        *[f"- {item}" for item in summary["not_assessed"]],
        "",
        "The PEPO panels are a two-step feasibility probe, not a thermodynamic "
        "curve or convergence claim.",
    ]
    temporary = output / "README.md.tmp"
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary, output / "README.md")


def render_current_evidence(pepo_dir: Path, qmc_dir: Path, output: Path) -> None:
    pepo = load_pepo_probe(pepo_dir)
    qmc = load_qmc_validation(qmc_dir)
    plot_pepo_probe(pepo, output)
    plot_qmc_validation(qmc, output)
    write_summary(pepo, qmc, output)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pepo", type=Path, required=True)
    parser.add_argument("--qmc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    render_current_evidence(args.pepo, args.qmc, args.output)
    print(f"Wrote current-evidence figures to {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
