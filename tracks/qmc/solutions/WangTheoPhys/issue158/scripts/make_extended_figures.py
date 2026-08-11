#!/usr/bin/env python3
"""Create the extended Issue #158 audit figures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedFormatter, FixedLocator, NullFormatter
import numpy as np
import pandas as pd


COLORS = {
    1: "#1f77b4",
    2: "#ff7f0e",
    4: "#2ca02c",
    8: "#d62728",
}


def figure_kernel(kernel_dir: Path, output: Path) -> None:
    result = json.loads(
        (kernel_dir / "kernel_extended_results.json").read_text()
    )
    inf = pd.DataFrame(result["infinite_PI_rows"])
    mi = pd.DataFrame(result["minimum_image_rows"])
    predicted = result["predicted_log_slope"]

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 8.2))
    ax = axes[0, 0]
    x = np.log(1 / inf["k"].to_numpy())
    y = inf["E_over_k2"].to_numpy()
    ax.plot(x, y, "o", ms=4, label="exact infinite/PI sum")
    fit_x = np.linspace(x.min(), x.max(), 200)
    intercept = result["fitted_intercept_last_six"]
    ax.plot(
        fit_x,
        predicted * fit_x + intercept,
        "-",
        lw=1.5,
        label=rf"slope $\pi c_\infty/2={predicted:.7f}$",
    )
    ax.set(
        xlabel=r"$\log(1/k)$",
        ylabel=r"$E_\infty(k)/k^2$",
        title="(a) Marginal infinite-lattice kernel",
    )
    ax.legend(frameon=False, fontsize=9)

    ax = axes[0, 1]
    valid = inf["local_log_slope"].notna()
    ax.semilogx(
        inf.loc[valid, "L"],
        inf.loc[valid, "local_log_slope"],
        "o-",
        ms=4,
        label="adjacent-size local slope",
    )
    ax.axhline(predicted, color="black", ls="--", lw=1, label="exact")
    ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    ax.set(
        xlabel=r"$L=2\pi/k$",
        ylabel="local logarithmic slope",
        title="(b) Coefficient convergence",
    )
    ax.legend(frameon=False, fontsize=9)

    ax = axes[1, 0]
    sigma2 = mi[np.isclose(mi["sigma"], 2.0)]
    ax.semilogx(
        sigma2["L"],
        sigma2["relative_times_logL"],
        "o-",
        label=r"$[(E_{\rm MI}-E_{\rm PI})/E_{\rm PI}]\log L$",
    )
    ax.axhline(
        sigma2["relative_times_logL"].iloc[-1],
        color="black",
        ls=":",
        lw=1,
    )
    ax.set(
        xlabel="$L$",
        ylabel="scaled relative difference",
        title=r"(c) MI--PI difference is $O(1/\log L)$",
    )
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1, 1]
    for sigma, marker in [(1.875, "o"), (2.0, "s"), (2.125, "^")]:
        rows = mi[np.isclose(mi["sigma"], sigma)].dropna(
            subset=["effective_power"]
        )
        ax.semilogx(
            rows["L"],
            rows["effective_power"],
            marker=marker,
            label=rf"$\sigma={sigma}$",
        )
    ax.axhline(2, color="black", ls="--", lw=1)
    ax.set(
        xlabel="$L$",
        ylabel=r"$-\Delta\log E/\Delta\log L$",
        title="(d) Control-point effective powers",
    )
    ax.legend(frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


def figure_public_data(
    extended_dir: Path, matched_dir: Path, output: Path
) -> None:
    effective = pd.read_csv(extended_dir / "effective_log_exponents.csv")
    matched = pd.read_csv(matched_dir / "publication_matched_windows.csv")
    residual = pd.read_csv(
        matched_dir / "residual_magnetization_sensitivity.csv"
    )

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 8.2))
    ax = axes[0, 0]
    for beta in [1, 2, 4, 8]:
        rows = effective[effective["beta"] == beta]
        ax.errorbar(
            np.sqrt(rows["L1"] * rows["L2"]),
            rows["p_eff"],
            yerr=rows["p_eff_se"],
            marker="o",
            ms=3.5,
            capsize=2,
            lw=1,
            color=COLORS[beta],
            label=rf"$\beta={beta}$",
        )
    ax.set_xscale("log")
    ax.set(
        xlabel=r"geometric scale $\sqrt{L_1L_2}$",
        ylabel=r"$p_{\rm eff}$ from $M^2$",
        title="(a) Doubling-size log exponents",
    )
    ax.legend(frameon=False, fontsize=8, ncol=2)

    ax = axes[0, 1]
    op = matched[matched["model"] == "OP"]
    for beta in [1, 2, 4, 8]:
        rows = op[op["beta"] == beta]
        ax.plot(
            np.arange(len(rows)),
            rows["delta_AICc_OP_minus_DP"],
            "o-",
            ms=3.5,
            color=COLORS[beta],
            label=rf"$\beta={beta}$",
        )
    ax.axhline(0, color="black", lw=1)
    ax.axhline(6, color="black", ls=":", lw=0.8)
    ax.set_yscale("symlog", linthresh=2)
    window_labels = [16, 32, 48, 64, 96, 128, 192, 256, 384, 512]
    ax.set_xticks(
        np.arange(len(window_labels)),
        [str(value) for value in window_labels],
        rotation=35,
    )
    ax.set(
        xlabel=r"$L_{\min}$",
        ylabel=r"$\Delta$AICc (ordered $-$ decaying)",
        title="(b) Source-matched model comparison",
    )
    ax.legend(frameon=False, fontsize=8, ncol=2)

    ax = axes[1, 0]
    for beta in [1, 2, 4, 8]:
        rows = op[op["beta"] == beta]
        ax.plot(
            np.arange(len(rows)),
            rows["g0"],
            "o-",
            ms=3.5,
            color=COLORS[beta],
            label=rf"$\beta={beta}$",
        )
    ax.set_xticks(
        np.arange(len(window_labels)),
        [str(value) for value in window_labels],
        rotation=35,
    )
    ax.set(
        xlabel=r"$L_{\min}$",
        ylabel=r"ordered-fit intercept $\widehat g_0$",
        title="(c) Positive intercept drifts with fit window",
    )
    ax.legend(frameon=False, fontsize=8, ncol=2)

    ax = axes[1, 1]
    for beta in [1, 2, 4, 8]:
        rows = residual[residual["beta"] == beta]
        ax.plot(
            rows["rho"],
            rows["delta_AICc_ordered_minus_decaying"],
            "o-",
            ms=3.5,
            color=COLORS[beta],
            label=rf"$\beta={beta}$",
        )
    ax.axhline(0, color="black", lw=1)
    ax.set(
        xlabel=r"assumed $\rho(M^2,M^2_{k_{\min}})$",
        ylabel=r"$\Delta$AICc (ordered $-$ decaying)",
        title="(d) Residual subtraction loses discrimination",
    )
    ax.legend(frameon=False, fontsize=8, ncol=2)

    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


def figure_fit_residuals(
    matched_dir: Path, output: Path
) -> None:
    payload = json.loads(
        (matched_dir / "publication_matched_results.json").read_text()
    )
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.0), sharex=False)
    for ax, beta in zip(axes.flat, [1, 2, 4, 8]):
        row = next(
            entry
            for entry in payload["source_matched_windows"]
            if entry["beta"] == beta and entry["Lmin"] == 64
        )
        op = row["ordered_shift"]
        dp = row["decaying_shift"]
        # The prediction vectors follow the primary-size order in the window.
        n = len(op["prediction"])
        max_L = row["Lmax"]
        candidates = np.array(
            [
                64,
                96,
                128,
                192,
                256,
                384,
                512,
                768,
                1024,
                2048,
                4096,
                8192,
            ],
            dtype=float,
        )
        L = candidates[candidates <= max_L][-n:]
        # Recover observed values and standard errors from residual identities
        # is not possible from the fit JSON alone; plot model disagreement
        # normalized by its maximum absolute value instead.
        difference = np.asarray(op["prediction"]) - np.asarray(
            dp["prediction"]
        )
        ax.semilogx(
            L,
            difference,
            "o-",
            color=COLORS[beta],
            ms=4,
        )
        ax.axhline(0, color="black", lw=0.8)
        ax.set(
            xlabel="$L$",
            ylabel=r"$M^2_{\rm OP}-M^2_{\rm DP}$",
            title=(
                rf"$\beta={beta}$: $\Delta$AICc="
                f"{row['delta_AICc_ordered_minus_decaying']:.1f}"
            ),
        )
    fig.suptitle(
        r"Source-matched ordered and decaying predictions, $L_{\min}=64$",
        y=1.01,
    )
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel-dir", type=Path, required=True)
    parser.add_argument("--extended-dir", type=Path, required=True)
    parser.add_argument("--matched-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    figure_kernel(
        args.kernel_dir, args.out_dir / "extended_kernel_audit.png"
    )
    figure_public_data(
        args.extended_dir,
        args.matched_dir,
        args.out_dir / "public_data_identifiability.png",
    )
    figure_fit_residuals(
        args.matched_dir, args.out_dir / "source_matched_fit_difference.png"
    )


if __name__ == "__main__":
    main()
