#!/usr/bin/env python3
"""Run the issue #92 fixed-gamma rooted thermodynamic scan."""

from __future__ import annotations

import csv
from pathlib import Path

from issue92.graphs import GEOMETRIES, rooted_radius_one
from issue92.rooted_sdp import solve_rooted_gap

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    parameter_points = [
        ("fixed_mu", 0.03, 0.50),
        ("fixed_mu", 0.05, 0.50),
        ("fixed_mu", 0.06, 0.50),
        ("fixed_t", 0.03, 0.15),
        ("fixed_t", 0.03, 0.75),
    ]
    rows: list[dict[str, object]] = []
    for geometry in GEOMETRIES:
        graph = rooted_radius_one(geometry)
        for nmax in (1, 2, 3):
            for scan, hopping, mu in parameter_points:
                for gamma in (0.00, 0.05, 0.10):
                    row = solve_rooted_gap(
                        graph, nmax, gamma, hopping=hopping, mu=mu
                    ).as_dict()
                    row["scan"] = scan
                    rows.append(row)

    output = RESULTS / "rooted_issue_fixed_gamma_scan.csv"
    fieldnames = list(rows[0]) + ["scan"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} fixed-gamma rooted rows to {output}")


if __name__ == "__main__":
    main()
