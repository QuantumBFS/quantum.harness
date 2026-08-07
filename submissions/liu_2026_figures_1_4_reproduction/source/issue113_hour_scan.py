#!/usr/bin/env python3
"""Run and aggregate the one-hour Issue #113 gap/seed scan.

The optimized waveform and Hessian are fixed theory artifacts.  Each cell
changes only the query-only synthetic plant's AOM gap strength and binomial
measurement seed.  Theory cache identities are verified before the scan and
then deliberately reused; black-box settings are recorded separately in every
cell manifest.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPRODUCE_ROOT = PACKAGE_ROOT / "source" / "reproduce"
if str(REPRODUCE_ROOT) not in sys.path:
    sys.path.insert(0, str(REPRODUCE_ROOT))

import liu_2026_fig234_reproduction as core  # noqa: E402


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def strict_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: strict_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [strict_json_value(item) for item in value]
    if isinstance(value, np.generic):
        return strict_json_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(
            strict_json_value(value),
            handle,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        handle.write("\n")
    temporary.replace(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def locate_cell(run_spec: dict[str, Any], cell_id: str) -> dict[str, Any]:
    for cell in run_spec["cells"]:
        if cell["cell_id"] == cell_id:
            return cell
    raise KeyError(f"cell {cell_id!r} is not present in the run spec")


def load_cache_identity(
    base_run_dir: Path,
) -> tuple[str, str]:
    hessian_path = base_run_dir / "data" / "fig3_hessian_modes.npz"
    with np.load(hessian_path) as archive:
        return (
            str(archive["config_hash"].item()),
            str(archive["code_version"].item()),
        )


def copy_fixed_theory_artifacts(base_run_dir: Path, cell_dir: Path) -> None:
    data_dir = cell_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (cell_dir / "figs").mkdir(parents=True, exist_ok=True)
    (cell_dir / "logs").mkdir(parents=True, exist_ok=True)
    for name in ("robust_waveform.npz", "fig3_hessian_modes.npz"):
        shutil.copy2(base_run_dir / "data" / name, data_dir / name)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def extract_metrics(
    cell_dir: Path,
    target: float,
    maximum_cycle: int,
) -> dict[str, Any]:
    scans = [
        row
        for row in read_csv(cell_dir / "data" / "fig4_synthetic_scans.csv")
        if int(row["cycle"]) <= maximum_cycle
    ]
    cycles = [
        row
        for row in read_csv(cell_dir / "data" / "fig4_synthetic_cycles.csv")
        if int(row["cycle"]) <= maximum_cycle
    ]
    if not cycles or int(cycles[-1]["cycle"]) != maximum_cycle:
        raise RuntimeError(
            f"serialized cell does not reach requested cycle {maximum_cycle}"
        )

    target_cycle: int | None = None
    for row in cycles:
        if float(row["full_schrodinger_infidelity_raw"]) <= target:
            target_cycle = int(row["cycle"])
            break

    total_queries = len(scans) + len(cycles)
    total_shots = sum(int(row["shots"]) for row in scans + cycles)
    if target_cycle is None:
        query_count_to_target = None
        shots_to_target = None
    else:
        target_scans = [
            row for row in scans if int(row["cycle"]) <= target_cycle
        ]
        target_cycles = [
            row for row in cycles if int(row["cycle"]) <= target_cycle
        ]
        query_count_to_target = len(target_scans) + len(target_cycles)
        shots_to_target = sum(
            int(row["shots"]) for row in target_scans + target_cycles
        )

    return {
        "target_reached": target_cycle is not None,
        "target_cycle": target_cycle,
        "query_count_to_target": query_count_to_target,
        "shots_to_target": shots_to_target,
        "total_queries": total_queries,
        "total_shots": total_shots,
        "initial_coherent_error": float(
            cycles[0]["full_schrodinger_infidelity_raw"]
        ),
        "final_coherent_error": float(
            cycles[-1]["full_schrodinger_infidelity_raw"]
        ),
        "final_observed_total_error": float(
            cycles[-1]["synthetic_observed_total_error"]
        ),
        "final_observed_uncertainty": float(
            cycles[-1]["synthetic_uncertainty"]
        ),
        "oracle_information_used": False,
        "acceptance": {
            "serialized_scans_present": True,
            "target_budget_cycle_present": True
        },
    }


def run_cell(args: argparse.Namespace) -> None:
    started = time.perf_counter()
    run_spec = read_json(args.run_spec)
    cell = locate_cell(run_spec, args.cell_id)
    params = cell["params"]
    settings = {**run_spec.get("settings", {}), **cell.get("settings", {})}
    provenance = run_spec.get("provenance", {})
    cell_dir = Path(run_spec["run_dir"]) / "cells" / args.cell_id
    manifest_path = cell_dir / "manifest.json"
    cell_dir.mkdir(parents=True, exist_ok=True)

    try:
        base_config = core.load_config(args.base_config, "standard")
        base_hash = core.config_hash(base_config)
        cached_hash, cached_code_version = load_cache_identity(args.base_run_dir)
        if base_hash != cached_hash:
            raise RuntimeError(
                "base configuration does not match the fixed Hessian cache: "
                f"{base_hash} != {cached_hash}"
            )

        aom = replace(
            base_config.aom,
            case="paper_scale",
            distortion_strength_paper_scale=float(params["gap_strength"]),
            random_seed=int(params["seed"]),
            cycles=int(settings["cycles"]),
            scan_points=int(settings["scan_points"]),
            shots=int(settings["shots_per_query"]),
            irreducible_baseline=float(settings["irreducible_raw_floor"]),
        )
        scan_config = replace(base_config, aom=aom)
        copy_fixed_theory_artifacts(args.base_run_dir, cell_dir)
        cycles_path = cell_dir / "data" / "fig4_synthetic_cycles.csv"
        scans_path = cell_dir / "data" / "fig4_synthetic_scans.csv"
        reuse_serialized = cycles_path.exists() and scans_path.exists()
        if reuse_serialized:
            existing_cycles = read_csv(cycles_path)
            reuse_serialized = any(
                int(row["cycle"]) == int(settings["cycles"])
                for row in existing_cycles
            )
        if not reuse_serialized:
            original_config_hash = core.config_hash
            original_code_version = core.code_version
            core.config_hash = lambda _config: cached_hash
            core.code_version = lambda: cached_code_version
            try:
                core.synthetic_closed_loop_analysis(cell_dir, scan_config)
            finally:
                core.config_hash = original_config_hash
                core.code_version = original_code_version

        metrics = extract_metrics(
            cell_dir,
            float(settings["target_coherent_error"]),
            int(settings["cycles"]),
        )
        manifest = {
            "cell_id": args.cell_id,
            "params": params,
            "settings": settings,
            "provenance": provenance,
            "status": "success",
            "success": True,
            "results": metrics,
            "evidence": {
                "fixed_theory_config_hash": cached_hash,
                "fixed_theory_code_version": cached_code_version,
                "waveform_sha256": file_sha256(
                    args.base_run_dir / "data" / "robust_waveform.npz"
                ),
                "hessian_sha256": file_sha256(
                    args.base_run_dir / "data" / "fig3_hessian_modes.npz"
                ),
                "runtime_seconds": time.perf_counter() - started,
                "reused_complete_serialized_cell": reuse_serialized,
            },
        }
        write_json(manifest_path, manifest)
        print(
            f"{args.cell_id}: gap={params['gap_strength']} "
            f"seed={params['seed']} target={metrics['target_reached']} "
            f"final={metrics['final_coherent_error']:.6e} "
            f"queries={metrics['query_count_to_target']}",
            flush=True,
        )
    except Exception as error:
        write_json(
            manifest_path,
            {
                "cell_id": args.cell_id,
                "params": params,
                "settings": settings,
                "provenance": provenance,
                "status": "failed",
                "success": False,
                "error": f"{type(error).__name__}: {error}",
                "evidence": {
                    "runtime_seconds": time.perf_counter() - started,
                },
            },
        )
        raise


def finite_mean_std(values: list[float]) -> tuple[float, float]:
    array = np.asarray([value for value in values if math.isfinite(value)])
    if not len(array):
        return math.nan, math.nan
    return float(np.mean(array)), float(np.std(array, ddof=1)) if len(array) > 1 else 0.0


def aggregate(args: argparse.Namespace) -> None:
    rows = read_csv(args.csv)
    groups: dict[float, list[dict[str, str]]] = {}
    for row in rows:
        if row["status"] != "success":
            continue
        groups.setdefault(float(row["gap_strength"]), []).append(row)

    aggregate_rows: list[dict[str, Any]] = []
    for gap in sorted(groups):
        group = groups[gap]
        final_values = [float(row["final_coherent_error"]) for row in group]
        reached = [row["target_reached"].lower() == "true" for row in group]
        query_values = [
            float(row["query_count_to_target"])
            for row in group
            if row["query_count_to_target"]
        ]
        final_mean, final_std = finite_mean_std(final_values)
        query_mean, query_std = finite_mean_std(query_values)
        aggregate_rows.append(
            {
                "gap_strength": gap,
                "successful_cells": len(group),
                "target_success_rate": sum(reached) / len(reached),
                "final_coherent_error_mean": final_mean,
                "final_coherent_error_std": final_std,
                "queries_to_target_mean": query_mean,
                "queries_to_target_std": query_std,
            }
        )

    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    gaps = [row["gap_strength"] for row in aggregate_rows]
    axes[0].errorbar(
        gaps,
        [row["final_coherent_error_mean"] for row in aggregate_rows],
        yerr=[row["final_coherent_error_std"] for row in aggregate_rows],
        marker="o",
        capsize=4,
        color="#315a9a",
    )
    axes[0].axhline(1e-3, color="#c43b3b", linestyle="--", label="target 10⁻³")
    axes[0].set(
        xlabel="AOM model–truth gap strength",
        ylabel="Final coherent error",
        yscale="log",
        title="Fixed rank-10 closure (3 seeds)",
    )
    axes[0].legend(frameon=False)

    query_means = [row["queries_to_target_mean"] for row in aggregate_rows]
    query_stds = [row["queries_to_target_std"] for row in aggregate_rows]
    axes[1].errorbar(
        gaps,
        query_means,
        yerr=query_stds,
        marker="o",
        capsize=4,
        color="#7a4e9d",
    )
    for gap, mean, rate in zip(
        gaps,
        query_means,
        [row["target_success_rate"] for row in aggregate_rows],
    ):
        axes[1].annotate(
            f"{rate:.0%} success",
            (gap, mean),
            xytext=(4, 8),
            textcoords="offset points",
            fontsize=8,
        )
    axes[1].set(
        xlabel="AOM model–truth gap strength",
        ylabel="Black-box queries to coherent error ≤10⁻³",
        title="Query cost",
    )
    figure.suptitle(
        "Issue #113 one-hour scan: gap dependence at fixed k=10",
        fontsize=12,
    )
    figure.tight_layout()
    args.plot.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.plot, dpi=200)
    plt.close(figure)

    write_json(
        args.summary,
        {
            "scope": "fixed k=10; three gap strengths; three seeds",
            "claim_boundary": (
                "This is a gap/seed scan, not the required subspace-dimension "
                "scan or a full-parameter black-box baseline."
            ),
            "aggregate": aggregate_rows,
            "plot": str(args.plot),
        },
    )
    print(f"wrote {args.summary} and {args.plot}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    cell = subparsers.add_parser("run-cell")
    cell.add_argument("--run-spec", type=Path, required=True)
    cell.add_argument("--cell-id", required=True)
    cell.add_argument("--base-run-dir", type=Path, required=True)
    cell.add_argument("--base-config", type=Path, required=True)
    cell.set_defaults(func=run_cell)

    collect = subparsers.add_parser("aggregate")
    collect.add_argument("--csv", type=Path, required=True)
    collect.add_argument("--summary", type=Path, required=True)
    collect.add_argument("--plot", type=Path, required=True)
    collect.set_defaults(func=aggregate)
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    parsed.func(parsed)
