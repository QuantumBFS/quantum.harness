#!/usr/bin/env python3
"""Visualize charge gap landscapes, minima, and split analysis.

Produces:
  Fig 1: Δc heatmaps with contours and minima markers (one per L, U)
  Fig 2: U=0 vs U>0 side-by-side comparison
  Fig 3: Minima trajectories in (δ, Δ) plane
  Fig 4: Split distance d(U) vs U
  Fig 5: Finite-size extrapolation d(U) vs 1/L
  Fig 6: Line cuts Δc(δ, Δ=0) and Δc(δ=0, Δ)

Usage:
    python scripts/plot_results.py --results-dir ../../results/gapless-point-split
    python scripts/plot_results.py --results-dir ... --output-dir figures/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_HERE))

from run_scan import detect_local_minima  # noqa: E402


def _check_mpl():
    try:
        import matplotlib  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def discover_results(results_dir: Path) -> dict[tuple, dict]:
    """Discover all coarse scan NPZ files. Returns {(L, U): data_dict}."""
    results: dict[tuple, dict] = {}
    for L_dir in sorted(results_dir.glob("L*")):
        if not L_dir.is_dir():
            continue
        L = int(L_dir.name[1:])
        coarse_dir = L_dir / "coarse"
        if not coarse_dir.exists():
            continue
        for npz_path in sorted(coarse_dir.glob("gaps_U*.npz")):
            stem = npz_path.stem
            U_str = stem.replace("gaps_U", "").replace("p", ".")
            try:
                U = float(U_str)
            except ValueError:
                continue
            data = np.load(npz_path, allow_pickle=False)
            results[(L, U)] = {
                "delta": data["delta_values"],
                "Delta": data["Delta_values"],
                "Delta_c": np.nan_to_num(data["Delta_c"], nan=np.inf),
                "Delta_s": np.nan_to_num(data["Delta_s"], nan=np.inf),
                "path": npz_path,
            }
    return results


def load_minima_csv(results_dir: Path, L: int, U: float) -> list[dict]:
    """Load refined minima CSV if available."""
    tag = f"U{U:.3f}".replace(".", "p")
    path = results_dir / f"L{L}" / "refine" / f"minima_{tag}.csv"
    if not path.exists():
        # Fall back: detect from coarse
        data = discover_results(results_dir).get((L, U))
        if data is None:
            return []
        return detect_local_minima(
            data["delta"], data["Delta"], data["Delta_c"], eps=0.05)

    import csv
    minima = []
    with open(path) as fh:
        for row in csv.DictReader(fh):
            minima.append({
                "delta": float(row["delta"]),
                "Delta": float(row["Delta"]),
                "gap": float(row["gap"]),
            })
    return minima


# ---------------------------------------------------------------------------
# Figure 1: Heatmaps with contours and minima
# ---------------------------------------------------------------------------

def plot_heatmaps(results: dict, results_dir: Path, output_dir: Path) -> None:
    """One heatmap per (L, U) with log scale, contours, and minima markers."""
    import matplotlib.pyplot as plt

    eps_log = 1e-8

    for (L, U), data in sorted(results.items()):
        delta = data["delta"]
        Dv = data["Delta"]
        gap = np.maximum(data["Delta_c"], 1e-16)

        minima = load_minima_csv(results_dir, L, U)

        fig, ax = plt.subplots(figsize=(8, 7))
        extent = [delta[0], delta[-1], Dv[0], Dv[-1]]

        # Log-scale heatmap
        log_gap = np.log10(gap + eps_log)
        im = ax.imshow(log_gap.T, origin="lower", cmap="viridis",
                        extent=extent, aspect="auto")

        # Contours at selected levels
        levels = [-3, -2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1]
        CS = ax.contour(delta, Dv, log_gap.T, levels=levels,
                         colors="white", linewidths=0.6, alpha=0.6)
        ax.clabel(CS, inline=True, fontsize=7, fmt="%.1f")

        # Mark minima
        for m in minima:
            ax.plot(m["delta"], m["Delta"], "r*", markersize=12,
                    markeredgecolor="white", markeredgewidth=0.8)
            ax.annotate(f"{m['gap']:.4f}",
                        (m["delta"], m["Delta"]),
                        xytext=(8, 8), textcoords="offset points",
                        color="red", fontsize=8,
                        bbox=dict(boxstyle="round,pad=0.2",
                                  facecolor="white", alpha=0.8))

        ax.set_xlabel(r"$\delta$ (dimerization)")
        ax.set_ylabel(r"$\Delta$ (staggered potential)")
        ax.set_title(f"Charge gap $\\Delta_c$  $L={L}$  $U={U:.3f}$")

        cbar = plt.colorbar(im, ax=ax, label=r"$\log_{10}(\Delta_c + 10^{-8})$")
        fig.tight_layout()

        tag = f"U{U:.3f}".replace(".", "p")
        fig.savefig(output_dir / f"heatmap_L{L}_{tag}.png", dpi=150)
        fig.savefig(output_dir / f"heatmap_L{L}_{tag}.pdf")
        plt.close(fig)
        print(f"  heatmap_L{L}_{tag}.png")


# ---------------------------------------------------------------------------
# Figure 2: U=0 vs U>0 comparison
# ---------------------------------------------------------------------------

def plot_uo_comparison(results: dict, results_dir: Path,
                        output_dir: Path) -> None:
    """Side-by-side: U=0 heatmap + U>0 heatmap + difference map."""
    import matplotlib.pyplot as plt

    eps_log = 1e-8

    # Group by L
    by_L: dict[int, dict[float, dict]] = {}
    for (L, U), data in results.items():
        by_L.setdefault(L, {})[U] = data

    for L, U_data in by_L.items():
        if 0.0 not in U_data:
            continue
        base = U_data[0.0]
        delta = base["delta"]
        Dv = base["Delta"]
        base_gap = np.maximum(base["Delta_c"], 1e-16)
        base_log = np.log10(base_gap + eps_log)

        for U in sorted(U_data):
            if U == 0.0:
                continue
            data = U_data[U]
            gap = np.maximum(data["Delta_c"], 1e-16)
            log_gap = np.log10(gap + eps_log)
            diff = gap - base_gap

            minima_u = load_minima_csv(results_dir, L, U)

            fig, axes = plt.subplots(1, 3, figsize=(21, 6))
            extent = [delta[0], delta[-1], Dv[0], Dv[-1]]
            vmin = min(base_log.min(), log_gap.min())
            vmax = max(base_log.max(), log_gap.max())

            # U=0
            ax = axes[0]
            im0 = ax.imshow(base_log.T, origin="lower", cmap="viridis",
                            extent=extent, aspect="auto",
                            vmin=vmin, vmax=vmax)
            ax.contour(delta, Dv, base_log.T, levels=8, colors="white",
                        linewidths=0.5, alpha=0.5)
            ax.set_title(f"U = 0")
            ax.set_xlabel(r"$\delta$")
            ax.set_ylabel(r"$\Delta$")

            # U > 0
            ax = axes[1]
            ax.imshow(log_gap.T, origin="lower", cmap="viridis",
                       extent=extent, aspect="auto",
                       vmin=vmin, vmax=vmax)
            ax.set_title(f"U = {U:.3f}")
            ax.set_xlabel(r"$\delta$")
            ax.set_ylabel(r"$\Delta$")
            # Overlay U=0 contour as dashed lines
            ax.contour(delta, Dv, base_log.T, levels=8, colors="white",
                        linewidths=0.5, alpha=0.4, linestyles="dashed")
            for m in minima_u:
                ax.plot(m["delta"], m["Delta"], "r*", markersize=14,
                        markeredgecolor="white", markeredgewidth=1.0)

            # Colorbar
            plt.colorbar(im0, ax=axes[1],
                          label=r"$\log_{10}(\Delta_c + 10^{-8})$")

            # Difference
            ax = axes[2]
            diff_lim = max(abs(diff.min()), abs(diff.max()))
            im_diff = ax.imshow(diff.T, origin="lower", cmap="RdBu_r",
                                extent=extent, aspect="auto",
                                vmin=-diff_lim, vmax=diff_lim)
            ax.set_title(f"Δc(U={U:.3f}) − Δc(U=0)")
            ax.set_xlabel(r"$\delta$")
            ax.set_ylabel(r"$\Delta$")
            for m in minima_u:
                ax.plot(m["delta"], m["Delta"], "k*", markersize=14,
                        markeredgecolor="lime", markeredgewidth=1.0)
            plt.colorbar(im_diff, ax=ax)

            fig.suptitle(f"Charge gap  $L={L}$  — comparison", fontsize=14)
            fig.tight_layout()

            tag = f"U{U:.3f}".replace(".", "p")
            fig.savefig(output_dir / f"compare_U0_vs_{tag}_L{L}.png", dpi=150)
            fig.savefig(output_dir / f"compare_U0_vs_{tag}_L{L}.pdf")
            plt.close(fig)
            print(f"  compare_U0_vs_{tag}_L{L}.png")


# ---------------------------------------------------------------------------
# Figure 3: Minima trajectories in (δ, Δ) plane
# ---------------------------------------------------------------------------

def plot_trajectories(results: dict, results_dir: Path,
                       output_dir: Path) -> None:
    """Plot minima positions as U varies, for each L."""
    import matplotlib.pyplot as plt

    by_L: dict[int, dict[float, list[dict]]] = {}
    U_set: set[float] = set()

    for (L, U) in results:
        minima = load_minima_csv(results_dir, L, U)
        by_L.setdefault(L, {})[U] = minima
        U_set.add(U)

    U_sorted = sorted(U_set)

    fig, axes = plt.subplots(1, max(1, len(by_L)), figsize=(6 * len(by_L), 5.5),
                              squeeze=False)
    axes = axes[0]

    for idx, L in enumerate(sorted(by_L)):
        ax = axes[idx]
        U_data = by_L[L]

        # Plot U=0 minimum first as reference
        if 0.0 in U_data and U_data[0.0]:
            m0 = U_data[0.0][0]
            ax.plot(m0["delta"], m0["Delta"], "ko", markersize=10,
                    label="U=0")

        # Plot small-U minima with color gradient
        colors = plt.cm.viridis(np.linspace(0.2, 0.95, len(U_sorted) - 1))
        ci = 0
        for U in U_sorted:
            if U == 0.0:
                continue
            if U not in U_data:
                continue
            minima = U_data[U]
            color = colors[ci]
            ci += 1
            for k, m in enumerate(minima):
                ax.plot(m["delta"], m["Delta"], "o", color=color,
                        markersize=8, markeredgecolor="white",
                        markeredgewidth=0.5)
                ax.annotate(f"U={U:.1f}",
                            (m["delta"], m["Delta"]),
                            xytext=(5, 5), textcoords="offset points",
                            fontsize=6, color=color)

        # Connect minima belonging to the same branch across U
        all_U_minima = [(U, m) for U in U_sorted if U in U_data
                        for m in U_data[U]]
        if len(all_U_minima) >= 2:
            pts = np.array([[m["delta"], m["Delta"], U]
                            for U, m in all_U_minima])
            # Sort by U
            order = np.argsort(pts[:, 2])
            pts = pts[order]
            ax.plot(pts[:, 0], pts[:, 1], "k--", linewidth=0.5, alpha=0.3)

        ax.set_xlabel(r"$\delta$")
        ax.set_ylabel(r"$\Delta$")
        ax.set_title(f"Minima trajectories  $L={L}$")
        ax.axhline(0, color="gray", linewidth=0.5, linestyle=":")
        ax.axvline(0, color="gray", linewidth=0.5, linestyle=":")
        if U_data.get(0.0):
            ax.legend(fontsize=7)

    fig.suptitle("Charge gap minima trajectories", fontsize=13)
    fig.tight_layout()
    fig.savefig(output_dir / "minima_trajectories.png", dpi=150)
    fig.savefig(output_dir / "minima_trajectories.pdf")
    plt.close(fig)
    print("  minima_trajectories.png")


# ---------------------------------------------------------------------------
# Figure 4: Split distance d(U) vs U
# ---------------------------------------------------------------------------

def plot_split_vs_U(results: dict, results_dir: Path,
                     output_dir: Path) -> None:
    """Plot split distance as function of U for each L."""
    import matplotlib.pyplot as plt

    by_L: dict[int, list[tuple[float, float]]] = {}
    for (L, U) in results:
        minima = load_minima_csv(results_dir, L, U)
        if len(minima) >= 2:
            d = np.sqrt((minima[1]["delta"] - minima[0]["delta"])**2 +
                        (minima[1]["Delta"] - minima[0]["Delta"])**2)
            by_L.setdefault(L, []).append((U, d))

    if not by_L:
        print("  No split cases to plot for d(U) vs U")
        return

    fig, ax = plt.subplots(figsize=(8, 5.5))
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(by_L)))

    for idx, L in enumerate(sorted(by_L)):
        points = sorted(by_L[L])
        Us = [p[0] for p in points]
        ds = [p[1] for p in points]
        ax.plot(Us, ds, "o-", color=colors[idx], label=f"L={L}",
                markersize=6)

    ax.set_xlabel("U")
    ax.set_ylabel(r"Split distance $d(U)$")
    ax.set_title("Charge gap minima splitting vs Hubbard U")
    ax.legend()
    ax.set_xlim(left=-0.05)
    ax.set_ylim(bottom=-0.005)
    fig.tight_layout()
    fig.savefig(output_dir / "split_distance_vs_U.png", dpi=150)
    fig.savefig(output_dir / "split_distance_vs_U.pdf")
    plt.close(fig)
    print("  split_distance_vs_U.png")


# ---------------------------------------------------------------------------
# Figure 5: Finite-size d(U) vs 1/L
# ---------------------------------------------------------------------------

def plot_finite_size(results: dict, results_dir: Path,
                      output_dir: Path) -> None:
    """Plot split distance vs 1/L for each U."""
    import matplotlib.pyplot as plt

    # Collect split distances
    U_d_by_L: dict[float, dict[int, float]] = {}
    for (L, U) in results:
        minima = load_minima_csv(results_dir, L, U)
        if len(minima) >= 2:
            d = np.sqrt((minima[1]["delta"] - minima[0]["delta"])**2 +
                        (minima[1]["Delta"] - minima[0]["Delta"])**2)
            U_d_by_L.setdefault(U, {})[L] = d

    U_with_data = sorted(U_d_by_L)
    if not U_with_data:
        print("  No split cases for finite-size analysis")
        return

    fig, ax = plt.subplots(figsize=(8, 5.5))
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(U_with_data)))

    for idx, U in enumerate(U_with_data):
        d_by_L = U_d_by_L[U]
        Ls = sorted(d_by_L)
        inv_L = [1.0 / L for L in Ls]
        ds = [d_by_L[L] for L in Ls]
        ax.plot(inv_L, ds, "o-", color=colors[idx], label=f"U={U:.3f}",
                markersize=6)
        # Linear extrapolation to 1/L → 0 if ≥ 2 points
        if len(Ls) >= 2:
            fit = np.polyfit(inv_L, ds, 1)
            inv_L_fine = np.linspace(0, max(inv_L) * 1.1, 50)
            ax.plot(inv_L_fine, np.polyval(fit, inv_L_fine),
                    "--", color=colors[idx], linewidth=0.8, alpha=0.5)
            d_inf = fit[1]  # intercept
            ax.plot(0, d_inf, "s", color=colors[idx], markersize=8,
                    markeredgecolor="white", markeredgewidth=0.5)
            ax.annotate(f"{d_inf:.4f}", (0.001, d_inf), fontsize=7,
                        color=colors[idx])

    ax.set_xlabel(r"$1/L$")
    ax.set_ylabel(r"Split distance $d(U)$")
    ax.set_title("Finite-size extrapolation of split distance")
    ax.legend(fontsize=8)
    ax.set_xlim(left=-0.005)
    fig.tight_layout()
    fig.savefig(output_dir / "finite_size_extrapolation.png", dpi=150)
    fig.savefig(output_dir / "finite_size_extrapolation.pdf")
    plt.close(fig)
    print("  finite_size_extrapolation.png")


# ---------------------------------------------------------------------------
# Figure 6: Line cuts
# ---------------------------------------------------------------------------

def plot_line_cuts(results: dict, output_dir: Path) -> None:
    """Line cuts: Δc(δ, Δ=0) and Δc(δ=0, Δ) for all U at each L."""
    import matplotlib.pyplot as plt

    by_L: dict[int, dict[float, dict]] = {}
    for (L, U), data in results.items():
        by_L.setdefault(L, {})[U] = data

    for L, U_data in by_L.items():
        U_sorted = sorted(U_data)
        n_colors = len(U_sorted)
        colors = plt.cm.viridis(np.linspace(0.1, 0.9, max(1, n_colors)))

        fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

        # Line cut at Δ = 0
        ax = axes[0]
        for idx, U in enumerate(U_sorted):
            data = U_data[U]
            Dv = data["Delta"]
            j0 = np.argmin(np.abs(Dv))  # closest to Δ=0
            cut = data["Delta_c"][:, j0]
            ax.plot(data["delta"], cut, color=colors[idx],
                    label=f"U={U:.3f}", linewidth=1.2)
        ax.set_xlabel(r"$\delta$")
        ax.set_ylabel(r"$\Delta_c(\delta, \Delta=0)$")
        ax.set_title(f"Line cut at $\\Delta=0$  $L={L}$")
        ax.legend(fontsize=7)
        ax.set_ylim(bottom=-0.05)

        # Line cut at δ = 0
        ax = axes[1]
        for idx, U in enumerate(U_sorted):
            data = U_data[U]
            delta = data["delta"]
            i0 = np.argmin(np.abs(delta))  # closest to δ=0
            cut = data["Delta_c"][i0, :]
            ax.plot(data["Delta"], cut, color=colors[idx],
                    label=f"U={U:.3f}", linewidth=1.2)
        ax.set_xlabel(r"$\Delta$")
        ax.set_ylabel(r"$\Delta_c(\delta=0, \Delta)$")
        ax.set_title(f"Line cut at $\delta=0$  $L={L}$")
        ax.legend(fontsize=7)
        ax.set_ylim(bottom=-0.05)

        fig.suptitle(f"Charge gap line cuts  $L={L}$", fontsize=13)
        fig.tight_layout()
        fig.savefig(output_dir / f"line_cuts_L{L}.png", dpi=150)
        fig.savefig(output_dir / f"line_cuts_L{L}.pdf")
        plt.close(fig)
        print(f"  line_cuts_L{L}.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Plot charge gap landscapes and split analysis")
    parser.add_argument("--results-dir", required=True,
                        help="Path to results/gapless-point-split/")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for figures")
    args = parser.parse_args()

    if not _check_mpl():
        print("matplotlib not available — cannot plot.")
        sys.exit(1)

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else results_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load all data
    results = discover_results(results_dir)
    if not results:
        print("No results found.")
        sys.exit(1)

    print(f"Loaded {len(results)} result sets")
    print(f"Figures → {output_dir}/\n")

    # Generate figures
    print("Fig 1: Heatmaps...")
    plot_heatmaps(results, results_dir, output_dir)

    print("Fig 2: U=0 vs U>0 comparison...")
    plot_uo_comparison(results, results_dir, output_dir)

    print("Fig 3: Minima trajectories...")
    plot_trajectories(results, results_dir, output_dir)

    print("Fig 4: Split distance vs U...")
    plot_split_vs_U(results, results_dir, output_dir)

    print("Fig 5: Finite-size extrapolation...")
    plot_finite_size(results, results_dir, output_dir)

    print("Fig 6: Line cuts...")
    plot_line_cuts(results, output_dir)

    print(f"\nAll figures saved to {output_dir}/")
    print("Done.")


if __name__ == "__main__":
    main()
