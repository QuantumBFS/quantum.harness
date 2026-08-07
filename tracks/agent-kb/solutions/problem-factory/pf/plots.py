"""Metric plots for the flight report.

Panel 1: decisiveness per launched card against the kill/dead thresholds —
the verdict picture at a glance. Panel 2: heuristics-library growth — the
issue #133 deliverable made visible.
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

KILL, DEAD = 2.0, 0.5
COLORS = {"survivor": "#2ca02c", "deferred": "#ff7f0e", "dead": "#d62728"}


def plot(telemetry_path, out_path):
    records = [json.loads(line) for line in open(telemetry_path)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))

    measured = [r for r in records if r["metrics"]]
    ids = [r["problem_id"] for r in measured]
    vals = [r["metrics"]["decisiveness"] for r in measured]
    colors = [COLORS[r["verdict"]] for r in measured]
    ax1.bar(range(len(ids)), vals, color=colors)
    ax1.axhline(KILL, color="#2ca02c", ls="--", lw=1, label=f"kill threshold {KILL}")
    ax1.axhline(DEAD, color="#d62728", ls="--", lw=1, label=f"dead below {DEAD}")
    ax1.set_xticks(range(len(ids)), ids, rotation=30, ha="right", fontsize=8)
    ax1.set_ylabel("decisiveness (signal / finite-size noise)")
    ax1.set_title("Hop-test decisiveness vs gates")
    ax1.legend(fontsize=8)

    ax2.plot(range(1, len(records) + 1), range(1, len(records) + 1), "o-", color="#1f77b4")
    ax2.set_xlabel("problems processed")
    ax2.set_ylabel("heuristics library size")
    ax2.set_title("Library growth (every verdict deposits one entry)")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
