#!/usr/bin/env python3
"""Plot Process 2 spinon-holon deconfinement results.

Six diagnostic figure types:
  1. h_j(t), s_j(t) spacetime heatmaps (CW, CCW, frozen)
  2. X_h(t), X_s(t) COM trajectories
  3. D_hs(t), ξ_hs(t), O_hs(t) relative motion metrics
  4. P_hs(r, t) at half-period and full period
  5. CW, CCW, frozen direct comparison
  6. Summary figures across U, R_δ, T, L

Usage:
  python scripts/plot_spinon_holon.py results/spinon-holon/deconfinement/deconfinement_L8_U10p0_Rd0p4_T60_k00p00.npz
  python scripts/plot_spinon_holon.py results/spinon-holon/deconfinement/ --summary
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "legend.fontsize": 8,
    "figure.dpi": 150,
})

COLORS = {
    "cw": "#2166ac",        # blue
    "ccw": "#b2182b",       # red
    "frozen": "#666666",    # gray
    "odd": "#000000",       # black
    "delta_cw": "#4393c3",
    "delta_ccw": "#d6604d",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_deconf_file(path: Path) -> dict:
    """Load a deconfinement .npz file."""
    data = np.load(path, allow_pickle=True)
    result = {key: data[key] for key in data.files}
    data.close()
    if "metadata" in result:
        result["metadata"] = json.loads(str(result["metadata"]))
    return result


def parse_label(meta: dict) -> str:
    """Compact label from metadata."""
    return (f"L={meta.get('L','?')} U={meta.get('U','?')} "
            f"Rδ={meta.get('R_delta','?')} T={meta.get('T','?')} "
            f"k₀={meta.get('k0','?')}")


def unpack_rm(d: dict, key: str) -> dict:
    """Unpack RelativeMotionResult fields from saved dict."""
    rm = d[key]
    if isinstance(rm, np.ndarray):
        # Already an array (from npz)
        return {
            "O_hs": d[f"{key}_O_hs"] if f"{key}_O_hs" in d else rm[()]["O_hs"],
        }
    return rm.item() if rm.dtype == np.dtype("O") else rm


# ---------------------------------------------------------------------------
# Figure 1: Spacetime heatmaps
# ---------------------------------------------------------------------------

def fig_heatmaps(d: dict, out_path: Path, meta: dict) -> None:
    """h_j(t), s_j(t) for CW, CCW, frozen side-by-side."""
    L = meta["L"]
    T = meta["T"]
    tau = d["tau"]
    tau_T = tau / T

    fig, axes = plt.subplots(3, 2, figsize=(14, 12), constrained_layout=True)

    protocols = ["cw", "ccw", "frozen"]
    labels = ["CW", "CCW", "Frozen"]

    for row, (prot, plabel) in enumerate(zip(protocols, labels)):
        h_j_key = f"{prot}_h_j"
        s_j_key = f"{prot}_s_j"

        if h_j_key not in d:
            continue

        h_j = d[h_j_key]
        s_j = d[s_j_key]

        # Hole density heatmap
        ax = axes[row, 0]
        im = ax.pcolormesh(np.arange(L), tau_T, h_j, shading="auto",
                           cmap="RdBu_r", rasterized=True)
        ax.set_ylabel(r"$\tau / T$")
        if row == 0:
            ax.set_title(r"Hole density $h_j(\tau)$")
        ax.set_xlabel("Site j")
        ax.text(0.02, 0.98, plabel, transform=ax.transAxes,
                va="top", fontweight="bold", fontsize=10,
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        plt.colorbar(im, ax=ax)

        # Spin defect heatmap
        ax = axes[row, 1]
        im = ax.pcolormesh(np.arange(L), tau_T, s_j, shading="auto",
                           cmap="RdBu_r", rasterized=True)
        ax.set_ylabel(r"$\tau / T$")
        if row == 0:
            ax.set_title(r"Spin defect $s_j(\tau)$")
        ax.set_xlabel("Site j")
        ax.text(0.02, 0.98, plabel, transform=ax.transAxes,
                va="top", fontweight="bold", fontsize=10,
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        plt.colorbar(im, ax=ax)

    fig.suptitle(f"Spacetime defect densities — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 2: COM trajectories
# ---------------------------------------------------------------------------

def fig_com_trajectories(d: dict, out_path: Path, meta: dict) -> None:
    """X_h(t), X_s(t) for CW, CCW, frozen."""
    T = meta["T"]
    L = meta["L"]
    n_cells = L // 2
    tau_T = d["tau"] / T

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)

    for ax, obs_name, ylabel in [
        (axes[0], "X_h", r"Hole COM $X_h(\tau)$"),
        (axes[1], "X_s", r"Spin COM $X_s(\tau)$"),
    ]:
        for prot, color, ls in [("cw", COLORS["cw"], "-"),
                                 ("ccw", COLORS["ccw"], "-"),
                                 ("frozen", COLORS["frozen"], "--")]:
            key = f"{prot}_{obs_name}"
            if key in d:
                ax.plot(tau_T, d[key], color=color, ls=ls, label=prot.upper())
        ax.set_xlabel(r"$\tau / T$")
        ax.set_ylabel(ylabel + " (unit cells)")
        ax.set_title(ylabel)
        ax.legend()

    fig.suptitle(f"COM trajectories — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 3: Relative motion metrics D_hs, ξ_hs, O_hs
# ---------------------------------------------------------------------------

def fig_relative_metrics(d: dict, out_path: Path, meta: dict) -> None:
    """D_hs(t), ξ_hs(t), O_hs(t) with CW, CCW, frozen."""
    T = meta["T"]
    tau_T = d["tau"] / T

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)

    # Top row: raw metrics
    panels = [
        (axes[0, 0], "D_hs", r"$D_{hs}(\tau)$", "PBC distance (cells)"),
        (axes[0, 1], "xi_hs", r"$\xi_{hs}(\tau)$", "Relative width (cells)"),
        (axes[0, 2], "O_hs", r"$\mathcal{O}_{hs}(\tau)$", "Overlap"),
    ]

    for ax, key, title, ylabel in panels:
        for prot in ["cw", "ccw", "frozen"]:
            rm = d[prot]
            if hasattr(rm, 'dtype') and rm.dtype == np.dtype("O"):
                rm = rm.item()
            if key in rm:
                color = COLORS[prot]
                ls = "--" if prot == "frozen" else "-"
                ax.plot(tau_T, rm[key], color=color, ls=ls, label=prot.upper())
        ax.set_xlabel(r"$\tau / T$")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend()

    # Bottom row: pump deltas and odd components
    # δD^pump = D^pump - D^frozen
    ax = axes[1, 0]
    for prot, color in [("cw", COLORS["delta_cw"]), ("ccw", COLORS["delta_ccw"])]:
        rm = d[prot]
        if hasattr(rm, 'dtype') and rm.dtype == np.dtype("O"):
            rm = rm.item()
        frozen_rm = d["frozen"]
        if hasattr(frozen_rm, 'dtype') and frozen_rm.dtype == np.dtype("O"):
            frozen_rm = frozen_rm.item()
        if "D_hs" in rm and "D_hs" in frozen_rm:
            delta_D = rm["D_hs"] - frozen_rm["D_hs"]
            ax.plot(tau_T, delta_D, color=color, label=f"{prot.upper()}")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$\delta D_{hs}^{\rm pump}$ (cells)")
    ax.set_title(r"$\delta D_{hs}^{\rm pump}$ vs frozen")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    ax = axes[1, 1]
    for prot, color in [("cw", COLORS["delta_cw"]), ("ccw", COLORS["delta_ccw"])]:
        rm = d[prot]
        if hasattr(rm, 'dtype') and rm.dtype == np.dtype("O"):
            rm = rm.item()
        frozen_rm = d["frozen"]
        if hasattr(frozen_rm, 'dtype') and frozen_rm.dtype == np.dtype("O"):
            frozen_rm = frozen_rm.item()
        if "xi_hs" in rm and "xi_hs" in frozen_rm:
            delta_xi = rm["xi_hs"] - frozen_rm["xi_hs"]
            ax.plot(tau_T, delta_xi, color=color, label=f"{prot.upper()}")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$\delta \xi_{hs}^{\rm pump}$ (cells)")
    ax.set_title(r"$\delta \xi_{hs}^{\rm pump}$ vs frozen")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    # CW-CCW odd components
    ax = axes[1, 2]
    if "D_hs_odd" in d:
        ax.plot(tau_T, d["D_hs_odd"], color=COLORS["odd"], label=r"$D_{hs}^{\rm odd}$")
    if "xi_hs_odd" in d:
        ax.plot(tau_T, d["xi_hs_odd"], color=COLORS["cw"], ls="--",
                label=r"$\xi_{hs}^{\rm odd}$")
    if "O_hs_odd" in d:
        ax.plot(tau_T, d["O_hs_odd"] / np.max(np.abs(d["O_hs_odd"]) + 1e-30),
                color=COLORS["ccw"], ls=":", label=r"$O_{hs}^{\rm odd}$ (norm)")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel("CW-CCW odd")
    ax.set_title("CW-CCW odd components")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    fig.suptitle(f"Relative motion metrics — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 4: P_hs(r, t) at half and full periods
# ---------------------------------------------------------------------------

def fig_relative_distribution(d: dict, out_path: Path, meta: dict) -> None:
    """P_hs(r, t) at t = T/2 and t = T."""
    T = meta["T"]
    L = meta["L"]
    n_cells = L // 2
    tau = d["tau"]
    r = np.arange(n_cells)

    # Find indices for t ≈ T/2 and t ≈ T
    idx_half = np.argmin(np.abs(tau - T / 2))
    idx_full = len(tau) - 1

    fig, axes = plt.subplots(2, 3, figsize=(16, 8), constrained_layout=True)

    for col, (prot, plabel) in enumerate([
        ("cw", "CW"), ("ccw", "CCW"), ("frozen", "Frozen")
    ]):
        rm = d[prot]
        if hasattr(rm, 'dtype') and rm.dtype == np.dtype("O"):
            rm = rm.item()
        P = rm["P_hs"]

        # t = T/2
        ax = axes[0, col]
        ax.bar(r, P[idx_half], color=COLORS.get(prot, "C0"), alpha=0.7)
        ax.set_xlabel("r (cell shift)")
        ax.set_ylabel(r"$P_{hs}(r)$")
        ax.set_title(f"{plabel} at τ = T/2")
        ax.axhline(0, color="gray", lw=0.5)

        # t = T
        ax = axes[1, col]
        ax.bar(r, P[idx_full], color=COLORS.get(prot, "C0"), alpha=0.7)
        ax.set_xlabel("r (cell shift)")
        ax.set_ylabel(r"$P_{hs}(r)$")
        ax.set_title(f"{plabel} at τ = T")

    fig.suptitle(f"Relative distribution $P_{{hs}}(r,t)$ — {parse_label(meta)}",
                 fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 5: CW vs CCW vs Frozen direct comparison
# ---------------------------------------------------------------------------

def fig_protocol_comparison(d: dict, out_path: Path, meta: dict) -> None:
    """Direct overlay of D_hs and O_hs across protocols."""
    T = meta["T"]
    tau_T = d["tau"] / T

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)

    # D_hs: raw
    ax = axes[0, 0]
    for prot, color, ls in [("cw", COLORS["cw"], "-"),
                             ("ccw", COLORS["ccw"], "-"),
                             ("frozen", COLORS["frozen"], "--")]:
        rm = d[prot]
        if hasattr(rm, 'dtype') and rm.dtype == np.dtype("O"):
            rm = rm.item()
        ax.plot(tau_T, rm["D_hs"], color=color, ls=ls, label=prot.upper())
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$D_{hs}$ (cells)")
    ax.set_title(r"$D_{hs}$: Raw")
    ax.legend()

    # D_hs: pump-induced delta
    ax = axes[0, 1]
    frozen_rm = d["frozen"]
    if hasattr(frozen_rm, 'dtype') and frozen_rm.dtype == np.dtype("O"):
        frozen_rm = frozen_rm.item()
    for prot, color in [("cw", COLORS["cw"]), ("ccw", COLORS["ccw"])]:
        rm = d[prot]
        if hasattr(rm, 'dtype') and rm.dtype == np.dtype("O"):
            rm = rm.item()
        dD = rm["D_hs"] - frozen_rm["D_hs"]
        ax.plot(tau_T, dD, color=color, label=f"{prot.upper()}−frozen")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$\delta D_{hs}$ (cells)")
    ax.set_title(r"$D_{hs}$: Pump-induced ($-$ frozen)")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    # O_hs: raw
    ax = axes[1, 0]
    for prot, color, ls in [("cw", COLORS["cw"], "-"),
                             ("ccw", COLORS["ccw"], "-"),
                             ("frozen", COLORS["frozen"], "--")]:
        rm = d[prot]
        if hasattr(rm, 'dtype') and rm.dtype == np.dtype("O"):
            rm = rm.item()
        ax.plot(tau_T, rm["O_hs"], color=color, ls=ls, label=prot.upper())
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$\mathcal{O}_{hs}$")
    ax.set_title(r"$\mathcal{O}_{hs}$: Raw")
    ax.legend()

    # O_hs: pump-induced delta
    ax = axes[1, 1]
    for prot, color in [("cw", COLORS["cw"]), ("ccw", COLORS["ccw"])]:
        rm = d[prot]
        if hasattr(rm, 'dtype') and rm.dtype == np.dtype("O"):
            rm = rm.item()
        dO = rm["O_hs"] - frozen_rm["O_hs"]
        ax.plot(tau_T, dO, color=color, label=f"{prot.upper()}−frozen")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$\delta \mathcal{O}_{hs}$")
    ax.set_title(r"$\mathcal{O}_{hs}$: Pump-induced ($-$ frozen)")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    fig.suptitle(f"Protocol comparison — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 6: Summary across parameters
# ---------------------------------------------------------------------------

def fig_summary(files: list[Path], out_path: Path) -> None:
    """Summary grid: pump-induced D_hs and xi_hs across all parameter points."""
    n_files = len(files)
    if n_files == 0:
        return

    n_cols = min(4, n_files)
    n_rows = int(np.ceil(n_files / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 3 * n_rows),
                             constrained_layout=True)
    if n_files == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes[None, :]
    elif n_cols == 1:
        axes = axes[:, None]

    for idx, fp in enumerate(files):
        row = idx // n_cols
        col = idx % n_cols
        ax = axes[row, col]

        d = load_deconf_file(fp)
        meta = d["metadata"]
        T = meta["T"]
        tau_T = d["tau"] / T
        label = (f"L={meta['L']} U={meta['U']} "
                 f"Rd={meta['R_delta']} T={meta['T']}")

        frozen_rm = d["frozen"]
        if hasattr(frozen_rm, 'dtype') and frozen_rm.dtype == np.dtype("O"):
            frozen_rm = frozen_rm.item()

        for prot, color in [("cw", COLORS["cw"]), ("ccw", COLORS["ccw"])]:
            rm = d[prot]
            if hasattr(rm, 'dtype') and rm.dtype == np.dtype("O"):
                rm = rm.item()
            dD = rm["D_hs"] - frozen_rm["D_hs"]
            ax.plot(tau_T, dD, color=color, lw=0.8,
                    label=prot.upper() if idx == 0 else "")

        ax.set_title(label, fontsize=8)
        ax.set_xlabel(r"$\tau/T$" if row == n_rows - 1 else "")
        ax.set_ylabel(r"$\delta D_{hs}$" if col == 0 else "")
        ax.axhline(0, color="gray", lw=0.3)
        if idx == 0:
            ax.legend(fontsize=6)

    # Hide unused axes
    for idx in range(n_files, n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        axes[row, col].set_visible(False)

    fig.suptitle(r"Summary: $\delta D_{hs}^{\rm pump}$ across parameters",
                 fontsize=14)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")

    # Second summary: D_hs_odd (CW-CCW)/2
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 3 * n_rows),
                             constrained_layout=True)
    if n_files == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes[None, :]
    elif n_cols == 1:
        axes = axes[:, None]

    for idx, fp in enumerate(files):
        row = idx // n_cols
        col = idx % n_cols
        ax = axes[row, col]

        d = load_deconf_file(fp)
        meta = d["metadata"]
        T = meta["T"]
        tau_T = d["tau"] / T
        label = (f"L={meta['L']} U={meta['U']} "
                 f"Rd={meta['R_delta']} T={meta['T']}")

        ax.plot(tau_T, d["D_hs_odd"], color=COLORS["odd"], lw=0.8)
        ax.set_title(label, fontsize=8)
        ax.set_xlabel(r"$\tau/T$" if row == n_rows - 1 else "")
        ax.set_ylabel(r"$D_{hs}^{\rm odd}$" if col == 0 else "")
        ax.axhline(0, color="gray", lw=0.3)

    for idx in range(n_files, n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        axes[row, col].set_visible(False)

    fig.suptitle(r"Summary: $D_{hs}^{\rm odd} = (D^{\rm CW} - D^{\rm CCW})/2$",
                 fontsize=14)
    fig.savefig(out_path.with_name(out_path.stem + "_odd.png"),
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path.with_name(out_path.stem + '_odd.png')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Plot spinon-holon deconfinement results"
    )
    parser.add_argument("input", type=str,
                        help="Path to .npz file or directory of .npz files")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output directory for plots")
    parser.add_argument("--summary", action="store_true",
                        help="Generate multi-file summary plots")
    args = parser.parse_args()

    in_path = Path(args.input)

    if in_path.is_dir():
        files = sorted(in_path.glob("deconfinement_*.npz"))
        if not files:
            print(f"No deconfinement_*.npz files found in {in_path}")
            sys.exit(1)
        out_dir = Path(args.output) if args.output else in_path / "plots"
    else:
        files = [in_path]
        out_dir = Path(args.output) if args.output else in_path.parent / "plots"

    out_dir.mkdir(parents=True, exist_ok=True)

    # Per-file plots
    for fp in files:
        print(f"\nPlotting: {fp.name}")
        d = load_deconf_file(fp)
        meta = d["metadata"]
        stem = fp.stem

        fig_heatmaps(d, out_dir / f"fig1_heatmaps_{stem}.png", meta)
        fig_com_trajectories(d, out_dir / f"fig2_com_{stem}.png", meta)
        fig_relative_metrics(d, out_dir / f"fig3_metrics_{stem}.png", meta)
        fig_relative_distribution(d, out_dir / f"fig4_Phs_{stem}.png", meta)
        fig_protocol_comparison(d, out_dir / f"fig5_comparison_{stem}.png", meta)

    # Summary
    if args.summary and len(files) >= 2:
        print(f"\nGenerating summary plots for {len(files)} files ...")
        fig_summary(files, out_dir / "fig_summary.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
