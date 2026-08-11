#!/usr/bin/env python3
"""Plot P_ex(T) for all L values with comparison and scaling analysis.

Reads merged CSV data from L=6,8,10,12,14 runs.

Usage:
    /opt/anaconda3/bin/python scripts/plot_excitation_probability.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
RESULTS_ROOT = _PROJECT.parent.parent / "results" / "delta-crossing"
FIG_DIR = RESULTS_ROOT / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def _try_import_mpl() -> bool:
    try:
        import matplotlib  # noqa: F401
        return True
    except ImportError:
        return False


def load_all_data():
    """Load merged CSVs for all L values."""
    # L=6 was run locally
    l6 = [
        {"T": 1.0, "P_ex": 0.8169, "L": 6},
        {"T": 2.0, "P_ex": 0.8393, "L": 6},
        {"T": 5.0, "P_ex": 0.8886, "L": 6},
        {"T": 10.0, "P_ex": 0.4274, "L": 6},
        {"T": 20.0, "P_ex": 0.3479, "L": 6},
        {"T": 50.0, "P_ex": 0.0885, "L": 6},
        {"T": 100.0, "P_ex": 0.0840, "L": 6},
    ]
    all_data = {6: l6}

    for csv_path in sorted(RESULTS_ROOT.glob("L*/P_ex_vs_T_L*.csv")):
        L = int(csv_path.parent.name[1:])
        rows = []
        with open(csv_path) as fh:
            for row in csv.DictReader(fh):
                rows.append({
                    "T": float(row["T"]),
                    "P_ex": float(row["P_ex"]),
                    "L": L,
                    "E_i": float(row.get("E_i", 0)),
                    "E_f": float(row.get("E_f", 0)),
                })
        rows.sort(key=lambda r: r["T"])
        all_data[L] = rows

    return all_data


def main() -> None:
    if not _try_import_mpl():
        print("matplotlib not available — skipping figures")
        return

    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    plt.rcParams.update({
        "figure.dpi": 150, "font.size": 10,
        "axes.labelsize": 12, "axes.titlesize": 13,
    })

    all_data = load_all_data()
    Ls = sorted(all_data.keys())
    colors = {6: "#2166ac", 8: "#67a9cf", 10: "#f4a582", 12: "#d6604d", 14: "#b2182b"}
    markers = {6: "o", 8: "s", 10: "D", 12: "^", 14: "v"}

    # ============================================================
    # 1. All L on one plot — linear x-axis
    # ============================================================
    fig, ax = plt.subplots(figsize=(10, 6))
    for L in Ls:
        data = all_data[L]
        Ts = [r["T"] for r in data]
        Ps = [r["P_ex"] for r in data]
        ax.plot(Ts, Ps, marker=markers[L], ms=6, color=colors[L],
                label=f"L={L}", linewidth=1.5)
    ax.set_xlabel("T")
    ax.set_ylabel(r"$P_{\rm ex}(T)$")
    ax.set_title(r"Non-adiabatic excitation probability  $U=12\ \Delta=2\ \delta_0=0.5$")
    ax.legend(ncol=2, fontsize=9)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlim(0, 105)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "P_ex_vs_T_all_L.png", dpi=200)
    plt.close(fig)
    print("Saved: P_ex_vs_T_all_L.png")

    # ============================================================
    # 2. All L on one plot — log x-axis
    # ============================================================
    fig, ax = plt.subplots(figsize=(10, 6))
    for L in Ls:
        data = all_data[L]
        Ts = [r["T"] for r in data]
        Ps = [r["P_ex"] for r in data]
        ax.semilogx(Ts, Ps, marker=markers[L], ms=6, color=colors[L],
                    label=f"L={L}", linewidth=1.5)
    ax.set_xlabel("T (log scale)")
    ax.set_ylabel(r"$P_{\rm ex}(T)$")
    ax.set_title(r"Non-adiabatic excitation probability (log T)  $U=12\ \Delta=2$")
    ax.legend(ncol=2, fontsize=9)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "P_ex_vs_T_all_L_log.png", dpi=200)
    plt.close(fig)
    print("Saved: P_ex_vs_T_all_L_log.png")

    # ============================================================
    # 3. Individual panels per L (2x3 grid)
    # ============================================================
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    for idx, L in enumerate(Ls):
        ax = axes[idx // 3][idx % 3]
        data = all_data[L]
        Ts = [r["T"] for r in data]
        Ps = [r["P_ex"] for r in data]
        ax.plot(Ts, Ps, "o-", ms=6, color=colors[L], linewidth=1.5)
        ax.set_xlabel("T")
        ax.set_ylabel(r"$P_{\rm ex}$")
        ax.set_title(f"L={L}  ({len(data)} points)")
        ax.set_ylim(-0.02, 1.02)
        ax.grid(True, alpha=0.3)
        # annotate
        for t, p in zip(Ts, Ps):
            if t in [1, 10, 100]:
                ax.annotate(f"{p:.3f}", (t, p), textcoords="offset points",
                            xytext=(0, 8), fontsize=7, ha="center")
    fig.suptitle(r"$P_{\rm ex}(T)$ per system size  $U=12\ \Delta=2\ \delta_0=0.5$",
                 fontsize=14)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "P_ex_per_L_panels.png", dpi=200)
    plt.close(fig)
    print("Saved: P_ex_per_L_panels.png")

    # ============================================================
    # 4. Size dependence: P_ex vs L at fixed T
    # ============================================================
    T_compare = [1, 5, 10, 20, 50, 100]
    fig, ax = plt.subplots(figsize=(9, 6))
    for T in T_compare:
        L_vals, P_vals = [], []
        for L in Ls:
            for r in all_data[L]:
                if abs(r["T"] - T) < 1e-6:
                    L_vals.append(L)
                    P_vals.append(r["P_ex"])
                    break
        if L_vals:
            ax.plot(L_vals, P_vals, "o-", ms=6, label=f"T={T}", linewidth=1.3)
    ax.set_xlabel("L")
    ax.set_ylabel(r"$P_{\rm ex}$")
    ax.set_title(r"$P_{\rm ex}$ vs system size at fixed ramp time")
    ax.legend(fontsize=9)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "P_ex_vs_L.png", dpi=200)
    plt.close(fig)
    print("Saved: P_ex_vs_L.png")

    # ============================================================
    # 5. Energy gap ΔE = |E_f - E_i| vs L
    # ============================================================
    fig, ax = plt.subplots(figsize=(8, 5))
    for L in Ls:
        data = all_data[L]
        if data:
            L_vals = [data[0]["L"]]
            dE = [abs(data[0]["E_f"] - data[0]["E_i"])]
            ax.plot(L_vals, dE, "o", ms=8, color=colors[L], label=f"L={L}")
    ax.set_xlabel("L")
    ax.set_ylabel(r"$|E_f - E_i|$")
    ax.set_title("Ground-state energy difference between endpoints")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "energy_gap_vs_L.png", dpi=200)
    plt.close(fig)
    print("Saved: energy_gap_vs_L.png")

    print(f"\nAll figures saved to: {FIG_DIR}/")
    print(f"Data summary: L={Ls}")


if __name__ == "__main__":
    main()
