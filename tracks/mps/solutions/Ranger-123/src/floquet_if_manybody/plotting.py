"""Publication-oriented deterministic baseline plots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle

from .heat_valve_audit import audit_heat_valve_manifest


def _save(figure: Figure, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        stem.with_suffix(".pdf"),
        bbox_inches="tight",
        metadata={"Creator": "floquet-if"},
    )
    figure.savefig(stem.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(figure)


def plot_n2(result: dict[str, Any], stem: Path) -> None:
    rows = result["data"]
    j = np.array([row["j"] for row in rows])
    figure, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    axes[0].plot(j, [row["gap_low"] for row in rows], label=r"$\Delta_{\rm low}$")
    axes[0].plot(j, [row["gap_high"] for row in rows], label=r"$\Delta_{\rm high}$")
    axes[0].set(xlabel=r"$J/\Omega$", ylabel=r"gap$/\Omega$")
    axes[0].legend(frameon=False)
    axes[1].plot(j, [row["weight_low"] for row in rows], label="low")
    axes[1].plot(j, [row["weight_high"] for row in rows], label="high")
    axes[1].set(xlabel=r"$J/\Omega$", ylabel=r"$|\langle f|S_2|i\rangle|^2$")
    axes[1].legend(frameon=False)
    figure.suptitle("N=2 interacting triplet — exact diagonalization")
    figure.tight_layout()
    _save(figure, stem)


def plot_n3(result: dict[str, Any], stem: Path) -> None:
    rows = result["data"]
    j = np.array([row["j"] for row in rows])
    gaps = np.array([row["primary_even_gap"] for row in rows])
    weights = np.array([row["primary_even_weight"] for row in rows])
    figure, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    axes[0].loglog(j[j > 0], gaps[j > 0], "o-", label="exact primary gap")
    asymptotic = 1 / (4 * j[j > 0] ** 2)
    axes[0].loglog(j[j > 0], asymptotic, "--", label=r"$\Omega^3/(4J^2)$")
    axes[0].set(xlabel=r"$J/\Omega$", ylabel=r"gap$/\Omega$")
    axes[0].legend(frameon=False)
    axes[1].plot(j, weights, "o-", label="reflection-even")
    axes[1].set(xlabel=r"$J/\Omega$", ylabel="primary bright weight")
    axes[1].legend(frameon=False)
    figure.suptitle("N=3 symmetry-resolved collective mode")
    figure.tight_layout()
    _save(figure, stem)


def plot_backend_comparison(result: dict[str, Any], stem: Path) -> None:
    rows = result["data"]
    alpha = [row["alpha"] for row in rows]
    distance = [row["trace_distance"] for row in rows]
    figure, axis = plt.subplots(figsize=(5.2, 3.7))
    axis.plot(alpha, distance, "o-", color="#D55E00")
    axis.set(
        xlabel=r"bath coupling $\alpha$",
        ylabel="trace distance",
        title="Finite-memory IF vs Floquet-Markov\n(both approximate)",
    )
    axis.grid(alpha=0.25)
    figure.tight_layout()
    _save(figure, stem)


def plot_heat_spectrum(result: dict[str, Any], stem: Path) -> None:
    rows = result["data"]
    frequencies = np.array([row["frequency"] for row in rows])
    current = np.array([row["continuous"] for row in rows])
    figure, axis = plt.subplots(figsize=(6.2, 3.8))
    axis.plot(frequencies, current, color="#0072B2", label="continuous")
    delta_axis = axis.twinx()
    peak_frequencies = [peak["frequency"] for peak in result["delta_peaks"]]
    peak_weights = [peak["weight"] for peak in result["delta_peaks"]]
    delta_axis.semilogy(
        peak_frequencies,
        peak_weights,
        "D",
        color="#D55E00",
        label=r"coherent $\delta$ weight",
    )
    delta_axis.set_ylabel(r"analytic $\delta$ weight", color="#D55E00")
    delta_axis.tick_params(axis="y", colors="#D55E00")
    method_title = (
        "PT-TEMPO multitime"
        if result["method"] == "pt_tempo_multitime"
        else "Floquet-Markov/QRT"
    )
    axis.set(
        xlabel=r"bath frequency $\omega/\Omega$",
        ylabel=r"$\bar j(\omega)$",
        title=f"N=2 heat-current spectrum — {method_title}",
    )
    handles, labels = axis.get_legend_handles_labels()
    delta_handles, delta_labels = delta_axis.get_legend_handles_labels()
    axis.legend(handles + delta_handles, labels + delta_labels, frameon=False)
    axis.grid(alpha=0.2)
    figure.tight_layout()
    _save(figure, stem)


def plot_n3_pt_dynamics(result: dict[str, Any], stem: Path) -> None:
    rows = result["data"]
    phase = np.array([row["phase_index"] for row in rows]) / len(rows)
    magnetization = np.array([row["magnetization"] for row in rows])
    figure, axis = plt.subplots(figsize=(5.5, 3.6))
    axis.plot(phase, magnetization, "o-", color="#009E73")
    axis.set(
        xlabel=r"drive phase $t/T$",
        ylabel=r"$\langle S_3\rangle$",
        title="N=3 reflection-even periodic state — PT-TEMPO",
    )
    axis.grid(alpha=0.2)
    figure.tight_layout()
    _save(figure, stem)


def plot_n3_sector_heat(manifest: dict[str, Any], stem: Path) -> None:
    backend_label = (
        "uniform TEMPO"
        if manifest.get("exact_backend") == "uniform_tempo"
        else "PT-TEMPO"
    )
    figure, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for axis, sector in zip(axes, ("even", "odd"), strict=True):
        for point in manifest["points"]:
            if point["sector"] != sector:
                continue
            axis.plot(
                point["frequency"],
                point["continuous"],
                "--" if not point["adaptive_converged"] else "-",
                label=(
                    rf"$J/\Omega={point['model']['j']:g}$ "
                    f"({point.get('adaptive_status', 'converged')})"
                ),
            )
        axis.set(
            xlabel=r"bath frequency $\omega/\Omega$",
            title=f"reflection-{sector} — {backend_label}",
        )
        axis.grid(alpha=0.2)
        if axis.lines:
            axis.legend(frameon=False, fontsize=8)
    axes[0].set_ylabel(r"continuous $\bar j(\omega)$")
    qualifier = (
        "converged grid"
        if manifest.get("converged")
        else "dashed curves are resource-limited"
    )
    figure.suptitle(rf"$N=3$ symmetry-resolved calorimetry — {qualifier}")
    figure.tight_layout()
    _save(figure, stem)


def plot_odd_sector_difference(manifest: dict[str, Any], stem: Path) -> None:
    odd = [
        point
        for point in manifest["points"]
        if point["sector"] == "odd"
    ]
    figure, axis = plt.subplots(figsize=(6.1, 3.7))
    if odd:
        reference = np.asarray(odd[0]["continuous"], dtype=float)
        frequency = np.asarray(odd[0]["frequency"], dtype=float)
        for point in odd[1:]:
            difference = np.asarray(point["continuous"], dtype=float) - reference
            axis.plot(
                frequency,
                difference,
                label=rf"$J={point['model']['j']:g}$ minus $J={odd[0]['model']['j']:g}$",
            )
    axis.axhline(0, color="black", lw=0.7)
    axis.set(
        xlabel=r"bath frequency $\omega/\Omega$",
        ylabel=r"$\Delta\bar j(\omega)$",
        title=r"Reflection-odd heat spectrum: exact $J$-invariance check",
    )
    axis.grid(alpha=0.2)
    if axis.lines:
        axis.legend(frameon=False)
    figure.tight_layout()
    _save(figure, stem)


def plot_error_maps(manifest: dict[str, Any], stem: Path) -> None:
    alphas = [0.025, 0.05, 0.1]
    ratios = [0.75, 1.0, 1.25]
    names = (
        ("trace_distance", r"$D_\rho$"),
        ("correlation", r"$\epsilon_C$"),
        ("heat", r"$\epsilon_j$"),
    )
    figure, axes = plt.subplots(1, 3, figsize=(11.5, 3.5))
    for axis, (name, label) in zip(axes, names, strict=True):
        values = np.full((len(alphas), len(ratios)), np.nan)
        for point in manifest["points"]:
            if point["status"] != "converged":
                continue
            row = alphas.index(float(point["alpha"]))
            column = ratios.index(float(point["drive_ratio"]))
            values[row, column] = point["metrics"][name]
        image = axis.imshow(values, origin="lower", aspect="auto", cmap="magma")
        axis.set_xticks(range(len(ratios)), labels=ratios)
        axis.set_yticks(range(len(alphas)), labels=alphas)
        axis.set(
            xlabel=r"$\omega_d/\Delta_g$",
            ylabel=r"$\alpha$",
            title=label,
        )
        for row in range(len(alphas)):
            for column in range(len(ratios)):
                if np.isnan(values[row, column]):
                    text = "masked"
                elif name == "trace_distance":
                    text = f"{values[row, column]:.4f}"
                else:
                    text = f"{values[row, column]:.2g}"
                if np.isnan(values[row, column]):
                    axis.add_patch(
                        Rectangle(
                            (column - 0.5, row - 0.5),
                            1,
                            1,
                            fill=False,
                            hatch="///",
                            edgecolor="#777777",
                            linewidth=0.0,
                        )
                    )
                axis.text(
                    column,
                    row,
                    text,
                    ha="center",
                    va="center",
                    color="black" if np.isnan(values[row, column]) else "white",
                    fontsize=8,
                )
        figure.colorbar(image, ax=axis, fraction=0.046)
    scope = manifest.get("model_scope", "audited calibration grid")
    exact_label = (
        "uniform TEMPO"
        if manifest.get("exact_backend") == "uniform_tempo"
        else "PT-TEMPO"
    )
    figure.suptitle(f"{exact_label} vs Floquet-Markov/QRT — {scope}")
    figure.tight_layout()
    _save(figure, stem)


def plot_dark_diagnostics(manifest: dict[str, Any], stem: Path) -> None:
    diagnostics = sorted(
        [
            item
            for item in manifest.get("dark_diagnostics", [])
            if item["sector"] == "even"
        ],
        key=lambda item: item["j"],
    )
    figure, axes = plt.subplots(1, 2, figsize=(9.5, 3.7))
    j_values = [item["j"] for item in diagnostics]
    strongest = [
        max(
            (
                record["weight"]
                for record in item["strongest_transitions"]
                if record["source"] != record["target"]
            ),
            default=np.nan,
        )
        for item in diagnostics
    ]
    axes[0].semilogy(j_values, strongest, "o-", color="#0072B2")
    axes[0].set(
        xlabel=r"$J/\Omega$",
        ylabel=r"largest off-diagonal $|S_{\alpha\beta}^{(m)}|^2$",
        title="Floquet matrix-element diagnostic",
    )
    axes[1].plot(
        j_values,
        [item["integrated_continuous_heat"] for item in diagnostics],
        "s-",
        color="#D55E00",
        label="integrated heat",
    )
    axes[1].plot(
        j_values,
        [item["period_variance"] for item in diagnostics],
        "o--",
        color="#009E73",
        label=r"$\overline{\mathrm{Var}(S)}$",
    )
    axes[1].set(xlabel=r"$J/\Omega$", title="Heat and collective variance")
    axes[1].legend(frameon=False)
    for axis in axes:
        axis.grid(alpha=0.2)
    qualifier = "converged heat" if manifest.get("converged") else "provisional heat"
    figure.suptitle(f"Floquet diagnostics with {qualifier}", fontsize=12)
    figure.tight_layout()
    _save(figure, stem)


def plot_model_variants(manifest: dict[str, Any], stem: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    for point in manifest["points"]:
        style = "-" if point.get("adaptive_converged") else "--"
        axes[0].plot(
            point["frequency"], point["continuous"], style, label=point["variant"]
        )
        axes[1].plot(
            point["frequency"],
            point["continuous_eta_rescaled"],
            style,
            label=point["variant"],
        )
    axes[0].set(title="Raw heat spectra", ylabel=r"$\bar j(\omega)$")
    axes[1].set(title=r"Diagnostic $\bar j(\omega)/\eta^2$")
    for axis in axes:
        axis.set_xlabel(r"bath frequency $\omega/\Omega$")
        axis.grid(alpha=0.2)
        axis.legend(frameon=False, fontsize=8)
    backend_label = (
        "uniform TEMPO"
        if manifest.get("exact_backend") == "uniform_tempo"
        else "PT-TEMPO"
    )
    if manifest.get("converged"):
        qualifier = "fully converged"
    elif manifest.get("locally_complete"):
        qualifier = "bounded converged; Kac compression-audited"
    else:
        qualifier = "exploratory"
    figure.suptitle(
        f"N=3 normalization/counterterm comparison — {qualifier} {backend_label}"
    )
    figure.tight_layout()
    _save(figure, stem)


def plot_heat_valve_hero(manifest: dict[str, Any], stem: Path) -> None:
    """Render the audited four-panel Floquet heat-valve summary."""
    audit = audit_heat_valve_manifest(manifest)
    points = list(manifest.get("points", ()))
    figure, axes = plt.subplots(2, 2, figsize=(11.2, 8.0))
    colors = {1: "#0072B2", 2: "#E69F00", 3: "#009E73"}

    for n in (1, 2, 3):
        rows = sorted(
            [item for item in points if int(item["point"]["n"]) == n],
            key=lambda item: float(item["point"]["xi"]),
        )
        if not rows:
            continue
        xi = np.asarray([item["point"]["xi"] for item in rows], dtype=float)
        heat = np.asarray(
            [item["integrated_absolute_heat"] for item in rows],
            dtype=float,
        )
        residue = np.asarray(
            [item["visible_residue_weight"] for item in rows],
            dtype=float,
        )
        heat_scale = float(np.max(heat)) + 1e-15
        residue_scale = float(np.max(residue)) + 1e-15
        style = "-" if all(item.get("converged", False) for item in rows) else ":"
        axes[0, 0].plot(
            xi,
            heat / heat_scale,
            marker="o",
            linestyle=style,
            color=colors[n],
            label=rf"$N={n}$ heat",
        )
        axes[0, 0].plot(
            xi,
            residue / residue_scale,
            marker="s",
            linestyle="--",
            color=colors[n],
            alpha=0.75,
            label=rf"$N={n}$ residue",
        )
    axes[0, 0].set(
        xlabel=r"$\xi=2A/\omega_d$",
        ylabel="within-size normalized weight",
        title="Heat and observable transfer-mode weight",
    )
    axes[0, 0].grid(alpha=0.2)
    axes[0, 0].legend(frameon=False, fontsize=7, ncol=2)

    target: dict[str, Any] | None = None
    selected_n3 = [
        item
        for item in manifest.get("selected_points", ())
        if int(item["n"]) == 3
    ]
    if len(selected_n3) == 3:
        target_xi = float(selected_n3[1]["xi"])
        target = next(
            (
                item
                for item in points
                if int(item["point"]["n"]) == 3
                and np.isclose(float(item["point"]["xi"]), target_xi)
            ),
            None,
        )
    if target is None and points:
        target = points[0]

    unit_axis = axes[0, 1]
    unit_axis.add_patch(
        Circle((0, 0), 1, fill=False, color="#777777", linestyle="--")
    )
    if target is not None:
        poles = list(target.get("poles", ()))
        real = np.asarray(
            [item["eigenvalue"].get("real", 0.0) for item in poles],
            dtype=float,
        )
        imag = np.asarray(
            [item["eigenvalue"].get("imag", 0.0) for item in poles],
            dtype=float,
        )
        log_residue = np.log10(
            np.asarray(
                [item["residue"]["abs"] for item in poles],
                dtype=float,
            )
            + 1e-15
        )
        if len(poles):
            scatter = unit_axis.scatter(
                real,
                imag,
                c=log_residue,
                cmap="viridis",
                edgecolor="black",
                linewidth=0.3,
            )
            figure.colorbar(
                scatter,
                ax=unit_axis,
                label=r"$\log_{10}|A_a|$",
                fraction=0.046,
            )
    unit_axis.set(
        xlabel=r"$\mathrm{Re}\,\lambda_a$",
        ylabel=r"$\mathrm{Im}\,\lambda_a$",
        title=r"Floquet transfer poles ($N=3$ selected minimum)",
        xlim=(-1.08, 1.08),
        ylim=(-1.08, 1.08),
        aspect="equal",
    )
    unit_axis.axhline(0, color="#BBBBBB", lw=0.5)
    unit_axis.axvline(0, color="#BBBBBB", lw=0.5)

    spectrum_axis = axes[1, 0]
    n3_rows = sorted(
        [item for item in points if int(item["point"]["n"]) == 3],
        key=lambda item: float(item["point"]["xi"]),
    )
    for index, item in enumerate(n3_rows):
        role = ("lower flank", "minimum", "upper flank")[min(index, 2)]
        spectrum_axis.plot(
            item.get("frequency", ()),
            item.get("continuous", ()),
            "-" if item.get("converged", False) else ":",
            label=rf"{role}, $\xi={float(item['point']['xi']):.2f}$",
        )
    if target is not None:
        for item in target.get("poles", ())[:4]:
            center = abs(float(item.get("quasifrequency", 0.0)))
            width = max(float(item.get("decay_rate", 0.0)), 0.0)
            spectrum_axis.axvline(center, color="#555555", lw=0.7, alpha=0.5)
            spectrum_axis.axvspan(
                max(0.0, center - width),
                center + width,
                color="#999999",
                alpha=0.08,
            )
    spectrum_axis.set(
        xlabel=r"bath frequency $\omega/\Omega$",
        ylabel=r"continuous $\bar j(\omega)$",
        title="Exact heat spectrum with pole centres/widths",
    )
    spectrum_axis.grid(alpha=0.2)
    if spectrum_axis.lines:
        spectrum_axis.legend(frameon=False, fontsize=7)

    contrast_axis = axes[1, 1]
    sizes = np.asarray([1, 2, 3])
    heat_contrast = np.asarray(
        [audit.metrics.get(f"heat_contrast_n{n}", np.nan) for n in sizes]
    )
    residue_contrast = np.asarray(
        [
            1 / audit.metrics.get(f"residue_ratio_n{n}", np.nan)
            for n in sizes
        ]
    )
    contrast_axis.bar(
        sizes - 0.16,
        heat_contrast,
        width=0.32,
        color="#0072B2",
        label="heat contrast",
    )
    contrast_axis.bar(
        sizes + 0.16,
        residue_contrast,
        width=0.32,
        color="#CC79A7",
        label="residue contrast",
    )
    contrast_axis.axhline(10, color="#D55E00", linestyle="--", label="dark gate")
    contrast_axis.set(
        xlabel="system size $N$",
        ylabel="weaker-flank / minimum",
        title="Size dependence and tenfold claim gate",
        xticks=sizes,
        yscale="log",
    )
    contrast_axis.grid(axis="y", alpha=0.2)
    contrast_axis.legend(frameon=False, fontsize=8)

    title = (
        "audited dark channel"
        if audit.dark_channel_passed
        else "candidate; claim gates not met"
    )
    figure.suptitle(f"Pole-resolved Floquet heat valve — {title}")
    figure.tight_layout()
    _save(figure, stem)
