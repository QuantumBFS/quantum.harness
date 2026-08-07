#!/usr/bin/env python3
"""Solve the issue #112 erosion axis: detune J2/J1 away from 2 and watch the
exact localized-magnon features die. One command, all artifacts regenerated:

  python3 run_sawtooth.py

Outputs: briefs/data/erosion.json, briefs/figures/magnetization_curves.png,
briefs/figures/erosion_metrics.png
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from pf import sawtooth

DELTAS = [-0.3, -0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2, 0.3]
SIZES = [12, 16]
CURVE_DELTAS = [-0.2, 0.0, 0.2]
OUT_DATA = Path("briefs/data")
OUT_FIG = Path("briefs/figures")


def main():
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_FIG.mkdir(parents=True, exist_ok=True)

    data = {}
    for N in SIZES:
        for d in DELTAS:
            j2 = 2.0 + d
            print(f"N={N} delta={d:+.2f} ...", flush=True)
            data[f"N{N}_d{d:+.2f}"] = sawtooth.erosion_metrics(N, j2)
    with open(OUT_DATA / "erosion.json", "w") as f:
        json.dump(data, f)

    # Figure 1: magnetization staircases at N=16 for three detunings
    fig, ax = plt.subplots(figsize=(6, 4.5))
    for d in CURVE_DELTAS:
        r = data[f"N16_d{d:+.2f}"]
        ax.plot(r["h"], np.array(r["m"]) / 0.5, drawstyle="steps-post",
                label=f"δ = {d:+.1f}")
    for y, t in [(0.5, "m = M_sat/2 crystal plateau"), (1.0, "saturation")]:
        ax.axhline(y, color="gray", lw=0.5, ls=":")
    ax.axvline(4.0, color="gray", lw=0.5, ls=":")
    ax.set_xlabel("field h / J₁")
    ax.set_ylabel("M / M_sat")
    ax.set_title("Magnetization curves, sawtooth chain N=16 (δ = J₂/J₁ − 2)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_FIG / "magnetization_curves.png", dpi=150)
    plt.close(fig)

    # Figure 2: erosion metrics vs delta, both sizes + one-magnon bandwidth
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for N, mark in zip(SIZES, "os"):
        W = [data[f"N{N}_d{d:+.2f}"]["W"] for d in DELTAS]
        dM = [data[f"N{N}_d{d:+.2f}"]["dM"] for d in DELTAS]
        G = [data[f"N{N}_d{d:+.2f}"]["Gamma"] for d in DELTAS]
        axes[0].plot(DELTAS, W, mark + "-", label=f"N={N}")
        axes[1].plot(DELTAS, np.array(dM) / 0.25, mark + "-", label=f"N={N}")
        axes[2].plot(DELTAS, G, mark + "-", label=f"N={N} Γ")
    bw = [data[f"N16_d{d:+.2f}"]["bandwidth"] for d in DELTAS]
    axes[2].plot(DELTAS, bw, "k--", label="1-magnon bandwidth")
    axes[0].set_ylabel("W(δ) / J₁")
    axes[0].set_title("plateau width")
    axes[1].set_ylabel("ΔM(δ) / (M_sat/2)")
    axes[1].set_title("jump height")
    axes[2].set_ylabel("field scale / J₁")
    axes[2].set_title("jump smearing vs bandwidth")
    for ax in axes:
        ax.set_xlabel("δ = J₂/J₁ − 2")
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_FIG / "erosion_metrics.png", dpi=150)
    plt.close(fig)

    print("\nwrote briefs/data/erosion.json, briefs/figures/*.png", flush=True)


if __name__ == "__main__":
    main()
