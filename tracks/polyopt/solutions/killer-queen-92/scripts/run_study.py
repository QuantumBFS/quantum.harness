#!/usr/bin/env python3
"""Run the atomic SDP and the finite radius-one ED baseline for issue #92."""

from __future__ import annotations

import csv
import importlib.metadata
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / ".figures"
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".raw" / "matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from issue92.atomic_sdp import (
    atomic_observables,
    bisect_atomic_gap,
    solve_atomic_gap,
)
from issue92.ed import solve_finite_patch
from issue92.graphs import GEOMETRIES, graph_summary, hyperbolic_rooted_ball, rooted_radius_one
from issue92.local_algebra import cutoff_commutator_error


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_atomic() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    solver_rows: list[dict[str, object]] = []
    brackets: list[dict[str, object]] = []
    for nmax in (1, 2, 3):
        for gamma in (0.0, 0.05, 0.10, 0.49, 0.50, 0.51):
            row = solve_atomic_gap(nmax, gamma).as_dict()
            row["run_type"] = "fixed_gamma"
            solver_rows.append(row)

        lower, upper, history = bisect_atomic_gap(nmax, tolerance=1e-6)
        for result in history:
            row = result.as_dict()
            row["run_type"] = "bisection"
            solver_rows.append(row)
        brackets.append(
            {
                "claim_type": "U1_RESTRICTED_ATOMIC_STATE_POLYNOMIAL_SDP",
                "nmax": nmax,
                "lower_feasible": lower,
                "upper_infeasible": upper,
                "width": upper - lower,
                "analytic_gap": 0.5,
            }
        )

        for gamma in (0.0, 0.05, 0.10):
            for observable_name, observable in atomic_observables(nmax).items():
                for sense in ("min", "max"):
                    row = solve_atomic_gap(
                        nmax,
                        gamma,
                        observable=observable,
                        observable_name=observable_name,
                        sense=sense,
                    ).as_dict()
                    row["run_type"] = "observable_bound"
                    solver_rows.append(row)
    return solver_rows, brackets


def run_graphs() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for geometry in GEOMETRIES:
        exact = graph_summary(rooted_radius_one(geometry))
        exact["generator_check"] = "exact_radius_one_template"
        rows.append(exact)
        for radius in (1, 2, 3):
            summary = graph_summary(hyperbolic_rooted_ball(geometry, radius))
            summary["generator_check"] = "genuine_hypertiling_dual"
            rows.append(summary)
    return rows


def run_ed() -> list[dict[str, object]]:
    parameter_points = [
        ("atomic_check", 0.00, 0.50),
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
                result = solve_finite_patch(
                    graph, nmax=nmax, hopping=hopping, interaction=1.0, mu=mu
                )
                row = result.as_dict()
                row["scan"] = scan
                rows.append(row)
    return rows


def plot_ed(rows: list[dict[str, object]]) -> None:
    labels = {key: geometry.label for key, geometry in GEOMETRIES.items()}
    for horizontal, fixed, values, filename in (
        ("hopping", ("mu", 0.5), (0.03, 0.05, 0.06), "finite_patch_gap_vs_t.pdf"),
        ("mu", ("hopping", 0.03), (0.15, 0.5, 0.75), "finite_patch_gap_vs_mu.pdf"),
    ):
        figure, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
        for axis, geometry in zip(axes, GEOMETRIES):
            for nmax in (1, 2, 3):
                selected = [
                    row
                    for row in rows
                    if row["geometry"] == geometry
                    and row["nmax"] == nmax
                    and abs(float(row[fixed[0]]) - fixed[1]) < 1e-12
                    and any(abs(float(row[horizontal]) - value) < 1e-12 for value in values)
                ]
                selected.sort(key=lambda row: float(row[horizontal]))
                axis.plot(
                    [row[horizontal] for row in selected],
                    [row["finite_patch_gap"] for row in selected],
                    marker="o",
                    label=f"nmax={nmax}",
                )
            axis.set_title(labels[geometry])
            axis.set_xlabel("t" if horizontal == "hopping" else "mu")
            axis.grid(alpha=0.25)
        axes[0].set_ylabel("finite open radius-1 gap")
        axes[-1].legend(frameon=False)
        figure.suptitle("Diagnostic only — not a thermodynamic bulk-gap certificate")
        figure.tight_layout()
        figure.savefig(FIGURES / filename, bbox_inches="tight")
        figure.savefig(
            FIGURES / filename.replace(".pdf", ".png"),
            dpi=180,
            bbox_inches="tight",
        )
        plt.close(figure)


def environment_metadata() -> dict[str, object]:
    packages = {}
    for package in ("clarabel", "cvxpy", "hypertiling", "matplotlib", "networkx", "numpy", "scipy"):
        packages[package] = importlib.metadata.version(package)
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": packages,
        "claim_boundary": {
            "atomic_sdp": "U(1)-restricted one-site state-polynomial certificate",
            "finite_ed": "open finite-patch diagnostic only",
            "geometry": "hypertiling dual graph; boundary nodes are incomplete",
        },
    }


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    atomic_rows, brackets = run_atomic()
    graph_rows = run_graphs()
    ed_rows = run_ed()

    write_csv(RESULTS / "atomic_sdp_runs.csv", atomic_rows)
    write_csv(RESULTS / "atomic_gap_brackets.csv", brackets)
    write_csv(RESULTS / "graph_scaling.csv", graph_rows)
    write_csv(RESULTS / "finite_patch_ed.csv", ed_rows)
    (RESULTS / "metadata.json").write_text(
        json.dumps(environment_metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (RESULTS / "algebra_checks.json").write_text(
        json.dumps(
            {str(nmax): cutoff_commutator_error(nmax) for nmax in (1, 2, 3)},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    plot_ed(ed_rows)
    print(f"wrote {len(atomic_rows)} atomic SDP rows")
    print(f"wrote {len(ed_rows)} finite-patch ED rows")
    print(f"wrote {len(graph_rows)} graph summaries")
    print(f"results: {RESULTS}")
    print(f"figures: {FIGURES}")


if __name__ == "__main__":
    main()
