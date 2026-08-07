#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import invariant_probe


FIELDS = (
    "system",
    "hilbert_dim",
    "benchmark_rank",
    "observed_curved_rank",
    "pulse_dim_or_chart_dim",
    "evidence_type",
    "rank_metric",
    "curvature_at_benchmark_rank",
    "formal_effective_rank",
    "source_seed",
    "open_loop_infidelity",
    "caveat",
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_figure(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = [f"{row['system']}\nd={row['hilbert_dim']}" for row in rows]
    benchmark = [row["benchmark_rank"] for row in rows]
    observed = [row["observed_curved_rank"] for row in rows]
    xs = list(range(len(rows)))
    width = 0.36

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar([x - width / 2 for x in xs], benchmark, width=width, label="d^2 - 1")
    ax.bar([x + width / 2 for x in xs], observed, width=width, label="observed metric")
    ax.set_title("Invariant Curved Dimension Probe")
    ax.set_ylabel("rank")
    ax.set_xticks(xs, labels)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run(out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    rows = invariant_probe.rank_probe_rows()
    csv_path = out_dir / "invariant_rank_probe.csv"
    figure_path = out_dir / "figures" / "invariant_rank_probe.png"
    _write_csv(csv_path, rows)
    _write_figure(figure_path, rows)
    return {
        "rows": len(rows),
        "csv": str(csv_path),
        "figure": str(figure_path),
        "three_qubit_evidence_type": next(
            row["evidence_type"] for row in rows if row["hilbert_dim"] == 8
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.out), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
