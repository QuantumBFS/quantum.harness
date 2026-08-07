#!/usr/bin/env python3
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 300})

fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
values = [3.014303, 7.845999]
papers = [3.045, 7.858]
low = [2.938373, 7.763790]
high = [3.053566, 7.902479]
x = np.arange(2)
axes[0].errorbar(x, values, yerr=[np.array(values)-low, np.array(high)-values], fmt="o", color="#0072B2", capsize=4, label="NNRH-VMCRG reproduction (95% CI)")
axes[0].scatter(x, papers, marker="x", color="#D55E00", label="Published L=45")
axes[0].set_xticks(x, ["even", "odd"]); axes[0].set_ylabel("Leading eigenvalue"); axes[0].legend(frameon=False, fontsize=7)
axes[1].bar([0, 1], [4.980871, 475.546313], color=["#009E73", "#999999"])
axes[1].set_yscale("log"); axes[1].set_xticks([0, 1], ["biased", "unbiased"]); axes[1].set_ylabel("Integrated autocorrelation time")
fig.suptitle("2D VMCRG paper reproduction"); fig.tight_layout(); fig.savefig(OUT / "vmcrg_reproduction.png"); fig.savefig(OUT / "vmcrg_reproduction.pdf"); plt.close(fig)

rounds = np.arange(1, 5)
operator = [0.258610, 0.212841, 0.077681, 0.026534]
patch = [0.313538, 0.301902, 0.137724, 0.094025]
fig, ax = plt.subplots(figsize=(5.2, 3.2))
ax.plot(rounds, operator, "o-", color="#0072B2", label="Operator-equivalence bound")
ax.plot(rounds, patch, "s--", color="#D55E00", label="Legacy patch-TV value")
ax.axhline(0.02, color="black", linestyle=":", label="Frozen threshold 0.02")
ax.set_yscale("log"); ax.set_xticks(rounds); ax.set_xlabel("Legacy round"); ax.set_ylabel("Upper bound"); ax.legend(frameon=False, fontsize=7)
ax.text(0.02, 0.03, "Historical only: patch-TV gate implementation was invalid", transform=ax.transAxes, fontsize=7)
fig.tight_layout(); fig.savefig(OUT / "easy_goal_n3_gates.png"); fig.savefig(OUT / "easy_goal_n3_gates.pdf"); plt.close(fig)

labels = ["Reproduction", "Easy Goal", "MPS/TT", "Hard Goal"]
scores = [1.0, 0.25, 0.5, 0.45]
colors = ["#009E73", "#D55E00", "#56B4E9", "#E69F00"]
states = ["COMPLETE", "PROTOCOL INCOMPLETE", "SUPPORTING ONLY", "STAGE 6 NO-GO"]
fig, ax = plt.subplots(figsize=(6.2, 3.0))
bars = ax.barh(labels, scores, color=colors)
ax.set_xlim(0, 1.05); ax.set_xlabel("Gate progress (categorical, not a completion percentage)")
for bar, state in zip(bars, states): ax.text(0.02, bar.get_y()+bar.get_height()/2, state, va="center", color="white" if bar.get_width() > 0.4 else "black", fontweight="bold", fontsize=7)
fig.tight_layout(); fig.savefig(OUT / "final_gate_overview.png"); fig.savefig(OUT / "final_gate_overview.pdf"); plt.close(fig)
