"""Build deterministic, publication-sized native-vector figures."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from paper_data import PaperData, load_paper_data
from vector_data import VectorPlotData, load_vector_plot_data


EXPECTED_FIGURES = (
    "fig01-workflow.pdf",
    "fig02-clean.pdf",
    "fig03-nishimori.pdf",
    "fig04-weak-self-dual.pdf",
    "fig05-benchmark-comparison.pdf",
    "fig06-phase-scans.pdf",
    "fig07-entanglement.pdf",
    "fig08-learning-diagnostics.pdf",
)

COLORS = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "sky": "#56B4E9",
    "gray": "#5B5B5B",
}

plt.rcParams.update(
    {
        "font.size": 8.2,
        "axes.labelsize": 8.2,
        "axes.titlesize": 8.7,
        "legend.fontsize": 7.0,
        "xtick.labelsize": 7.2,
        "ytick.labelsize": 7.2,
        "lines.linewidth": 1.15,
        "lines.markersize": 4.5,
        "axes.linewidth": 0.7,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.bbox": None,
    }
)

_PDF_METADATA = {
    "Title": "Quantum criticality benchmark figure",
    "Author": "Xu Tian and Huidan Tan",
    "Creator": "Quantum Harness PRB paper builder",
    "CreationDate": datetime(2026, 7, 30, tzinfo=timezone.utc),
    "ModDate": datetime(2026, 7, 30, tzinfo=timezone.utc),
}


def build_all_figures(repo_root: Path, output_dir: Path) -> tuple[Path, ...]:
    root = Path(repo_root).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    headline = load_paper_data(root)
    vectors = load_vector_plot_data(root)
    builders: tuple[
        Callable[[PaperData, VectorPlotData], Figure], ...
    ] = (
        figure_workflow,
        figure_clean,
        figure_nishimori,
        figure_weak_self_dual,
        figure_benchmark_comparison,
        figure_phase_scans,
        figure_entanglement,
        figure_learning_diagnostics,
    )
    paths: list[Path] = []
    for name, builder in zip(EXPECTED_FIGURES, builders):
        figure = builder(headline, vectors)
        path = output / name
        figure.savefig(path, format="pdf", metadata=_PDF_METADATA)
        plt.close(figure)
        paths.append(path)
    return tuple(paths)


def figure_workflow(_: PaperData, __: VectorPlotData) -> Figure:
    figure, axis = plt.subplots(figsize=(7.0, 2.8))
    axis.set(xlim=(0, 10), ylim=(0, 4))
    axis.axis("off")
    models = (
        ("Clean Ising", "exact + Wolff", COLORS["blue"]),
        ("Nishimori", "quenched transfer", COLORS["orange"]),
        ("Weak self-dual", "Born Gaussian", COLORS["green"]),
        ("Learning-induced MIT", "XY validation + DIII", COLORS["red"]),
    )
    for index, (title, method, color) in enumerate(models):
        x = 0.25 + 2.45 * index
        axis.add_patch(
            plt.Rectangle((x, 2.55), 2.0, 0.9, facecolor=color, alpha=0.18,
                          edgecolor=color, linewidth=1.0)
        )
        axis.text(x + 1.0, 3.12, title, ha="center", va="center", weight="bold")
        axis.text(x + 1.0, 2.80, method, ha="center", va="center", fontsize=7)
        axis.annotate(
            "", xy=(5.0, 1.75), xytext=(x + 1.0, 2.53),
            arrowprops={"arrowstyle": "->", "color": COLORS["gray"], "lw": 1.0},
        )
    for index, label in enumerate(
        ("Exact / small-system\noracles", "Correlation-aware\nresampling",
         "Finite-size\nstability", "Predeclared\nclaim gates")
    ):
        x = 0.3 + 2.45 * index
        axis.add_patch(
            plt.Rectangle((x, 0.35), 2.0, 0.62, facecolor="#F2F2F2",
                          edgecolor=COLORS["gray"], linewidth=0.8)
        )
        axis.text(x + 1.0, 0.66, label, ha="center", va="center", fontsize=6.8)
    axis.text(5.0, 1.55, "Validation hierarchy", ha="center", va="center",
              weight="bold", fontsize=9)
    _panel(axis, "a")
    return figure


def figure_clean(headline: PaperData, vectors: VectorPlotData) -> Figure:
    points = vectors.clean.free_energy
    widths = np.array([point.width for point in points], dtype=float)
    inverse_square = widths ** -2
    exact = np.array([point.exact for point in points])
    mc = np.array([point.monte_carlo for point in points])
    errors = np.array([point.monte_carlo_se for point in points])
    coarse = np.array([point.coarse_grid for point in points])
    figure, axes = plt.subplots(1, 2, figsize=(7.0, 2.75))
    axis = axes[0]
    axis.plot(inverse_square, exact, "-", color=COLORS["gray"], label="Transfer matrix")
    axis.errorbar(inverse_square, mc, yerr=errors, fmt="o", capsize=2.2,
                  color=COLORS["blue"], label="MC, 129-point TI")
    axis.plot(inverse_square, coarse, "s", fillstyle="none", color=COLORS["orange"],
              label="MC, 65-point TI")
    axis.set(xlabel=r"$L^{-2}$", ylabel=r"$g_L$", title="Free-energy scaling")
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    _panel(axis, "a")

    axis = axes[1]
    fit_rows = sorted(vectors.clean.fits, key=lambda fit: (fit.minimum_width, fit.method))
    x = np.arange(len(fit_rows))
    values = np.array([fit.value for fit in fit_rows])
    yerr = np.array([fit.standard_error or 0.0 for fit in fit_rows])
    colors = [COLORS["blue"] if fit.method == "monte_carlo" else COLORS["green"]
              for fit in fit_rows]
    axis.errorbar(x, values, yerr=yerr, fmt="none", ecolor=COLORS["gray"], capsize=2.5)
    axis.scatter(x, values, c=colors, zorder=3)
    axis.axhline(0.5, color=COLORS["red"], linestyle="--", label=r"Exact $c=1/2$")
    axis.set_xticks(
        x,
        [f"{'MC' if fit.method == 'monte_carlo' else 'TM'}\n$L_{{min}}={fit.minimum_width}$"
         for fit in fit_rows],
    )
    axis.set(ylabel=r"$c$", title="Independent estimators")
    axis.text(0.98, 0.06, rf"primary MC: ${headline.clean.c_eff:.6f}$",
              transform=axis.transAxes, ha="right", va="bottom", fontsize=7)
    axis.legend(frameon=False, loc="upper right")
    axis.grid(axis="y", alpha=0.2)
    _panel(axis, "b")
    figure.tight_layout(w_pad=1.0)
    return figure


def figure_nishimori(headline: PaperData, vectors: VectorPlotData) -> Figure:
    points = vectors.nishimori.free_energy
    widths = np.array([point.width for point in points], dtype=float)
    xscale = widths ** -2
    values = np.array([point.value for point in points])
    errors = np.array([point.standard_error for point in points])
    fitted = np.array([point.fitted for point in points])
    boot = vectors.nishimori.bootstrap
    primary = np.array([point.primary for point in boot])
    alternate = np.array([point.alternate for point in boot])
    figure, axes = plt.subplots(1, 3, figsize=(7.0, 3.0))

    axis = axes[0]
    order = np.argsort(xscale)
    axis.errorbar(xscale, values, yerr=errors, fmt="o", color=COLORS["blue"], capsize=2)
    axis.plot(xscale[order], fitted[order], "-", color=COLORS["red"], label="correlated fit")
    axis.set(xlabel=r"$L^{-2}$", ylabel=r"$\phi_L$", title="Quenched free energy")
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    _panel(axis, "a")

    axis = axes[1]
    bins = np.linspace(min(primary.min(), alternate.min()),
                       max(primary.max(), alternate.max()), 32)
    axis.hist(primary, bins=bins, density=True, histtype="step", color=COLORS["blue"],
              label=r"$L_{\min}=4$")
    axis.hist(alternate, bins=bins, density=True, histtype="step",
              color=COLORS["orange"], label=r"$L_{\min}=6$")
    axis.axvline(0.464, color=COLORS["red"], linestyle="--", label="reference")
    axis.set(xlabel=r"$c_{\mathrm{eff}}$", ylabel="Bootstrap density",
             title="Hierarchical bootstrap")
    axis.legend(frameon=False)
    _panel(axis, "b")

    axis = axes[2]
    means = np.array([primary.mean(), alternate.mean()])
    intervals = np.percentile(np.vstack((primary, alternate)), [2.5, 97.5], axis=1)
    low = means - intervals[0]
    high = intervals[1] - means
    axis.errorbar([0, 1], means, yerr=np.vstack((low, high)), fmt="o",
                  color=COLORS["blue"], ecolor=COLORS["gray"], capsize=3)
    axis.axhline(0.464, color=COLORS["red"], linestyle="--")
    axis.set_xticks([0, 1], (r"$L_{\min}=4$", r"$L_{\min}=6$"))
    axis.set(ylabel=r"$c_{\mathrm{eff}}$", title="Fit-window stability")
    axis.text(0.98, 0.05, rf"reported: ${headline.nishimori.c_eff:.6f}$",
              transform=axis.transAxes, ha="right", fontsize=6.8)
    axis.grid(axis="y", alpha=0.2)
    _panel(axis, "c")
    figure.tight_layout(w_pad=0.8)
    return figure


def figure_weak_self_dual(_: PaperData, vectors: VectorPlotData) -> Figure:
    weak = vectors.weak
    points = weak.finite_size
    widths = np.array([point.width for point in points], dtype=float)
    xscale = widths ** -2
    values = np.array([point.value for point in points])
    errors = np.array([point.standard_error for point in points])
    fitted = np.array([point.fitted for point in points])
    residuals = np.array([point.residual for point in points])
    figure, axes = plt.subplots(2, 2, figsize=(7.0, 5.0))

    axis = axes[0, 0]
    order = np.argsort(xscale)
    axis.errorbar(xscale, values, yerr=errors, fmt="o", color=COLORS["blue"], capsize=2)
    axis.plot(xscale[order], fitted[order], color=COLORS["red"], label="finite-size fit")
    axis.set(xlabel=r"$L^{-2}$", ylabel=r"$\gamma_L/L$",
             title="Weak-self-dual scaling")
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    _panel(axis, "a")

    axis = axes[0, 1]
    axis.axhline(0.0, color=COLORS["gray"], linewidth=0.8)
    axis.errorbar(widths, residuals, yerr=errors, fmt="o", color=COLORS["purple"],
                  capsize=2)
    axis.set(xlabel=r"$L$", ylabel="Fit residual", title="Residual diagnostics")
    axis.grid(alpha=0.2)
    _panel(axis, "b")

    axis = axes[1, 0]
    densities = [weak.electric_density, weak.magnetic_density]
    axis.bar([0, 1], densities, color=(COLORS["blue"], COLORS["orange"]), width=0.58)
    axis.axhline(0.5, color=COLORS["red"], linestyle="--")
    axis.set_xticks([0, 1], ("electric", "magnetic"))
    axis.set(ylabel="Event density", title="Weak self-duality")
    axis.set_ylim(0.4997, 0.5003)
    axis.text(0.5, 0.08, rf"difference $z={weak.self_duality_log_ratio:.2f}$",
              transform=axis.transAxes, ha="center", fontsize=7)
    axis.grid(axis="y", alpha=0.2)
    _panel(axis, "c")

    axis = axes[1, 1]
    diagnostics = weak.sampling_diagnostics
    diag_widths = np.array([row[0] for row in diagnostics])
    ess = np.array([row[1] for row in diagnostics])
    lag = np.array([row[2] for row in diagnostics])
    axis.plot(diag_widths, ess, "o-", color=COLORS["green"], label="ESS")
    axis.set(xlabel=r"$L$", ylabel="Effective sample size", title="Sampling convergence")
    twin = axis.twinx()
    twin.plot(diag_widths, lag, "s--", color=COLORS["orange"], label=r"max $|\rho_1|$")
    twin.set_ylabel(r"Maximum $|\rho_1|$")
    handles = axis.lines + twin.lines
    axis.legend(handles, [line.get_label() for line in handles], frameon=False,
                loc="lower left")
    axis.grid(alpha=0.2)
    _panel(axis, "d")
    figure.tight_layout(w_pad=1.0, h_pad=1.1)
    return figure


def figure_benchmark_comparison(data: PaperData, _: VectorPlotData) -> Figure:
    figure, axis = plt.subplots(figsize=(3.35, 2.55))
    models = (data.clean, data.nishimori, data.weak)
    y = np.arange(len(models))
    values = np.array([model.c_eff for model in models])
    low = values - np.array([model.ci95[0] for model in models])
    high = np.array([model.ci95[1] for model in models]) - values
    targets = np.array([model.target for model in models])
    axis.errorbar(values, y, xerr=np.vstack((low, high)), fmt="o",
                  color=COLORS["blue"], ecolor=COLORS["gray"], capsize=3,
                  label="Estimate (95% CI)")
    axis.scatter(targets, y, marker="x", s=42, color=COLORS["red"], label="Reference")
    axis.set_yticks(y, ("Clean Ising", "Nishimori", "Weak self-dual"))
    axis.set(xlabel=r"$c$ or $c_{\mathrm{eff}}$", xlim=(0.425, 0.515))
    axis.grid(axis="x", alpha=0.25)
    axis.legend(frameon=False, loc="lower right")
    axis.invert_yaxis()
    figure.tight_layout()
    return figure


def figure_phase_scans(_: PaperData, vectors: VectorPlotData) -> Figure:
    learning = vectors.learning
    figure, axes = plt.subplots(1, 2, figsize=(7.0, 2.8))
    for axis, evidence, title, color, label in (
        (axes[0], learning.xy_evidence, "XY validation", COLORS["blue"], "a"),
        (axes[1], learning.diii_evidence, "Generic-DIII evidence", COLORS["orange"], "b"),
    ):
        phi = np.array([point.phi_pi for point in evidence])
        score = np.array([point.score for point in evidence])
        axis.plot(phi, score, "o-", color=color)
        axis.axhline(0.0, color=COLORS["gray"], linewidth=0.8)
        axis.set(xlabel=r"$\phi/\pi$", ylabel="Transition score", title=title)
        axis.grid(alpha=0.2)
        _panel(axis, label)
    axes[0].axvspan(*learning.xy_bracket, color=COLORS["green"], alpha=0.18,
                   label="validated bracket")
    axes[0].legend(frameon=False)
    axes[1].axvline(learning.candidate_phi_pi, color=COLORS["red"], linestyle="--",
                    label="exploratory candidate")
    axes[1].text(0.98, 0.06, "no DIII bracket criterion satisfied",
                 transform=axes[1].transAxes, ha="right", color=COLORS["red"], fontsize=7)
    axes[1].legend(frameon=False)
    figure.tight_layout(w_pad=1.2)
    return figure


def figure_entanglement(_: PaperData, vectors: VectorPlotData) -> Figure:
    ent = vectors.learning.entanglement
    figure, axes = plt.subplots(1, 2, figsize=(7.0, 2.8))
    axis = axes[0]
    axis.errorbar(ent.chord_log, ent.entropy, yerr=ent.uncertainty, fmt="o",
                  color=COLORS["blue"], capsize=2, label="entropy data")
    order = np.argsort(ent.chord_log)
    axis.plot(np.array(ent.chord_log)[order], np.array(ent.fitted_chord)[order],
              color=COLORS["red"], label="chord-length fit")
    axis.set(xlabel=r"$\ln[(L/\pi)\sin(\pi\ell/L)]$",
             ylabel=r"$S(\ell)$", title="Entanglement chord fit")
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    _panel(axis, "a")

    axis = axes[1]
    widths = np.array(ent.widths, dtype=float)
    axis.errorbar(1.0 / widths, ent.per_width_values,
                  yerr=ent.per_width_standard_errors, fmt="o",
                  color=COLORS["blue"], capsize=2, label="per-width estimate")
    order = np.argsort(1.0 / widths)
    axis.plot((1.0 / widths)[order], np.array(ent.fitted_widths)[order],
              color=COLORS["red"], label="model-averaged fit")
    axis.errorbar([0.0], [ent.value], yerr=[ent.standard_error], fmt="D",
                  color=COLORS["green"], capsize=3, label=r"$L\to\infty$")
    axis.set(xlabel=r"$1/L$", ylabel=r"$c_{\mathrm{eff}}^{(S)}$",
             title="Infinite-width extrapolation")
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    _panel(axis, "b")
    figure.tight_layout(w_pad=1.2)
    return figure


def figure_learning_diagnostics(_: PaperData, vectors: VectorPlotData) -> Figure:
    learning = vectors.learning
    cas = learning.casimir
    anis = learning.anisotropy
    figure, axes = plt.subplots(1, 3, figsize=(7.0, 3.0))

    axis = axes[0]
    widths = np.array(cas.widths, dtype=float)
    axis.plot(widths ** -2, cas.gamma, "o", color=COLORS["blue"], label="data")
    order = np.argsort(widths ** -2)
    axis.plot((widths ** -2)[order], np.array(cas.fitted)[order],
              color=COLORS["red"], label="Casimir fit")
    axis.set(xlabel=r"$L^{-2}$", ylabel=r"$\gamma_L/L$", title="Casimir estimator")
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    _panel(axis, "a")

    axis = axes[1]
    spatial = np.array(anis.spatial)
    temporal = np.array(anis.temporal)
    axis.plot(spatial[:, 0], spatial[:, 1], "o-", color=COLORS["blue"],
              label="spatial")
    axis.plot(temporal[:, 0], temporal[:, 1], "s--", color=COLORS["orange"],
              label="temporal")
    axis.set(xlabel=r"$L$", ylabel="Characteristic scale",
             title="Anisotropy stability")
    axis.text(0.03, 0.06, rf"$\alpha={anis.alpha:.4f}$; stability gate failed",
              transform=axis.transAxes, fontsize=6.6, color=COLORS["red"])
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    _panel(axis, "b")

    axis = axes[2]
    estimates = [learning.entanglement, learning.casimir]
    values = np.array([estimate.value for estimate in estimates])
    errors = np.array([estimate.standard_error for estimate in estimates])
    axis.errorbar([0, 1], values, yerr=1.96 * errors, fmt="o",
                  color=COLORS["blue"], ecolor=COLORS["gray"], capsize=3)
    axis.set_xticks([0, 1], ("entanglement", "Casimir"), rotation=15)
    axis.set(ylabel=r"Candidate $c_{\mathrm{eff}}$", title="Estimator disagreement")
    comparison = learning.estimator_comparison
    axis.text(
        0.5, 0.06,
        rf"$|\Delta|={comparison.difference:.2f}>"
        rf"{comparison.combined_95_threshold:.2f}$",
        transform=axis.transAxes, ha="center", color=COLORS["red"], fontsize=7,
    )
    axis.grid(axis="y", alpha=0.2)
    _panel(axis, "c")
    figure.tight_layout(w_pad=0.7)
    return figure


def _panel(axis: plt.Axes, label: str) -> None:
    axis.text(0.01, 0.98, f"({label})", transform=axis.transAxes,
              ha="left", va="top", weight="bold")


if __name__ == "__main__":
    package = Path(__file__).resolve().parent
    build_all_figures(package.parents[4], package / "generated")
