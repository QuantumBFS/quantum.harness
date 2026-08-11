#!/usr/bin/env python3
"""Plot three gap landscapes from merged NPZ data.

Usage:
    /opt/anaconda3/bin/python scripts/plot_landscapes.py --input results/rmh_gap_landscape/L6_smoke/gaps_L6_smoke.npz
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def _try_import_mpl():
    try:
        import matplotlib.pyplot as plt  # noqa: F401
        return True
    except ImportError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot gap landscapes")
    parser.add_argument("--input", required=True, help="Merged NPZ file")
    parser.add_argument("--output-dir", default=None, help="Output directory for figures")
    args = parser.parse_args()

    if not _try_import_mpl():
        print("matplotlib not available — skipping")
        return
    import matplotlib.pyplot as plt

    data = np.load(args.input, allow_pickle=False)
    delta = data["delta_values"]
    Dv = data["Delta_values"]
    L_val = int(data["L"][0]) if "L" in data else 6
    U_val = float(data["U"][0]) if "U" in data else 12.0

    gaps = {
        "Δ_MB": data["Delta_MB"],
        "Δ_s": data["Delta_s"],
        "Δ_c": data["Delta_c"],
    }

    out_dir = Path(args.output_dir) if args.output_dir else Path(args.input).parent / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({
        "figure.dpi": 150, "font.size": 9,
        "axes.labelsize": 11, "axes.titlesize": 12,
    })

    extent = [delta[0], delta[-1], Dv[0], Dv[-1]]

    # ---- individual linear heatmaps ----
    for name, arr in gaps.items():
        fig, ax = plt.subplots(figsize=(7, 6))
        im = ax.imshow(arr.T, origin="lower", cmap="viridis",
                       extent=extent, aspect="auto")
        ax.set_xlabel(r"$\delta$")
        ax.set_ylabel(r"$\Delta$")
        ax.set_title(f"{name}  $L={L_val}$  $U={U_val}$")
        plt.colorbar(im, ax=ax, label=name)
        fig.tight_layout()
        fig.savefig(out_dir / f"gap_{name.replace('Δ_','')}_linear.png")
        plt.close(fig)
        print(f"Saved: gap_{name.replace('Δ_','')}_linear.png")

    # ---- log-scale versions ----
    eps = 1e-8
    for name, arr in gaps.items():
        fig, ax = plt.subplots(figsize=(7, 6))
        log_arr = np.log10(np.maximum(arr, 1e-16) + eps)
        im = ax.imshow(log_arr.T, origin="lower", cmap="viridis",
                       extent=extent, aspect="auto")
        ax.set_xlabel(r"$\delta$")
        ax.set_ylabel(r"$\Delta$")
        ax.set_title(f"{name} (log₁₀)  $L={L_val}$  $U={U_val}$")
        cbar = plt.colorbar(im, ax=ax, label=rf"$\log_{{10}}({name} + {eps})$")
        fig.tight_layout()
        fig.savefig(out_dir / f"gap_{name.replace('Δ_','')}_log.png")
        plt.close(fig)
        print(f"Saved: gap_{name.replace('Δ_','')}_log.png")

    # ---- triplet panel (all three gaps side by side, linear) ----
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    for ax, (name, arr) in zip(axes, gaps.items()):
        im = ax.imshow(arr.T, origin="lower", cmap="viridis",
                       extent=extent, aspect="auto")
        ax.set_xlabel(r"$\delta$")
        ax.set_ylabel(r"$\Delta$")
        ax.set_title(name)
        plt.colorbar(im, ax=ax)
    fig.suptitle(f"Three-gap landscape  $L={L_val}$  $U={U_val}$", fontsize=13)
    fig.tight_layout()
    fig.savefig(out_dir / "gaps_triplet_panel.png")
    plt.close(fig)
    print("Saved: gaps_triplet_panel.png")

    # ---- line cut at δ=0 ----
    idx0 = np.argmin(np.abs(delta))
    fig, ax = plt.subplots(figsize=(8, 5))
    for name, arr in gaps.items():
        cut = arr[idx0, :]
        ax.plot(Dv, cut, label=name)
    ax.set_xlabel(r"$\Delta$")
    ax.set_ylabel("Gap")
    ax.set_title(f"Gap line cuts at $\\delta=0$  $L={L_val}$  $U={U_val}$")
    ax.legend()
    ax.set_ylim(bottom=-0.05)
    fig.tight_layout()
    fig.savefig(out_dir / "line_cut_delta_zero.png")
    plt.close(fig)
    print("Saved: line_cut_delta_zero.png")

    # ---- symmetry check: gaps(δ,Δ) vs gaps(-δ,-Δ) ----
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    n_d = len(delta)
    n_D = len(Dv)
    for ax, (name, arr) in zip(axes, gaps.items()):
        vals_fwd = arr.ravel()
        vals_rev = arr[::-1, ::-1].ravel()
        ax.scatter(vals_fwd, vals_rev, s=1, alpha=0.5, rasterized=True)
        lims = [min(vals_fwd.min(), vals_rev.min()), max(vals_fwd.max(), vals_rev.max())]
        ax.plot(lims, lims, "r--", lw=0.8)
        ax.set_xlabel(f"{name}(δ,Δ)")
        ax.set_ylabel(f"{name}(-δ,-Δ)")
        ax.set_title(f"Symmetry check: {name}")
    fig.suptitle(f"Symmetry $(\\delta,\\Delta) \\leftrightarrow (-\\delta,-\\Delta)$  $L={L_val}$", fontsize=13)
    fig.tight_layout()
    fig.savefig(out_dir / "symmetry_check.png")
    plt.close(fig)
    print("Saved: symmetry_check.png")

    print(f"\nAll figures saved to {out_dir}/")


if __name__ == "__main__":
    main()
