#!/usr/bin/env python3
"""Run the pre-registered temporal-block sampler validation and A/B test."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import statistics
import subprocess
import time

from tensor_square.dqmc import DQMCConfig, run_chain
from tensor_square.scan import run_fingerprint
from tensor_square.stage4 import (
    BLAS_THREAD_VARIABLES,
    MONITORED_TAU_KEYS,
    validate_blas_environment,
)
from tensor_square.stage4_analysis import aggregate_replica_estimate
from tensor_square.thermal_ed import thermal_m3


EXPERIMENT_ID = "stage4-autocorrelation-mitigation-20260729-v1"
ARMS = {
    "control": 0.0,
    "temporal_block": 0.1,
}
METRICS = ("energy", "density", "q_a_sq", "q_b_sq", "q_combined")


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _git_metadata(project_root: Path) -> dict[str, object]:
    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def _validate_m3_release(path: Path, source_revision: str) -> str:
    encoded = path.read_bytes()
    release = json.loads(encoded)
    if (
        release.get("experiment_id") != EXPERIMENT_ID
        or release.get("phase") != "m3_ed"
        or release.get("source_revision") != source_revision
        or dict(release.get("decision", {})).get("status") != "PASS"
    ):
        raise ValueError(
            "stage4_ab requires a passing same-revision m3 release"
        )
    return hashlib.sha256(encoded).hexdigest()


def _seed(phase: str, replica: int) -> int:
    material = f"{EXPERIMENT_ID}|{phase}|{replica}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:4], "big")


def _phase_spec(
    phase: str,
) -> tuple[DQMCConfig, int, int, int, int]:
    if phase == "m3_ed":
        return (
            DQMCConfig(
                m=3,
                beta=2.0,
                dt=0.1,
                t=0.5,
                g_b_over_g_a=1.0,
                mu=0.0,
                v_asymmetry=0.15,
                proposal_scale=0.75,
            ),
            4,
            240,
            800,
            2,
        )
    if phase == "stage4_ab":
        return (
            DQMCConfig(
                m=8,
                beta=8.0,
                dt=0.2,
                t=0.5,
                g_b_over_g_a=0.25,
                mu=0.0,
                proposal_scale=0.25,
                stabilize=True,
            ),
            2,
            240,
            640,
            2,
        )
    raise ValueError(f"unknown phase: {phase}")


def _run_task(task: dict[str, object]) -> dict[str, object]:
    output_dir = Path(str(task["output_dir"]))
    phase = str(task["phase"])
    arm = str(task["arm"])
    replica = int(task["replica"])
    config = DQMCConfig(**dict(task["config"]))
    summary_path = output_dir / "chains" / arm / f"replica_{replica:02d}.json"
    fingerprint = run_fingerprint(
        {
            key: value
            for key, value in task.items()
            if key != "output_dir"
        }
    )
    if summary_path.exists():
        previous = json.loads(summary_path.read_text(encoding="utf-8"))
        if previous.get("run_fingerprint") != fingerprint:
            raise ValueError("existing chain fingerprint mismatch")
        return previous
    checkpoint_path = (
        output_dir
        / "checkpoint"
        / arm
        / f"replica_{replica:02d}.npz"
    )
    timing_complete_from_start = not checkpoint_path.exists()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    chain = run_chain(
        config,
        seed=int(task["seed"]),
        warmup_sweeps=int(task["warmup_sweeps"]),
        measurement_sweeps=int(task["measurement_sweeps"]),
        measure_every=int(task["measure_every"]),
        progress_every=80,
        checkpoint_path=checkpoint_path,
        checkpoint_every=80,
        run_fingerprint=fingerprint,
    )
    cpu_seconds = time.process_time() - cpu_start
    wall_seconds = time.perf_counter() - wall_start
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "phase": phase,
        "arm": arm,
        "replica": replica,
        "source_revision": task["source_revision"],
        "run_fingerprint": fingerprint,
        "cpu_seconds": cpu_seconds,
        "wall_seconds": wall_seconds,
        "timing_complete_from_start": timing_complete_from_start,
        **chain,
    }
    _atomic_json(summary_path, payload)
    return payload


def _arm_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {
        "replicas": len(rows),
        "acceptance_min": min(float(row["acceptance"]) for row in rows),
        "acceptance_max": max(float(row["acceptance"]) for row in rows),
        "temporal_block_acceptance_min": min(
            float(row["temporal_block_acceptance"]) for row in rows
        ),
        "temporal_block_acceptance_max": max(
            float(row["temporal_block_acceptance"]) for row in rows
        ),
        "direct_sign_min": min(float(row["direct_sign_min"]) for row in rows),
        "weight_log_error_max": max(
            float(row["weight_log_error_max"]) for row in rows
        ),
        "density_min": min(float(row["density_min"]) for row in rows),
        "density_max": max(float(row["density_max"]) for row in rows),
        "timing_complete_from_start": all(
            bool(row["timing_complete_from_start"]) for row in rows
        ),
        "cpu_seconds_median": statistics.median(
            float(row["cpu_seconds"]) for row in rows
        ),
        "wall_seconds_median": statistics.median(
            float(row["wall_seconds"]) for row in rows
        ),
    }
    tau_rows = [
        [float(row[key]) for key in MONITORED_TAU_KEYS] for row in rows
    ]
    tau_audit_pass = all(
        math.isfinite(value) and value >= 0.5
        for values in tau_rows
        for value in values
    )
    result["tau_audit_pass"] = tau_audit_pass
    worst_taus = (
        [max(values) for values in tau_rows]
        if tau_audit_pass
        else []
    )
    result["worst_tau_by_replica"] = worst_taus
    result["worst_tau_median"] = (
        statistics.median(worst_taus) if worst_taus else None
    )
    effective_samples = (
        [
            int(row["measurements"]) / (2.0 * tau)
            for row, tau in zip(rows, worst_taus, strict=True)
        ]
        if worst_taus
        else []
    )
    result["minimum_fixed_budget_ess"] = (
        min(effective_samples) if effective_samples else 0.0
    )
    result["cpu_seconds_per_effective_sample_median"] = (
        statistics.median(
            float(row["cpu_seconds"]) / effective
            for row, effective in zip(rows, effective_samples, strict=True)
        )
        if effective_samples
        else None
    )
    for metric in METRICS:
        estimate = aggregate_replica_estimate(
            rows,
            value_key=f"{metric}_mean",
            stderr_key=f"{metric}_stderr",
        )
        result[metric] = estimate
    return result


def _comparison(
    control: dict[str, object],
    block: dict[str, object],
    *,
    sigma_limit: float,
) -> dict[str, object]:
    metrics: dict[str, object] = {}
    passes = True
    for metric in METRICS:
        left = dict(control[metric])
        right = dict(block[metric])
        delta = float(right["mean"]) - float(left["mean"])
        combined = math.hypot(
            float(left["stderr"]), float(right["stderr"])
        )
        z = abs(delta) / combined if combined > 0.0 else math.inf
        passed = z <= sigma_limit
        passes = passes and passed
        metrics[metric] = {
            "block_minus_control": delta,
            "combined_stderr": combined,
            "absolute_z": z,
            "pass": passed,
        }
    return {
        "sigma_limit": sigma_limit,
        "all_metrics_pass": passes,
        "metrics": metrics,
    }


def _stability_pass(arm: dict[str, object], *, block: bool) -> bool:
    acceptance_ok = (
        float(arm["acceptance_min"]) >= 0.05
        and float(arm["acceptance_max"]) <= 0.995
    )
    block_acceptance_ok = True
    if block:
        block_acceptance_ok = (
            float(arm["temporal_block_acceptance_min"]) >= 0.05
            and float(arm["temporal_block_acceptance_max"]) <= 0.995
        )
    return (
        acceptance_ok
        and block_acceptance_ok
        and bool(arm["tau_audit_pass"])
        and float(arm["direct_sign_min"]) >= 1.0 - 1.0e-8
        and float(arm["weight_log_error_max"]) <= 1.0e-6
        and float(arm["density_min"]) >= -1.0e-7
        and float(arm["density_max"]) <= 1.0 + 1.0e-7
    )


def _aggregate(
    phase: str,
    rows: list[dict[str, object]],
    base_config: DQMCConfig,
) -> dict[str, object]:
    by_arm = {
        arm: _arm_summary(
            sorted(
                [row for row in rows if row["arm"] == arm],
                key=lambda row: int(row["replica"]),
            )
        )
        for arm in ARMS
    }
    numerical = {
        arm: _stability_pass(summary, block=arm == "temporal_block")
        for arm, summary in by_arm.items()
    }
    comparison = _comparison(
        by_arm["control"],
        by_arm["temporal_block"],
        sigma_limit=3.0 if phase == "m3_ed" else 2.0,
    )
    result: dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "phase": phase,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_without_sampler": base_config.as_dict(),
        "arms": by_arm,
        "numerical_audit": numerical,
        "observable_consistency": comparison,
    }
    if phase == "m3_ed":
        exact = thermal_m3(base_config)
        ed_checks: dict[str, object] = {}
        ed_pass = True
        for arm, arm_summary in by_arm.items():
            arm_checks: dict[str, object] = {}
            for metric in ("energy", "density", "q_combined"):
                estimate = dict(arm_summary[metric])
                error = float(estimate["stderr"])
                z = (
                    abs(float(estimate["mean"]) - float(exact[metric]))
                    / error
                    if error > 0.0
                    else math.inf
                )
                passed = z <= 3.0
                ed_pass = ed_pass and passed
                arm_checks[metric] = {
                    "exact": exact[metric],
                    "absolute_z": z,
                    "pass": passed,
                }
            ed_checks[arm] = arm_checks
        passed = (
            all(numerical.values())
            and bool(comparison["all_metrics_pass"])
            and ed_pass
        )
        result["ed_checks"] = ed_checks
        result["decision"] = {
            "status": "PASS" if passed else "STOP",
            "reason": (
                "both samplers pass numerical, ED, and mutual consistency gates"
                if passed
                else "at least one pre-registered m=3 validation gate failed"
            ),
        }
    else:
        tau_ready = all(
            bool(by_arm[arm]["tau_audit_pass"]) for arm in ARMS
        )
        tau_ratio = None
        cost_ratio = None
        if tau_ready:
            control_tau = float(by_arm["control"]["worst_tau_median"])
            block_tau = float(by_arm["temporal_block"]["worst_tau_median"])
            tau_ratio = block_tau / control_tau
            control_cost = float(
                by_arm["control"][
                    "cpu_seconds_per_effective_sample_median"
                ]
            )
            block_cost = float(
                by_arm["temporal_block"][
                    "cpu_seconds_per_effective_sample_median"
                ]
            )
            cost_ratio = block_cost / control_cost
        stable = all(numerical.values()) and bool(
            comparison["all_metrics_pass"]
        )
        if stable and tau_ratio is not None and tau_ratio <= 0.75:
            status = "ADVANCE"
            reason = "stable observables and at least 25% median worst-tau reduction"
        elif stable and tau_ratio is not None and tau_ratio < 1.0:
            status = "INCONCLUSIVE"
            reason = "stable but sub-threshold tau reduction; require one longer confirmation"
        else:
            status = "STOP"
            reason = (
                "observable/stability gate failed or temporal block did not reduce "
                "median worst tau"
            )
        result["tau_reduction"] = {
            "block_over_control": tau_ratio,
            "fractional_reduction": (
                1.0 - tau_ratio if tau_ratio is not None else None
            ),
            "advance_threshold": 0.25,
        }
        result["cost_audit"] = {
            "block_over_control_cpu_seconds_per_effective_sample": (
                cost_ratio
            ),
            "timing_complete_from_start": all(
                bool(by_arm[arm]["timing_complete_from_start"])
                for arm in ARMS
            ),
            "inference": (
                "reported separately; the frozen ADVANCE gate concerns "
                "statistical mixing rather than throughput"
            ),
        }
        result["decision"] = {"status": status, "reason": reason}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("m3_ed", "stage4_ab"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--machine", choices=("wsl", "cpu"), required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--m3-result", type=Path)
    args = parser.parse_args()
    worker_limit = 14 if args.machine == "wsl" else 62
    if not 1 <= args.workers <= worker_limit:
        raise ValueError(f"workers must be in [1, {worker_limit}]")
    validate_blas_environment(
        {name: os.environ.get(name, "") for name in BLAS_THREAD_VARIABLES}
    )
    project_root = Path(__file__).resolve().parents[6]
    git_metadata = _git_metadata(project_root)
    if git_metadata["dirty"]:
        raise ValueError("autocorrelation mitigation runs require a clean commit")
    m3_release_digest = None
    if args.phase == "stage4_ab":
        if args.m3_result is None:
            raise ValueError("stage4_ab requires --m3-result")
        m3_release_digest = _validate_m3_release(
            args.m3_result, str(git_metadata["commit"])
        )
    base_config, replicas, warmup, measurement, measure_every = _phase_spec(
        args.phase
    )
    tasks = []
    for arm, scale in ARMS.items():
        config = replace(base_config, temporal_block_scale=scale)
        for replica in range(replicas):
            tasks.append(
                {
                    "output_dir": str(args.output_dir),
                    "phase": args.phase,
                    "arm": arm,
                    "replica": replica,
                    "seed": _seed(args.phase, replica),
                    "config": {
                        key: value
                        for key, value in config.as_dict().items()
                        if key != "slices"
                    },
                    "warmup_sweeps": warmup,
                    "measurement_sweeps": measurement,
                    "measure_every": measure_every,
                    "source_revision": git_metadata["commit"],
                    "m3_release_digest": m3_release_digest,
                }
            )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _atomic_json(
        args.output_dir / "manifest.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "phase": args.phase,
            "machine": args.machine,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_revision": git_metadata["commit"],
            "dirty": git_metadata["dirty"],
            "replicas_per_arm": replicas,
            "warmup_sweeps": warmup,
            "measurement_sweeps": measurement,
            "measure_every": measure_every,
            "paired_seed_rule": (
                "sha256(experiment_id|phase|replica), identical across arms"
            ),
            "temporal_block_scale": ARMS["temporal_block"],
            "m3_release_digest": m3_release_digest,
            "workers": min(args.workers, len(tasks)),
            "blas_threads": {
                name: os.environ[name] for name in BLAS_THREAD_VARIABLES
            },
        },
    )
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=min(args.workers, len(tasks)),
        mp_context=context,
    ) as executor:
        rows = list(executor.map(_run_task, tasks))
    aggregate = _aggregate(args.phase, rows, base_config)
    aggregate["source_revision"] = git_metadata["commit"]
    _atomic_json(args.output_dir / "aggregate.json", aggregate)
    print(json.dumps(aggregate, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
