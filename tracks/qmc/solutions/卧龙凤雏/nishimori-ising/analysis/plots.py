from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.fitting import FreeEnergyFit, evaluate_fit


COLOR = "#225ea8"
ACCENT = "#d95f0e"
TARGET = "#238b45"


def make_all_plots(
    *,
    figures_dir: Path,
    widths: np.ndarray,
    phi: np.ndarray,
    phi_se: np.ndarray,
    primary_fit: FreeEnergyFit,
    diagnostic_fit: FreeEnergyFit,
    primary_bootstrap: np.ndarray,
    diagnostic_bootstrap: np.ndarray,
    stability: dict,
    identity: dict,
    bond: dict,
) -> list[Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        _free_energy_plot(figures_dir, widths, phi, phi_se, primary_fit),
        _bootstrap_plot(figures_dir, primary_bootstrap),
        _fit_window_plot(
            figures_dir,
            primary_fit,
            diagnostic_fit,
            primary_bootstrap,
            diagnostic_bootstrap,
        ),
        _stability_plot(figures_dir, stability),
        _identity_plot(figures_dir, identity),
        _bond_plot(figures_dir, bond),
    ]
    return outputs


def _style(axis) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(alpha=0.2)


def _save(figure, path: Path) -> Path:
    figure.tight_layout()
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return path


def _free_energy_plot(
    directory: Path,
    widths: np.ndarray,
    phi: np.ndarray,
    phi_se: np.ndarray,
    fit: FreeEnergyFit,
) -> Path:
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    x = 1.0 / widths**2
    axis.errorbar(
        x,
        phi,
        yerr=phi_se,
        fmt="o",
        color=COLOR,
        capsize=3,
        label="quenched block mean",
    )
    dense_widths = np.linspace(widths.min(), widths.max(), 300)
    order = np.argsort(1.0 / dense_widths**2)
    axis.plot(
        (1.0 / dense_widths**2)[order],
        evaluate_fit(fit, dense_widths)[order],
        color=ACCENT,
        label=r"$\phi_\infty+\pi c_{\rm eff}/(6L^2)+a/L^4$",
    )
    axis.set_xlabel(r"$1/L^2$")
    axis.set_ylabel(r"$\phi_L=\mathbb{E}[\ln Z]/(ML)$")
    axis.set_title("Nishimori quenched free-energy scaling")
    axis.legend(frameon=False)
    _style(axis)
    return _save(figure, directory / "free_energy_fit.png")


def _bootstrap_plot(directory: Path, bootstrap: np.ndarray) -> Path:
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    axis.hist(bootstrap, bins=36, color=COLOR, alpha=0.82, density=True)
    axis.axvline(0.464, color=TARGET, linewidth=2, label="benchmark 0.464")
    axis.axvline(np.mean(bootstrap), color=ACCENT, linewidth=2, label="bootstrap mean")
    axis.set_xlabel(r"$c_{\rm eff}$")
    axis.set_ylabel("bootstrap density")
    axis.set_title("Joint-width hierarchical bootstrap")
    axis.legend(frameon=False)
    _style(axis)
    return _save(figure, directory / "central_charge_bootstrap.png")


def _fit_window_plot(
    directory: Path,
    primary: FreeEnergyFit,
    diagnostic: FreeEnergyFit,
    primary_bootstrap: np.ndarray,
    diagnostic_bootstrap: np.ndarray,
) -> Path:
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    values = [primary.central_charge, diagnostic.central_charge]
    errors = [
        np.std(primary_bootstrap, ddof=1),
        np.std(diagnostic_bootstrap, ddof=1),
    ]
    axis.errorbar(
        ["Lmin = 4", "Lmin = 6"],
        values,
        yerr=errors,
        fmt="o",
        color=COLOR,
        capsize=5,
        markersize=7,
    )
    axis.axhline(0.464, color=TARGET, linestyle="--", label="benchmark 0.464")
    axis.set_ylabel(r"$c_{\rm eff}$")
    axis.set_title("Finite-size fit-window stability")
    axis.legend(frameon=False)
    _style(axis)
    return _save(figure, directory / "fit_window_stability.png")


def _stability_plot(directory: Path, stability: dict) -> Path:
    figure, axis = plt.subplots(figsize=(8.0, 4.8))
    labels = ["first half", "second half"] + [
        f"leave R{index} out"
        for index in range(len(stability["leave_one_replica_out"]))
    ]
    values = stability["half_central_charges"] + stability["leave_one_replica_out"]
    axis.plot(range(len(values)), values, "o", color=COLOR)
    axis.axhline(0.464, color=TARGET, linestyle="--", label="benchmark 0.464")
    axis.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
    axis.set_ylabel(r"$c_{\rm eff}$")
    axis.set_title("Half-run and replica-deletion stability")
    axis.legend(frameon=False)
    _style(axis)
    return _save(figure, directory / "sampling_stability.png")


def _identity_plot(directory: Path, identity: dict) -> Path:
    figure, axis = plt.subplots(figsize=(6.5, 4.8))
    axis.bar(
        ["finite difference", r"$2\tanh K_N$"],
        [identity["derivative"], identity["expected"]],
        color=[COLOR, TARGET],
        width=0.62,
    )
    axis.set_ylabel(r"$\partial\phi/\partial K$")
    axis.set_title("Nishimori internal-energy identity")
    axis.text(
        0.5,
        0.04,
        f"absolute error = {identity['absolute_error']:.3g}",
        transform=axis.transAxes,
        ha="center",
    )
    _style(axis)
    return _save(figure, directory / "nishimori_energy_identity.png")


def _bond_plot(directory: Path, bond: dict) -> Path:
    figure, axis = plt.subplots(figsize=(6.5, 4.8))
    axis.bar(
        ["observed", "configured"],
        [bond["observed_probability"], bond["expected_probability"]],
        color=[COLOR, TARGET],
        width=0.62,
    )
    axis.set_ylabel("antiferromagnetic-bond probability")
    axis.set_title("Disorder-stream frequency check")
    axis.text(
        0.5,
        0.04,
        f"z = {bond['z_score']:.3f}, N = {bond['total_bonds']:,}",
        transform=axis.transAxes,
        ha="center",
    )
    _style(axis)
    return _save(figure, directory / "negative_bond_frequency.png")
