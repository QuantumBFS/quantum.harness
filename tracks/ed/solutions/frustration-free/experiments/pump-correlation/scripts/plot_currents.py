#!/usr/bin/env python3
"""Plot instantaneous current and cumulative transport diagnostics.

Figure 1: Total instantaneous current — J(φ) + Q(τ) for all L
Figure 2: Even/odd bond decomposition per L
Figure 3: Bond-resolved J_j(τ) heatmaps per L
Figure 4: L=10 four-panel alignment: C_S, C_n, J(φ), Q(τ)

Usage:
    /opt/anaconda3/bin/python scripts/plot_currents.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
RESULTS_DIR = _PROJECT.parent.parent / "results" / "pump-correlation"

L_LIST = [6, 8, 10, 12, 14]
DT = 0.1

# Colourblind-friendly palette (IBM)
COLORS = {6: "#648FFF", 8: "#785EF0", 10: "#DC267F", 12: "#FE6100", 14: "#FFB000"}


def load_data(L: int, dt: float = DT) -> dict | None:
    path = RESULTS_DIR / f"L{L}" / f"pump_correlation_L{L}_dt{dt}.npz"
    if not path.exists():
        print(f"WARNING: {path} not found, skipping L={L}")
        return None
    return dict(np.load(path, allow_pickle=True))


def fig1_total_current(data: dict[int, dict], out_dir: Path):
    """Figure 1: J(φ) and Q(τ) for all L, two panels stacked."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)

    ref_lines = [0.25, 0.5, 0.75, 1.0]

    for L in L_LIST:
        d = data.get(L)
        if d is None:
            continue
        c = COLORS[L]
        tau_T = d["tau_over_T"]
        ax1.plot(tau_T, d["scaled_current"], color=c, lw=1.2, label=f"L={L}")
        ax2.plot(tau_T, d["Q"], color=c, lw=1.2, label=f"L={L}")

    for x in ref_lines:
        for ax in (ax1, ax2):
            ax.axvline(x=x, color="gray", ls="--", lw=0.5, alpha=0.6)

    ax1.set_ylabel(r"$\mathcal{J}(\phi) = \frac{T}{2\pi}J(\tau)$")
    ax1.legend(ncol=5, fontsize=8, loc="upper right")
    ax1.set_title("Instantaneous current")

    ax2.set_ylabel(r"$Q(\tau)$")
    ax2.set_xlabel(r"$\tau / T$")
    ax2.legend(ncol=5, fontsize=8, loc="upper left")
    ax2.set_title("Cumulative transport")

    fig.tight_layout()
    out = out_dir / "fig1_total_current.pdf"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


def fig2_even_odd(data: dict[int, dict], out_dir: Path):
    """Figure 2: J_even(φ) and J_odd(φ) for each L, separate panels."""
    available = [L for L in L_LIST if L in data]
    ncols = min(3, len(available))
    nrows = int(np.ceil(len(available) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows), squeeze=False)

    ref_lines = [0.25, 0.5, 0.75, 1.0]

    for idx, L in enumerate(available):
        ax = axes[idx // ncols][idx % ncols]
        d = data[L]
        tau_T = d["tau_over_T"]
        ax.plot(tau_T, d["scaled_current_even"], color="#648FFF", lw=1.2, label="even bonds")
        ax.plot(tau_T, d["scaled_current_odd"], color="#DC267F", lw=1.2, label="odd bonds")
        for x in ref_lines:
            ax.axvline(x=x, color="gray", ls="--", lw=0.5, alpha=0.6)
        ax.set_title(f"L = {L}")
        ax.set_xlabel(r"$\tau / T$")
        ax.set_ylabel(r"$\mathcal{J}(\phi)$")
        ax.legend(fontsize=8)

    # hide unused axes
    for idx in range(len(available), nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    fig.tight_layout()
    out = out_dir / "fig2_even_odd.pdf"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


def fig3_bond_heatmaps(data: dict[int, dict], out_dir: Path):
    """Figure 3: Bond-resolved J_j(τ) heatmaps for each L."""
    available = [L for L in L_LIST if L in data]
    ncols = min(3, len(available))
    nrows = int(np.ceil(len(available) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.5 * nrows), squeeze=False)

    for idx, L in enumerate(available):
        ax = axes[idx // ncols][idx % ncols]
        d = data[L]
        J_bond = d["bond_current"]  # (n_save, L)
        tau_T = d["tau_over_T"]

        # Determine symmetric colour scale
        vmax = max(abs(np.min(J_bond)), abs(np.max(J_bond)))
        im = ax.pcolormesh(tau_T, np.arange(L), J_bond.T,
                           shading="nearest", cmap="RdBu_r",
                           vmin=-vmax, vmax=vmax)
        ax.set_title(f"L = {L}")
        ax.set_xlabel(r"$\tau / T$")
        ax.set_ylabel("bond index j")
        plt.colorbar(im, ax=ax, label=r"$J_j(\tau)$", fraction=0.046)

    for idx in range(len(available), nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    fig.tight_layout()
    out = out_dir / "fig3_bond_heatmaps.pdf"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


def fig4_alignment(data: dict[int, dict], out_dir: Path):
    """Figure 4: L=10 four-panel alignment — C_S, C_n, J(φ), Q(τ)."""
    d = data.get(10)
    if d is None:
        print("WARNING: L=10 data not available, skipping Figure 4")
        return

    fig, axes = plt.subplots(4, 1, figsize=(8, 10), sharex=True)
    tau_T = d["tau_over_T"]

    ref_lines = [0.25, 0.5, 0.75, 1.0]

    # Panel 1: C_S
    ax = axes[0]
    ax.plot(tau_T, d["C_spin"], color="#648FFF", lw=1.2)
    ax.set_ylabel(r"$C_S(\tau)$")
    ax.set_title("Spin correlation (L=10)")
    for x in ref_lines:
        ax.axvline(x=x, color="gray", ls="--", lw=0.5, alpha=0.6)

    # Panel 2: C_n
    ax = axes[1]
    ax.plot(tau_T, d["C_charge"], color="#DC267F", lw=1.2)
    ax.set_ylabel(r"$C_n(\tau)$")
    ax.set_title("Charge correlation (L=10)")
    for x in ref_lines:
        ax.axvline(x=x, color="gray", ls="--", lw=0.5, alpha=0.6)

    # Panel 3: J(φ)
    ax = axes[2]
    ax.plot(tau_T, d["scaled_current"], color="#FE6100", lw=1.2)
    ax.set_ylabel(r"$\mathcal{J}(\phi)$")
    ax.set_title("Instantaneous current (L=10)")
    for x in ref_lines:
        ax.axvline(x=x, color="gray", ls="--", lw=0.5, alpha=0.6)

    # Panel 4: Q(τ)
    ax = axes[3]
    ax.plot(tau_T, d["Q"], color="#FFB000", lw=1.2)
    ax.set_ylabel(r"$Q(\tau)$")
    ax.set_xlabel(r"$\tau / T$")
    ax.set_title("Cumulative transport (L=10)")
    for x in ref_lines:
        ax.axvline(x=x, color="gray", ls="--", lw=0.5, alpha=0.6)

    fig.tight_layout()
    out = out_dir / "fig4_L10_alignment.pdf"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


def main():
    out_dir = RESULTS_DIR / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load all data
    data: dict[int, dict] = {}
    for L in L_LIST:
        d = load_data(L)
        if d is not None:
            data[L] = d
            # Print diagnostics
            Qc = float(d["Q_cycle"]) if np.ndim(d["Q_cycle"]) == 0 else float(d["Q_cycle"].item())
            cres = float(d["continuity_residual"]) if np.ndim(d["continuity_residual"]) == 0 else float(d["continuity_residual"].item())
            print(f"L={L}: Q_cycle = {Qc:.6f}  continuity_residual = {cres:.2e}")

    if not data:
        print("No data found. Run run_pump_correlation.py --all first.")
        sys.exit(1)

    fig1_total_current(data, out_dir)
    fig2_even_odd(data, out_dir)
    fig3_bond_heatmaps(data, out_dir)
    fig4_alignment(data, out_dir)

    print("\nAll figures saved to", out_dir)


if __name__ == "__main__":
    main()
