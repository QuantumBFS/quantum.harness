"""Publication-oriented plots for the clean Ising verification report."""

from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FIGURE_NAMES = (
    "free_energy_scaling.png",
    "central_charge_comparison.png",
    "energy_vs_k.png",
    "integration_convergence.png",
    "fit_stability.png",
    "replica_diagnostics.png",
)


def build_all_figures(results: Mapping[str, Any], figure_dir: Path) -> None:
    destination = Path(figure_dir)
    destination.mkdir(parents=True, exist_ok=True)
    _free_energy_scaling(results, destination / FIGURE_NAMES[0])
    _central_charge_comparison(results, destination / FIGURE_NAMES[1])
    _energy_vs_k(results, destination / FIGURE_NAMES[2])
    _integration_convergence(results, destination / FIGURE_NAMES[3])
    _fit_stability(results, destination / FIGURE_NAMES[4])
    _replica_diagnostics(results, destination / FIGURE_NAMES[5])


def _free_energy_scaling(results: Mapping[str, Any], path: Path) -> None:
    widths = np.asarray(results["widths"], dtype=float)
    x_values = 1.0 / widths**2
    fig, axis = _figure()
    axis.plot(x_values, np.asarray(results["exact_g"]) / widths, "o-", label="Transfer matrix")
    axis.errorbar(
        x_values,
        np.asarray(results["mc_g"]) / widths,
        yerr=np.asarray(results["mc_g_se"]) / widths,
        fmt="s",
        capsize=3,
        label="Wolff + integration",
    )
    axis.set_xlabel("Inverse squared circumference, 1/L²")
    axis.set_ylabel("Dimensionless free energy per site, g(L)/L")
    axis.set_title("Critical free-energy scaling")
    axis.legend(frameon=False)
    _save(fig, path)


def _central_charge_comparison(results: Mapping[str, Any], path: Path) -> None:
    exact = results["exact_fits"][6]["c"]
    mc = results["mc_fits"][6]
    fig, axis = _figure()
    axis.axhspan(0.495, 0.505, color="#4daf4a", alpha=0.12, label="Exact pass band")
    axis.axhspan(0.47, 0.53, color="#377eb8", alpha=0.08, label="MC pass band")
    axis.axhline(0.5, color="black", linewidth=1.2, linestyle="--", label="Ising c=0.5")
    axis.scatter([0], [exact], color="#d95f02", s=55, zorder=3)
    axis.errorbar(
        [1],
        [mc["c"]],
        yerr=[[mc["c"] - mc["low"]], [mc["high"] - mc["c"]]],
        fmt="o",
        color="#1b9e77",
        capsize=5,
        zorder=3,
    )
    axis.set_xticks([0, 1], ["Transfer matrix", "Monte Carlo"])
    axis.set_ylabel("Central charge c")
    axis.set_title("Independent central-charge estimates")
    axis.legend(frameon=False, fontsize=8)
    _save(fig, path)


def _energy_vs_k(results: Mapping[str, Any], path: Path) -> None:
    widths = np.asarray(results["widths"], dtype=float)
    k_values = np.asarray(results["k_values"], dtype=float)
    energies = np.asarray(results["mean_energy"], dtype=float)
    fig, axis = _figure()
    for index, width in enumerate(widths):
        sites = float(results["aspect_ratio"]) * width**2
        axis.plot(k_values, energies[index] / sites, label=f"L={int(width)}")
    axis.set_xlabel("Dimensionless coupling K")
    axis.set_ylabel("Mean energy per site ⟨H⟩/N")
    axis.set_title("Thermodynamic-integration integrand")
    axis.legend(frameon=False, ncol=2, fontsize=8)
    _save(fig, path)


def _integration_convergence(results: Mapping[str, Any], path: Path) -> None:
    mc_33 = results["mc_fits"][6]
    mc_17 = float(results["mc_c_17"])
    fig, axis = _figure()
    axis.errorbar(
        [17, 33],
        [mc_17, mc_33["c"]],
        yerr=[mc_33["se"], mc_33["se"]],
        fmt="o-",
        capsize=4,
        color="#377eb8",
    )
    axis.axhline(0.5, color="black", linestyle="--", linewidth=1)
    axis.set_xticks([17, 33])
    axis.set_xlabel("Integration grid points")
    axis.set_ylabel("Primary-fit central charge c")
    axis.set_title("Nested Simpson-grid convergence")
    _save(fig, path)


def _fit_stability(results: Mapping[str, Any], path: Path) -> None:
    windows = np.array([4, 6, 8])
    exact = np.array([results["exact_fits"][value]["c"] for value in windows])
    mc = np.array([results["mc_fits"][value]["c"] for value in windows])
    mc_error = np.array([results["mc_fits"][value]["se"] for value in windows])
    fig, axis = _figure()
    axis.plot(windows, exact, "o-", label="Transfer matrix")
    axis.errorbar(windows, mc, yerr=mc_error, fmt="s-", capsize=4, label="Monte Carlo")
    axis.axhline(0.5, color="black", linestyle="--", linewidth=1)
    axis.set_xticks(windows)
    axis.set_xlabel("Minimum retained width L_min")
    axis.set_ylabel("Central charge c")
    axis.set_title("Predeclared fit-window stability")
    axis.legend(frameon=False)
    _save(fig, path)


def _replica_diagnostics(results: Mapping[str, Any], path: Path) -> None:
    diagnostics = results["diagnostics"]
    values = [diagnostics["max_half_z"], diagnostics["max_replica_z"]]
    fig, axis = _figure()
    colors = ["#4daf4a" if value < 4.0 else "#e41a1c" for value in values]
    axis.bar(["Half-chain drift", "Replica disagreement"], values, color=colors)
    axis.axhline(4.0, color="black", linestyle="--", linewidth=1, label="Declared |z|=4 limit")
    axis.set_ylabel("Maximum absolute z score")
    axis.set_title("Chain stationarity and replica agreement")
    axis.legend(frameon=False)
    _save(fig, path)


def _figure():
    fig, axis = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
    axis.grid(alpha=0.2)
    return fig, axis


def _save(figure, path: Path) -> None:
    figure.savefig(path, dpi=160, facecolor="white")
    plt.close(figure)
