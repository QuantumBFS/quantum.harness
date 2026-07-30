#!/usr/bin/env python3
"""Run a conservative set of the first rooted thermodynamic outer SDPs."""

from __future__ import annotations

import csv
from pathlib import Path

from issue92.graphs import GEOMETRIES, rooted_radius_one
from issue92.rooted_sdp import solve_rooted_gap

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    # Exact atomic validation of the full rooted formulation.
    atomic_graph = rooted_radius_one("83")
    for nmax in (1, 2, 3):
        for gamma in (0.49, 0.50, 0.51):
            row = solve_rooted_gap(
                atomic_graph, nmax, gamma, hopping=0.0, mu=0.5
            ).as_dict()
            row["run_type"] = "atomic_validation"
            rows.append(row)

    # The strongest-hopping issue point exposes the first relaxation's useful
    # range without pretending that an UNKNOWN status is a certificate.
    for geometry in GEOMETRIES:
        graph = rooted_radius_one(geometry)
        for nmax in (1, 2, 3):
            for gamma in (0.00, 0.05, 0.10, 0.40, 0.50, 0.60, 0.80, 1.00):
                row = solve_rooted_gap(
                    graph, nmax, gamma, hopping=0.06, mu=0.5
                ).as_dict()
                row["run_type"] = "gap_probe_t0.06_mu0.5"
                rows.append(row)

    # Observable outer bounds at the issue's largest requested assumed gap.
    # nmax=1,2 are used here because the open-source nmax=3 objective models
    # are currently too poorly conditioned to report as dependable results.
    for geometry in GEOMETRIES:
        graph = rooted_radius_one(geometry)
        for nmax in (1, 2):
            for observable in ("rho0", "F0", "K0"):
                for sense in ("min", "max"):
                    row = solve_rooted_gap(
                        graph,
                        nmax,
                        0.10,
                        hopping=0.06,
                        mu=0.5,
                        observable=observable,
                        sense=sense,
                    ).as_dict()
                    row["run_type"] = "observable_bound_t0.06_mu0.5_gamma0.1"
                    rows.append(row)

    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    output = RESULTS / "rooted_thermodynamic_sdp.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rooted thermodynamic SDP rows to {output}")


if __name__ == "__main__":
    main()
