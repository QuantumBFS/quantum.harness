#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import config
import device
import hardware_adapter
import hessian
import open_loop
import pulses
import systems


def _candidate_set(system, theta, basis, step_size: float) -> list[hardware_adapter.HardwareCandidate]:
    candidates = [
        hardware_adapter.HardwareCandidate(
            "center",
            pulses.clip_pulse(theta, system.config),
            metadata={"source": "open_loop_center"},
        )
    ]
    for index in range(basis.shape[1]):
        direction = basis[:, index]
        for sign, label in ((1.0, "plus"), (-1.0, "minus")):
            candidate_id = f"hessian-{index + 1}-{label}"
            candidates.append(
                hardware_adapter.HardwareCandidate(
                    candidate_id,
                    pulses.clip_pulse(theta + sign * step_size * direction, system.config),
                    metadata={
                        "source": "hessian_direction",
                        "direction_index": index,
                        "sign": label,
                        "step_size": step_size,
                    },
                )
            )
    return candidates


def run_dry_run(out_dir: Path, shots: int) -> dict:
    system = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=31)
    open_cfg = config.OpenLoopConfig(
        steps=25,
        learning_rate=0.045,
        target_infidelity=5e-2,
        seed_scale=0.0,
    )
    optimized = open_loop.optimize_model_pulse(system, start, open_cfg)
    hess = hessian.dense_hessian(system, optimized.theta)
    eigenspace = hessian.leading_eigenspace(hess, k=3)
    candidates = _candidate_set(system, optimized.theta, eigenspace.vectors, step_size=0.04)

    metadata = {
        "attempt": "attempt-004",
        "mode": "hardware_dry_run",
        "system": system.config.name,
        "target_gate": system.config.target,
        "real_hardware": False,
        "candidate_generation": "open_loop_center_plus_minus_top_three_hessian_directions",
    }
    artifact_paths = hardware_adapter.write_batch_bundle(
        candidates,
        out_dir,
        shots=shots,
        metadata=metadata,
    )

    true_system = device.build_true_system(system, "small", seed=32)
    backend = hardware_adapter.DryRunBatchBackend(true_system, seed=33)
    jobs = backend.submit_batch(candidates, shots=shots, metadata=metadata)
    results = backend.collect_results([job.job_id for job in jobs])
    results_path = hardware_adapter.write_results_jsonl(
        results,
        Path(out_dir) / "hardware_results.jsonl",
    )
    evaluations = [hardware_adapter.evaluate_result(result) for result in results]
    summary = hardware_adapter.summarize_evaluations(evaluations)
    summary.update(
        {
            "schema_version": 1,
            "attempt": "attempt-004",
            "mode": "hardware_dry_run",
            "real_hardware": False,
            "submitted_jobs": len(jobs),
            "query_count": backend.query_count,
            "shot_count": backend.shot_count,
            "model_open_loop_infidelity": float(optimized.final_infidelity),
            "hessian_eigenvalues": [float(value) for value in eigenspace.values],
            "artifact_files": {
                "batch_manifest": str(artifact_paths["manifest"]),
                "candidates": str(artifact_paths["candidates"]),
                "pulse_payloads": str(artifact_paths["pulse_payloads"]),
                "hardware_results": str(results_path),
                "hardware_summary": str(Path(out_dir) / "hardware_summary.json"),
            },
        }
    )
    summary_path = Path(out_dir) / "hardware_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--shots", type=int, default=256)
    args = parser.parse_args()

    summary = run_dry_run(args.out, args.shots)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
