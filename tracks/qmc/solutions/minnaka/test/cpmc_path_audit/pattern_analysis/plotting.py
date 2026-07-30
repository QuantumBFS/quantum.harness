"""Publication-quality figures for CPMC path-pattern diagnostics."""

from __future__ import annotations

import pathlib
from typing import Iterable

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt


OKABE_ITO = [
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#F0E442",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
    "#000000",
]


def publication_style() -> dict[str, object]:
    """Return a self-contained style based on the visualization skill asset."""

    return {
        "figure.dpi": 100,
        "figure.facecolor": "white",
        "figure.constrained_layout.use": True,
        "font.size": 8,
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "axes.linewidth": 0.5,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.prop_cycle": mpl.cycler(color=OKABE_ITO),
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "lines.linewidth": 1.5,
        "lines.markersize": 4,
        "legend.fontsize": 7,
        "legend.frameon": False,
        "image.cmap": "viridis",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }


def save_publication_figure(
    figure: plt.Figure,
    filename: pathlib.Path | str,
    formats: Iterable[str] = ("pdf", "png"),
    dpi: int = 300,
) -> list[pathlib.Path]:
    """Save vector PDF and lossless 300-dpi PNG with a white background."""

    stem = pathlib.Path(filename)
    stem.parent.mkdir(parents=True, exist_ok=True)
    paths = []
    for suffix in formats:
        output = stem.with_suffix(f".{suffix}")
        figure.savefig(
            output,
            format=suffix,
            dpi=min(dpi, 300) if suffix in {"pdf", "eps", "svg"} else dpi,
            bbox_inches="tight",
            pad_inches=0.05,
            facecolor="white",
            edgecolor="none",
            transparent=False,
        )
        paths.append(output)
    return paths


def _finish(
    figure: plt.Figure, stem: pathlib.Path | str
) -> list[pathlib.Path]:
    paths = save_publication_figure(figure, stem)
    plt.close(figure)
    return paths


def plot_weight_vs_efficiency(
    selection: pd.DataFrame, stem: pathlib.Path | str
) -> list[pathlib.Path]:
    with mpl.rc_context(publication_style()):
        figure, axis = plt.subplots(figsize=(7.0, 3.5))
        roles = selection["role"].isin(["case", "worst_low"])
        data = selection.loc[roles]
        markers = {"rhf_x": "o", "rhf_y": "s", "uhf": "^"}
        for index, (trial, group) in enumerate(data.groupby("trial")):
            if len(group) > 60_000:
                group = group.iloc[
                    np.linspace(0, len(group) - 1, 60_000, dtype=int)
                ]
            axis.scatter(
                group["log_d_over_mean"] / np.log(10.0),
                group["score"],
                s=5,
                alpha=0.25,
                marker=markers.get(trial, "o"),
                color=OKABE_ITO[index],
                edgecolors="none",
                label=f"{trial} (n={len(data.loc[data.trial == trial])})",
            )
        for value, label in (
            (np.log10(0.5), "0.5"),
            (0.0, "1"),
            (np.log10(2.0), "2"),
        ):
            axis.axvline(value, color="0.5", linewidth=0.7, linestyle="--")
            axis.text(value, 0.98, label, transform=axis.get_xaxis_transform(),
                      ha="center", va="top", fontsize=7)
        axis.set_xlabel("Physical path weight  log₁₀[D/⟨D⟩]")
        axis.set_ylabel("Under-sampling score  log₁₀[(D/ΣD)/Q]")
        axis.legend(loc="best")
        return _finish(figure, stem)


def plot_matched_weight_trajectories(
    steps: pd.DataFrame, stem: pathlib.Path | str
) -> list[pathlib.Path]:
    with mpl.rc_context(publication_style()):
        figure, axes = plt.subplots(
            1, 2, figsize=(7.0, 3.1), sharex=True
        )
        styles = {"case": "-", "control": "--", "low_weight_reference": ":"}
        for trial_index, (trial, trial_data) in enumerate(
            steps.groupby("trial")
        ):
            for role, role_data in trial_data.groupby("role"):
                if role not in styles:
                    continue
                grouped = role_data.groupby("event_index")
                x = np.array(sorted(grouped.groups))
                color = OKABE_ITO[trial_index]
                for axis, column, ylabel in (
                    (axes[0], "cumulative_log_w", "Cumulative log W"),
                    (axes[1], "cumulative_log_q", "Cumulative log Q"),
                ):
                    median = grouped[column].median().reindex(x).to_numpy()
                    low = grouped[column].quantile(0.25).reindex(x).to_numpy()
                    high = grouped[column].quantile(0.75).reindex(x).to_numpy()
                    axis.plot(
                        x,
                        median,
                        linestyle=styles[role],
                        color=color,
                        label=f"{trial} {role}",
                    )
                    axis.fill_between(x, low, high, color=color, alpha=0.08)
                    axis.set_ylabel(ylabel)
                    axis.set_xlabel("Propagation event")
        handles, labels = axes[0].get_legend_handles_labels()
        if handles:
            figure.legend(
                handles,
                labels,
                loc="upper center",
                bbox_to_anchor=(0.5, 1.13),
                ncol=3,
            )
        return _finish(figure, stem)


def plot_event_attribution_heatmap(
    steps: pd.DataFrame, stem: pathlib.Path | str
) -> list[pathlib.Path]:
    cases = steps.loc[steps["role"] == "case"]
    trials = list(cases["trial"].drop_duplicates())
    matrix = np.vstack(
        [
            cases.loc[cases["trial"] == trial]
            .groupby("event_index")["paired_delta_log_w"]
            .median()
            .to_numpy()
            for trial in trials
        ]
    )
    limit = max(float(np.nanmax(np.abs(matrix))), 1.0e-12)
    with mpl.rc_context(publication_style()):
        figure, axis = plt.subplots(figsize=(7.0, 2.2))
        image = axis.imshow(
            matrix,
            aspect="auto",
            cmap="PuOr",
            vmin=-limit,
            vmax=limit,
        )
        axis.set_yticks(np.arange(len(trials)), labels=trials)
        axis.set_xlabel("Propagation event")
        axis.set_ylabel("Trial")
        colorbar = figure.colorbar(image, ax=axis, pad=0.02)
        colorbar.set_label("Median paired Δlog W")
        return _finish(figure, stem)


def plot_principal_angle_trajectories(
    steps: pd.DataFrame, stem: pathlib.Path | str
) -> list[pathlib.Path]:
    with mpl.rc_context(publication_style()):
        figure, axes = plt.subplots(1, 2, figsize=(7.0, 2.8), sharex=True)
        for trial_index, (trial, trial_data) in enumerate(
            steps.groupby("trial")
        ):
            for role, linestyle in (("case", "-"), ("control", "--")):
                data = trial_data.loc[
                    trial_data["role"] == role
                ].copy()
                data["sigma_min"] = data[
                    ["sigma_min_up", "sigma_min_down"]
                ].min(axis=1)
                data["angle_max"] = data[
                    ["angle_max_up", "angle_max_down"]
                ].max(axis=1)
                grouped = data.groupby("event_index")
                x = np.array(sorted(grouped.groups))
                sigma = grouped["sigma_min"].median().reindex(x)
                angle = grouped["angle_max"].median().reindex(x)
                axes[0].plot(
                    x,
                    sigma,
                    linestyle=linestyle,
                    color=OKABE_ITO[trial_index],
                    label=f"{trial} {role}",
                )
                axes[1].plot(
                    x,
                    angle,
                    linestyle=linestyle,
                    color=OKABE_ITO[trial_index],
                )
        axes[0].set_ylabel("Median min σ")
        axes[1].set_ylabel("Median max principal angle (rad)")
        for axis in axes:
            axis.set_xlabel("Propagation event")
        axes[0].legend(ncol=2)
        return _finish(figure, stem)


def plot_motif_enrichment(
    motifs: pd.DataFrame, stem: pathlib.Path | str
) -> list[pathlib.Path]:
    data = motifs.loc[
        (motifs["comparison"] == "all_relevant")
        & np.isfinite(motifs["odds_ratio"])
        & (motifs["case_count"] >= 10)
        & (motifs["control_count"] >= 10)
        & (motifs["q_value"] < 0.05)
    ].copy()
    selected = []
    for _, group in data.groupby("trial", sort=False):
        selected.append(
            group.loc[group["odds_ratio"] > 1.0].nlargest(
                2, "risk_difference"
            )
        )
        selected.append(
            group.loc[group["odds_ratio"] < 1.0].nsmallest(
                2, "risk_difference"
            )
        )
    data = (
        pd.concat(selected, ignore_index=True)
        if selected
        else data.iloc[0:0].copy()
    )
    data["log_odds"] = np.log2(data["odds_ratio"])
    data = data.sort_values("log_odds")
    labels = [
        f"{row.trial}: {row.mask_class}"
        for row in data.itertuples()
    ]
    values = data["log_odds"].to_numpy(dtype=float)
    with mpl.rc_context(publication_style()):
        figure, axis = plt.subplots(figsize=(7.0, 3.5))
        colors = [
            OKABE_ITO[4] if value >= 0 else OKABE_ITO[0]
            for value in values
        ]
        axis.barh(np.arange(len(data)), values, color=colors)
        axis.set_yticks(np.arange(len(data)), labels=labels)
        axis.axvline(0.0, color="black", linewidth=0.6)
        axis.set_xlabel("Matched enrichment  log₂ odds ratio")
        return _finish(figure, stem)


def plot_m4_counterfactual(
    counterfactual: pd.DataFrame, stem: pathlib.Path | str
) -> list[pathlib.Path]:
    variants = ["reverse", "sublattice", "joint"]
    trials = list(counterfactual["trial"].drop_duplicates())
    positions = np.arange(len(variants), dtype=float)
    width = 0.8 / max(len(trials), 1)
    with mpl.rc_context(publication_style()):
        figure, axis = plt.subplots(figsize=(7.0, 3.0))
        for trial_index, trial in enumerate(trials):
            data = counterfactual.loc[counterfactual["trial"] == trial]
            if "relevant_worst_1pct" in data:
                data = data.loc[data["relevant_worst_1pct"]]
            medians = [
                data[f"score_improvement_{variant}"].median()
                for variant in variants
            ]
            axis.bar(
                positions
                + (trial_index - (len(trials) - 1) / 2.0) * width,
                medians,
                width=width,
                color=OKABE_ITO[trial_index],
                label=trial,
            )
        axis.set_xticks(positions, labels=variants)
        axis.axhline(0.0, color="black", linewidth=0.6)
        axis.set_ylabel("Median reduction, relevant worst 1%")
        axis.set_xlabel("Counterfactual proposal")
        axis.legend()
        return _finish(figure, stem)


def create_all_figures(
    *,
    selection: pd.DataFrame,
    steps: pd.DataFrame,
    slice_motifs: pd.DataFrame,
    counterfactual: pd.DataFrame,
    output_directory: pathlib.Path | str,
) -> list[pathlib.Path]:
    output = pathlib.Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    paths.extend(
        plot_weight_vs_efficiency(selection, output / "weight_vs_efficiency")
    )
    paths.extend(
        plot_matched_weight_trajectories(
            steps, output / "matched_weight_trajectories"
        )
    )
    paths.extend(
        plot_event_attribution_heatmap(
            steps, output / "event_attribution_heatmap"
        )
    )
    paths.extend(
        plot_principal_angle_trajectories(
            steps, output / "principal_angle_trajectories"
        )
    )
    paths.extend(
        plot_motif_enrichment(
            slice_motifs, output / "motif_enrichment"
        )
    )
    paths.extend(
        plot_m4_counterfactual(
            counterfactual, output / "m4_counterfactual"
        )
    )
    return paths
