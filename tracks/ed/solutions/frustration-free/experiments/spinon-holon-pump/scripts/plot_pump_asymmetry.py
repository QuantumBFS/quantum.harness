#!/usr/bin/env python3
"""Plot pump asymmetry results — 5 diagnostic figure types.

Usage:
  python scripts/plot_pump_asymmetry.py results/spinon-holon/pump-asymmetry/pump_asymmetry_L6_U10p0_Rd0p2_T5p0_k00p00.npz
  python scripts/plot_pump_asymmetry.py results/spinon-holon/pump-asymmetry/ --compare  # multi-file comparison
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
    "hole_charge": "C0",
    "hole_spin": "C1",
    "particle_charge": "C2",
    "particle_spin": "C3",
    "cw": "C0",
    "ccw": "C1",
    "frozen": "gray",
    "odd": "black",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_pump_file(path: Path) -> dict:
    """Load a pump asymmetry .npz file, returning a dict with all arrays."""
    data = np.load(path, allow_pickle=True)
    result = {key: data[key] for key in data.files}
    data.close()
    if "metadata" in result:
        result["metadata"] = json.loads(str(result["metadata"]))
    return result


def parse_label(meta: dict) -> str:
    """Make a compact label from metadata."""
    return (f"L={meta.get('L','?')} U={meta.get('U','?')} "
            f"Rδ={meta.get('R_delta','?')} T={meta.get('T','?')} "
            f"k₀={meta.get('k0','?')}")


# ---------------------------------------------------------------------------
# Figure 1: Spacetime heatmaps
# ---------------------------------------------------------------------------

def fig_heatmaps(d: dict, out_path: Path, meta: dict) -> None:
    """h_j(t), p_j(t), s_j^(-)(t), s_j^(+)(t) as spacetime heatmaps."""
    L = meta["L"]
    tau = d["tau"]
    tau_T = tau / meta["T"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)

    titles = [
        (d["h_j"], r"Hole density $h_j(\tau)$"),
        (d["p_j"], r"Particle density $p_j(\tau)$"),
        (d["s_j"], r"Spin defect $s_j^{(-)}(\tau)$"),
        (d["s_j_plus"], r"Spin density $s_j^{(+)}(\tau)$"),
    ]

    for ax, (data_2d, title) in zip(axes.flat, titles):
        im = ax.pcolormesh(np.arange(L), tau_T, data_2d, shading="auto", cmap="RdBu_r")
        ax.set_xlabel("Site j")
        ax.set_ylabel(r"$\tau / T$")
        ax.set_title(title)
        plt.colorbar(im, ax=ax)

    fig.suptitle(f"Spacetime defect densities — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 2: COM trajectories
# ---------------------------------------------------------------------------

def fig_com_trajectories(d: dict, out_path: Path, meta: dict) -> None:
    """X_h, X_p, X_s^(-), X_s^(+) for CW, CCW, frozen on one figure.

    Uses saved CCW and frozen COMs from extra fields if available.
    """
    tau_T = d["tau"] / meta["T"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)

    panels = [
        (axes[0, 0], "X_h", d["X_h"],
         d.get("X_h_ccw", None), d.get("X_h_frozen", None),
         r"Hole COM $X_h(\tau)$"),
        (axes[0, 1], "X_p", d["X_p"],
         d.get("X_p_ccw", None), d.get("X_p_frozen", None),
         r"Particle COM $X_p(\tau)$"),
        (axes[1, 0], "X_s", d["X_s"],
         d.get("X_s_ccw", None), d.get("X_s_frozen", None),
         r"Spin$^{(-)}$ COM $X_s^{(-)}(\tau)$"),
        (axes[1, 1], "X_s_plus", d["X_s_plus"],
         d.get("X_s_plus_ccw", None), d.get("X_s_plus_frozen", None),
         r"Spin$^{(+)}$ COM $X_s^{(+)}(\tau)$"),
    ]

    for ax, key, cw, ccw, frozen, title in panels:
        ax.plot(tau_T, cw, color=COLORS["cw"], label="CW")
        if ccw is not None:
            ax.plot(tau_T, ccw, color=COLORS["ccw"], label="CCW")
        if frozen is not None:
            ax.plot(tau_T, frozen, color=COLORS["frozen"], ls="--", label="Frozen")
        ax.set_xlabel(r"$\tau / T$")
        ax.set_ylabel("COM (unit cells)")
        ax.set_title(title)
        ax.legend()

    fig.suptitle(f"COM trajectories — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 3: Pump-odd displacements
# ---------------------------------------------------------------------------

def fig_pump_odd(d: dict, out_path: Path, meta: dict) -> None:
    """Pump-odd displacement ΔX^odd(τ) for all four observables."""
    tau_T = d["tau"] / meta["T"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    # Panel 1: All four pump-odd displacements
    ax = axes[0]
    ax.plot(tau_T, d["dX_h_odd"], color=COLORS["hole_charge"], label=r"$\Delta X_h^{\rm odd}$")
    ax.plot(tau_T, d["dX_p_odd"], color=COLORS["particle_charge"], label=r"$\Delta X_p^{\rm odd}$")
    ax.plot(tau_T, d["dX_s_minus_odd"], color=COLORS["hole_spin"], ls="--",
            label=r"$\Delta X_s^{(-),\rm odd}$")
    ax.plot(tau_T, d["dX_s_plus_odd"], color=COLORS["particle_spin"], ls="--",
            label=r"$\Delta X_s^{(+),\rm odd}$")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel(r"$\Delta X^{\rm odd}$ (unit cells)")
    ax.set_title("Pump-odd displacements")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    # Panel 2: Key comparisons
    ax = axes[1]
    ax.plot(tau_T, d["hole_vs_particle_diff"], color="C0",
            label=r"$\Delta X_h^{\rm odd} + \Delta X_p^{\rm odd}$")
    ax.plot(tau_T, d["hole_charge_vs_spin_diff"], color="C1",
            label=r"$\Delta X_h^{\rm odd} - \Delta X_s^{(-),\rm odd}$")
    ax.plot(tau_T, d["particle_charge_vs_spin_diff"], color="C2",
            label=r"$\Delta X_p^{\rm odd} - \Delta X_s^{(+),\rm odd}$")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel("Difference (unit cells)")
    ax.set_title("Asymmetry diagnostics")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    fig.suptitle(f"Pump-odd analysis — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 4: Hole vs particle scatter
# ---------------------------------------------------------------------------

def fig_hole_vs_particle(d: dict, out_path: Path, meta: dict) -> None:
    """Parametric/scatter comparison of hole vs particle pump-odd displacement."""
    tau_T = d["tau"] / meta["T"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)

    # Panel 1: Parametric plot ΔX_p^odd vs ΔX_h^odd
    ax = axes[0]
    points = ax.scatter(d["dX_h_odd"], d["dX_p_odd"], c=tau_T, cmap="viridis", s=5)
    # Diagonal: ΔX_p^odd = -ΔX_h^odd (symmetric case)
    lims = max(abs(d["dX_h_odd"]).max(), abs(d["dX_p_odd"]).max()) * 1.1
    ax.plot([-lims, lims], [lims, -lims], "k--", lw=0.5, label="Symmetric")
    ax.set_xlabel(r"$\Delta X_h^{\rm odd}$")
    ax.set_ylabel(r"$\Delta X_p^{\rm odd}$")
    ax.set_title(r"Hole vs Particle: $\Delta X^{\rm odd}$")
    ax.axhline(0, color="gray", lw=0.3)
    ax.axvline(0, color="gray", lw=0.3)
    ax.legend()
    plt.colorbar(points, ax=ax, label=r"$\tau / T$")

    # Panel 2: Charge vs spin for hole and particle
    ax = axes[1]
    ax.plot(tau_T, d["dX_h_odd"] - d["dX_s_minus_odd"], color=COLORS["hole_charge"],
            label=r"Hole: $\Delta X_h - \Delta X_s^{(-)}$")
    ax.plot(tau_T, d["dX_p_odd"] - d["dX_s_plus_odd"], color=COLORS["particle_charge"],
            label=r"Particle: $\Delta X_p - \Delta X_s^{(+)}$")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel("Charge − Spin (unit cells)")
    ax.set_title("Charge-spin separation vs protocol")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    fig.suptitle(f"Hole vs Particle comparison — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Figure 5: Convergence & sum rules
# ---------------------------------------------------------------------------

def fig_convergence(d: dict, out_path: Path, meta: dict) -> None:
    """Sum rules and diagnostics."""
    tau_T = d["tau"] / meta["T"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)

    # Sum rules
    ax = axes[0, 0]
    ax.plot(tau_T, d["sum_h"], label=r"$\sum_j h_j$", color=COLORS["hole_charge"])
    ax.plot(tau_T, d["sum_p"], label=r"$\sum_j p_j$", color=COLORS["particle_charge"])
    ax.plot(tau_T, d["sum_s"], label=r"$\sum_j s_j^{(-)}$", color=COLORS["hole_spin"])
    ax.plot(tau_T, d["sum_s_plus"], label=r"$\sum_j s_j^{(+)}$", color=COLORS["particle_spin"])
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel("Sum")
    ax.set_title("Sum rules (should = 1)")
    ax.axhline(1.0, color="gray", lw=0.5)
    ax.legend()

    # Frozen baselines
    ax = axes[0, 1]
    frozen_keys = [
        ("X_h_frozen", "Hole charge"),
        ("X_p_frozen", "Particle charge"),
        ("X_s_frozen", "Hole spin"),
        ("X_s_plus_frozen", "Particle spin"),
    ]
    for key, label in frozen_keys:
        if key in d:
            ax.plot(tau_T, d[key], label=label)
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel("COM (unit cells)")
    ax.set_title("Frozen evolution baselines")
    ax.legend()

    # dX_h^odd vs -dX_p^odd
    ax = axes[1, 0]
    ax.plot(tau_T, d["dX_h_odd"], label=r"$\Delta X_h^{\rm odd}$", color=COLORS["hole_charge"])
    ax.plot(tau_T, -d["dX_p_odd"], ls="--",
            label=r"$-\Delta X_p^{\rm odd}$", color=COLORS["particle_charge"])
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel("Displacement (unit cells)")
    ax.set_title(r"Hole vs (negated) Particle")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    # Charge vs spin pump-odd
    ax = axes[1, 1]
    ax.plot(tau_T, d["dX_h_odd"], label=r"$\Delta X_h^{\rm odd}$ (charge)",
            color=COLORS["hole_charge"])
    ax.plot(tau_T, d["dX_s_minus_odd"], ls="--",
            label=r"$\Delta X_s^{(-),\rm odd}$ (spin)",
            color=COLORS["hole_spin"])
    ax.set_xlabel(r"$\tau / T$")
    ax.set_ylabel("Displacement (unit cells)")
    ax.set_title("Hole: charge vs spin pump-odd")
    ax.legend()
    ax.axhline(0, color="gray", lw=0.5)

    fig.suptitle(f"Diagnostics — {parse_label(meta)}", fontsize=13)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Multi-file comparison plot
# ---------------------------------------------------------------------------

def fig_compare_pump_odd(files: list[Path], out_path: Path) -> None:
    """Overlay pump-odd displacements from multiple parameter points."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)
    all_meta = []

    for fp in files:
        d = load_pump_file(fp)
        meta = d["metadata"]
        label = parse_label(meta)
        all_meta.append(meta)
        tau_T = d["tau"] / meta["T"]

        axes[0, 0].plot(tau_T, d["dX_h_odd"], label=label, lw=0.8)
        axes[0, 1].plot(tau_T, d["dX_p_odd"], label=label, lw=0.8)
        axes[1, 0].plot(tau_T, d["hole_vs_particle_diff"], label=label, lw=0.8)
        axes[1, 1].plot(tau_T, np.abs(d["hole_vs_particle_diff"]), label=label, lw=0.8)

    axes[0, 0].set_title(r"$\Delta X_h^{\rm odd}$")
    axes[0, 1].set_title(r"$\Delta X_p^{\rm odd}$")
    axes[1, 0].set_title(r"$\Delta X_h^{\rm odd} + \Delta X_p^{\rm odd}$ (asymmetry)")
    axes[1, 1].set_title(r"$|\Delta X_h^{\rm odd} + \Delta X_p^{\rm odd}|$ (abs asymmetry)")

    for ax in axes.flat:
        ax.set_xlabel(r"$\tau / T$")
        ax.axhline(0, color="gray", lw=0.5)
        ax.legend(fontsize=6)

    fig.suptitle("Pump asymmetry comparison across parameters", fontsize=14)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Plot pump asymmetry results")
    parser.add_argument("input", type=str,
                        help="Path to .npz file or directory of .npz files")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output directory for plots (default: same as input)")
    parser.add_argument("--compare", action="store_true",
                        help="Generate multi-file comparison plot")
    args = parser.parse_args()

    in_path = Path(args.input)

    if in_path.is_dir():
        files = sorted(in_path.glob("pump_asymmetry_*.npz"))
        if not files:
            print(f"No pump_asymmetry_*.npz files found in {in_path}")
            sys.exit(1)
        out_dir = Path(args.output) if args.output else in_path / "plots"
    else:
        files = [in_path]
        out_dir = Path(args.output) if args.output else in_path.parent / "plots"

    out_dir.mkdir(parents=True, exist_ok=True)

    # Per-file plots
    for fp in files:
        print(f"\nPlotting: {fp.name}")
        d = load_pump_file(fp)
        meta = d["metadata"]
        stem = fp.stem

        fig_heatmaps(d, out_dir / f"fig1_heatmaps_{stem}.png", meta)
        fig_com_trajectories(d, out_dir / f"fig2_com_{stem}.png", meta)
        fig_pump_odd(d, out_dir / f"fig3_pump_odd_{stem}.png", meta)
        fig_hole_vs_particle(d, out_dir / f"fig4_comparison_{stem}.png", meta)
        fig_convergence(d, out_dir / f"fig5_diagnostics_{stem}.png", meta)

    # Multi-file comparison
    if args.compare and len(files) > 1:
        print(f"\nGenerating comparison plot for {len(files)} files ...")
        fig_compare_pump_odd(files, out_dir / "fig_compare_pump_odd.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
