#!/usr/bin/env python3
"""Create the five publication figures and generated LaTeX inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d


VERSION = "v1"
FIGURE_WIDTH = 7.0
DPI = 300
COLORS = {
    "physical": "#0072B2",
    "haar": "#222222",
    "deformed": "#E69F00",
    "atom": "#CC79A7",
    "reference": "#666666",
    "accent": "#009E73",
}
LABELS = {
    "physical": "physical",
    "haar": "Haar--Jacobi",
    "deformed": "covariance model",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["STIX Two Text", "STIXGeneral", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 8.2,
            "axes.labelsize": 8.5,
            "axes.titlesize": 9.0,
            "legend.fontsize": 7.2,
            "xtick.labelsize": 7.4,
            "ytick.labelsize": 7.4,
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
) -> None:
    mean = arrays[f"{prefix}_mean"]
    lower = arrays[f"{prefix}_lower"]
    upper = arrays[f"{prefix}_upper"]
    ax.fill_between(x, lower, upper, color=color, alpha=0.16, linewidth=0)
    ax.plot(x, mean, color=color, label=label)


def _save(fig, output_dir: Path, stem: str) -> dict[str, Any]:
    pdf = output_dir / f"{stem}.pdf"
    png = output_dir / f"{stem}.png"
    fig.savefig(pdf, format="pdf")
    fig.savefig(png, format="png", dpi=DPI)
    plt.close(fig)
    return {
        "pdf": str(pdf),
        "png": str(png),
        "width_inches": FIGURE_WIDTH,
        "png_width_pixels": int(round(FIGURE_WIDTH * DPI)),
        "dpi": DPI,
    }


def _figure_physical_law(
    stat: Any,
    covariance: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    grid = stat["density_grid"]
    fig = plt.figure(figsize=(FIGURE_WIDTH, 4.65), layout="constrained")
    axes = fig.subplot_mosaic(
        [["density", "density"], ["residual", "moments"]],
        height_ratios=[1.25, 1.0],
    )
    ax = axes["density"]
    for name in ("haar", "deformed", "physical"):
        _band(
            ax,
            grid,
            stat,
            f"{name}_density",
            COLORS[name],
            LABELS[name],
        )
    ax.set_xlim(-1.0, 1.0)
    ax.set_ylabel(r"one-point density $\rho(\lambda)$")
    ax.set_xlabel(r"normalized curvature eigenvalue $\lambda$")
    ax.legend(frameon=False, ncol=3, loc="upper center")
    _panel(ax, "a", "High-statistics physical law")

    ax = axes["residual"]
    physical = stat["physical_density_mean"]
    for name in ("haar", "deformed"):
        difference = physical - stat[f"{name}_density_mean"]
        standard_error = np.sqrt(
            stat["physical_density_standard_error"] ** 2
            + stat[f"{name}_density_standard_error"] ** 2
        )
        color = COLORS[name]
        ax.fill_between(
            grid,
            difference - 2.5 * standard_error,
            difference + 2.5 * standard_error,
            color=color,
            alpha=0.16,
            linewidth=0,
        )
        ax.plot(
            grid,
            difference,
            color=color,
            label=f"physical $-$ {LABELS[name]}",
        )
    ax.axhline(0.0, color="#777777", linewidth=0.7)
    ax.set_xlim(-1.0, 1.0)
    ax.set_xlabel(r"$\lambda$")
    ax.set_ylabel(r"density residual")
    ax.legend(frameon=False, loc="upper left")
    _panel(ax, "b", "Resolved global deformation")

    ax = axes["moments"]
    orders = stat["moment_orders"]
    width = 0.22
    positions = np.arange(orders.size)
    for shift, name in zip(
        (-width, 0.0, width),
        ("haar", "deformed", "physical"),
        strict=True,
    ):
        mean = stat[f"{name}_moments_mean"]
        error = stat[f"{name}_moments_standard_error"]
        ax.bar(
            positions + shift,
            mean,
            width=width,
            color=COLORS[name],
            alpha=0.82,
            label=LABELS[name],
            yerr=1.96 * error,
            capsize=2,
            linewidth=0,
        )
    ax.set_xticks(positions, [rf"$m_{{{int(order)}}}$" for order in orders])
    ax.set_ylabel(r"$D^{-1}\langle\mathrm{Tr}\,\Omega^k\rangle$")
    ax.set_yscale("log")
    ax.legend(frameon=False, ncol=1, loc="upper right")
    _panel(ax, "c", "Moments through eighth order")
    return _save(fig, output_dir, "figure_1_physical_law_v1")


def _figure_scale_hierarchy(
    stat: Any,
    output_dir: Path,
) -> dict[str, Any]:
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(FIGURE_WIDTH, 5.2),
        layout="constrained",
    )
    configurations = (
        (
            axes[0, 0],
            stat["ratio_centers"],
            "ratio",
            r"$P(r)$",
            r"adjacent-gap ratio $r$",
            "a",
            "Local level repulsion",
        ),
        (
            axes[0, 1],
            stat["lengths"],
            "number",
            r"$\Sigma^2(L)$",
            r"window length $L$",
            "b",
            "Number variance",
        ),
        (
            axes[1, 0],
            stat["lengths"],
            "rigidity",
            r"$\Delta_3(L)$",
            r"window length $L$",
            "c",
            "Spectral rigidity",
        ),
        (
            axes[1, 1],
            stat["form_factor_times"],
            "form_factor",
            r"$K_c(\tau)$",
            r"scaled time $\tau$",
            "d",
            "Connected form factor",
        ),
    )
    for ax, x, metric, ylabel, xlabel, label, title in configurations:
        for name in ("haar", "deformed", "physical"):
            _band(
                ax,
                x,
                stat,
                f"{name}_{metric}",
                COLORS[name],
                LABELS[name],
            )
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        _panel(ax, label, title)
    axes[0, 0].legend(frameon=False, loc="lower right")
    axes[1, 1].set_xlim(0.0, 1.5)
    axes[1, 1].set_ylim(bottom=-0.04)
    return _save(fig, output_dir, "figure_2_scale_hierarchy_v1")


def _hist_density(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    edges = np.linspace(-1.02, 1.02, 409)
    density, _ = np.histogram(values.ravel(), bins=edges, density=True)
    centers = 0.5 * (edges[:-1] + edges[1:])
    smoothed = gaussian_filter1d(density, 2.0)
    curve = np.interp(grid, centers, smoothed)
    return curve / np.trapezoid(curve, grid)


def _figure_atom_crossover(
    scaling_json: dict[str, Any],
    scaling: Any,
    output_dir: Path,
) -> dict[str, Any]:
    cases = scaling_json["cases"]
    grid = np.linspace(-1.0, 1.0, 500)
    fig, (ax, atom_ax) = plt.subplots(
        1,
        2,
        figsize=(FIGURE_WIDTH, 4.7),
        gridspec_kw={"width_ratios": [2.2, 1.0]},
        layout="constrained",
    )
    colors = plt.cm.viridis(np.linspace(0.12, 0.9, len(cases)))
    offset = 0.9
    for index, (case, color) in enumerate(
        zip(cases, colors, strict=True)
    ):
        n = case["n"]
        physical = _hist_density(
            scaling[f"n{n}_interior_spectra"],
            grid,
        )
        reference = _hist_density(
            scaling[f"n{n}_reference_interior_spectra"],
            grid,
        )
        baseline = index * offset
        ax.fill_between(
            grid,
            baseline,
            baseline + 0.52 * physical / np.max(physical),
            color=color,
            alpha=0.60,
            linewidth=0,
        )
        ax.plot(
            grid,
            baseline + 0.52 * physical / np.max(physical),
            color=color,
            linewidth=1.15,
        )
        ax.plot(
            grid,
            baseline + 0.52 * reference / np.max(reference),
            color=COLORS["reference"],
            linewidth=0.75,
            linestyle=(0, (2, 2)),
        )
    ax.set_yticks(
        np.arange(len(cases)) * offset + 0.16,
        [
            rf"$D={case['D']}$" + (
                rf", $a={case['plus_atoms_per_matrix']}$"
                if case["plus_atoms_per_matrix"]
                else ""
            )
            for case in cases
        ],
    )
    ax.set_xlabel(r"interior eigenvalue $\lambda$")
    ax.set_ylabel("increasing root rank")
    ax.set_xlim(-1.0, 1.0)
    ax.set_ylim(-0.08, (len(cases) - 1) * offset + 0.72)
    ax.plot([], [], color=COLORS["reference"], linestyle=(0, (2, 2)),
            label="exact Jacobi")
    ax.plot([], [], color=colors[-1], label="root response")
    ax.legend(
        frameon=False,
        loc="center",
        bbox_to_anchor=(0.53, 0.105),
        ncol=2,
    )
    _panel(ax, "a", "Continuous spectrum across the capacity boundary")

    D = np.asarray([case["D"] for case in cases], dtype=float)
    M = np.asarray([case["M"] for case in cases], dtype=float)
    atom_weight = np.asarray(
        [
            2.0 * case["plus_atoms_per_matrix"] / case["D"]
            for case in cases
        ]
    )
    atom_ax.plot(
        D,
        D / M,
        color=COLORS["accent"],
        marker="o",
        label=r"capacity ratio $D/M$",
    )
    atom_ax.axhline(1.0, color="#777777", linestyle="--", linewidth=0.8)
    atom_ax.set_xscale("log")
    atom_ax.set_xlabel(r"active rank $D$")
    atom_ax.set_ylabel(r"$D/M$")
    atom_ax.set_ylim(0.0, 1.35)
    twin = atom_ax.twinx()
    twin.plot(
        D,
        atom_weight,
        color=COLORS["atom"],
        marker="s",
        label="total atom weight",
    )
    twin.set_ylabel(r"$2(D-M)_+/D$", color=COLORS["atom"])
    twin.tick_params(axis="y", colors=COLORS["atom"])
    twin.set_ylim(0.0, 0.36)
    handles, labels = atom_ax.get_legend_handles_labels()
    handles2, labels2 = twin.get_legend_handles_labels()
    atom_ax.legend(
        handles + handles2,
        labels + labels2,
        frameon=False,
        loc="upper left",
    )
    _panel(atom_ax, "b", "Exact atom onset at $D=M$")
    return _save(fig, output_dir, "figure_3_atom_crossover_v1")


def _fit_curve(model: dict[str, Any], grid: np.ndarray) -> np.ndarray:
    return (
        model["offset"]
        + model["amplitude"] * grid ** (-model["exponent"])
    )


def _figure_finite_size(
    statistical_json: dict[str, Any],
    stat: Any,
    output_dir: Path,
) -> dict[str, Any]:
    D = stat["scaling_D"]
    grid = np.geomspace(float(np.min(D)), float(np.max(D)), 300)
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(FIGURE_WIDTH, 2.75),
        layout="constrained",
    )
    panels = (
        (
            axes[0],
            "density_l1",
            stat["scaling_density_l1"],
            stat["scaling_density_se"],
            r"interior density $L^1$",
            "a",
            "Global density",
        ),
        (
            axes[1],
            "gap_ratio_difference",
            stat["scaling_gap_difference"],
            stat["scaling_gap_se"],
            r"$|\Delta\langle r\rangle|$",
            "b",
            "Local repulsion",
        ),
        (
            axes[2],
            "participation_deficit",
            1.0 - stat["scaling_participation"],
            stat["scaling_participation_se"],
            r"$1-\mathcal{P}$",
            "c",
            "Channel participation",
        ),
    )
    atom_mask = stat["scaling_atom_weight"] > 0
    for ax, key, y, error, ylabel, label, title in panels:
        fit = statistical_json["finite_size_fits"][key]
        best = fit["best_by_loo"]
        model = fit["models"][best]
        ax.errorbar(
            D[~atom_mask],
            y[~atom_mask],
            yerr=1.96 * error[~atom_mask],
            fmt="o",
            color=COLORS["physical"],
            capsize=2,
            label="atom free",
        )
        ax.errorbar(
            D[atom_mask],
            y[atom_mask],
            yerr=1.96 * error[atom_mask],
            fmt="s",
            color=COLORS["atom"],
            capsize=2,
            label="atom sector present",
        )
        ax.plot(
            grid,
            _fit_curve(model, grid),
            color=COLORS["haar"],
            linestyle="--",
            label=rf"best LOO: $p={model['exponent']:.2f}$",
        )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(r"active rank $D$")
        ax.set_ylabel(ylabel)
        ax.legend(frameon=False, loc="upper right")
        _panel(ax, label, title)
    return _save(fig, output_dir, "figure_4_finite_size_v1")


def _figure_covariance_mechanism(
    covariance_json: dict[str, Any],
    covariance: Any,
    statistical_json: dict[str, Any],
    stat: Any,
    output_dir: Path,
) -> dict[str, Any]:
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(FIGURE_WIDTH, 5.0),
        layout="constrained",
    )
    eigenvalues = np.sort(covariance["covariance_eigenvalues"])[::-1]
    eigenvalues = eigenvalues / np.mean(eigenvalues)
    ax = axes[0, 0]
    ax.plot(
        np.arange(1, eigenvalues.size + 1),
        eigenvalues,
        color=COLORS["physical"],
    )
    ax.axhline(1.0, color=COLORS["haar"], linestyle="--", linewidth=0.8)
    ax.set_yscale("log")
    ax.set_xlabel("covariance eigenvalue index")
    ax.set_ylabel(r"$c_\alpha/\overline{c}$")
    _panel(ax, "a", "Learned channel covariance")

    ax = axes[0, 1]
    floors = np.asarray(covariance_json["candidate_floors"])
    density = np.asarray(
        [
            covariance_json["validation_scores"][str(value)][
                "density_l1"
            ]
            for value in floors
        ]
    )
    gap = np.asarray(
        [
            covariance_json["validation_scores"][str(value)][
                "gap_ratio_difference"
            ]
            for value in floors
        ]
    )
    ax.plot(
        floors,
        density,
        marker="o",
        color=COLORS["deformed"],
        label="density $L^1$",
    )
    ax.set_xscale("log")
    ax.set_xlabel("eigenvalue floor")
    ax.set_ylabel(r"validation density $L^1$")
    twin = ax.twinx()
    twin.plot(
        floors,
        gap,
        marker="s",
        color=COLORS["physical"],
        label=r"$|\Delta\langle r\rangle|$",
    )
    twin.set_ylabel(r"validation $|\Delta\langle r\rangle|$")
    selected = covariance_json["selected_floor"]
    ax.axvline(selected, color="#777777", linestyle=":", linewidth=0.9)
    ax.text(
        selected,
        np.max(density),
        f" selected {selected:g}",
        ha="left",
        va="top",
        fontsize=7.0,
    )
    handles, labels = ax.get_legend_handles_labels()
    handles2, labels2 = twin.get_legend_handles_labels()
    ax.legend(
        handles + handles2,
        labels + labels2,
        frameon=False,
        loc="lower left",
    )
    _panel(ax, "b", "Validation-only regularization")

    ax = axes[1, 0]
    orders = stat["moment_orders"]
    physical = stat["physical_moments_mean"]
    for name, marker in (("haar", "o"), ("deformed", "s")):
        ratio = stat[f"{name}_moments_mean"] / physical
        ratio_error = stat[f"{name}_moments_standard_error"] / physical
        ax.errorbar(
            orders,
            ratio,
            yerr=1.96 * ratio_error,
            marker=marker,
            color=COLORS[name],
            capsize=2,
            label=LABELS[name],
        )
    ax.axhline(1.0, color=COLORS["physical"], linewidth=1.0,
               label="physical target")
    ax.set_xticks(orders)
    ax.set_xlabel("moment order")
    ax.set_ylabel("model / physical")
    ax.legend(frameon=False, loc="best")
    _panel(ax, "c", "Global moments")

    ax = axes[1, 1]
    bandwidth = statistical_json["sensitivity"]["bandwidth"]
    widths = np.asarray([float(value) for value in bandwidth])
    haar_l1 = np.asarray(
        [bandwidth[str(value)]["physical_haar_l1"] for value in widths]
    )
    deformed_l1 = np.asarray(
        [
            bandwidth[str(value)]["physical_deformed_l1"]
            for value in widths
        ]
    )
    ax.plot(
        widths,
        haar_l1,
        marker="o",
        color=COLORS["haar"],
        label=LABELS["haar"],
    )
    ax.plot(
        widths,
        deformed_l1,
        marker="s",
        color=COLORS["deformed"],
        label=LABELS["deformed"],
    )
    ax.set_xlabel("KDE bandwidth")
    ax.set_ylabel(r"test density $L^1$")
    ax.legend(frameon=False, loc="best")
    _panel(ax, "d", "Bandwidth-stable improvement")
    return _save(fig, output_dir, "figure_5_covariance_mechanism_v1")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_generated_inputs(
    output_dir: Path,
    physical_json: dict[str, Any],
    covariance_json: dict[str, Any],
    scaling_json: dict[str, Any],
    statistical_json: dict[str, Any],
    stat: Any,
) -> None:
    held_out = covariance_json["held_out_test"]
    largest = scaling_json["cases"][-1]
    physical_case = physical_json["physical_case"]
    density_fit = statistical_json["finite_size_fits"]["density_l1"][
        "models"
    ]["free"]
    length_index = int(np.argmin(np.abs(stat["lengths"] - 8.0)))
    time_index = int(
        np.argmin(np.abs(stat["form_factor_times"] - 0.5))
    )
    lines = [
        rf"\newcommand{{\PhysicalMatrices}}{{{physical_json['sample_count']}}}",
        rf"\newcommand{{\PhysicalTestMatrices}}{{{statistical_json['physical_test_matrices']}}}",
        rf"\newcommand{{\PhysicalRank}}{{{physical_case['D']}}}",
        rf"\newcommand{{\PhysicalChannels}}{{{physical_case['M']}}}",
        rf"\newcommand{{\TrainingRows}}{{{covariance_json['diagnostic_training_rows']}}}",
        rf"\newcommand{{\HaarMatrices}}{{{statistical_json['haar_matrices']}}}",
        rf"\newcommand{{\DeformedMatrices}}{{{statistical_json['deformed_matrices']}}}",
        rf"\newcommand{{\SelectedCovFloor}}{{{covariance_json['selected_floor']:.3f}}}",
        rf"\newcommand{{\DensityHaarLone}}{{{held_out['density_l1']['physical_vs_haar']:.4f}}}",
        rf"\newcommand{{\DensityCovLone}}{{{held_out['density_l1']['physical_vs_deformed']:.4f}}}",
        rf"\newcommand{{\DensityImprovementPercent}}{{{100.0 * held_out['density_l1']['relative_improvement']:.1f}\%}}",
        rf"\newcommand{{\PhysicalGapRatio}}{{{held_out['mean_gap_ratio']['physical']:.6f}}}",
        rf"\newcommand{{\HaarGapRatio}}{{{held_out['mean_gap_ratio']['haar']:.6f}}}",
        rf"\newcommand{{\DeformedGapRatio}}{{{held_out['mean_gap_ratio']['deformed']:.6f}}}",
        rf"\newcommand{{\LargestRank}}{{{largest['D']}}}",
        rf"\newcommand{{\LargestChannels}}{{{largest['M']}}}",
        rf"\newcommand{{\LargestAtomMultiplicity}}{{{largest['plus_atoms_per_matrix']}}}",
        rf"\newcommand{{\LargestAtomWeightPercent}}{{{100.0 * 2 * largest['plus_atoms_per_matrix'] / largest['D']:.1f}\%}}",
        rf"\newcommand{{\LargestInteriorDensityLone}}{{{largest['interior_density_l1']:.4f}}}",
        rf"\newcommand{{\DensityFitExponent}}{{{density_fit['exponent']:.3f}}}",
        rf"\newcommand{{\BootstrapReplicates}}{{{statistical_json['bootstrap_replicates']}}}",
        rf"\newcommand{{\RootMatricesTotal}}{{{sum(case['samples'] for case in scaling_json['cases'])}}}",
        rf"\newcommand{{\CovarianceAnisotropy}}{{{covariance_json['training_geometry']['relative_frobenius_anisotropy']:.3f}}}",
        rf"\newcommand{{\PhysicalParticipation}}{{{covariance_json['training_geometry']['mean_participation_fraction']:.3f}}}",
        rf"\newcommand{{\NumberVariancePhysEight}}{{{float(stat['physical_number_mean'][length_index]):.3f}}}",
        rf"\newcommand{{\NumberVarianceHaarEight}}{{{float(stat['haar_number_mean'][length_index]):.3f}}}",
        rf"\newcommand{{\NumberVarianceCovEight}}{{{float(stat['deformed_number_mean'][length_index]):.3f}}}",
        rf"\newcommand{{\FormFactorPhysHalf}}{{{float(stat['physical_form_factor_mean'][time_index]):.3f}}}",
        rf"\newcommand{{\FormFactorHaarHalf}}{{{float(stat['haar_form_factor_mean'][time_index]):.3f}}}",
        rf"\newcommand{{\FormFactorCovHalf}}{{{float(stat['deformed_form_factor_mean'][time_index]):.3f}}}",
    ]
    (output_dir / "generated_numbers_v1.tex").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    table = [
        r"\begin{tabular}{rrrrrr}",
        r"\hline\hline",
        r"$D$ & $M$ & samples & atoms/edge & $\Delta\langle r\rangle$ & $L^1_{\rm int}$ \\",
        r"\hline",
    ]
    for case in scaling_json["cases"]:
        table.append(
            f"{case['D']} & {case['M']} & {case['samples']} & "
            f"{case['plus_atoms_per_matrix']} & "
            f"{case['gap_ratio_difference']:.5f} & "
            f"{case['interior_density_l1']:.5f} \\\\"
        )
    table.extend([r"\hline\hline", r"\end{tabular}"])
    (output_dir / "generated_tables_v1.tex").write_text(
        "\n".join(table) + "\n",
        encoding="utf-8",
    )


def run(
    output_dir: Path,
    physical_json_path: Path = Path("output/physical_ensemble_v1.json"),
    covariance_json_path: Path = Path("output/covariance_model_v1.json"),
    covariance_npz_path: Path = Path("output/covariance_model_v1.npz"),
    scaling_json_path: Path = Path("output/rank_scaling_v1.json"),
    scaling_npz_path: Path = Path("output/rank_scaling_v1.npz"),
    statistical_json_path: Path = Path(
        "output/statistical_analysis_v1.json"
    ),
    statistical_npz_path: Path = Path(
        "output/statistical_analysis_v1.npz"
    ),
) -> dict[str, Any]:
    """Generate figures, macros, tables, and a hash manifest."""

    _style()
    output_dir.mkdir(parents=True, exist_ok=True)
    physical_json = json.loads(
        physical_json_path.read_text(encoding="utf-8")
    )
    covariance_json = json.loads(
        covariance_json_path.read_text(encoding="utf-8")
    )
    scaling_json = json.loads(
        scaling_json_path.read_text(encoding="utf-8")
    )
    statistical_json = json.loads(
        statistical_json_path.read_text(encoding="utf-8")
    )
    with (
        np.load(covariance_npz_path) as covariance,
        np.load(scaling_npz_path) as scaling,
        np.load(statistical_npz_path) as stat,
    ):
        figures = {
            "figure_1": _figure_physical_law(
                stat,
                covariance_json,
                output_dir,
            ),
            "figure_2": _figure_scale_hierarchy(stat, output_dir),
            "figure_3": _figure_atom_crossover(
                scaling_json,
                scaling,
                output_dir,
            ),
            "figure_4": _figure_finite_size(
                statistical_json,
                stat,
                output_dir,
            ),
            "figure_5": _figure_covariance_mechanism(
                covariance_json,
                covariance,
                statistical_json,
                stat,
                output_dir,
            ),
        }
        _write_generated_inputs(
            output_dir,
            physical_json,
            covariance_json,
            scaling_json,
            statistical_json,
            stat,
        )
    inputs = (
        physical_json_path,
        covariance_json_path,
        covariance_npz_path,
        scaling_json_path,
        scaling_npz_path,
        statistical_json_path,
        statistical_npz_path,
    )
    manifest = {
        "schema_version": 1,
        "version": VERSION,
        "figure_width_inches": FIGURE_WIDTH,
        "png_dpi": DPI,
        "inputs": {
            str(path): _sha256(path) for path in inputs
        },
        "figures": figures,
        "atom_annotations": {
            "D546_each_boundary": 6,
            "D800_each_boundary": 120,
            "D800_total_weight": 0.30,
        },
    }
    for figure in figures.values():
        figure["pdf_sha256"] = _sha256(Path(figure["pdf"]))
        figure["png_sha256"] = _sha256(Path(figure["png"]))
    manifest_path = output_dir / "figure_manifest_v1.json"
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
        default=Path("output"),
    )
    args = parser.parse_args()
    manifest = run(args.output_dir)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
