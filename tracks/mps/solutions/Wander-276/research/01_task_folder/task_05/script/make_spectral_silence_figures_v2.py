#!/usr/bin/env python3
"""Create the argument-ordered v2 publication figures and TeX inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np


VERSION = "v2"
FIGURE_WIDTH = 7.0
DPI = 300
COLORS = {
    "structured": "#CC79A7",
    "physical": "#0072B2",
    "haar": "#222222",
    "jacobi": "#009E73",
    "spectral": "#E69F00",
    "residual": "#D55E00",
    "gray": "#777777",
    "light": "#D9D9D9",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": [
                "STIX Two Text",
                "STIXGeneral",
                "DejaVu Serif",
            ],
            "mathtext.fontset": "stix",
            "font.size": 8.2,
            "axes.labelsize": 8.5,
            "axes.titlesize": 9.0,
            "legend.fontsize": 7.0,
            "xtick.labelsize": 7.3,
            "ytick.labelsize": 7.3,
            "axes.linewidth": 0.75,
            "lines.linewidth": 1.35,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _panel(ax, label: str, title: str) -> None:
    ax.text(
        -0.12,
        1.04,
        f"({label})",
        transform=ax.transAxes,
        fontweight="bold",
        va="bottom",
    )
    ax.set_title(title, loc="left", pad=5.0)


def _band(
    ax,
    x: np.ndarray,
    arrays: Any,
    prefix: str,
    color: str,
    label: str,
    alpha: float = 0.16,
    linestyle: str = "-",
) -> None:
    ax.fill_between(
        x,
        arrays[f"{prefix}_lower"],
        arrays[f"{prefix}_upper"],
        color=color,
        alpha=alpha,
        linewidth=0,
    )
    ax.plot(
        x,
        arrays[f"{prefix}_mean"],
        color=color,
        label=label,
        linestyle=linestyle,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _save(
    fig,
    output_dir: Path,
    stem: str,
) -> dict[str, Any]:
    pdf = (output_dir / f"{stem}.pdf").resolve()
    png = (output_dir / f"{stem}.png").resolve()
    fig.savefig(pdf, format="pdf")
    fig.savefig(png, format="png", dpi=DPI)
    plt.close(fig)
    return {
        "pdf": str(pdf),
        "png": str(png),
        "pdf_sha256": _sha256(pdf),
        "png_sha256": _sha256(png),
        "width_inches": FIGURE_WIDTH,
        "png_width_pixels": int(round(FIGURE_WIDTH * DPI)),
        "dpi": DPI,
    }


def _combined_legend(ax, twin=None, **kwargs) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if twin is not None:
        twin_handles, twin_labels = twin.get_legend_handles_labels()
        handles += twin_handles
        labels += twin_labels
    ax.legend(handles, labels, frameon=False, **kwargs)


def _figure_spectral_silence(
    source: Any,
    stat: Any,
    output_dir: Path,
) -> dict[str, Any]:
    times = stat["times"]
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(FIGURE_WIDTH, 5.15),
        layout="constrained",
    )
    ax = axes[0, 0]
    ax.plot(
        times,
        source["energy_raw"],
        color=COLORS["haar"],
        label=r"raw energy SFF $K_{E,\rm raw}=D$",
    )
    ax.plot(
        times,
        source["energy_connected"],
        color=COLORS["residual"],
        label=r"connected energy SFF $K_{E,c}=0$",
    )
    ax.scatter(
        np.linspace(0.25, 2.75, 22),
        np.full(22, 43.0),
        marker="_",
        color=COLORS["gray"],
        s=18,
        linewidths=0.75,
        label=r"$E_a=E_0$ (exactly degenerate)",
    )
    ax.set_xlim(0.0, 3.0)
    ax.set_ylim(-2.0, 54.0)
    ax.set_xlabel(r"Fourier variable $t$")
    ax.set_ylabel(r"$K_E(t)$")
    ax.legend(frameon=False, loc="center right")
    _panel(ax, "a", "Exact degeneracy: spectral silence")

    ax = axes[0, 1]
    rows = (
        (
            source["structured_spectra"][0],
            2.0,
            COLORS["structured"],
            "structured Fourier",
        ),
        (
            source["physical_test_spectra"][0],
            1.0,
            COLORS["physical"],
            "physical random local",
        ),
        (
            source["haar_spectra"][0],
            0.0,
            COLORS["haar"],
            "Haar--Jacobi",
        ),
    )
    for spectrum, baseline, color, label in rows:
        ax.eventplot(
            np.asarray(spectrum, dtype=float),
            lineoffsets=baseline,
            linelengths=0.62,
            linewidths=0.72,
            colors=color,
            label=label,
        )
    ax.set_yticks([0, 1, 2], ["Jacobi", "physical", "structured"])
    ax.set_xlim(-1.02, 1.02)
    ax.set_ylim(-0.55, 2.55)
    ax.set_xlabel(r"metric-normalized curvature eigenvalue $\lambda$")
    _panel(ax, "b", "Same rank, different geometry")

    ax = axes[1, 0]
    _band(
        ax,
        times,
        stat,
        "physical_form",
        COLORS["physical"],
        "physical",
    )
    ax.plot(
        times,
        stat["jacobi_connected_D50"],
        color=COLORS["jacobi"],
        linestyle="--",
        label="finite-$D$ Jacobi",
    )
    ax.set_xlim(0.0, 1.5)
    ax.set_ylim(-0.04, 1.12)
    ax.set_xlabel(r"dimensionless Fourier scale $\tau$")
    ax.set_ylabel(r"$K_{F,c}(\tau)$")
    twin = ax.twinx()
    twin.plot(
        times,
        stat["structured_form_mean"],
        color=COLORS["structured"],
        alpha=0.82,
        label="structured (right axis)",
    )
    twin.fill_between(
        times,
        stat["structured_form_lower"],
        stat["structured_form_upper"],
        color=COLORS["structured"],
        alpha=0.10,
        linewidth=0,
    )
    twin.set_ylim(-0.2, 6.2)
    twin.set_ylabel(
        r"structured $K_{F,c}$",
        color=COLORS["structured"],
    )
    twin.tick_params(axis="y", colors=COLORS["structured"])
    _combined_legend(ax, twin, loc="lower right")
    _panel(ax, "c", "Geometry restores a correlation ramp")

    ax = axes[1, 1]
    _band(
        ax,
        times,
        stat,
        "physical_form_residual",
        COLORS["residual"],
        r"physical $-$ finite-$D$ Jacobi",
        alpha=0.18,
    )
    ax.axhline(0.0, color=COLORS["gray"], linewidth=0.75)
    ax.axvspan(0.25, 1.5, color=COLORS["jacobi"], alpha=0.06)
    ax.set_xlim(0.0, 1.55)
    ax.set_xlabel(r"$\tau$")
    ax.set_ylabel(r"$\delta K_{F,c}$")
    ax.legend(frameon=False, loc="upper right")
    inset = ax.inset_axes([0.50, 0.12, 0.47, 0.42])
    inset.fill_between(
        stat["lengths"],
        stat["physical_haar_number_residual_lower"],
        stat["physical_haar_number_residual_upper"],
        color=COLORS["physical"],
        alpha=0.18,
        linewidth=0,
    )
    inset.plot(
        stat["lengths"],
        stat["physical_haar_number_residual_mean"],
        color=COLORS["physical"],
        linewidth=1.0,
    )
    inset.axhline(0.0, color=COLORS["gray"], linewidth=0.6)
    inset.axvline(1.0, color=COLORS["residual"], linestyle=":", linewidth=0.8)
    inset.set_xlabel(r"$L$", fontsize=6.8)
    inset.set_ylabel(r"$\Delta\Sigma^2$", fontsize=6.8)
    inset.tick_params(labelsize=6.2)
    _panel(ax, "d", "Ramp universal, long range nonuniversal")
    return _save(
        fig,
        output_dir,
        "figure_1_spectral_silence_v2",
    )


def _figure_falsification_triangle(
    stat: Any,
    output_dir: Path,
) -> dict[str, Any]:
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(FIGURE_WIDTH, 2.75),
        layout="constrained",
    )
    ax = axes[0]
    for prefix, color, label in (
        ("structured", COLORS["structured"], "structured"),
        ("physical", COLORS["physical"], "physical"),
        ("haar", COLORS["haar"], "Haar--Jacobi"),
    ):
        _band(
            ax,
            stat["ratio_centers"],
            stat,
            f"{prefix}_ratio",
            color,
            label,
            alpha=0.13,
        )
    ax.set_yscale("log")
    ax.set_ylim(2e-2, 80)
    ax.set_xlabel(r"adjacent-gap ratio $r$")
    ax.set_ylabel(r"$P(r)$")
    ax.legend(frameon=False, loc="upper right")
    _panel(ax, "a", "Local repulsion")

    ax = axes[1]
    for prefix, color, label in (
        ("physical", COLORS["physical"], "physical"),
        ("haar", COLORS["haar"], "Haar--Jacobi"),
    ):
        _band(
            ax,
            stat["times"],
            stat,
            f"{prefix}_form",
            color,
            label,
            alpha=0.13,
        )
    ax.plot(
        stat["times"],
        stat["jacobi_connected_D50"],
        color=COLORS["jacobi"],
        linestyle="--",
        label="exact finite-$D$",
    )
    twin = ax.twinx()
    twin.plot(
        stat["times"],
        stat["structured_form_mean"],
        color=COLORS["structured"],
        label="structured (right)",
    )
    twin.set_ylim(-0.2, 6.2)
    twin.tick_params(axis="y", colors=COLORS["structured"])
    ax.set_xlim(0.0, 1.5)
    ax.set_ylim(-0.04, 1.12)
    ax.set_xlabel(r"$\tau$")
    ax.set_ylabel(r"$K_{F,c}(\tau)$")
    _combined_legend(ax, twin, loc="lower right")
    _panel(ax, "b", "Connected curvature SFF")

    ax = axes[2]
    for prefix, color, label in (
        ("structured", COLORS["structured"], "structured"),
        ("physical", COLORS["physical"], "physical"),
        ("haar", COLORS["haar"], "Haar--Jacobi"),
    ):
        _band(
            ax,
            stat["lengths"],
            stat,
            f"{prefix}_number",
            color,
            label,
            alpha=0.13,
        )
    ax.set_yscale("log")
    ax.set_xlabel(r"window length $L$")
    ax.set_ylabel(r"$\Sigma^2(L)$")
    ax.legend(frameon=False, loc="lower right")
    _panel(ax, "c", "Long-range memory")
    return _save(
        fig,
        output_dir,
        "figure_2_falsification_triangle_v2",
    )


def _figure_independent_channels(
    stat: Any,
    statistical_json: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(FIGURE_WIDTH, 5.0),
        layout="constrained",
    )
    alpha = stat["alpha_values"]
    ax = axes[0, 0]
    ax.fill_between(
        alpha,
        stat["energy_gap_ratio_lower"],
        stat["energy_gap_ratio_upper"],
        color=COLORS["spectral"],
        alpha=0.18,
        linewidth=0,
    )
    ax.plot(
        alpha,
        stat["energy_gap_ratio_mean"],
        color=COLORS["spectral"],
        marker="o",
        markersize=3.3,
        label=r"energy spectrum of $PHP$",
    )
    ax.axhspan(
        float(stat["haar_ratio_mean_lower"][0]),
        float(stat["haar_ratio_mean_upper"][0]),
        color=COLORS["haar"],
        alpha=0.10,
        label="Haar/GUE interval",
    )
    ax.axvline(0.5, color=COLORS["gray"], linestyle=":", linewidth=0.8)
    ax.set_xlabel(r"intrafiber interpolation $\alpha$")
    ax.set_ylabel(r"$\langle r_E\rangle$")
    ax.legend(frameon=False, loc="lower right")
    _panel(ax, "a", r"Spectral channel: change $PHP$")

    ax = axes[0, 1]
    projector = np.maximum(stat["projector_distance_alpha"], 1e-18)
    curvature = np.maximum(stat["curvature_error_alpha"], 1e-18)
    ax.plot(
        alpha,
        projector,
        color=COLORS["physical"],
        marker="o",
        markersize=3.0,
        label=r"$\|P_\alpha-P_0\|_F$",
    )
    ax.plot(
        alpha,
        curvature,
        color=COLORS["jacobi"],
        marker="s",
        markersize=3.0,
        label=r"curvature-spectrum error",
    )
    ax.set_yscale("log")
    ax.set_ylim(3e-19, 3e-13)
    ax.set_xlabel(r"$\alpha$")
    ax.set_ylabel("invariance error")
    ax.legend(frameon=False, loc="upper left")
    _panel(ax, "b", "Projector geometry does not move")

    ax = axes[1, 0]
    g = np.concatenate([[0.0], stat["g_values"]])
    structured_ratio = float(stat["structured_ratio_mean_mean"][0])
    mean = np.concatenate(
        [[structured_ratio], stat["g_ratio_scalar_mean"]]
    )
    lower = np.concatenate(
        [[structured_ratio], stat["g_ratio_scalar_lower"]]
    )
    upper = np.concatenate(
        [[structured_ratio], stat["g_ratio_scalar_upper"]]
    )
    ax.fill_between(
        g,
        lower,
        upper,
        color=COLORS["physical"],
        alpha=0.18,
        linewidth=0,
    )
    ax.plot(
        g,
        mean,
        color=COLORS["physical"],
        marker="o",
        markersize=3.3,
        label=r"curvature spectrum",
    )
    ax.axhspan(
        float(stat["haar_ratio_mean_lower"][0]),
        float(stat["haar_ratio_mean_upper"][0]),
        color=COLORS["haar"],
        alpha=0.10,
        label="Haar--Jacobi interval",
    )
    ax.axvline(
        0.2,
        color=COLORS["jacobi"],
        linestyle=":",
        linewidth=0.9,
        label=r"$g_{\rm local}=0.20$",
    )
    ax.axvline(
        0.4,
        color=COLORS["residual"],
        linestyle="--",
        linewidth=0.9,
        label=r"$g_{\rm ramp}=0.40$",
    )
    ax.set_xlabel(r"geometric scrambling $g$")
    ax.set_ylabel(r"$\langle r_F\rangle$")
    ax.legend(frameon=False, loc="lower right")
    _panel(ax, "c", r"Geometric channel: change $P(\partial H)Q$")

    ax = axes[1, 1]
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.axvline(0.5, color="white", linewidth=1.3)
    ax.axhline(0.4, color="white", linewidth=1.3)
    colors = np.asarray(
        [
            [
                matplotlib.colors.to_rgb("#ECECEC"),
                matplotlib.colors.to_rgb("#F7DFB1"),
            ],
            [
                matplotlib.colors.to_rgb("#B9DDED"),
                matplotlib.colors.to_rgb("#C9E9D9"),
            ],
        ]
    )
    ax.imshow(
        colors,
        origin="lower",
        extent=(0, 1, 0, 1),
        aspect="auto",
    )
    labels = (
        (0.25, 0.20, "neither"),
        (0.75, 0.20, "spectral only"),
        (0.25, 0.70, "geometric only"),
        (0.75, 0.70, "both"),
    )
    for x, y, label in labels:
        ax.text(x, y, label, ha="center", va="center", fontweight="bold")
    ax.set_xticks([0.25, 0.75], ["regular", "GUE-like"])
    ax.set_yticks([0.20, 0.70], ["structured", "Jacobi-like"])
    ax.set_xlabel(r"intrafiber spectral channel $PHP$")
    ax.set_ylabel(r"projector-geometric channel")
    _panel(ax, "d", "Two independent notions of chaos")
    return _save(
        fig,
        output_dir,
        "figure_3_independent_channels_v2",
    )


def _figure_geometric_hierarchy(
    source: Any,
    stat: Any,
    statistical_json: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    times = stat["times"]
    all_g = np.concatenate([[0.0], stat["g_values"]])
    residual = np.vstack(
        [
            stat["structured_form_mean"]
            - stat["jacobi_connected_D50"],
            stat["g_form_mean"]
            - stat["jacobi_connected_D50"][None, :],
        ]
    )
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(FIGURE_WIDTH, 5.0),
        layout="constrained",
    )
    ax = axes[0, 0]
    mask = times <= 1.5
    image = ax.imshow(
        residual[:, mask],
        origin="lower",
        aspect="auto",
        extent=(
            float(times[mask][0]),
            float(times[mask][-1]),
            -0.5,
            all_g.size - 0.5,
        ),
        cmap="RdBu_r",
        norm=TwoSlopeNorm(vmin=-0.25, vcenter=0.0, vmax=0.25),
    )
    ax.set_yticks(np.arange(all_g.size), [f"{value:g}" for value in all_g])
    ax.set_xlabel(r"$\tau$")
    ax.set_ylabel(r"scrambling $g$")
    colorbar = fig.colorbar(image, ax=ax, pad=0.02)
    colorbar.set_label(r"$K_{F,c}-K_{J,c}$")
    _panel(ax, "a", "Residual flow toward finite-$D$ Jacobi")

    ax = axes[0, 1]
    registered_mask = (times >= 0.25) & (times <= 1.5)
    rms_residual = np.sqrt(
        np.mean(
            (
                stat["g_form_mean"][:, registered_mask]
                - stat["jacobi_connected_D50"][
                    None,
                    registered_mask,
                ]
            )
            ** 2,
            axis=1,
        )
    )
    ax.plot(
        stat["g_values"],
        rms_residual,
        color=COLORS["residual"],
        marker="o",
        markersize=3.4,
        label=r"RMS SFF residual, $0.25\leq\tau\leq1.5$",
    )
    ax.axvline(
        0.2,
        color=COLORS["jacobi"],
        linestyle=":",
        label=r"local $P(r)$ onset",
    )
    ax.axvline(
        0.4,
        color=COLORS["residual"],
        linestyle="--",
        label=r"first registered ramp window",
    )
    ax.set_xlim(0.0, 1.02)
    ax.set_yscale("log")
    ax.set_xlabel(r"$g$")
    ax.set_ylabel(r"RMS$(K_{F,c}-K_{J,c})$")
    ax.legend(frameon=False, loc="upper right")
    _panel(ax, "b", "Local correlations precede the ramp")

    ax = axes[1, 0]
    _band(
        ax,
        times,
        stat,
        "physical_form_residual",
        COLORS["residual"],
        "physical $-$ finite-$D$ Jacobi",
    )
    ax.axhline(0.0, color=COLORS["gray"], linewidth=0.75)
    ax.axvspan(0.25, 1.5, color=COLORS["jacobi"], alpha=0.07)
    ax.set_xlim(0.0, 1.55)
    ax.set_xlabel(r"$\tau$")
    ax.set_ylabel(r"$\delta K_{F,c}$")
    ax.legend(frameon=False, loc="upper right")
    _panel(ax, "c", r"Physical ramp: compatible for $\tau\geq0.25$")

    ax = axes[1, 1]
    _band(
        ax,
        stat["lengths"],
        stat,
        "physical_haar_number_residual",
        COLORS["physical"],
        r"physical $-$ Haar--Jacobi",
    )
    ax.axhline(0.0, color=COLORS["gray"], linewidth=0.75)
    ax.axvline(
        1.0,
        color=COLORS["residual"],
        linestyle=":",
        label=r"$L_{\rm universal}=1$",
    )
    ax.set_xlabel(r"window length $L$")
    ax.set_ylabel(r"$\Delta\Sigma^2(L)$")
    ax.legend(frameon=False, loc="upper left")
    _panel(ax, "d", "Long-range memory survives")
    return _save(
        fig,
        output_dir,
        "figure_4_geometric_hierarchy_v2",
    )


def _figure_jacobi_atoms(
    source: Any,
    output_dir: Path,
) -> dict[str, Any]:
    times = source["times"]
    D = np.asarray(source["rank_D"], dtype=float)
    k = np.asarray(source["rank_interior"], dtype=float)
    atoms = np.asarray(source["rank_atom_each"], dtype=float)
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(FIGURE_WIDTH, 5.0),
        layout="constrained",
    )
    for ax, index, label, title in (
        (axes[0, 0], 5, "a", r"$D=546$: six atoms per edge"),
        (axes[0, 1], 6, "b", r"$D=800$: 120 atoms per edge"),
    ):
        ax.plot(
            times,
            source["rank_physical_connected_full"][index],
            color=COLORS["physical"],
            label="physical full spectrum",
        )
        ax.plot(
            times,
            source["rank_reference_connected_full"][index],
            color=COLORS["haar"],
            label="Jacobi full spectrum",
        )
        if index == 6:
            ax.plot(
                times,
                source["rank_reference_connected_continuous"][index],
                color=COLORS["jacobi"],
                linestyle="--",
                label="atom-stripped continuous",
            )
        plateau = k[index] / D[index]
        ax.axhline(
            plateau,
            color=COLORS["structured"],
            linestyle=":",
            label=rf"full plateau $k/D={plateau:.3f}$",
        )
        ax.set_xlim(0.0, 2.0)
        ax.set_ylim(-0.04, 1.08)
        ax.set_xlabel(r"$\tau$")
        ax.set_ylabel(r"$K_{F,c}(\tau)$")
        ax.legend(frameon=False, loc="lower right")
        _panel(ax, label, title)

    ax = axes[1, 0]
    plateau = k / D
    ax.plot(
        D,
        plateau,
        color=COLORS["jacobi"],
        marker="o",
        label=r"exact full connected plateau $k/D$",
    )
    ax.plot(
        D,
        2.0 * atoms / D,
        color=COLORS["structured"],
        marker="s",
        label=r"total atom weight $2(D-M)_+/D$",
    )
    ax.set_xscale("log")
    ax.set_xlabel(r"active rank $D$")
    ax.set_ylabel("spectral weight")
    ax.set_ylim(-0.03, 1.06)
    ax.legend(frameon=False, loc="center left")
    _panel(ax, "c", "Exact atom suppression of connected SFF")

    ax = axes[1, 1]
    index = 6
    for key, color, label, linestyle in (
        (
            "rank_reference_raw_full",
            COLORS["haar"],
            "full raw SFF",
            "-",
        ),
        (
            "rank_reference_raw_atom_atom",
            COLORS["structured"],
            "atom--atom",
            "--",
        ),
        (
            "rank_reference_raw_atom_continuum",
            COLORS["residual"],
            "atom--continuum",
            "-.",
        ),
        (
            "rank_reference_raw_continuum_continuum",
            COLORS["physical"],
            "continuum--continuum",
            ":",
        ),
    ):
        ax.plot(
            times,
            source[key][index],
            color=color,
            label=label,
            linestyle=linestyle,
        )
    ax.set_xlim(0.0, 1.5)
    ax.set_xlabel(r"raw Fourier scale $\tau$")
    ax.set_ylabel(r"raw $K_F(\tau)$")
    ax.legend(frameon=False, loc="upper right")
    _panel(ax, "d", "Raw atom decomposition closes exactly")
    return _save(
        fig,
        output_dir,
        "figure_5_jacobi_atoms_v2",
    )


def _write_generated_inputs(
    output_dir: Path,
    source_json: dict[str, Any],
    statistical_json: dict[str, Any],
    source: Any,
    stat: Any,
) -> None:
    outcomes = statistical_json["outcomes"]
    tau_half = int(np.argmin(np.abs(stat["times"] - 0.5)))
    residual = outcomes["number_variance_L8_residual"]
    energy = outcomes["energy_gap_ratio_endpoints"]
    lines = [
        r"\newcommand{\EnergyRawSFF}{50}",
        r"\newcommand{\EnergyConnectedSFF}{0}",
        rf"\newcommand{{\StructuredFormHalf}}{{{float(stat['structured_form_mean'][tau_half]):.3f}}}",
        rf"\newcommand{{\PhysicalFormHalf}}{{{float(stat['physical_form_mean'][tau_half]):.3f}}}",
        rf"\newcommand{{\JacobiFormHalf}}{{{float(stat['jacobi_connected_D50'][tau_half]):.3f}}}",
        rf"\newcommand{{\GeometricTauOnset}}{{{outcomes['physical_tau_compatibility_onset']:.2f}}}",
        rf"\newcommand{{\GeometricLocalOnset}}{{{outcomes['first_g_with_haar_gap_ratio_interval']:.2f}}}",
        rf"\newcommand{{\GeometricRampOnset}}{{{outcomes['first_g_with_registered_jacobi_window']:.2f}}}",
        rf"\newcommand{{\NumberVarianceExtent}}{{{outcomes['number_variance_compatibility_extent']:.1f}}}",
        rf"\newcommand{{\NumberResidualEight}}{{{residual['mean']:.5f}}}",
        rf"\newcommand{{\NumberResidualEightLower}}{{{residual['lower']:.5f}}}",
        rf"\newcommand{{\NumberResidualEightUpper}}{{{residual['upper']:.5f}}}",
        rf"\newcommand{{\PoissonEndpointRatio}}{{{energy['poisson']:.6f}}}",
        rf"\newcommand{{\GUEEndpointRatio}}{{{energy['gue']:.6f}}}",
        rf"\newcommand{{\StructuredMomenta}}{{{source_json['sample_counts']['structured_momenta']}}}",
        rf"\newcommand{{\StructuredOrbits}}{{{source_json['sample_counts']['structured_orbits']}}}",
        rf"\newcommand{{\GeometricSamplesPerPoint}}{{{source_json['sample_counts']['per_positive_g']}}}",
        rf"\newcommand{{\SpectralSamplesPerPoint}}{{{source_json['sample_counts']['fixed_projector_per_alpha']}}}",
        rf"\newcommand{{\BootstrapReplicatesVTwo}}{{{statistical_json['bootstrap_replicates']}}}",
        rf"\newcommand{{\LargestRankVTwo}}{{{int(source['rank_D'][-1])}}}",
        rf"\newcommand{{\LargestAtomEachVTwo}}{{{int(source['rank_atom_each'][-1])}}}",
        rf"\newcommand{{\LargestConnectedPlateau}}{{{float(source['rank_interior'][-1] / source['rank_D'][-1]):.1f}}}",
    ]
    (output_dir / "generated_numbers_v2.tex").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    table = [
        r"\begin{tabular}{rrrr}",
        r"\hline\hline",
        r"$g$ & $\langle r_F\rangle$ & lower & upper \\",
        r"\hline",
    ]
    for index, g in enumerate(stat["g_values"]):
        table.append(
            f"{float(g):.2f} & "
            f"{float(stat['g_ratio_scalar_mean'][index]):.6f} & "
            f"{float(stat['g_ratio_scalar_lower'][index]):.6f} & "
            f"{float(stat['g_ratio_scalar_upper'][index]):.6f} \\\\"
        )
    table.extend([r"\hline\hline", r"\end{tabular}"])
    (output_dir / "generated_tables_v2.tex").write_text(
        "\n".join(table) + "\n",
        encoding="utf-8",
    )


def run(
    output_dir: Path,
    source_json_path: Path | None = None,
    source_npz_path: Path | None = None,
    statistical_json_path: Path | None = None,
    statistical_npz_path: Path | None = None,
    sync_overleaf: bool = False,
) -> dict[str, Any]:
    """Generate five figures, generated TeX, and a hash manifest."""

    _style()
    script_dir = Path(__file__).resolve().parent
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_json_path = (
        script_dir / "output" / "spectral_silence_v2.json"
        if source_json_path is None
        else source_json_path
    )
    source_npz_path = (
        script_dir / "output" / "spectral_silence_v2.npz"
        if source_npz_path is None
        else source_npz_path
    )
    statistical_json_path = (
        script_dir
        / "output"
        / "spectral_silence_statistics_v2.json"
        if statistical_json_path is None
        else statistical_json_path
    )
    statistical_npz_path = (
        script_dir
        / "output"
        / "spectral_silence_statistics_v2.npz"
        if statistical_npz_path is None
        else statistical_npz_path
    )
    source_json = json.loads(
        source_json_path.read_text(encoding="utf-8")
    )
    statistical_json = json.loads(
        statistical_json_path.read_text(encoding="utf-8")
    )
    if not source_json["all_checks_pass"]:
        raise RuntimeError("source scientific artifact failed")
    if not statistical_json["all_checks_pass"]:
        raise RuntimeError("statistical scientific artifact failed")
    with (
        np.load(source_npz_path, allow_pickle=False) as source,
        np.load(statistical_npz_path, allow_pickle=False) as stat,
    ):
        figures = {
            "figure_1": _figure_spectral_silence(
                source,
                stat,
                output_dir,
            ),
            "figure_2": _figure_falsification_triangle(
                stat,
                output_dir,
            ),
            "figure_3": _figure_independent_channels(
                stat,
                statistical_json,
                output_dir,
            ),
            "figure_4": _figure_geometric_hierarchy(
                source,
                stat,
                statistical_json,
                output_dir,
            ),
            "figure_5": _figure_jacobi_atoms(
                source,
                output_dir,
            ),
        }
        _write_generated_inputs(
            output_dir,
            source_json,
            statistical_json,
            source,
            stat,
        )
        annotations = {
            "energy_raw": float(source["energy_raw"][0]),
            "energy_connected": float(source["energy_connected"][0]),
            "local_g": round(
                statistical_json["outcomes"][
                    "first_g_with_haar_gap_ratio_interval"
                ],
                2,
            ),
            "ramp_g": round(
                statistical_json["outcomes"][
                    "first_g_with_registered_jacobi_window"
                ],
                2,
            ),
            "number_extent": float(
                statistical_json["outcomes"][
                    "number_variance_compatibility_extent"
                ]
            ),
            "D800_atom_each": int(source["rank_atom_each"][-1]),
            "D800_connected_plateau": float(
                source["rank_interior"][-1] / source["rank_D"][-1]
            ),
        }
    if sync_overleaf:
        project = (
            script_dir.parents[2]
            / "overleaf_sync"
            / "geometric_eth_large_scale"
        )
        figure_target = project / "figures"
        generated_target = project / "generated"
        figure_target.mkdir(parents=True, exist_ok=True)
        generated_target.mkdir(parents=True, exist_ok=True)
        for figure in figures.values():
            shutil.copy2(figure["pdf"], figure_target)
        shutil.copy2(
            output_dir / "generated_numbers_v2.tex",
            generated_target / "generated_numbers_v2.tex",
        )
        shutil.copy2(
            output_dir / "generated_tables_v2.tex",
            generated_target / "generated_tables_v2.tex",
        )
    inputs = {
        str(path.resolve()): _sha256(path)
        for path in (
            source_json_path,
            source_npz_path,
            statistical_json_path,
            statistical_npz_path,
        )
    }
    checks = {
        "source_artifacts_pass": bool(
            source_json["all_checks_pass"]
            and statistical_json["all_checks_pass"]
        ),
        "five_figures_generated": len(figures) == 5,
        "all_pdf_png_pairs_exist": all(
            Path(figure["pdf"]).is_file()
            and Path(figure["png"]).is_file()
            for figure in figures.values()
        ),
        "registered_annotations_exact": bool(
            annotations["energy_raw"] == 50.0
            and annotations["energy_connected"] == 0.0
            and annotations["local_g"] == 0.2
            and annotations["ramp_g"] == 0.4
            and annotations["number_extent"] == 1.0
            and annotations["D800_atom_each"] == 120
            and abs(
                annotations["D800_connected_plateau"] - 0.7
            )
            < 1e-12
        ),
    }
    manifest = {
        "schema_version": 2,
        "version": VERSION,
        "inputs": inputs,
        "figures": figures,
        "generated_tex": {
            "numbers": str(
                (output_dir / "generated_numbers_v2.tex").resolve()
            ),
            "tables": str(
                (output_dir / "generated_tables_v2.tex").resolve()
            ),
        },
        "scientific_annotations": annotations,
        "checks": checks,
        "all_checks_pass": bool(all(checks.values())),
    }
    manifest_path = output_dir / "figure_manifest_v2.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
    )
    parser.add_argument(
        "--no-sync-overleaf",
        action="store_true",
    )
    args = parser.parse_args()
    result = run(
        args.output_dir,
        sync_overleaf=not args.no_sync_overleaf,
    )
    print(json.dumps(result, indent=2))
    if not result["all_checks_pass"]:
        raise SystemExit("v2 figure audit failed")


if __name__ == "__main__":
    main()
