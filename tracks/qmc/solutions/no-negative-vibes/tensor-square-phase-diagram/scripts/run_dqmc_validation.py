#!/usr/bin/env python3
"""Run independent DQMC chains and aggregate the Stage 2 ED comparison."""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from tensor_square.dqmc import DQMCConfig, run_chain
from tensor_square.thermal_ed import thermal_m3


def validation_grid(quick: bool) -> list[tuple[DQMCConfig, int]]:
    replicas = 2 if quick else 4
    tasks: list[tuple[DQMCConfig, int]] = []
    configs = [
        DQMCConfig(
            m=3,
            beta=2.0,
            dt=dt,
            t=0.5,
            g_b_over_g_a=1.0,
            mu=0.0,
            v_asymmetry=0.15,
        )
        for dt in (0.2, 0.1, 0.05)
    ]
    configs += [
        DQMCConfig(
            m=4,
            beta=4.0,
            dt=dt,
            t=1.0,
            g_b_over_g_a=1.0,
            mu=0.0,
            v_asymmetry=0.0,
        )
        for dt in (0.2, 0.1)
    ]
    configs += [
        DQMCConfig(
            m=4,
            beta=8.0,
            dt=0.1,
            t=1.0,
            g_b_over_g_a=1.0,
            mu=0.0,
            v_asymmetry=0.0,
            proposal_scale=0.25,
        )
    ]
    for config_index, config in enumerate(configs):
        for replica in range(replicas):
            seed = 2026072900 + 100 * config_index + replica
            tasks.append((config, seed))
    return tasks


def _worker(
    task: tuple[DQMCConfig, int, str],
    quick: bool,
) -> dict[str, object]:
    config, seed, checkpoint = task
    summary = run_chain(
        config,
        seed=seed,
        warmup_sweeps=30 if quick else 240,
        measurement_sweeps=60 if quick else 800,
        measure_every=2,
        progress_every=30 if quick else 80,
        checkpoint_path=Path(checkpoint),
        checkpoint_every=30 if quick else 80,
    )
    print(
        f"complete m={config.m} dt={config.dt} seed={seed} "
        f"E={summary['energy_mean']:.6f}",
        flush=True,
    )
    return summary


def aggregate(chains: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[int, float, float], list[dict[str, object]]] = {}
    for chain in chains:
        config = chain["config"]
        key = (
            int(config["m"]),
            float(config["beta"]),
            float(config["dt"]),
        )
        grouped.setdefault(key, []).append(chain)
    rows = []
    metrics = (
        "energy",
        "density",
        "q_a_sq",
        "q_b_sq",
        "q_combined",
        "nematic_sq",
    )
    for (m, beta, dt), group in sorted(grouped.items()):
        row: dict[str, object] = {
            "m": m,
            "dt": dt,
            "beta": beta,
            "t": group[0]["config"]["t"],
            "g_b_over_g_a": group[0]["config"]["g_b_over_g_a"],
            "replicas": len(group),
            "acceptance_mean": float(
                np.mean([float(chain["acceptance"]) for chain in group])
            ),
            "max_weight_log_error": max(
                float(chain["weight_log_error_mean"]) for chain in group
            ),
            "min_direct_sign": min(
                float(chain["direct_sign_mean"]) for chain in group
            ),
        }
        for metric in metrics:
            values = np.asarray(
                [float(chain[f"{metric}_mean"]) for chain in group]
            )
            row[f"{metric}_mean"] = float(np.mean(values))
            row[f"{metric}_stderr"] = float(
                np.std(values, ddof=1) / np.sqrt(len(values))
                if len(values) > 1
                else float(chain[f"{metric}_stderr"])
            )
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 62:
        raise ValueError("worker count must be in [1, 62]")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_tasks = validation_grid(args.quick)
    tasks = []
    for task_index, (config, seed) in enumerate(raw_tasks):
        checkpoint = (
            args.output_dir.parent
            / "checkpoint"
            / (
                f"chain_{task_index:03d}_{seed}"
                f"{'_stable' if config.beta >= 6.0 else ''}.npz"
            )
        )
        tasks.append((config, seed, str(checkpoint)))
    context = mp.get_context("spawn")
    chains = []
    with ProcessPoolExecutor(
        max_workers=min(args.workers, len(tasks)), mp_context=context
    ) as executor:
        futures = [
            executor.submit(_worker, task, args.quick) for task in tasks
        ]
        for future in futures:
            chains.append(future.result())
    rows = aggregate(chains)
    exact = {}
    for dt in (0.2, 0.1, 0.05):
        config = DQMCConfig(
            m=3,
            beta=2.0,
            dt=dt,
            t=0.5,
            g_b_over_g_a=1.0,
            mu=0.0,
            v_asymmetry=0.15,
        )
        exact[str(dt)] = thermal_m3(config)
    for row in rows:
        if row["m"] == 3:
            reference = exact[str(row["dt"])]
            for metric in ("energy", "density", "q_combined"):
                row[f"{metric}_ed"] = reference[metric]
                row[f"{metric}_z_score"] = (
                    float(row[f"{metric}_mean"]) - reference[metric]
                ) / max(1.0e-12, float(row[f"{metric}_stderr"]))
    table = args.output_dir / "table.csv"
    fieldnames = sorted({key for row in rows for key in row})
    with table.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "experiment_id": "stage2-dqmc-validation-20260729",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "quick": args.quick,
        "workers": min(args.workers, len(tasks)),
        "blas_threads": 1,
        "chains": len(chains),
        "exact_m3": exact,
        "rows": rows,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
