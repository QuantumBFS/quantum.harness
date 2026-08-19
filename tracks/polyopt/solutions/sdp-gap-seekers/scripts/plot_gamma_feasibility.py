#!/usr/bin/env python3
"""Gamma-feasibility summary for the L=1/d=2 SDP gap scans (challenge #88).

Plots the tested gamma points per model at the smallest tractable relaxation
level (L=1, d=2). Every point is OPTIMAL-feasible, so no gamma is excluded and
no bulk-gap upper bound is certified at this level. This is the headline
"too weak at d=2" figure for the submission report.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# (label, [gamma points], marker) -- all feasible_residual_checked_float
models = [
    ("Square J1-J2  Rung A (bare_weight_one)", [0, 0.25, 2], "o"),
    ("Square J1-J2  Rung B + D4", [0, 0.25, 0.40, 2], "s"),
    ("Square J1-J2  Rung C (spin-isotypic)", [0, 2], "D"),
    ("Shastry-Sutherland  (spin-isotypic)", [0.5, 1, 2, 4], "^"),
    ("Triangular J1  (spin-isotypic)", [0, 1, 2], "v"),
]

fig, ax = plt.subplots(figsize=(8.0, 4.2))
ax.axvline(0, color="0.75", lw=0.8, zorder=0)
for i, (label, gammas, marker) in enumerate(models):
    y = len(models) - i
    ax.plot(gammas, [y] * len(gammas), marker=marker, ls="-", lw=1.2,
            ms=8, label=label)
ax.set_yticks(range(1, len(models) + 1))
ax.set_yticklabels([m[0] for m in reversed(models)], fontsize=9)
ax.set_xlabel(r"gap threshold  $\gamma$   (F($\gamma$) feasible $\Rightarrow$ $\gamma$ not excluded)",
              fontsize=9)
ax.set_xlim(-0.3, 4.5)
ax.set_ylim(0.4, len(models) + 0.6)
ax.set_title("L=1, d=2  $\\gamma$-feasibility: every point OPTIMAL-feasible $\\Rightarrow$ "
             "no bulk-gap upper bound at d=2", fontsize=10)
ax.grid(axis="x", ls=":", alpha=0.5)
fig.tight_layout()

import sys
out = sys.argv[1] if len(sys.argv) > 1 else "gammascan.png"
fig.savefig(out, dpi=150)
print("wrote", out)
