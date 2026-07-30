#!/usr/bin/env python3
"""Run the pre-registered parameter-free channel-reflection validation."""

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

import run_autocorrelation_mitigation as common
from tensor_square.dqmc import DQMCConfig
from tensor_square.stage4 import (
    BLAS_THREAD_VARIABLES,
    validate_blas_environment,
)
from tensor_square.thermal_ed import thermal_m3


EXPERIMENT_ID = "stage4-channel-reflection-20260729-v1"
ARMS = ("control", "channel_reflection")
PROPOSAL_ACCEPTANCE_KEY = "temporal_reflection_acceptance"


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


def _aggregate(
    phase: str,
    rows: list[dict[str, object]],
    base_config: DQMCConfig,
) -> dict[str, object]:
    by_arm = {
        arm: common._arm_summary(
            sorted(
                [row for row in rows if row["arm"] == arm],
                key=lambda row: int(row["replica"]),
            ),
            proposal_acceptance_key=PROPOSAL_ACCEPTANCE_KEY,
        )
        for arm in ARMS
    }
    numerical = {
        arm: common._stability_pass(
            summary,
            block=arm == "channel_reflection",
            proposal_acceptance_key=PROPOSAL_ACCEPTANCE_KEY,
        )
        for arm, summary in by_arm.items()
    }
    comparison = common._comparison(
        by_arm["control"],
        by_arm["channel_reflection"],
        sigma_limit=3.0 if phase == "m3_ed" else 2.0,
    )
    result: dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "phase": phase,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config_without_sampler": base_config.as_dict(),
        "candidate": {
            "name": "full-imaginary-time channel reflection",
            "parameter_free": True,
            "proposal": "phi_c(tau) -> -phi_c(tau)",
        },
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
        return result

    tau_ready = all(bool(by_arm[arm]["tau_audit_pass"]) for arm in ARMS)
    tau_ratio = None
    cost_ratio = None
    if tau_ready:
        control_tau = float(by_arm["control"]["worst_tau_median"])
        reflection_tau = float(
            by_arm["channel_reflection"]["worst_tau_median"]
        )
        tau_ratio = reflection_tau / control_tau
        control_cost = float(
            by_arm["control"]["cpu_seconds_per_effective_sample_median"]
        )
        reflection_cost = float(
            by_arm["channel_reflection"][
                "cpu_seconds_per_effective_sample_median"
            ]
        )
        cost_ratio = reflection_cost / control_cost
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
            "observable/stability gate failed or reflection did not reduce "
            "median worst tau"
        )
    result["tau_reduction"] = {
        "reflection_over_control": tau_ratio,
        "fractional_reduction": (
            1.0 - tau_ratio if tau_ratio is not None else None
        ),
        "advance_threshold": 0.25,
    }
    result["cost_audit"] = {
        "reflection_over_control_cpu_seconds_per_effective_sample": cost_ratio,
        "timing_complete_from_start": all(
            bool(by_arm[arm]["timing_complete_from_start"]) for arm in ARMS
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
    git_metadata = common._git_metadata(project_root)
    if git_metadata["dirty"]:
        raise ValueError("channel-reflection runs require a clean commit")
    m3_release_digest = None
    if args.phase == "stage4_ab":
        if args.m3_result is None:
            raise ValueError("stage4_ab requires --m3-result")
        m3_release_digest = common._validate_m3_release(
            args.m3_result,
            str(git_metadata["commit"]),
            EXPERIMENT_ID,
        )
    base_config, replicas, warmup, measurement, measure_every = _phase_spec(
        args.phase
    )
    tasks = []
    for arm in ARMS:
        config = replace(
            base_config,
            temporal_reflection_updates=arm == "channel_reflection",
        )
        for replica in range(replicas):
            tasks.append(
                {
                    "output_dir": str(args.output_dir),
                    "experiment_id": EXPERIMENT_ID,
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
    common._atomic_json(
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
            "proposal": "full-channel sign reflection once per channel per sweep",
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
        rows = list(executor.map(common._run_task, tasks))
    aggregate = _aggregate(args.phase, rows, base_config)
    aggregate["source_revision"] = git_metadata["commit"]
    common._atomic_json(args.output_dir / "aggregate.json", aggregate)
    print(json.dumps(aggregate, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
