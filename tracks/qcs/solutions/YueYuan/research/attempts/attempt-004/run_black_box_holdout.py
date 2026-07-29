#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np

import config
import device
import device_subspace
import hessian
import open_loop
import sealed_black_box
import pulses
import systems


SUMMARY_FIELDS = (
    "split",
    "true_device_variant",
    "system",
    "shots_per_query",
    "method",
    "records",
    "success_rate",
    "median_query_count",
    "median_total_shots",
    "median_final_infidelity",
    "median_probe_query_count",
    "median_probe_directions_selected",
)


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _adaptive_initial_k(system_config) -> int:
    return min(3, system_config.benchmark_rank, system_config.raw_dim)


def _adaptive_max_k(system_config) -> int:
    return min(
        system_config.raw_dim,
        max(system_config.benchmark_rank + 1, 2 * system_config.benchmark_rank),
    )


def _closed_loop_config(base, fast: bool):
    if not fast:
        return base
    return config.ClosedLoopConfig(
        query_budget=48,
        target_infidelity=base.target_infidelity,
        initial_step=base.initial_step,
    )


def _open_loop_config(base, fast: bool):
    if not fast:
        return base
    return config.OpenLoopConfig(
        steps=18,
        learning_rate=base.learning_rate,
        target_infidelity=5e-2,
        seed_scale=0.0,
    )


def work_items(fast: bool) -> list[tuple]:
    if fast:
        return [
            (config.ONE_QUBIT_X, "pulse_distortion", 256, "dev", 0),
            (config.TWO_QUBIT_CZ, "pulse_distortion", 256, "holdout", 100),
        ]
    return [
        (system_cfg, mismatch, shots, split, seed)
        for system_cfg in (config.ONE_QUBIT_X, config.TWO_QUBIT_CZ)
        for mismatch in ("medium", "large", "pulse_distortion")
        for shots in (512, 2048)
        for split, seeds in (("dev", (0, 1)), ("holdout", (100, 101)))
        for seed in seeds
    ]


def _pulse_transform(system, mismatch_name: str):
    mismatch = device.MISMATCHES[mismatch_name]
    if not mismatch.pulse_smoothing and not mismatch.pulse_memory:
        return None
    return lambda pulse: device.distort_pulse_parameters(
        pulse,
        system.config,
        smoothing=mismatch.pulse_smoothing,
        memory=mismatch.pulse_memory,
    )


def _true_device_pair(system, mismatch_name: str, seed: int):
    true_system = device.build_true_system(system, mismatch_name, seed=seed)
    transform = _pulse_transform(system, mismatch_name)
    oracle = sealed_black_box.RecordingQueryOracle(
        device.QueryOnlyDevice(
            true_system,
            seed=seed + 10_000,
            pulse_transform=transform,
        )
    )
    return true_system, transform, oracle


def _run_methods_for_item(system_cfg, mismatch, shots, split, seed, fast: bool) -> list[dict]:
    sweep = config.default_full_sweep()
    open_cfg = _open_loop_config(sweep.open_loop, fast)
    closed_cfg = _closed_loop_config(sweep.closed_loop, fast)
    system = systems.build_system(system_cfg)
    start = pulses.initial_pulse(system_cfg, seed=seed)
    optimized = open_loop.optimize_model_pulse(system, start, open_cfg)
    hess = hessian.dense_hessian(system, optimized.theta)
    method_specs = [
        ("full_space_nelder_mead", system_cfg.raw_dim),
        ("random_subspace_nelder_mead", min(system_cfg.benchmark_rank, system_cfg.raw_dim)),
        ("hessian_subspace_nelder_mead", min(system_cfg.benchmark_rank, system_cfg.raw_dim)),
    ]
    sealed_results = []
    for method, k in method_specs:
        true_system, transform, oracle = _true_device_pair(system, mismatch, seed)
        sealed = sealed_black_box.run_sealed_subspace_method(
            method,
            system,
            oracle,
            optimized.theta,
            hess,
            k=k,
            shots=shots,
            seed=seed,
            cfg=closed_cfg,
        )
        sealed_results.append((sealed, true_system, transform))

    true_system, transform, oracle = _true_device_pair(system, mismatch, seed)
    sealed_results.append(
        (
            sealed_black_box.run_sealed_adaptive_hessian_method(
                system,
                oracle,
                optimized.theta,
                hess,
                initial_k=_adaptive_initial_k(system_cfg),
                max_k=_adaptive_max_k(system_cfg),
                shots=shots,
                seed=seed,
                cfg=closed_cfg,
            ),
            true_system,
            transform,
        )
    )

    true_system, transform, oracle = _true_device_pair(system, mismatch, seed)
    sealed_results.append(
        (
            sealed_black_box.run_sealed_device_informed_adaptive_hessian_method(
                system,
                oracle,
                optimized.theta,
                hess,
                initial_k=_adaptive_initial_k(system_cfg),
                max_k=_adaptive_max_k(system_cfg),
                shots=shots,
                seed=seed,
                cfg=closed_cfg,
                probe_cfg=device_subspace.ProbeConfig(
                    direction_count=4 if fast else 8,
                    append_count=2 if fast else 4,
                    step=max(0.02, 0.5 * closed_cfg.initial_step),
                    repeats=1,
                    min_positive_curvature=-1e-12,
                ),
            ),
            true_system,
            transform,
        )
    )

    rows = []
    for sealed, true_system, transform in sealed_results:
        record = sealed_black_box.score_sealed_run(
            system,
            sealed,
            true_system,
            shots=shots,
            query_budget=closed_cfg.query_budget,
            seed=seed,
            target_infidelity=closed_cfg.target_infidelity,
            mismatch=mismatch,
            pulse_transform=transform,
        )
        row = record.to_json()
        row.update(
            {
                "split": split,
                "true_device_variant": mismatch,
                "black_box_boundary": "sealed_optimizer_posthoc_scoring",
                "transcript_length": len(sealed.transcript),
                "model_open_loop_infidelity": optimized.final_infidelity,
            }
        )
        rows.append(row)
    return rows


def _summary_rows(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        key = (
            row["split"],
            row["true_device_variant"],
            row["system"],
            row["shots_per_query"],
            row["method"],
        )
        grouped[key].append(row)
    summary = []
    for (split, variant, system, shots, method), items in sorted(grouped.items()):
        probe_queries = [
            item["device_probe_query_count"]
            for item in items
            if item.get("device_probe_query_count") is not None
        ]
        selected = [
            item["device_probe_directions_selected"]
            for item in items
            if item.get("device_probe_directions_selected") is not None
        ]
        summary.append(
            {
                "split": split,
                "true_device_variant": variant,
                "system": system,
                "shots_per_query": shots,
                "method": method,
                "records": len(items),
                "success_rate": sum(1 for item in items if item["success"]) / len(items),
                "median_query_count": statistics.median(item["query_count"] for item in items),
                "median_total_shots": statistics.median(item["total_shots"] for item in items),
                "median_final_infidelity": statistics.median(
                    item["final_infidelity"] for item in items
                ),
                "median_probe_query_count": statistics.median(probe_queries)
                if probe_queries
                else None,
                "median_probe_directions_selected": statistics.median(selected)
                if selected
                else None,
            }
        )
    return summary


def _write_summary(out_dir: Path, rows: list[dict]) -> list[dict]:
    tables = out_dir / "summary_tables"
    tables.mkdir(parents=True, exist_ok=True)
    summary = _summary_rows(rows)
    with (tables / "black_box_holdout_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary)
    (out_dir / "summary.json").write_text(
        json.dumps({"records": len(rows), "groups": len(summary)}, indent=2, sort_keys=True)
        + "\n"
    )
    _write_success_figure(out_dir / "figures" / "black_box_holdout_success.png", summary)
    return summary


def _write_success_figure(path: Path, summary: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        path.with_suffix(".skipped.txt").write_text(
            f"Figure skipped because matplotlib could not be imported: {exc}\n"
        )
        return
    focus = [
        row
        for row in summary
        if row["true_device_variant"] == "pulse_distortion"
        and row["method"]
        in {
            "hessian_subspace_nelder_mead",
            "adaptive_hessian_subspace_nelder_mead",
            "device_informed_adaptive_hessian_nelder_mead",
        }
    ]
    labels = [
        f"{row['split']}\n{row['system'].replace('_', ' ')}\n{row['method'].split('_')[0]}"
        for row in focus
    ]
    values = [row["success_rate"] for row in focus]
    fig, ax = plt.subplots(figsize=(max(7.0, 0.8 * len(labels)), 4.2))
    ax.bar(range(len(values)), values, color="#3b7ea1")
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("success rate")
    ax.set_title("Sealed Dev/Holdout Success On Pulse-Distorted Device")
    ax.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _write_outputs(out_dir: Path, rows: list[dict], task_index: int | None = None) -> dict:
    out_dir = Path(out_dir)
    if task_index is None:
        _write_jsonl(out_dir / "runs.jsonl", rows)
        summary = _write_summary(out_dir, rows)
    else:
        _write_jsonl(out_dir / "tasks" / f"runs_{task_index:03d}.jsonl", rows)
        summary = []
    return {
        "out": str(out_dir),
        "records": len(rows),
        "groups": len(summary),
        "splits": sorted({row["split"] for row in rows}),
        "true_device_variants": sorted({row["true_device_variant"] for row in rows}),
    }


def run(out_dir: Path, fast: bool = False, task_index: int | None = None) -> dict:
    items = work_items(fast)
    if task_index is not None:
        items = [items[task_index]]
    rows = []
    for item in items:
        rows.extend(_run_methods_for_item(*item, fast=fast))
    return _write_outputs(out_dir, rows, task_index=task_index)


def _expected_task_paths(out_dir: Path, task_count: int) -> list[Path]:
    return [out_dir / "tasks" / f"runs_{index:03d}.jsonl" for index in range(task_count)]


def combine_tasks(out_dir: Path, expected_task_files: int | None = None) -> dict:
    out_dir = Path(out_dir)
    task_paths = sorted((out_dir / "tasks").glob("runs_*.jsonl"))
    expected_task_files = len(work_items(False)) if expected_task_files is None else expected_task_files
    expected_paths = _expected_task_paths(out_dir, expected_task_files)
    missing_paths = [path.name for path in expected_paths if not path.exists()]
    extra_paths = [
        path.name
        for path in task_paths
        if path.name not in {expected_path.name for expected_path in expected_paths}
    ]
    if missing_paths or extra_paths:
        details = []
        if missing_paths:
            details.append(f"missing {len(missing_paths)}: {', '.join(missing_paths[:5])}")
        if extra_paths:
            details.append(f"extra {len(extra_paths)}: {', '.join(extra_paths[:5])}")
        raise ValueError(
            f"expected {expected_task_files} task files before combining; "
            + "; ".join(details)
        )
    rows = []
    for path in task_paths:
        rows.extend(_read_jsonl(path))
    _write_jsonl(out_dir / "runs.jsonl", rows)
    summary = _write_summary(out_dir, rows)
    return {
        "out": str(out_dir),
        "task_files": len(task_paths),
        "task_files_expected": expected_task_files,
        "records": len(rows),
        "groups": len(summary),
        "splits": sorted({row["split"] for row in rows}),
        "true_device_variants": sorted({row["true_device_variant"] for row in rows}),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--task-index", type=int)
    parser.add_argument("--combine-tasks", action="store_true")
    args = parser.parse_args()
    if args.combine_tasks:
        payload = combine_tasks(args.out)
    else:
        payload = run(args.out, fast=args.fast, task_index=args.task_index)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
