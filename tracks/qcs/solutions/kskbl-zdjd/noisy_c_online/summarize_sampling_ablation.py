"""Summarize uniform versus shuffled-cycle input sampling."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--uniform-run",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument(
        "--shuffled-run",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_run(path: Path) -> dict[str, Any]:
    run_path = path / "run.json"
    metrics_path = path / "metrics.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run["final"]["word_accuracy"] != 1.0:
        raise ValueError(f"{path}: final symbolic rule is not exact")
    if run["verification"]["clean_labels_used_for_updates"] is not False:
        raise ValueError(f"{path}: clean-label isolation is not verified")
    if run["verification"]["fresh_noise_each_sample"] is not True:
        raise ValueError(f"{path}: fresh-noise invariant is not verified")
    return {
        "path": path.as_posix(),
        "run_sha256": sha256(run_path),
        "metrics_sha256": sha256(metrics_path),
        "config": run["config"],
        "first_full_recovery_step": run["first_full_recovery_step"],
        "final": run["final"],
    }


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    first_steps = [run["first_full_recovery_step"] for run in runs]
    residuals = [
        run["final"]["maximum_rounding_residual"] for run in runs
    ]
    minimum_observations = [
        run["final"]["teacher_min_observations"] for run in runs
    ]
    return {
        "run_count": len(runs),
        "mean_first_full_recovery_step": statistics.mean(first_steps),
        "minimum_first_full_recovery_step": min(first_steps),
        "maximum_first_full_recovery_step": max(first_steps),
        "mean_final_maximum_rounding_residual": statistics.mean(residuals),
        "median_final_maximum_rounding_residual": statistics.median(
            residuals
        ),
        "minimum_final_input_observations": min(minimum_observations),
        "maximum_final_input_observations": max(minimum_observations),
    }


def main() -> None:
    args = parse_args()
    if len(args.uniform_run) != len(args.shuffled_run):
        raise ValueError("sampling modes require matched run counts")
    uniform = [load_run(path) for path in args.uniform_run]
    shuffled = [load_run(path) for path in args.shuffled_run]
    uniform_seeds = [run["config"]["base_seed"] for run in uniform]
    shuffled_seeds = [run["config"]["base_seed"] for run in shuffled]
    if uniform_seeds != shuffled_seeds:
        raise ValueError("sampling modes require matched seeds")
    if any(run["config"]["input_sampling"] != "uniform" for run in uniform):
        raise ValueError("uniform group contains another sampling mode")
    if any(
        run["config"]["input_sampling"] != "shuffled-cycle"
        for run in shuffled
    ):
        raise ValueError("shuffled group contains another sampling mode")

    summary = {
        "kind": "quadratic-discovery-input-sampling-ablation",
        "protocol": {
            "seeds": uniform_seeds,
            "steps": 3200,
            "batch_size": 100,
            "noise_rate": 0.25,
            "weight_mode": "observation",
            "fresh_noise_each_sample": True,
            "clean_domain_used_for_updates": False,
        },
        "uniform": {
            "aggregate": aggregate(uniform),
            "runs": uniform,
        },
        "shuffled_cycle": {
            "aggregate": aggregate(shuffled),
            "runs": shuffled,
        },
    }
    uniform_aggregate = summary["uniform"]["aggregate"]
    shuffled_aggregate = summary["shuffled_cycle"]["aggregate"]
    summary["claims"] = {
        "uniform_is_faster_on_mean_first_recovery": (
            uniform_aggregate["mean_first_full_recovery_step"]
            < shuffled_aggregate["mean_first_full_recovery_step"]
        ),
        "shuffled_cycle_has_lower_median_rounding_residual": (
            shuffled_aggregate[
                "median_final_maximum_rounding_residual"
            ]
            < uniform_aggregate[
                "median_final_maximum_rounding_residual"
            ]
        ),
        "mean_first_recovery_step_difference": (
            shuffled_aggregate["mean_first_full_recovery_step"]
            - uniform_aggregate["mean_first_full_recovery_step"]
        ),
        "median_residual_reduction_factor": (
            uniform_aggregate["median_final_maximum_rounding_residual"]
            / shuffled_aggregate[
                "median_final_maximum_rounding_residual"
            ]
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
