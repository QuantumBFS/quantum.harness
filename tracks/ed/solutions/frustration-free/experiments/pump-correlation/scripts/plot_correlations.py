#!/usr/bin/env python3
"""Generate plots for RMH pump correlation dynamics (Fig. 5(d,e) reproduction).

Usage:
    /opt/anaconda3/bin/python scripts/plot_correlations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
sys.path.insert(0, str(_PROJECT))

RESULTS_DIR = _PROJECT.parent.parent / "results" / "pump-correlation"
FIG_DIR = RESULTS_DIR / "figures"
T_TOTAL = 100.0


def _try_import_mpl():
    try:
        import matplotlib.pyplot as plt  # noqa: F401
        return True
    except ImportError:
        return False


def load_result(L: int, dt: float = 0.1) -> dict | None:
    """Load a saved .npz result."""
    path = RESULTS_DIR / f"L{L}" / f"pump_correlation_L{L}_dt{dt}.npz"
    if not path.exists():
        print(f"  [skip] {path} not found")
        return None
    data = np.load(path, allow_pickle=True)
    return {
        "L": int(data["L"]),
        "tau": data["tau"],
        "tau_over_T": data["tau_over_T"],
        "C_spin": data["C_spin"],
        "C_charge": data["C_charge"],
        "bond_spin": data["bond_spin"],
        "bond_charge": data["bond_charge"],
        "antiperiodic": bool(data["antiperiodic"]),
    }


def make_main_figure(all_data: dict[int, dict]) -> None:
    """Main figure: C_S(τ/T) and C_n(τ/T) for all L."""
    if not _try_import_mpl():
        print("matplotlib not available")
        return
    import matplotlib.pyplot as plt

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "figure.dpi": 150, "font.size": 10,
        "axes.labelsize": 12, "axes.titlesize": 13,
    })

    L_sorted = sorted(all_data.keys())
    colors = plt.cm.viridis(np.linspace(0, 0.9, len(L_sorted)))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9), sharex=True)

    for L, c in zip(L_sorted, colors):
        d = all_data[L]
        bc = "anti-PBC" if d["antiperiodic"] else "PBC"
        ax1.plot(d["tau_over_T"], d["C_spin"], color=c, lw=1.0,
                 label=f"L={L} ({bc})")
        ax2.plot(d["tau_over_T"], d["C_charge"], color=c, lw=1.0,
                 label=f"L={L} ({bc})")

    # vertical lines at τ/T = 1/4, 1/2
    for ax in (ax1, ax2):
        ax.axvline(0.25, color="gray", ls="--", lw=0.8, alpha=0.6)
        ax.axvline(0.50, color="gray", ls="--", lw=0.8, alpha=0.6)

    ax1.set_ylabel(r"$C_S(\tau)$")
    ax1.set_title("Spin correlation dynamics  $C_S(\\tau)$")
    ax1.legend(fontsize=7, ncol=2)

    ax2.set_xlabel(r"$\tau / T$")
    ax2.set_ylabel(r"$C_n(\tau)$")
    ax2.set_title("Charge correlation dynamics  $C_n(\\tau)$")
    ax2.legend(fontsize=7, ncol=2)

    fig.suptitle(
        f"Rice–Mele–Hubbard pump  $U={10}$  "
        r"$\Delta_c=5$  $R_\Delta=2.10$  $R_\delta=0.88$  (clockwise)",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(FIG_DIR / "Fig5_de_correlation_dynamics.png")
    plt.close(fig)
    print("Saved: Fig5_de_correlation_dynamics.png")


def make_bond_heatmaps(all_data: dict[int, dict]) -> None:
    """Per-bond heatmaps of c_S(j,τ) and c_n(j,τ) for each L."""
    if not _try_import_mpl():
        return
    import matplotlib.pyplot as plt

    for L, d in all_data.items():
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        tau_T = d["tau_over_T"]
        bonds = np.arange(L)

        im1 = ax1.pcolormesh(tau_T, bonds, d["bond_spin"].T,
                             shading="auto", cmap="RdBu_r")
        ax1.set_xlabel(r"$\tau/T$")
        ax1.set_ylabel("Bond j")
        ax1.set_title(f"$c_S(j,\\tau)$  L={L}")
        plt.colorbar(im1, ax=ax1)

        im2 = ax2.pcolormesh(tau_T, bonds, d["bond_charge"].T,
                             shading="auto", cmap="RdBu_r")
        ax2.set_xlabel(r"$\tau/T$")
        ax2.set_ylabel("Bond j")
        ax2.set_title(f"$c_n(j,\\tau)$  L={L}")
        plt.colorbar(im2, ax=ax2)

        fig.tight_layout()
        fig.savefig(FIG_DIR / f"bond_heatmap_L{L}.png")
        plt.close(fig)
        print(f"Saved: bond_heatmap_L{L}.png")


def make_dt_convergence(L: int = 10) -> None:
    """Compare dt = 0.1 vs 0.05 for given L."""
    if not _try_import_mpl():
        return
    import matplotlib.pyplot as plt

    d_01 = load_result(L, dt=0.1)
    d_005 = load_result(L, dt=0.05)

    if d_01 is None or d_005 is None:
        print(f"  dt convergence: missing data for L={L}")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # interpolate fine to coarse grid
    tau_interp = d_01["tau"]
    CS_fine = np.interp(tau_interp, d_005["tau"], d_005["C_spin"])
    Cn_fine = np.interp(tau_interp, d_005["tau"], d_005["C_charge"])

    ax1.plot(d_01["tau_over_T"], d_01["C_spin"], "b-", lw=1.0, label=r"$d\tau=0.1$")
    ax1.plot(d_01["tau_over_T"], CS_fine, "r--", lw=1.0, label=r"$d\tau=0.05$")
    ax1.set_ylabel(r"$C_S(\tau)$")
    ax1.set_title(f"dt convergence check  L={L}")
    ax1.legend()

    ax2.plot(d_01["tau_over_T"], d_01["C_charge"], "b-", lw=1.0, label=r"$d\tau=0.1$")
    ax2.plot(d_01["tau_over_T"], Cn_fine, "r--", lw=1.0, label=r"$d\tau=0.05$")
    ax2.set_xlabel(r"$\tau/T$")
    ax2.set_ylabel(r"$C_n(\tau)$")
    ax2.legend()

    # difference subplot
    dCS = np.abs(d_01["C_spin"] - CS_fine)
    dCn = np.abs(d_01["C_charge"] - Cn_fine)
    ax2.text(0.02, 0.98,
             f"max|ΔC_S| = {np.max(dCS):.2e}\nmax|ΔC_n| = {np.max(dCn):.2e}",
             transform=ax2.transAxes, va="top", fontsize=9,
             bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    fig.tight_layout()
    fig.savefig(FIG_DIR / f"dt_convergence_L{L}.png")
    plt.close(fig)
    print(f"Saved: dt_convergence_L{L}.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # Load all available data
    all_data: dict[int, dict] = {}
    for L in [6, 8, 10, 12, 14]:
        d = load_result(L)
        if d is not None:
            all_data[L] = d

    if not all_data:
        print("No results found. Run run_pump_correlation.py first.")
        return

    print(f"Loaded data for L = {sorted(all_data.keys())}")
    make_main_figure(all_data)
    make_bond_heatmaps(all_data)
    make_dt_convergence(L=10)


if __name__ == "__main__":
    main()
