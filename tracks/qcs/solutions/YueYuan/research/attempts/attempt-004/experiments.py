from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import baselines
import config
import device
import hessian
import open_loop
import pulses
import systems


def _k_grid(sweep, system_config):
    return sweep.one_qubit_k if system_config.name == "one_qubit_x" else sweep.two_qubit_k


def _adaptive_max_k(sweep, system_config) -> int:
    target = min(
        system_config.raw_dim,
        max(system_config.benchmark_rank + 1, 2 * system_config.benchmark_rank),
    )
    for k in _k_grid(sweep, system_config):
        if k >= target:
            return min(k, system_config.raw_dim)
    return system_config.raw_dim


def _adaptive_initial_k(system_config) -> int:
    return min(3, system_config.benchmark_rank, system_config.raw_dim)


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


def run_sweep(
    sweep,
    out_dir: Path,
    selected_index: int | None = None,
    fast: bool = False,
    include_adaptive: bool = True,
) -> list[dict]:
    out_dir = Path(out_dir)
    records: list[dict] = []
    open_history: list[dict] = []
    spectra: list[dict] = []
    work_items = _fast_work_items(sweep) if fast else _work_items(sweep)
    if selected_index is not None:
        work_items = [work_items[selected_index]]

    for system_cfg, mismatch, shots, seed in work_items:
        system = systems.build_system(system_cfg)
        start = pulses.initial_pulse(system_cfg, seed=seed)
        open_cfg = sweep.open_loop
        if fast:
            open_cfg = config.OpenLoopConfig(
                steps=18,
                learning_rate=open_cfg.learning_rate,
                target_infidelity=5e-2,
                seed_scale=0.0,
            )
        opt = open_loop.optimize_model_pulse(system, start, open_cfg)
        open_history.extend({**entry, "system": system_cfg.name, "seed": seed} for entry in opt.history)

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
        model_record = baselines.run_model_only(system, true_system, opt.theta, shots=shots, seed=seed)
        records.append({**model_record.to_json(), "mismatch": mismatch})

        closed_cfg = sweep.closed_loop
        if fast:
            closed_cfg = config.ClosedLoopConfig(
                query_budget=max(24, system_cfg.raw_dim + 1),
                target_infidelity=closed_cfg.target_infidelity,
                initial_step=closed_cfg.initial_step,
            )
        for method in (
            "full_space_nelder_mead",
            "random_subspace_nelder_mead",
            "hessian_subspace_nelder_mead",
        ):
            ks = (system_cfg.raw_dim,) if method == "full_space_nelder_mead" else _k_grid(sweep, system_cfg)
            if method == "random_subspace_nelder_mead":
                ks = (min(system_cfg.benchmark_rank, system_cfg.raw_dim),)
            if fast and method == "hessian_subspace_nelder_mead":
                ks = (min(system_cfg.benchmark_rank, system_cfg.raw_dim),)
            for k in ks:
                record = baselines.run_subspace_method(
                    method,
                    system,
                    true_system,
                    opt.theta,
                    hess,
                    k,
                    shots,
                    seed,
                    closed_cfg,
                )
                records.append({**record.to_json(), "mismatch": mismatch})

        if include_adaptive:
            adaptive = baselines.run_adaptive_hessian_method(
                system,
                true_system,
                opt.theta,
                hess,
                initial_k=_adaptive_initial_k(system_cfg),
                max_k=_adaptive_max_k(sweep, system_cfg),
                shots=shots,
                seed=seed,
                cfg=closed_cfg,
            )
            records.append({**adaptive.to_json(), "mismatch": mismatch})

    if selected_index is None:
        runs_path = out_dir / "runs.jsonl"
        history_path = out_dir / "open_loop_history.jsonl"
        spectra_path = out_dir / "hessian_spectra.json"
    else:
        tasks_dir = out_dir / "tasks"
        runs_path = tasks_dir / f"runs_{selected_index:03d}.jsonl"
        history_path = tasks_dir / f"open_loop_history_{selected_index:03d}.jsonl"
        spectra_path = tasks_dir / f"hessian_spectra_{selected_index:03d}.json"
    _write_jsonl(runs_path, records)
    _write_jsonl(history_path, open_history)
    spectra_path.parent.mkdir(parents=True, exist_ok=True)
    spectra_path.write_text(
        json.dumps(spectra, indent=2, sort_keys=True) + "\n"
    )
    return records


def _work_items(sweep) -> list[tuple]:
    return [
        (system_cfg, mismatch, shots, seed)
        for system_cfg in sweep.systems
        for mismatch in sweep.gaps
        for shots in sweep.shots_per_query
        for seed in sweep.seeds
    ]


def _fast_work_items(sweep) -> list[tuple]:
    return [
        (sweep.systems[0], sweep.gaps[0], sweep.shots_per_query[0], sweep.seeds[0]),
        (sweep.systems[1], sweep.gaps[1], sweep.shots_per_query[1], sweep.seeds[-1]),
        (sweep.systems[0], sweep.gaps[2], sweep.shots_per_query[2], sweep.seeds[0]),
    ]


def work_item_count(sweep) -> int:
    return len(_work_items(sweep))


def expected_record_count(sweep, include_adaptive: bool = True) -> int:
    records = 0
    repetitions = len(sweep.gaps) * len(sweep.shots_per_query) * len(sweep.seeds)
    for system_cfg in sweep.systems:
        methods_per_item = 3 + len(_k_grid(sweep, system_cfg))
        if include_adaptive:
            methods_per_item += 1
        records += repetitions * methods_per_item
    return records


def _expected_task_paths(out_dir: Path, task_count: int, stem: str, suffix: str) -> list[Path]:
    return [
        out_dir / "tasks" / f"{stem}_{index:03d}.{suffix}"
        for index in range(task_count)
    ]


def combine_task_outputs(
    out_dir: Path,
    expected_task_files: int | None = None,
    expected_records: int | None = None,
) -> dict:
    out_dir = Path(out_dir)
    expected_task_files = (
        work_item_count(config.default_full_sweep())
        if expected_task_files is None
        else expected_task_files
    )
    artifact_specs = (
        ("runs", "jsonl"),
        ("open_loop_history", "jsonl"),
        ("hessian_spectra", "json"),
    )
    missing = []
    extra = []
    expected_by_artifact = {}
    for stem, suffix in artifact_specs:
        expected_paths = _expected_task_paths(out_dir, expected_task_files, stem, suffix)
        expected_by_artifact[stem] = expected_paths
        expected_names = {path.name for path in expected_paths}
        actual_paths = sorted((out_dir / "tasks").glob(f"{stem}_*.{suffix}"))
        missing.extend(path.name for path in expected_paths if not path.exists())
        extra.extend(path.name for path in actual_paths if path.name not in expected_names)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing {len(missing)}: {', '.join(missing[:5])}")
        if extra:
            details.append(f"extra {len(extra)}: {', '.join(extra[:5])}")
        raise ValueError(
            f"expected {expected_task_files} complete task shards before combining; "
            + "; ".join(details)
        )

    records = []
    history = []
    spectra = []
    for path in expected_by_artifact["runs"]:
        records.extend(_read_jsonl(path))
    for path in expected_by_artifact["open_loop_history"]:
        history.extend(_read_jsonl(path))
    for path in expected_by_artifact["hessian_spectra"]:
        payload = json.loads(path.read_text())
        if not isinstance(payload, list):
            raise ValueError(f"expected a list in {path}")
        spectra.extend(payload)
    if expected_records is not None and len(records) != expected_records:
        raise ValueError(f"expected {expected_records} records, found {len(records)}")

    _write_jsonl(out_dir / "runs.jsonl", records)
    _write_jsonl(out_dir / "open_loop_history.jsonl", history)
    (out_dir / "hessian_spectra.json").write_text(
        json.dumps(spectra, indent=2, sort_keys=True) + "\n"
    )
    return {
        "out": str(out_dir),
        "task_files": expected_task_files,
        "task_files_expected": expected_task_files,
        "records": len(records),
        "open_loop_history_rows": len(history),
        "hessian_spectra": len(spectra),
    }
