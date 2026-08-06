#!/usr/bin/env python3
"""Plot deconfinement results — 6 diagnostic figure types.

Usage:
  python scripts/plot_deconfinement.py results/spinon-holon/deconfinement/deconfinement_L8_U10p0_Rd0p4_T60_k00p00.npz
  python scripts/plot_deconfinement.py results/spinon-holon/deconfinement/ --summary  # multi-file summary
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
    "cw": "C0",
    "ccw": "C1",
    "frozen": "gray",
    "odd": "black",
    "delta": "C3",
    "hole": "Blues",
    "spin": "Reds",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_file(path: Path) -> dict:
    """Load a deconfinement .npz file."""
    data = np.load(path, allow_pickle=True)
    result = {key: data[key] for key in data.files}
    data.close()
    if "metadata" in result:
        result["metadata"] = json.loads(str(result["metadata"]))
    # Unpack nested protocol dicts
    for proto in ["cw", "ccw", "frozen"]:
        if proto in result and isinstance(result[proto], np.ndarray):
            result[proto] = result[proto].item()
    return result


def parse_label(meta: dict) -> str:
    """Compact label from metadata."""
    return (f"L={meta.get('L','?')} U={meta.get('U','?')} "
            f"Rδ={meta.get('R_delta','?')} T={meta.get('T','?')} "
            f"k₀={meta.get('k0','?')}")


def get_proto(d: dict, proto: str, key: str) -> np.ndarray:
    """Extract a per-protocol array from the packed .npz dict."""
    p = d[proto]
    if isinstance(p, dict):
        return p[key]
    return p


# ---------------------------------------------------------------------------
# Figure 1: Spacetime heatmaps of h_j(t) and s_j(t)
# ---------------------------------------------------------------------------

def fig_heatmaps(d: dict, out_path: Path, meta: dict) -> None:
    """h_j(t), s_j(t) as spacetime heatmaps (CW protocol)."""
    L = meta["L"]
    tau_T = d["tau"] / meta["T"]
    h_j = d.get("h_j_cw", None)
    s_j = d.get("s_j_cw", None)

    if h_j is None:
        print("  Skipping heatmaps: no per-site data in file")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    for ax, data_2d, title, cmap in [
        (axes[0], h_j, r"Hole density $h_j(\tau)$ — CW", "Blues"),
        (axes[1], s_j, r"Spin defect $s_j(\tau)$ — CW", "Reds"),
    ]:
        im = ax.pcolormesh(np.arange(L), tau_T, data_2d, shading="auto", cmap=cmap)
        ax.set_xlabel("Site j")
        ax.set_ylabel(r"$\tau / T$")
        ax.set_title(title)
        plt.colorbar(im, ax=ax)

    fig.suptitle(f"Spacetime defect densities — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 2: COM trajectories X_h(t), X_s(t)
# ---------------------------------------------------------------------------

def fig_com_trajectories(d: dict, out_path: Path, meta: dict) -> None:
    """X_h(t), X_s(t) for CW, CCW, frozen."""
    tau_T = d["tau"] / meta["T"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    for ax, key, title in [
        (axes[0], "h", r"Hole COM $X_h(\tau)$"),
        (axes[1], "s", r"Spin COM $X_s(\tau)$"),
    ]:
        ax.plot(tau_T, d[f"X_{key}_cw"], color=COLORS["cw"], label="CW")
        ax.plot(tau_T, d[f"X_{key}_ccw"], color=COLORS["ccw"], label="CCW")
        ax.plot(tau_T, d[f"X_{key}_frozen"], color=COLORS["frozen"],
                ls="--", label="Frozen")
        ax.set_xlabel(r"$\tau / T$")
        ax.set_ylabel("COM (unit cells)")
        ax.set_title(title)
        ax.legend()

    fig.suptitle(f"COM trajectories — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 3: D_hs(t), ξ_hs(t), O_hs(t)
# ---------------------------------------------------------------------------

def fig_relative_metrics(d: dict, out_path: Path, meta: dict) -> None:
    """D_hs, ξ_hs, O_hs time series with CW/CCW/frozen and odd."""
    tau_T = d["tau"] / meta["T"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)

    # D_hs: all protocols
    ax = axes[0, 0]
    for proto, label, ls in [("cw", "CW", "-"), ("ccw", "CCW", "-"),
                               ("frozen", "Frozen", "--")]:
        D = get_proto(d, proto, "D_hs")
        ax.plot(tau_T, D, color=COLORS[proto], ls=ls, label=label)
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$D_{hs}$ (unit cells)")
    ax.set_title(r"Relative COM distance $D_{hs}(\tau)$")
    ax.legend()

    # ξ_hs: all protocols
    ax = axes[0, 1]
    for proto, label, ls in [("cw", "CW", "-"), ("ccw", "CCW", "-"),
                               ("frozen", "Frozen", "--")]:
        xi = get_proto(d, proto, "xi_hs")
        ax.plot(tau_T, xi, color=COLORS[proto], ls=ls, label=label)
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$\xi_{hs}$ (unit cells)")
    ax.set_title(r"Relative width $\xi_{hs}(\tau)$")
    ax.legend()

    # O_hs: all protocols
    ax = axes[1, 0]
    for proto, label, ls in [("cw", "CW", "-"), ("ccw", "CCW", "-"),
                               ("frozen", "Frozen", "--")]:
        O = get_proto(d, proto, "O_hs")
        ax.plot(tau_T, O, color=COLORS[proto], ls=ls, label=label)
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$\mathcal{O}_{hs}$")
    ax.set_title(r"Overlap $\mathcal{O}_{hs}(\tau)$")
    ax.legend()

    # δD_hs^pump and D_hs^odd
    ax = axes[1, 1]
    delta_D = get_proto(d, "cw", "delta_D_hs")
    if delta_D is not None and len(delta_D) > 0:
        ax.plot(tau_T, delta_D, color=COLORS["delta"],
                label=r"$\delta D_{hs}^{\rm pump}$ (CW)")
    D_odd = d.get("D_hs_odd", None)
    if D_odd is not None:
        ax.plot(tau_T, D_odd, color=COLORS["odd"], ls="--",
                label=r"$D_{hs}^{\rm odd}$ (CW−CCW)/2")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel("Displacement (unit cells)")
    ax.set_title("Pump-induced changes")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    fig.suptitle(f"Relative motion metrics — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 4: P_hs(r, t) at half and full period
# ---------------------------------------------------------------------------

def fig_relative_distribution(d: dict, out_path: Path, meta: dict) -> None:
    """P_hs(r, t) at τ/T = 0.5 and τ/T = 1.0 (signed)."""
    n_cells = meta["L"] // 2
    tau = d["tau"]
    T_val = meta["T"]
    r = np.arange(n_cells)

    # Find nearest indices
    idx_half = np.argmin(np.abs(tau / T_val - 0.5))
    idx_full = len(tau) - 1

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)

    for col, (proto, label) in enumerate([("cw", "CW"), ("ccw", "CCW")]):
        P = get_proto(d, proto, "P_hs")

        ax = axes[0, col]
        ax.bar(r - 0.15, P[idx_half], width=0.3, color=COLORS[proto],
               label=f"{label} τ/T=0.5")
        ax.set_xlabel("r (cell shift)")
        ax.set_ylabel(r"$P_{hs}(r)$")
        ax.set_title(f"{label}: τ/T = 0.5")
        ax.axhline(0, color="gray", lw=0.5)

        ax = axes[1, col]
        ax.bar(r - 0.15, P[idx_full], width=0.3, color=COLORS[proto],
               label=f"{label} τ/T=1")
        ax.set_xlabel("r (cell shift)")
        ax.set_ylabel(r"$P_{hs}(r)$")
        ax.set_title(f"{label}: τ/T = 1.0")
        ax.axhline(0, color="gray", lw=0.5)

    fig.suptitle(f"Relative distribution $P_{{hs}}(r)$ — {parse_label(meta)}",
                 fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 5: CW/CCW/frozen direct comparison of D_hs
# ---------------------------------------------------------------------------

def fig_protocol_comparison(d: dict, out_path: Path, meta: dict) -> None:
    """Overlay D_hs, ξ_hs, O_hs across protocols on shared axes."""
    tau_T = d["tau"] / meta["T"]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), constrained_layout=True)

    panels = [
        (axes[0], "D_hs", r"$D_{hs}$ (unit cells)"),
        (axes[1], "xi_hs", r"$\xi_{hs}$ (unit cells)"),
        (axes[2], "O_hs", r"$\mathcal{O}_{hs}$"),
    ]

    for ax, key, ylabel in panels:
        for proto, label, ls in [("cw", "CW", "-"), ("ccw", "CCW", "-"),
                                   ("frozen", "Frozen", "--")]:
            val = get_proto(d, proto, key)
            ax.plot(tau_T, val, color=COLORS[proto], ls=ls, label=label)
        ax.set_xlabel(r"$\tau / T$")
        ax.set_ylabel(ylabel)
        ax.set_title(key)
        ax.legend()

    fig.suptitle(f"Protocol comparison — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 6: Summary across parameters
# ---------------------------------------------------------------------------

def fig_summary_deconfinement(files: list[Path], out_dir: Path) -> None:
    """Compare D_hs(τ=T) and δD_hs^pump range across all parameter points."""
    records = []
    for fp in files:
        d = load_file(fp)
        meta = d["metadata"]
        tau = d["tau"]
        idx_end = len(tau) - 1

        D_cw_end = float(get_proto(d, "cw", "D_hs")[idx_end])
        D_fro_end = float(get_proto(d, "frozen", "D_hs")[idx_end])
        delta_D_range = float(np.max(get_proto(d, "cw", "delta_D_hs")) -
                              np.min(get_proto(d, "cw", "delta_D_hs")))

        records.append({
            "L": meta["L"],
            "U": meta["U"],
            "R_delta": meta["R_delta"],
            "T": meta["T"],
            "k0": meta["k0"],
            "D_cw_end": D_cw_end,
            "D_fro_end": D_fro_end,
            "delta_D_range": delta_D_range,
            "label": f"L={meta['L']} U={meta['U']} Rδ={meta['R_delta']} T={meta['T']}",
        })

    if not records:
        print("  No records for summary")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)

    # Sort by U then R_delta
    records.sort(key=lambda r: (r["L"], r["U"], r["R_delta"], r["T"], r["k0"]))

    labels = [r["label"] for r in records]
    x = np.arange(len(records))

    # D_hs at end of period
    ax = axes[0, 0]
    width = 0.25
    ax.bar(x - width, [r["D_cw_end"] for r in records], width,
           color=COLORS["cw"], label="CW")
    ax.bar(x, [r["D_fro_end"] for r in records], width,
           color=COLORS["frozen"], label="Frozen")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel(r"$D_{hs}(\tau=T)$")
    ax.set_title("Final relative distance")
    ax.legend()

    # δD range
    ax = axes[0, 1]
    ax.bar(x, [r["delta_D_range"] for r in records], color=COLORS["delta"])
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel(r"$\max \delta D - \min \delta D$")
    ax.set_title(r"Pump-induced $\delta D_{hs}$ range")
    ax.axhline(0, color="gray", lw=0.5)

    # D_cw vs D_fro scatter
    ax = axes[1, 0]
    for rec in records:
        marker = "o" if rec["k0"] == 0 else "s"
        ax.scatter(rec["D_fro_end"], rec["D_cw_end"], marker=marker,
                   label=rec["label"], s=30)
    lims = max(
        max(abs(r["D_cw_end"]) for r in records),
        max(abs(r["D_fro_end"]) for r in records),
    ) * 1.2
    ax.plot([-lims, lims], [-lims, lims], "k--", lw=0.5, label="CW = Frozen")
    ax.set_xlabel(r"$D_{hs}^{\rm frozen}(\tau=T)$")
    ax.set_ylabel(r"$D_{hs}^{\rm CW}(\tau=T)$")
    ax.set_title("CW vs Frozen final distance")
    ax.legend(fontsize=5)

    # D_hs^odd at τ=T
    ax = axes[1, 1]
    for fp in files:
        d = load_file(fp)
        meta = d["metadata"]
        D_odd = d.get("D_hs_odd")
        if D_odd is not None:
            idx_end = len(d["tau"]) - 1
            ax.bar(meta.get("U", 0), float(D_odd[idx_end]),
                   width=0.3, alpha=0.7,
                   label=f"L={meta['L']} Rδ={meta['R_delta']} T={meta['T']}")
    ax.set_xlabel("U")
    ax.set_ylabel(r"$D_{hs}^{\rm odd}(\tau=T)$")
    ax.set_title("CW-CCW odd component at τ=T")
    ax.axhline(0, color="gray", lw=0.5)

    fig.suptitle("Deconfinement summary across parameters", fontsize=14)
    fig.savefig(out_dir / "fig_summary_deconfinement.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_dir / 'fig_summary_deconfinement.png'}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Plot deconfinement results")
    parser.add_argument("input", type=str,
                        help="Path to .npz file or directory of .npz files")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output directory for plots")
    parser.add_argument("--summary", action="store_true",
                        help="Generate multi-file summary figure only")
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

    if args.summary:
        fig_summary_deconfinement(files, out_dir)
        print("\nDone.")
        return

    # Per-file plots
    for fp in files:
        print(f"\nPlotting: {fp.name}")
        d = load_file(fp)
        meta = d["metadata"]
        stem = fp.stem

        fig_heatmaps(d, out_dir / f"fig1_heatmaps_{stem}.png", meta)
        fig_com_trajectories(d, out_dir / f"fig2_com_{stem}.png", meta)
        fig_relative_metrics(d, out_dir / f"fig3_metrics_{stem}.png", meta)
        fig_relative_distribution(d, out_dir / f"fig4_Phs_{stem}.png", meta)
        fig_protocol_comparison(d, out_dir / f"fig5_comparison_{stem}.png", meta)

    # Summary
    if len(files) > 1:
        print(f"\nGenerating summary for {len(files)} files ...")
        fig_summary_deconfinement(files, out_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
