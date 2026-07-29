from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.fitting import evaluate_fit

COLOR = "#225ea8"
ACCENT = "#d95f0e"
TARGET = "#238b45"


def make_all_plots(
    *,
    figures_dir: Path,
    widths: np.ndarray,
    gamma: np.ndarray,
    gamma_se: np.ndarray,
    primary_fit,
    fit_samples: dict[str, np.ndarray],
    sampling: dict,
    self_duality: dict,
) -> list[Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    return [
        _finite_size(figures_dir, widths, gamma, gamma_se, primary_fit),
        _residuals(figures_dir, widths, gamma, gamma_se, primary_fit),
        _fit_stability(figures_dir, fit_samples),
        _convergence(figures_dir, widths, sampling),
        _self_duality(figures_dir, self_duality),
    ]


def _style(axis) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(alpha=0.2)


def _save(figure, path: Path) -> Path:
    figure.tight_layout()
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return path


def _finite_size(directory, widths, gamma, gamma_se, fit):
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    density = gamma / widths
    density_se = gamma_se / widths
    x = 1.0 / widths**2
    axis.errorbar(x, density, yerr=density_se, fmt="o", color=COLOR, capsize=3)
    dense = np.linspace(widths.min(), widths.max(), 400)
    order = np.argsort(1.0 / dense**2)
    axis.plot(
        (1.0 / dense**2)[order],
        (evaluate_fit(fit, dense) / dense)[order],
        color=ACCENT,
        label="primary L⁻¹+L⁻³ fit",
    )
    axis.set_xlabel("1/L²")
    axis.set_ylabel("γ₁(L)/L")
    axis.set_title("Weak self-dual vacuum free-energy scaling")
    axis.legend(frameon=False)
    _style(axis)
    return _save(figure, directory / "finite-size-scaling.png")


def _residuals(directory, widths, gamma, gamma_se, fit):
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    residual = (gamma - evaluate_fit(fit, widths)) / gamma_se
    axis.axhspan(-3, 3, color="#d9f0d3", alpha=0.5)
    axis.axhline(0, color="black", linewidth=1)
    axis.plot(widths, residual, "o-", color=COLOR)
    axis.set_xlabel("circumference L")
    axis.set_ylabel("studentized residual")
    axis.set_title("Finite-size fit residuals")
    _style(axis)
    return _save(figure, directory / "residuals.png")


def _fit_stability(directory, fit_samples):
    names = ["primary", "lmin8", "lmin10", "extra_burnin", "double_block", "drop_l30"]
    labels = ["primary", "Lmin 8", "Lmin 10", "extra burn", "2× block", "drop L30"]
    centers = [np.mean(fit_samples[name]) for name in names]
    intervals = [np.percentile(fit_samples[name], [2.5, 97.5]) for name in names]
    errors = np.asarray([[c - lo, hi - c] for c, (lo, hi) in zip(centers, intervals)]).T
    figure, axis = plt.subplots(figsize=(8.0, 4.8))
    axis.errorbar(labels, centers, yerr=errors, fmt="o", color=COLOR, capsize=4)
    axis.axhspan(0.446, 0.448, color=TARGET, alpha=0.18, label="0.447 ± 0.001")
    axis.tick_params(axis="x", rotation=25)
    axis.set_ylabel("c_eff")
    axis.set_title("Fit-window and sampling stability")
    axis.legend(frameon=False)
    _style(axis)
    return _save(figure, directory / "fit-stability.png")


def _convergence(directory, widths, sampling):
    ess = [sampling[str(int(width))]["effective_sample_size"] for width in widths]
    lag = [sampling[str(int(width))]["maximum_absolute_lag_one"] for width in widths]
    figure, first = plt.subplots(figsize=(7.2, 4.8))
    second = first.twinx()
    first.plot(widths, ess, "o-", color=COLOR, label="ESS")
    second.plot(widths, lag, "s--", color=ACCENT, label="|lag-1|")
    first.axhline(100, color=TARGET, linestyle=":", label="ESS gate")
    first.set_xlabel("circumference L")
    first.set_ylabel("effective sample size", color=COLOR)
    second.set_ylabel("maximum |lag-one correlation|", color=ACCENT)
    first.set_title("Sampling convergence by width")
    _style(first)
    return _save(figure, directory / "convergence-ess.png")


def _self_duality(directory, diagnostic):
    figure, axis = plt.subplots(figsize=(6.5, 4.8))
    axis.bar(
        ["electric", "magnetic"],
        [diagnostic["electric_density"], diagnostic["magnetic_density"]],
        color=[COLOR, ACCENT],
    )
    axis.set_ylabel("vortex density")
    axis.set_title(f"Self-duality check: difference z={diagnostic['z_score']:.3f}")
    _style(axis)
    return _save(figure, directory / "self-duality.png")
