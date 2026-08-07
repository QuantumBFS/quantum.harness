#!/usr/bin/env python3
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "figures"
OUT.mkdir(parents=True, exist_ok=True)

with (ROOT / "artifacts/issue128-summary.json").open() as handle:
    summary = json.load(handle)

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})
blue, green, orange, red = "#2455A4", "#2A7F62", "#D97706", "#B42318"

labels = ["Steps", "Merged groups", "Bond propagators", "CNOT upper"]
baseline = np.array([393, 11791, 848952, 2546856], dtype=float)
candidate = np.array([97, 2911, 209592, 628776], dtype=float)
x = np.arange(len(labels))
fig, ax = plt.subplots(figsize=(6.6, 3.1))
ax.bar(x - 0.19, np.ones(4), 0.38, label="Pinned baseline", color=blue)
ax.bar(x + 0.19, candidate / baseline, 0.38, label="Certified result", color=green)
ax.set_xticks(x, labels)
ax.set_ylabel("Resource normalized to baseline")
ax.set_ylim(0, 1.08)
for i, ratio in enumerate(candidate / baseline):
    ax.text(i + 0.19, ratio + 0.025, f"{ratio:.3f}", ha="center", va="bottom")
ax.legend(frameon=False, ncol=2, loc="upper right")
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(OUT / "resources.pdf", bbox_inches="tight")
plt.close(fig)

ledger = summary["error_ledger"]
names = ["D4", "D5", "D6", "D7", "D8+"]
values = [float(ledger[k]["decimal_outward"].replace("e", "E")) for k in ["degree4", "degree5", "degree6", "degree7", "tail"]]
fig, ax = plt.subplots(figsize=(6.6, 3.15))
bars = ax.bar(names, np.array(values) * 1e7, color=[blue, green, orange, "#7A5195", red])
ax.axhline(10.0, color="black", linestyle="--", linewidth=1, label=r"total tolerance $10^{-6}$")
ax.set_ylabel(r"Contribution ($10^{-7}$)")
ax.set_title(r"Certified right-generator ledger at $r=97$")
for bar, value in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.12, f"{value:.2e}", ha="center", fontsize=8)
ax.legend(frameon=False)
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(OUT / "error_ledger.pdf", bbox_inches="tight")
plt.close(fig)

direct, grouped = 20.160968407335066, 6.472926505087888
fig, ax = plt.subplots(figsize=(5.2, 3.0))
bars = ax.bar(["Termwise Pauli $\\ell_1$", "Certified anticommuting groups"], [direct, grouped], color=[orange, green])
ax.set_ylabel("D4 translation-cell norm bound")
ax.set_title("Norm-last structural reduction")
ax.text(0.5, 0.82, f"{direct/grouped:.6f}x tighter", transform=ax.transAxes, ha="center", color=blue, fontweight="bold")
for bar, value in zip(bars, [direct, grouped]):
    ax.text(bar.get_x()+bar.get_width()/2, value+0.35, f"{value:.6f}", ha="center", fontsize=8)
ax.set_ylim(0, 23)
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(OUT / "d4_norm.pdf", bbox_inches="tight")
plt.close(fig)

five_names = ["D4", "D5", "D6", "D7", "D8+"]
five_values = np.array([1.2590841639313686e-6, 4.1149153826738221e-7, 5.8406421306735928e-7, 8.7150631476060649e-8, 9.0076387927122002e-7])
fig, ax = plt.subplots(figsize=(6.6, 3.45))
bottom = 0.0
colors = [blue, green, orange, "#7A5195", red]
for name, value, color in zip(five_names, five_values, colors):
    ax.bar(["$r=78$ conditional audit"], [value*1e6], bottom=bottom, label=name, color=color)
    bottom += value*1e6
ax.axhline(1.0, color="black", linestyle="--", linewidth=1.2, label=r"target $10^{-6}$")
ax.set_ylabel(r"Error upper-bound ledger ($10^{-6}$)")
ax.set_title("Fivefold feasibility gap: not a global certificate", pad=10)
ax.text(0, bottom-0.10, f"total = {bottom:.3f} x target", ha="center", va="top", color="white", fontweight="bold")
ax.set_ylim(0, 3.65)
ax.legend(frameon=False, ncol=1, loc="upper left", bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
fig.tight_layout()
fig.savefig(OUT / "fivefold_gap.pdf", bbox_inches="tight")
plt.close(fig)

print(f"figures={len(list(OUT.glob('*.pdf')))}")
