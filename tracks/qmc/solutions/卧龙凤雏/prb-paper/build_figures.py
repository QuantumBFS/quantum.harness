"""Build deterministic, publication-sized figures from frozen artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from paper_data import PaperData, load_paper_data


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
    "gray": "#5B5B5B",
}

plt.rcParams.update(
    {
        "font.size": 8.0,
        "axes.labelsize": 8.0,
        "axes.titlesize": 8.5,
        "legend.fontsize": 7.0,
        "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0,
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
    data = load_paper_data(root)
    builders: tuple[Callable[[PaperData, Path], Figure], ...] = (
        figure_workflow,
        figure_clean,
        figure_nishimori,
        figure_weak_self_dual,
        figure_benchmark_comparison,
        figure_phase_scans,
        figure_entanglement,
        figure_learning_diagnostics,
    )
    paths = []
    for name, builder in zip(EXPECTED_FIGURES, builders, strict=True):
        figure = builder(data, root)
        path = output / name
        figure.savefig(path, format="pdf", metadata=_PDF_METADATA)
        plt.close(figure)
        paths.append(path)
    return tuple(paths)


def figure_workflow(data: PaperData, repo_root: Path) -> Figure:
    del data, repo_root
    figure, axis = plt.subplots(figsize=(7.0, 2.8))
    axis.set_xlim(0, 10)
    axis.set_ylim(0, 4)
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
            plt.Rectangle((x, 2.55), 2.0, 0.9, facecolor=color, alpha=0.18, edgecolor=color)
        )
        axis.text(x + 1.0, 3.12, title, ha="center", va="center", weight="bold")
        axis.text(x + 1.0, 2.80, method, ha="center", va="center", fontsize=7)
        axis.annotate(
            "",
            xy=(5.0, 1.75),
            xytext=(x + 1.0, 2.53),
            arrowprops={"arrowstyle": "->", "color": COLORS["gray"], "lw": 1.0},
        )
    gates = (
        "Exact / small-system\noracles",
        "Correlation-aware\nresampling",
        "Finite-size\nstability",
        "Predeclared\nclaim gates",
    )
    for index, label in enumerate(gates):
        x = 0.3 + 2.45 * index
        axis.add_patch(
            plt.Rectangle(
                (x, 0.35), 2.0, 0.62, facecolor="#F2F2F2", edgecolor=COLORS["gray"]
            )
        )
        axis.text(x + 1.0, 0.66, label, ha="center", va="center", fontsize=6.8)
    axis.text(
        5.0,
        1.55,
        "Validation hierarchy",
        ha="center",
        va="center",
        weight="bold",
        fontsize=9,
    )
    axis.text(0.02, 0.96, "(a)", transform=axis.transAxes, weight="bold")
    return figure


def figure_clean(data: PaperData, repo_root: Path) -> Figure:
    del data
    base = repo_root / "tracks/qmc/results/clean-ising-20260729-120302/figures"
    return _image_grid(
        ((base / "free_energy_scaling.png", "Free-energy scaling"),
         (base / "central_charge_comparison.png", "Independent estimates")),
        2,
        (7.0, 2.75),
    )


def figure_nishimori(data: PaperData, repo_root: Path) -> Figure:
    del data
    base = repo_root / "tracks/qmc/results/nishimori-ising-20260729-refinement1/figures"
    return _image_grid(
        (
            (base / "free_energy_fit.png", "Quenched free-energy fit"),
            (base / "central_charge_bootstrap.png", "Hierarchical bootstrap"),
            (base / "fit_window_stability.png", "Fit-window stability"),
        ),
        3,
        (7.0, 3.0),
    )


def figure_weak_self_dual(data: PaperData, repo_root: Path) -> Figure:
    del data
    base = repo_root / "tracks/qmc/results/weak-self-dual-20260729-154737/figures"
    return _image_grid(
        (
            (base / "finite-size-scaling.png", "Finite-size scaling"),
            (base / "residuals.png", "Fit residuals"),
            (base / "self-duality.png", "Weak self-duality"),
            (base / "convergence-ess.png", "Sampling convergence"),
        ),
        2,
        (7.0, 5.0),
    )


def figure_benchmark_comparison(data: PaperData, repo_root: Path) -> Figure:
    del repo_root
    figure, axis = plt.subplots(figsize=(3.35, 2.55))
    models = (data.clean, data.nishimori, data.weak)
    y = np.arange(len(models))
    values = np.array([model.c_eff for model in models])
    low = values - np.array([model.ci95[0] for model in models])
    high = np.array([model.ci95[1] for model in models]) - values
    targets = np.array([model.target for model in models])
    axis.errorbar(
        values,
        y,
        xerr=np.vstack((low, high)),
        fmt="o",
        color=COLORS["blue"],
        ecolor=COLORS["gray"],
        capsize=3,
        label="Estimate (95% CI)",
    )
    axis.scatter(targets, y, marker="x", s=42, color=COLORS["red"], label="Reference")
    axis.set_yticks(y, ("Clean Ising", "Nishimori", "Weak self-dual"))
    axis.set_xlabel(r"$c$ or $c_{\mathrm{eff}}$")
    axis.set_xlim(0.425, 0.515)
    axis.grid(axis="x", alpha=0.25)
    axis.legend(frameon=False, loc="lower right")
    axis.invert_yaxis()
    figure.tight_layout()
    return figure


def figure_phase_scans(data: PaperData, repo_root: Path) -> Figure:
    del data
    base = repo_root / "tracks/qmc/results/learning-mit-production-v2-20260730-132322/plots/en"
    return _image_grid(
        ((base / "xy-phase-scan.png", "XY validation"),
         (base / "diii-phase-scan.png", "Generic-DIII evidence")),
        2,
        (7.0, 2.8),
    )


def figure_entanglement(data: PaperData, repo_root: Path) -> Figure:
    del data
    base = repo_root / "tracks/qmc/results/learning-mit-production-v2-20260730-132322/plots/en"
    return _image_grid(
        (
            (base / "entropy-chord-fit.png", "Chord-length fits"),
            (base / "entropy-ceff-extrapolation.png", "Infinite-width extrapolation"),
        ),
        2,
        (7.0, 2.8),
    )


def figure_learning_diagnostics(data: PaperData, repo_root: Path) -> Figure:
    del data
    base = repo_root / "tracks/qmc/results/learning-mit-production-v2-20260730-132322/plots/en"
    return _image_grid(
        (
            (base / "casimir-fit.png", "Casimir fit"),
            (base / "anisotropy-stability.png", "Anisotropy stability"),
            (base / "ceff-comparison.png", "Estimator disagreement"),
        ),
        3,
        (7.0, 3.0),
    )


def _image_grid(
    panels: tuple[tuple[Path, str], ...],
    columns: int,
    size: tuple[float, float],
) -> Figure:
    rows = (len(panels) + columns - 1) // columns
    figure, axes = plt.subplots(rows, columns, figsize=size, squeeze=False)
    for index, axis in enumerate(axes.flat):
        if index >= len(panels):
            axis.axis("off")
            continue
        path, title = panels[index]
        if not path.is_file():
            raise ValueError(f"missing frozen figure: {path}")
        axis.imshow(mpimg.imread(path))
        axis.axis("off")
        axis.set_title(title, pad=2)
        axis.text(
            0.01,
            0.98,
            f"({chr(ord('a') + index)})",
            transform=axis.transAxes,
            ha="left",
            va="top",
            weight="bold",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75, "pad": 1},
        )
    figure.tight_layout(pad=0.4)
    return figure


if __name__ == "__main__":
    package = Path(__file__).resolve().parent
    build_all_figures(package.parents[4], package / "generated")
