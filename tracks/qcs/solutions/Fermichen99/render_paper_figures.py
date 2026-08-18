#!/usr/bin/env python3
"""Render the two headline figures used by the final challenge report."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


SOLUTION_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = SOLUTION_DIR / "artifacts"
RESULT_DIR = SOLUTION_DIR.parents[1] / "results"

BLUE = "#0072B2"
ORANGE = "#D55E00"
GREEN = "#009E73"
PURPLE = "#CC79A7"
GRAY = "#5B5B5B"
LIGHT = "#F4F5F6"


def rows(name: str) -> list[dict[str, str]]:
    with (ARTIFACT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def result_rows(name: str) -> list[dict[str, str]]:
    with (RESULT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def select(
    source: list[dict[str, str]],
    **criteria: object,
) -> dict[str, str]:
    matches = [
        row
        for row in source
        if all(
            (
                abs(float(row[key]) - float(value)) < 1e-12
                if isinstance(value, float)
                else row[key] == str(value)
            )
            for key, value in criteria.items()
        )
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one row for {criteria}, found {len(matches)}"
        )
    return matches[0]


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "axes.titlesize": 8.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.2,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.5,
            "lines.markersize": 4.5,
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def panel(axis: plt.Axes, label: str) -> None:
    axis.text(
        -0.12,
        1.04,
        label,
        transform=axis.transAxes,
        fontsize=10,
        fontweight="bold",
        va="bottom",
    )


def save(figure: plt.Figure, stem: str) -> None:
    for suffix in ("png", "pdf"):
        figure.savefig(
            ARTIFACT_DIR / f"{stem}.{suffix}",
            dpi=300 if suffix == "png" else None,
            bbox_inches="tight",
            facecolor="white",
        )
    plt.close(figure)


def box(
    axis: plt.Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    title: str,
    body: str,
    *,
    color: str = GRAY,
    title_size: float = 8.1,
    body_size: float = 6.8,
) -> None:
    x, y = xy
    axis.add_patch(
        FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            linewidth=1.0,
            edgecolor=color,
            facecolor=LIGHT,
        )
    )
    axis.text(
        x + width / 2,
        y + height * 0.67,
        title,
        ha="center",
        va="center",
        fontweight="bold",
        fontsize=title_size,
    )
    axis.text(
        x + width / 2,
        y + height * 0.30,
        body,
        ha="center",
        va="center",
        fontsize=body_size,
    )


def arrow(
    axis: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = BLUE,
    connectionstyle: str = "arc3",
) -> None:
    axis.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=1.1,
            color=color,
            connectionstyle=connectionstyle,
        )
    )


def figure_intrinsic_dimension() -> None:
    spectra = np.load(
        RESULT_DIR / "sim-to-real-invariant-v1" / "invariant_spectra.npz"
    )
    single = rows("single_qubit_summary.csv")

    figure = plt.figure(figsize=(7.2, 4.8))
    grid = figure.add_gridspec(
        2,
        2,
        height_ratios=[0.65, 1.0],
        hspace=0.34,
        wspace=0.32,
    )
    flow = figure.add_subplot(grid[0, :])
    spectrum = figure.add_subplot(grid[1, 0])
    closed = figure.add_subplot(grid[1, 1])

    flow.set_axis_off()
    flow.set(xlim=(0, 1), ylim=(0, 1))
    box(
        flow,
        (0.03, 0.39),
        0.27,
        0.34,
        "Differentiable model",
        "open-loop pulse θ*\nHessian eigenvectors Vₖ",
    )
    box(
        flow,
        (0.39, 0.39),
        0.22,
        0.34,
        "Reduced search",
        "θ = θ* + Vₖc\nk ≪ P",
        color=BLUE,
    )
    box(
        flow,
        (0.70, 0.39),
        0.27,
        0.34,
        "Query-only device",
        "finite-shot scalar loss\nno gradients or Hamiltonian",
        color=ORANGE,
    )
    arrow(flow, (0.30, 0.56), (0.39, 0.56))
    arrow(flow, (0.61, 0.56), (0.70, 0.56))
    arrow(
        flow,
        (0.84, 0.34),
        (0.52, 0.34),
        color=ORANGE,
        connectionstyle="arc3,rad=-0.18",
    )
    flow.text(
        0.68,
        0.17,
        "count every query and shot",
        ha="center",
        va="center",
        color=ORANGE,
        fontsize=7.2,
    )
    flow.plot(
        [0.665, 0.665],
        [0.28, 0.82],
        color=GRAY,
        linestyle="--",
        linewidth=0.8,
    )
    flow.text(
        0.665,
        0.85,
        "model/device boundary",
        ha="center",
        va="bottom",
        color=GRAY,
        fontsize=7.0,
    )
    panel(flow, "(a)")

    for key, label, color, rank in [
        ("single_qubit", "single-qubit X, d=2", BLUE, 3),
        ("two_qubit", "two-qubit CNOT, d=4", ORANGE, 15),
    ]:
        values = np.abs(np.asarray(spectra[key], dtype=float))
        values /= np.max(values)
        indices = np.arange(1, values.size + 1)
        spectrum.semilogy(
            indices,
            values,
            "o-",
            color=color,
            label=label,
        )
        spectrum.axvline(
            rank + 0.5,
            color=color,
            linestyle=":",
            linewidth=1.0,
        )
    spectrum.axhline(1e-6, color=GRAY, linestyle="--", linewidth=0.8)
    spectrum.set(
        xlabel="Hessian eigenvalue index",
        ylabel="normalized |λᵢ|",
        xlim=(0.5, 40.5),
        ylim=(1e-11, 2.0),
    )
    spectrum.text(3.8, 2.2e-2, "rank 3", color=BLUE, fontsize=7.2)
    spectrum.text(15.8, 2.2e-2, "rank 15", color=ORANGE, fontsize=7.2)
    spectrum.legend(frameon=False, loc="lower left")
    spectrum.grid(alpha=0.18)
    panel(spectrum, "(b)")

    model_rows = [
        select(
            single,
            epsilon=0.3,
            method="nominal_hessian",
            dimension=k,
        )
        for k in (1, 2, 3, 4)
    ]
    x_model = np.arange(4, dtype=float)
    y_model = np.asarray(
        [float(row["censored_query_median"]) for row in model_rows]
    )
    lower = y_model - np.asarray(
        [float(row["censored_query_q25"]) for row in model_rows]
    )
    upper = np.asarray(
        [float(row["censored_query_q75"]) for row in model_rows]
    ) - y_model
    closed.errorbar(
        x_model,
        y_model,
        yerr=np.vstack([lower, upper]),
        fmt="o-",
        color=BLUE,
        capsize=2.5,
    )
    for x, y, row in zip(x_model, y_model, model_rows, strict=True):
        closed.annotate(
            f"{100 * float(row['certified_success_rate']):.0f}%",
            (x, y),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            color=BLUE,
            fontsize=7.0,
        )
    for method, dimension, x, color in [
        ("random", 3, 4.0, PURPLE),
        ("raw_full", 20, 5.0, ORANGE),
    ]:
        row = select(
            single,
            epsilon=0.3,
            method=method,
            dimension=dimension,
        )
        y = float(row["censored_query_median"])
        closed.plot(x, y, "D", color=color)
        closed.annotate(
            f"{100 * float(row['certified_success_rate']):.0f}%",
            (x, y),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            color=color,
            fontsize=7.0,
        )
    closed.axvline(2, color=GRAY, linestyle=":", linewidth=1.0)
    closed.axhline(501, color=GRAY, linestyle="--", linewidth=0.8)
    closed.set(
        xlabel="closed-loop search space",
        ylabel="queries to certificate",
        xlim=(-0.35, 5.35),
        ylim=(0, 545),
        xticks=np.arange(6),
        xticklabels=[
            "model\nk=1",
            "model\nk=2",
            "model\nk=3",
            "model\nk=4",
            "random\nk=3",
            "raw\nk=20",
        ],
    )
    closed.text(
        2.05,
        445,
        "d²−1=3",
        rotation=90,
        va="top",
        fontsize=7.2,
        color=GRAY,
    )
    closed.grid(alpha=0.18)
    panel(closed, "(c)")
    save(figure, "paper_fig1_intrinsic_dimension")


def figure_closed_loop_answer() -> None:
    fixed = rows("closed_loop_cobyqa_summary.csv")
    adaptive = rows("adaptive_hybrid_summary.csv")
    figure, axes = plt.subplots(
        1,
        2,
        figsize=(7.2, 3.0),
        gridspec_kw={"wspace": 0.34},
    )

    axis = axes[0]
    for epsilon, marker, color in [
        (0.1, "o", BLUE),
        (0.5, "s", ORANGE),
    ]:
        selected = [
            select(
                fixed,
                epsilon=epsilon,
                method="nominal_hessian",
                dimension=k,
            )
            for k in (15, 20, 30)
        ]
        values = np.asarray(
            [
                float(row["censored_certified_query_median"])
                for row in selected
            ]
        )
        low = values - np.asarray(
            [
                float(row["censored_certified_query_q25"])
                for row in selected
            ]
        )
        high = np.asarray(
            [
                float(row["censored_certified_query_q75"])
                for row in selected
            ]
        ) - values
        axis.errorbar(
            (15, 20, 30),
            values,
            yerr=np.vstack([low, high]),
            fmt=f"{marker}-",
            color=color,
            capsize=2.5,
            label=f"ε={epsilon:g}",
        )
        for x, y, row in zip((15, 20, 30), values, selected, strict=True):
            offset = (
                (8, 6)
                if x == 15 and epsilon == 0.5
                else (0, 6)
            )
            axis.annotate(
                f"{100 * float(row['certified_success_rate']):.0f}%",
                (x, y),
                xytext=offset,
                textcoords="offset points",
                ha="center",
                color=color,
                fontsize=7.0,
            )
    axis.axhline(701, color=GRAY, linestyle="--", linewidth=0.8)
    axis.set(
        xlabel="fixed nominal search dimension k",
        ylabel="censored median queries",
        xticks=(15, 20, 30),
        ylim=(0, 760),
    )
    axis.legend(frameon=False, loc="lower right")
    axis.grid(alpha=0.18)
    panel(axis, "(a)")

    axis = axes[1]
    epsilons = (0.1, 0.3, 0.5)
    series = [
        ("nominal_hessian", 15, "fixed nominal k=15", BLUE, "o--"),
        ("robust_ensemble", 30, "fixed ensemble k=30", GREEN, "s--"),
    ]
    for method, dimension, label, color, fmt in series:
        selected = [
            select(
                fixed,
                epsilon=epsilon,
                method=method,
                dimension=dimension,
            )
            for epsilon in epsilons
        ]
        query_medians = [
            float(row["censored_certified_query_median"])
            for row in selected
        ]
        axis.plot(
            epsilons,
            query_medians,
            fmt,
            color=color,
            label=label,
        )
        for x, y, row in zip(
            epsilons,
            query_medians,
            selected,
            strict=True,
        ):
            axis.annotate(
                f"{100 * float(row['certified_success_rate']):.0f}%",
                (x, y),
                xytext=(0, 6),
                textcoords="offset points",
                ha="center",
                color=color,
                fontsize=7.0,
            )
    adaptive_rows = [
        select(adaptive, epsilon=epsilon) for epsilon in epsilons
    ]
    axis.plot(
        epsilons,
        [
            float(row["censored_certified_query_median"])
            for row in adaptive_rows
        ],
        "D-",
        color=ORANGE,
        label="triggered adaptive k≤20",
    )
    for x, row in zip(epsilons, adaptive_rows, strict=True):
        y = float(row["censored_certified_query_median"])
        offset = (
            (-4, 6)
            if x == epsilons[0]
            else (-8, 6)
            if x == epsilons[-1]
            else (0, 6)
        )
        horizontal_alignment = (
            "right" if x == epsilons[0] else "center"
        )
        axis.annotate(
            f"{100 * float(row['certified_success_rate']):.0f}%",
            (x, y),
            xytext=offset,
            textcoords="offset points",
            ha=horizontal_alignment,
            color=ORANGE,
            fontsize=7.0,
        )
    axis.axhline(701, color=GRAY, linestyle=":", linewidth=0.8)
    axis.set(
        xlabel="model–device mismatch ε",
        ylabel="censored median queries",
        xticks=epsilons,
        ylim=(0, 760),
    )
    axis.legend(frameon=False, loc="lower right")
    axis.grid(alpha=0.18)
    panel(axis, "(b)")
    save(figure, "paper_fig2_closed_loop_answer")


def figure_latent_world_model() -> None:
    stress = result_rows(
        "sim-to-real-transmon-external-validation-v1/"
        "transmon_validation_summary.csv"
    )

    figure, axes = plt.subplots(
        1,
        2,
        figsize=(7.2, 3.2),
        gridspec_kw={"width_ratios": [1.05, 1.35], "wspace": 0.30},
    )
    axis = axes[0]
    conditions = (
        ("hamiltonian", "Hamiltonian"),
        ("transfer", "Transfer"),
    )
    methods = (
        ("fixed_nominal_15", "fixed nominal-15", BLUE),
        ("adaptive_15_to_20", "adaptive 15→20", ORANGE),
        ("raw_40", "raw-40", GRAY),
    )
    locations = np.arange(len(conditions), dtype=np.float64)
    width = 0.23
    for method_index, (method, label, color) in enumerate(methods):
        selected = [
            select(
                stress,
                condition=condition,
                strength=1.0,
                method=method,
            )
            for condition, _ in conditions
        ]
        values = [
            float(row["best_exact_infidelity_median"])
            for row in selected
        ]
        bars = axis.bar(
            locations + (method_index - 1) * width,
            values,
            width=width,
            color=color,
            label=label,
        )
        for rectangle, row, value in zip(
            bars,
            selected,
            values,
            strict=True,
        ):
            axis.text(
                rectangle.get_x() + rectangle.get_width() / 2,
                value * 1.12,
                f"{100 * float(row['certified_success_rate']):.0f}%",
                ha="center",
                va="bottom",
                fontsize=6.8,
                color=color,
            )
    axis.axhline(1e-3, color="black", linestyle=":", linewidth=1.0)
    axis.text(
        locations[-1] + 0.34,
        1.15e-3,
        "target 10⁻³",
        ha="right",
        va="bottom",
        fontsize=6.8,
    )
    axis.set_yscale("log")
    axis.set(
        ylabel="median best infidelity",
        xticks=locations,
        xticklabels=[label for _, label in conditions],
        ylim=(5e-4, 3.5e-1),
    )
    axis.grid(axis="y", alpha=0.18)
    axis.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=3,
        fontsize=6.3,
        columnspacing=0.8,
        handletextpad=0.35,
    )
    panel(axis, "(a)")

    axis = axes[1]
    axis.set_axis_off()
    axis.set(xlim=(0, 1), ylim=(0, 1))
    box(
        axis,
        (0.02, 0.64),
        0.25,
        0.22,
        "Device episode",
        "Dₜ={(θᵢ,yᵢ)}\nscalar observations",
        title_size=6.6,
        body_size=5.7,
    )
    box(
        axis,
        (0.37, 0.64),
        0.23,
        0.22,
        "Encoder",
        "zₜ=E(Dₜ)\nlearned belief state",
        color=GREEN,
        title_size=7.0,
        body_size=5.7,
    )
    box(
        axis,
        (0.70, 0.64),
        0.27,
        0.22,
        "Predict + plan",
        "P(zₜ,θ) → loss/next z\nselect next query",
        color=BLUE,
        title_size=6.5,
        body_size=5.6,
    )
    arrow(axis, (0.27, 0.75), (0.37, 0.75))
    arrow(axis, (0.60, 0.75), (0.70, 0.75))
    arrow(
        axis,
        (0.84, 0.61),
        (0.15, 0.61),
        color=ORANGE,
        connectionstyle="arc3,rad=-0.16",
    )
    axis.text(
        0.52,
        0.51,
        "new device measurement updates the latent belief",
        ha="center",
        va="center",
        fontsize=6.2,
        color=ORANGE,
    )
    axis.add_patch(
        FancyBboxPatch(
            (0.10, 0.12),
            0.80,
            0.24,
            boxstyle="round,pad=0.015,rounding_size=0.02",
            linewidth=1.0,
            edgecolor=GREEN,
            facecolor="#EEF8F4",
        )
    )
    axis.text(
        0.50,
        0.28,
        "Offline training objective",
        ha="center",
        va="center",
        fontweight="bold",
        fontsize=7.3,
    )
    axis.text(
        0.50,
        0.19,
        "next-view / next-belief prediction  +  λ·SIGReg(z)\n"
        "broad, disjoint device episodes\n"
        "no physical labels at deployment",
        ha="center",
        va="center",
        fontsize=6.0,
    )
    axis.text(
        0.02,
        0.95,
        "proposed and not yet validated",
        ha="left",
        va="top",
        fontsize=7.2,
        color=PURPLE,
        fontweight="bold",
    )
    panel(axis, "(b)")
    save(figure, "paper_fig3_latent_world_model")


def main() -> None:
    style()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    figure_intrinsic_dimension()
    figure_closed_loop_answer()
    manifest = {
        "figures": [
            "paper_fig1_intrinsic_dimension",
            "paper_fig2_closed_loop_answer",
        ],
        "sources": [
            "invariant_spectra.npz",
            "single_qubit_summary.csv",
            "closed_loop_cobyqa_summary.csv",
            "adaptive_hybrid_summary.csv",
        ],
        "scope": "Two completed figures answering challenge issue #113.",
    }
    (ARTIFACT_DIR / "paper_figures.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print("rendered two final challenge-report figures", flush=True)


if __name__ == "__main__":
    main()
