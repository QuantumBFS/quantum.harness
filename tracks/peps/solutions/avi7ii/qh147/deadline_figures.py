"""Render the deadline-scoped four-figure story for challenge issue #147."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

import numpy as np

from .current_evidence import (
    _despine,
    _style,
    load_pepo_probe,
    load_qmc_validation,
    plot_qmc_validation,
)


def load_ed_diagnostic(assembled_dir: Path) -> list[dict]:
    root = Path(assembled_dir)
    manifest_path = root / "manifest.json"
    table_path = root / "thermodynamics.csv"
    import json

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "success" or manifest.get("state_count") != 65536:
        raise ValueError("ED diagnostic must contain all 65536 states")
    digest = hashlib.sha256(table_path.read_bytes()).hexdigest()
    if digest != manifest.get("thermodynamics_sha256"):
        raise ValueError("ED thermodynamics hash mismatch")
    with table_path.open(encoding="utf-8", newline="") as handle:
        rows = [
            {name: float(value) for name, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    if len(rows) < 3 or rows[0]["beta"] <= 0:
        raise ValueError("ED thermodynamics grid is incomplete")
    return rows


def _panel_label(axis, label: str) -> None:
    axis.text(
        -0.14,
        1.04,
        label,
        transform=axis.transAxes,
        fontweight="bold",
        fontsize=10,
        va="top",
    )


def plot_thermodynamics(pepo: dict, qmc: dict, ed: list[dict], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _style()
    ed_beta = np.asarray([row["beta"] for row in ed])
    ed_u = np.asarray([row["u"] for row in ed])
    ed_c = np.asarray([row["c"] for row in ed])
    pepo_beta = np.asarray([row["beta"] for row in pepo["points"]])
    pepo_u = np.asarray([row["u"] for row in pepo["points"]])
    fit = qmc["fit"]

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), constrained_layout=True)
    axes[0].plot(
        ed_beta,
        ed_u,
        color="#7F7F7F",
        linestyle="-.",
        label="4x4 ED (finite-size diagnostic)",
    )
    axes[0].plot(
        pepo_beta,
        pepo_u,
        color="#0072B2",
        marker="o",
        linestyle="-",
        label="10x10 thermodynamic PEPO probe",
    )
    axes[0].errorbar(
        [0.5],
        [fit["u_infinity"]],
        yerr=[fit["bootstrap_se"]],
        color="#000000",
        fmt="D",
        capsize=3,
        label="10x10 QMC zero-step estimate",
    )
    axes[0].set_xlabel("Inverse temperature beta J")
    axes[0].set_ylabel("Internal energy u/J per site")
    axes[0].set_title("Available internal-energy evidence")
    axes[0].legend(frameon=False, loc="best")

    axes[1].plot(
        ed_beta,
        ed_c,
        color="#7F7F7F",
        linestyle="-.",
        marker=".",
        markevery=max(1, len(ed_beta) // 10),
        label="4x4 ED (finite-size diagnostic)",
    )
    axes[1].set_xlabel("Inverse temperature beta J")
    axes[1].set_ylabel("Specific heat C per site")
    axes[1].set_title("Specific heat: ED only; PEPO/QMC unavailable")
    axes[1].legend(frameon=False, loc="best")
    _panel_label(axes[0], "A")
    _panel_label(axes[1], "B")
    _despine(axes)
    fig.suptitle(
        "Figure 1 | Available thermodynamics at h/J=3 (lattice sizes shown explicitly)",
        fontsize=10,
    )
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "figure-1-available-thermodynamics.png", dpi=300)
    fig.savefig(output / "figure-1-available-thermodynamics.pdf")
    plt.close(fig)


def plot_target_preservation(pepo: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _style()
    points = pepo["points"]
    beta = np.asarray([row["beta"] for row in points])
    du = np.abs([row["u_difference"] for row in points])
    dz = np.abs([row["z_difference"] for row in points])
    components = {
        "|Frobenius term|": np.abs([row["frobenius"] for row in points]),
        "u penalty": np.asarray([row["u_penalty"] for row in points]),
        "z penalty": np.asarray([row["z_penalty"] for row in points]),
        "|total objective|": np.abs([row["objective"] for row in points]),
    }
    colors = ("#0072B2", "#D55E00", "#CC79A7", "#009E73")
    markers = ("o", "s", "v", "^")
    linestyles = ("-", "--", ":", "-.")

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.75), constrained_layout=True)
    axes[0].plot(beta, du, color="#0072B2", marker="o")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Inverse temperature beta J")
    axes[0].set_ylabel("Teacher-student |delta u| per site")
    axes[0].set_title("Energy target")

    axes[1].plot(beta, dz, color="#D55E00", marker="s", linestyle="--")
    axes[1].set_xlabel("Inverse temperature beta J")
    axes[1].set_ylabel("Teacher-student |delta z|")
    axes[1].set_title("Log-partition target")
    axes[1].ticklabel_format(axis="y", style="sci", scilimits=(-2, 2))

    for (label, values), color, marker, linestyle in zip(
        components.items(), colors, markers, linestyles, strict=True
    ):
        positive = np.where(values > 0, values, np.nan)
        axes[2].plot(
            beta,
            positive,
            color=color,
            marker=marker,
            linestyle=linestyle,
            label=label,
        )
    axes[2].set_yscale("log")
    axes[2].set_xlabel("Inverse temperature beta J")
    axes[2].set_ylabel("Objective-component magnitude")
    axes[2].set_title("Compression objective (exact zeros omitted)")
    axes[2].legend(frameon=False, loc="best")
    for label, axis in zip(("A", "B", "C"), axes, strict=True):
        _panel_label(axis, label)
    _despine(axes)
    fig.suptitle(
        "Figure 2 | Internal target preservation (no ordinary-PEPO comparator)",
        fontsize=10,
    )
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "figure-2-target-preservation.png", dpi=300)
    fig.savefig(output / "figure-2-target-preservation.pdf")
    plt.close(fig)


def plot_resources_and_stability(pepo: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _style()
    points = pepo["points"]
    beta = np.asarray([row["beta"] for row in points])
    wall_minutes = np.asarray([row["wall_seconds"] for row in points]) / 60.0
    memory_gib = np.asarray([row["peak_memory_bytes"] for row in points]) / 2**30
    hermiticity = np.asarray([row["hermiticity_residual"] for row in points])
    iterations = np.asarray([row["iterations"] for row in points])

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.4), constrained_layout=True)
    axes = axes.flat
    axes[0].plot(beta, wall_minutes, color="#0072B2", marker="o")
    axes[0].set_ylabel("Wall time per step (minutes)")
    axes[0].set_title("Runtime")

    axes[1].plot(beta, memory_gib, color="#D55E00", marker="s", linestyle="--")
    axes[1].set_ylabel("Peak resident memory (GiB)")
    axes[1].set_title("Memory")

    axes[2].plot(beta, hermiticity, color="#009E73", marker="^", linestyle="-.")
    axes[2].set_ylabel("Hermiticity residual")
    axes[2].set_title("Physical-operator diagnostic")
    if np.all(hermiticity == 0):
        axes[2].set_ylim(-1e-12, 1e-12)
        axes[2].text(0.04, 0.83, "Both values are exactly zero", transform=axes[2].transAxes,
                     fontsize=7)

    axes[3].plot(beta, iterations, color="#CC79A7", marker="v", linestyle=":")
    axes[3].set_ylabel("Accepted optimizer iterations")
    axes[3].set_title("Optimization activity")
    axes[3].set_ylim(-0.05, 0.5)
    axes[3].text(0.04, 0.83, "No optimizer update was accepted", transform=axes[3].transAxes,
                 fontsize=7)

    for label, axis in zip(("A", "B", "C", "D"), axes, strict=True):
        axis.set_xlabel("Inverse temperature beta J")
        axis.text(
            0.01,
            0.98,
            label,
            transform=axis.transAxes,
            fontweight="bold",
            fontsize=10,
            va="top",
        )
    _despine(axes)
    fig.suptitle(
        "Figure 4 | PEPO cost and stability for the two-step feasibility probe",
        fontsize=10,
    )
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "figure-4-cost-and-stability.png", dpi=300)
    fig.savefig(output / "figure-4-cost-and-stability.pdf")
    plt.close(fig)


def _write_tables(pepo: dict, qmc: dict, ed: list[dict], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "available-thermodynamics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fields = ("method", "lattice", "beta", "u", "u_se", "c", "role")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in ed:
            writer.writerow(
                {
                    "method": "ED",
                    "lattice": "4x4 open",
                    "beta": row["beta"],
                    "u": row["u"],
                    "c": row["c"],
                    "role": "finite-size diagnostic",
                }
            )
        for row in pepo["points"]:
            writer.writerow(
                {
                    "method": "thermodynamic PEPO",
                    "lattice": "10x10 open",
                    "beta": row["beta"],
                    "u": row["u"],
                    "role": "two-step feasibility probe",
                }
            )
        writer.writerow(
            {
                "method": "QMC zero-step estimate",
                "lattice": "10x10",
                "beta": 0.5,
                "u": qmc["fit"]["u_infinity"],
                "u_se": qmc["fit"]["bootstrap_se"],
                "role": "Trotter-extrapolated reference point",
            }
        )

    with (output / "target-preservation.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fields = (
            "beta", "u_difference", "z_difference", "frobenius", "u_penalty",
            "z_penalty", "hermiticity_penalty", "total_objective",
        )
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in pepo["points"]:
            writer.writerow(
                {
                    "beta": row["beta"],
                    "u_difference": row["u_difference"],
                    "z_difference": row["z_difference"],
                    "frobenius": row["frobenius"],
                    "u_penalty": row["u_penalty"],
                    "z_penalty": row["z_penalty"],
                    "hermiticity_penalty": row["hermiticity_penalty"],
                    "total_objective": row["objective"],
                }
            )

    diagnostics = {row["M"]: row for row in qmc["diagnostics"]}
    with (output / "qmc-convergence.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        fields = ("M", "x", "u", "bootstrap_se", "residual_sigma", "rhat", "max_split_half_z")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in qmc["finite_m"]:
            writer.writerow({**row, **{key: diagnostics[row["M"]][key] for key in ("rhat", "max_split_half_z")}})

    with (output / "resources.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ("beta", "wall_seconds", "peak_memory_bytes", "hermiticity_residual", "iterations", "max_bond")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in pepo["points"]:
            writer.writerow({key: row[key] for key in fields})


def _write_readme(output: Path) -> None:
    text = """# Issue #147 Deadline Figure Set

This four-figure set uses completed validated outputs only.

1. Figure 1 shows available thermodynamics. The ED curve is a 4x4 finite-size
   diagnostic; PEPO and QMC use 10x10 data but do not form a common beta curve.
2. Figure 2 shows internal teacher-student target preservation. It is not an
   ordinary-versus-thermodynamic accuracy comparison.
3. Figure 3 shows the accepted beta=0.5 QMC Trotter extrapolation and chain
   diagnostics.
4. Figure 4 shows cost and stability for the two PEPO checkpoints.

Not assessed: ordinary PEPO, PEPO or QMC specific heat, a full 10x10 beta
curve, improvement factors, Pareto accuracy/cost, and PEPO convergence in chi,
D, or delta_beta. No interpolation or synthetic data were used.
"""
    (output / "README.md").write_text(text, encoding="utf-8")


def render_deadline_set(pepo_dir: Path, qmc_dir: Path, ed_dir: Path, output: Path) -> None:
    pepo = load_pepo_probe(pepo_dir)
    qmc = load_qmc_validation(qmc_dir)
    ed = load_ed_diagnostic(ed_dir)
    plot_thermodynamics(pepo, qmc, ed, output)
    plot_target_preservation(pepo, output)
    plot_qmc_validation(qmc, output)
    (output / "qmc-trotter-and-chain-diagnostics.png").replace(
        output / "figure-3-qmc-convergence.png"
    )
    (output / "qmc-trotter-and-chain-diagnostics.pdf").replace(
        output / "figure-3-qmc-convergence.pdf"
    )
    plot_resources_and_stability(pepo, output)
    _write_tables(pepo, qmc, ed, output)
    _write_readme(output)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pepo", type=Path, required=True)
    parser.add_argument("--qmc", type=Path, required=True)
    parser.add_argument("--ed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    render_deadline_set(args.pepo, args.qmc, args.ed, args.output)
    print(f"Wrote four deadline figures to {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
