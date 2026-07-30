#!/usr/bin/env python3
"""Attempt 45: compact existing mismatch-gap and system-size evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
CORE = HERE.parent
RESULTS = CORE / "results_summary"
OUTPUT = RESULTS / "QL1F-attempt45-existing-gap-size-evidence.json"
PROTOCOL = CORE / "docs" / "ATTEMPT45_PROTOCOL.md"
PLOTS = CORE / "plots"
PLOT_PNG = PLOTS / "attempt45-gap-size-evidence-development.png"
PLOT_SVG = PLOTS / "attempt45-gap-size-evidence-development.svg"

INPUTS = {
    "attempt25": RESULTS / "QL1F-attempt25-mismatch-boundary.json",
    "attempt28": RESULTS / "QL1F-attempt28-joint-dimension-scaling.json",
    "attempt34": RESULTS / "QL1F-attempt34-endpoint-rank-audit.json",
}


def canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def binary_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_success(run: dict[str, Any]) -> bool:
    scan = run["scan"]
    if run["method"] == "joint-15-v1":
        return scan["first_accepted_to_1e-3"] is not None
    return scan["first_accepted_to_threshold"]["1e-03"] is not None


def success_curve_rows(
    runs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    families = ("control-map", "drift", "combined")
    epsilons = (0.02, 0.05, 0.10)
    methods = ("raw-40", "principal-15", "joint-15-v1")
    rows: list[dict[str, Any]] = []
    for family_index, family in enumerate(families):
        for epsilon_index, epsilon in enumerate(epsilons):
            for method_index, method in enumerate(methods):
                chosen = [
                    run
                    for run in runs
                    if run["family"] == family
                    and float(run["epsilon"]) == epsilon
                    and run["method"] == method
                ]
                grouped: dict[int, list[float]] = {}
                for run in chosen:
                    grouped.setdefault(int(run["truth_seed"]), []).append(
                        float(run_success(run))
                    )
                truth_values = np.asarray(
                    [
                        np.mean(grouped[truth])
                        for truth in sorted(grouped)
                    ],
                    dtype=float,
                )
                if truth_values.size != 8:
                    raise AssertionError(
                        (family, epsilon, method, truth_values.size)
                    )
                rng = np.random.default_rng(
                    11304500
                    + 100 * family_index
                    + 10 * epsilon_index
                    + method_index
                )
                indices = rng.integers(
                    0, truth_values.size, size=(20_000, truth_values.size)
                )
                draws = np.mean(truth_values[indices], axis=1)
                rows.append(
                    {
                        "family": family,
                        "epsilon": epsilon,
                        "method": method,
                        "success": float(np.mean(truth_values)),
                        "lower_95": float(np.quantile(draws, 0.025)),
                        "upper_95": float(np.quantile(draws, 0.975)),
                        "truth_cells": int(truth_values.size),
                        "nested_replicates_per_truth": 4,
                    }
                )
    return rows


def make_plot(
    success_rows: list[dict[str, Any]],
    size_rows: list[dict[str, Any]],
) -> None:
    plt.rcParams.update({"font.size": 10})
    figure, axes = plt.subplots(2, 2, figsize=(12, 8))
    families = ("control-map", "drift", "combined")
    methods = (
        ("raw-40", "Raw-40", "#b54a3a", "X"),
        ("principal-15", "Principal-line-15", "#6b5aa6", "s"),
        ("joint-15-v1", "Joint-15 v1", "#2b61a3", "o"),
    )
    for axis, family in zip(axes.flat[:3], families, strict=True):
        for method, label, color, marker in methods:
            selected = sorted(
                (
                    row
                    for row in success_rows
                    if row["family"] == family and row["method"] == method
                ),
                key=lambda row: row["epsilon"],
            )
            x = np.asarray([row["epsilon"] for row in selected])
            y = np.asarray([row["success"] for row in selected])
            lower = y - np.asarray([row["lower_95"] for row in selected])
            upper = np.asarray([row["upper_95"] for row in selected]) - y
            axis.errorbar(
                x,
                y,
                yerr=np.vstack([lower, upper]),
                color=color,
                marker=marker,
                linewidth=1.8,
                capsize=3,
                label=label,
            )
        axis.axhline(0.75, color="black", linestyle="--", linewidth=1)
        axis.set_title(family)
        axis.set_xlabel("Model–truth gap ε")
        axis.set_ylabel("Oracle-scored target success")
        axis.set_xticks([0.02, 0.05, 0.10])
        axis.set_ylim(-0.04, 1.05)
        axis.grid(alpha=0.25)

    rank_axis = axes.flat[3]
    labels = [row["system"] for row in size_rows]
    x = np.arange(len(size_rows))
    endpoint = [row["endpoint_rank"] for row in size_rows]
    hessian = [row["hessian_rank"] for row in size_rows]
    rank_axis.plot(
        x, endpoint, color="#2b61a3", marker="o", linewidth=2, label="Endpoint"
    )
    rank_axis.plot(
        x,
        hessian,
        color="#b54a3a",
        marker="x",
        linestyle="--",
        linewidth=1.5,
        label="Hessian",
    )
    rank_axis.set_xticks(x, labels, rotation=18, ha="right")
    rank_axis.set_ylabel("Converged numerical rank")
    rank_axis.set_title("Cross-system invariant (mechanism only)")
    rank_axis.grid(alpha=0.25)

    handles, legend_labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(
        handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.955),
        ncol=3,
        frameon=True,
    )
    figure.suptitle(
        "Attempt 45 — existing development evidence; no new simulator queries",
        y=0.995,
        fontsize=14,
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.91))
    PLOTS.mkdir(parents=True, exist_ok=True)
    figure.savefig(PLOT_PNG, dpi=180)
    figure.savefig(PLOT_SVG)
    plt.close(figure)


def main() -> None:
    if not PROTOCOL.is_file():
        raise FileNotFoundError(PROTOCOL)
    for path in INPUTS.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    attempt25 = load(INPUTS["attempt25"])
    attempt28 = load(INPUTS["attempt28"])
    attempt34 = load(INPUTS["attempt34"])

    gap_rows: list[dict[str, Any]] = []
    for family in ("control-map", "drift", "combined"):
        for epsilon in ("0.02", "0.05", "0.10"):
            for method in ("joint-15-v1", "principal-15"):
                analysis = attempt25["analysis"][family][epsilon][method]
                gates = attempt25["gates"][family][epsilon][method]
                gap_rows.append(
                    {
                        "family": family,
                        "epsilon": float(epsilon),
                        "method": method,
                        "success_method": analysis["success_method"],
                        "success_raw": analysis["success_raw"],
                        "success_difference": analysis["success_difference"],
                        "query_ratio": analysis["query_ratio"],
                        "shot_ratio": analysis["shot_ratio"],
                        "resource_ratio_status": analysis[
                            "resource_ratio_status"
                        ],
                        "gates": gates,
                    }
                )

    selected_points = {
        "general-d2": "exact-construction",
        "general-d3": "exact-construction",
        "general-d4": "exact-construction",
        "original-d4-cnot": "refined-optimized",
    }
    size_rows: list[dict[str, Any]] = []
    for system in attempt34["systems"]:
        wanted = selected_points[system["label"]]
        point = next(row for row in system["points"] if row["label"] == wanted)
        size_rows.append(
            {
                "system": system["label"],
                "dimension": int(system["dimension"]),
                "point": wanted,
                "parameter_count": int(point["parameter_count"]),
                "infidelity": float(point["infidelity"]),
                "endpoint_rank": int(point["endpoint_rank"]["rank"]),
                "hessian_rank": int(point["hessian_rank"]["rank"]),
                "ranks_match": bool(
                    point["endpoint_rank"]["rank"]
                    == point["hessian_rank"]["rank"]
                ),
                "unitarity_residual_frobenius": float(
                    point["unitarity_residual_frobenius"]
                ),
            }
        )

    expected_ranks = [3, 8, 15, 15]
    observed_ranks = [row["endpoint_rank"] for row in size_rows]
    curve_rows = success_curve_rows(attempt25["runs"])
    make_plot(curve_rows, size_rows)
    zero_cost_raw = {
        dimension: (
            block["raw"]["restricted_mean_queries"] == 0.0
            and block["raw"]["success_rate"] == 1.0
        )
        for dimension, block in attempt28["summary"].items()
    }
    checks = {
        "three_epsilons_retained": sorted(
            {row["epsilon"] for row in gap_rows}
        )
        == [0.02, 0.05, 0.10],
        "three_families_retained": sorted(
            {row["family"] for row in gap_rows}
        )
        == ["combined", "control-map", "drift"],
        "both_historical_methods_retained": sorted(
            {row["method"] for row in gap_rows}
        )
        == ["joint-15-v1", "principal-15"],
        "converged_ranks_are_3_8_15_15": observed_ranks == expected_ranks,
        "all_converged_endpoint_hessian_ranks_match": all(
            row["ranks_match"] for row in size_rows
        ),
        "attempt28_zero_cost_raw_preserved": all(zero_cost_raw.values()),
        "new_simulator_queries": 0,
        "confirmation_truths_opened": 0,
    }
    if not all(
        bool(value)
        for key, value in checks.items()
        if key not in {"new_simulator_queries", "confirmation_truths_opened"}
    ):
        raise AssertionError(checks)

    payload = {
        "schema": "QL1F-attempt45-existing-gap-size-evidence-v1",
        "attempt": 45,
        "status": "complete",
        "scope": "development/mechanism evidence inventory; no new compute",
        "source_hashes": {
            **{
                name: {
                    "path": path.relative_to(CORE).as_posix(),
                    "canonical_sha256": canonical_text_sha256(path),
                }
                for name, path in INPUTS.items()
            },
            "protocol": {
                "path": PROTOCOL.relative_to(CORE).as_posix(),
                "canonical_sha256": canonical_text_sha256(PROTOCOL),
            },
            "runner": {
                "path": Path(__file__).resolve().relative_to(CORE).as_posix(),
                "canonical_sha256": canonical_text_sha256(
                    Path(__file__).resolve()
                ),
            },
        },
        "gap_evidence": {
            "source_attempt": 25,
            "method_scope": (
                "historical Joint-15 v1 / principal coordinate-scan package; "
                "not principal-global"
            ),
            "rows": gap_rows,
            "success_curve_truth_bootstrap": curve_rows,
            "passing_families": attempt25["passing_families"],
        },
        "size_evidence": {
            "rank_source_attempt": 34,
            "rows": size_rows,
            "rank_interpretation": (
                "near a converged optimum, Hessian rank matches accessible "
                "weighted phase-blind endpoint-error channels"
            ),
        },
        "negative_resource_scaling_result": {
            "source_attempt": 28,
            "zero_cost_raw_by_dimension": zero_cost_raw,
            "falsification_reason": attempt28["falsification_reason"],
            "claim": "no cross-dimension resource-scaling advantage",
        },
        "checks": checks,
        "claim_boundary": {
            "fresh_confirmation": False,
            "new_performance_data": False,
            "principal_global_gap_sweep": False,
            "cross_dimension_resource_advantage": False,
        },
        "artifacts": {
            "plot_png": {
                "path": PLOT_PNG.relative_to(CORE).as_posix(),
                "sha256": binary_sha256(PLOT_PNG),
            },
            "plot_svg": {
                "path": PLOT_SVG.relative_to(CORE).as_posix(),
                "sha256": binary_sha256(PLOT_SVG),
            },
        },
    }
    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(OUTPUT)
    print(
        "attempt45 complete; gap rows="
        f"{len(gap_rows)}, size rows={len(size_rows)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
