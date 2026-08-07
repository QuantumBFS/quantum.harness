#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import analysis
import baselines
import config
import device
import device_subspace
import hessian
import open_loop
import plotting
import pulses
import systems


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _adaptive_initial_k(system_config) -> int:
    return min(3, system_config.benchmark_rank, system_config.raw_dim)


def _adaptive_max_k(system_config) -> int:
    return min(
        system_config.raw_dim,
        max(system_config.benchmark_rank + 1, 2 * system_config.benchmark_rank),
    )


def _work_items(fast: bool):
    if fast:
        return [
            (config.ONE_QUBIT_X, "large", 256, 0),
            (config.TWO_QUBIT_CZ, "medium", 256, 1),
        ]
    return [
        (system_cfg, mismatch, 2048, seed)
        for system_cfg in (config.ONE_QUBIT_X, config.TWO_QUBIT_CZ)
        for mismatch in ("medium", "large")
        for seed in range(8)
    ]


def _open_loop_config(base, fast: bool):
    if not fast:
        return base
    return config.OpenLoopConfig(
        steps=18,
        learning_rate=base.learning_rate,
        target_infidelity=5e-2,
        seed_scale=0.0,
    )


def _closed_loop_config(base, fast: bool):
    if not fast:
        return base
    return config.ClosedLoopConfig(
        query_budget=48,
        target_infidelity=base.target_infidelity,
        initial_step=base.initial_step,
    )


def _focused_records(fast: bool) -> list[dict]:
    sweep = config.default_full_sweep()
    open_cfg = _open_loop_config(sweep.open_loop, fast)
    closed_cfg = _closed_loop_config(sweep.closed_loop, fast)
    records = []
    histories = []
    spectra = []

    for system_cfg, mismatch, shots, seed in _work_items(fast):
        system = systems.build_system(system_cfg)
        start = pulses.initial_pulse(system_cfg, seed=seed)
        opt = open_loop.optimize_model_pulse(system, start, open_cfg)
        histories.extend(
            {**entry, "system": system_cfg.name, "seed": seed}
            for entry in opt.history
        )
        hess = hessian.dense_hessian(system, opt.theta)
        eig_values = np.linalg.eigvalsh(hess)
        spectra.append(
            {
                "system": system_cfg.name,
                "mismatch": mismatch,
                "shots_per_query": shots,
                "seed": seed,
                "eigenvalues": [float(value) for value in eig_values],
                "effective_rank": hessian.effective_rank(eig_values),
                "benchmark_rank": system_cfg.benchmark_rank,
                "curvature_at_benchmark_k": hessian.curvature_fraction(
                    eig_values, system_cfg.benchmark_rank
                ),
                "k_for_90pct_curvature": hessian.min_k_for_curvature(eig_values, 0.90),
                "k_for_95pct_curvature": hessian.min_k_for_curvature(eig_values, 0.95),
                "k_for_99pct_curvature": hessian.min_k_for_curvature(eig_values, 0.99),
            }
        )
        true_system = device.build_true_system(system, mismatch, seed=seed)
        methods = [
            baselines.run_subspace_method(
                "full_space_nelder_mead",
                system,
                true_system,
                opt.theta,
                hess,
                system_cfg.raw_dim,
                shots,
                seed,
                closed_cfg,
            ),
            baselines.run_subspace_method(
                "random_subspace_nelder_mead",
                system,
                true_system,
                opt.theta,
                hess,
                min(system_cfg.benchmark_rank, system_cfg.raw_dim),
                shots,
                seed,
                closed_cfg,
            ),
            baselines.run_subspace_method(
                "hessian_subspace_nelder_mead",
                system,
                true_system,
                opt.theta,
                hess,
                min(system_cfg.benchmark_rank, system_cfg.raw_dim),
                shots,
                seed,
                closed_cfg,
            ),
            baselines.run_adaptive_hessian_method(
                system,
                true_system,
                opt.theta,
                hess,
                initial_k=_adaptive_initial_k(system_cfg),
                max_k=_adaptive_max_k(system_cfg),
                shots=shots,
                seed=seed,
                cfg=closed_cfg,
            ),
            baselines.run_device_informed_adaptive_hessian_method(
                system,
                true_system,
                opt.theta,
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
        ]
        records.extend({**record.to_json(), "mismatch": mismatch} for record in methods)

    return records, histories, spectra


def run(out_dir: Path, fast: bool) -> dict:
    out_dir = Path(out_dir)
    records, histories, spectra = _focused_records(fast)
    _write_jsonl(out_dir / "runs.jsonl", records)
    _write_jsonl(out_dir / "open_loop_history.jsonl", histories)
    (out_dir / "hessian_spectra.json").write_text(
        json.dumps(spectra, indent=2, sort_keys=True) + "\n"
    )
    summary = analysis.write_summary(out_dir)
    analysis.write_device_informed_tables(out_dir, summary)
    figure = plotting.make_device_informed_recovery(out_dir)
    payload = {
        "records": len(records),
        "device_informed_records": sum(
            1
            for record in records
            if record["method"] == "device_informed_adaptive_hessian_nelder_mead"
        ),
        "out": str(out_dir),
        "figure": str(figure),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.out, args.fast), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
