from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from device import QueryOnlyDevice


@dataclass(frozen=True)
class HardwareCandidate:
    candidate_id: str
    pulse_parameters: np.ndarray
    metadata: dict | None = None


@dataclass(frozen=True)
class HardwareJob:
    job_id: str
    candidate_id: str
    shots: int
    metadata: dict


@dataclass(frozen=True)
class HardwareResult:
    job_id: str
    candidate_id: str
    shots: int
    counts: dict[str, int]
    metadata: dict


@dataclass(frozen=True)
class HardwareEvaluation:
    candidate_id: str
    objective: float
    shots: int
    counts: dict[str, int]
    metadata: dict


OBJECTIVE_PROXY = "success_probability_infidelity"


def _candidate_payload(candidate: HardwareCandidate) -> dict:
    return {
        "candidate_id": candidate.candidate_id,
        "pulse_parameters": np.asarray(candidate.pulse_parameters, dtype=float).tolist(),
        "metadata": dict(candidate.metadata or {}),
    }


def _result_payload(result: HardwareResult) -> dict:
    return {
        "job_id": result.job_id,
        "candidate_id": result.candidate_id,
        "shots": int(result.shots),
        "counts": {str(key): int(value) for key, value in result.counts.items()},
        "metadata": dict(result.metadata),
    }


def _validated_counts(result: HardwareResult) -> dict[str, int]:
    counts = {str(key): int(value) for key, value in result.counts.items()}
    if any(value < 0 for value in counts.values()):
        raise ValueError("counts must be non-negative")
    total = sum(counts.values())
    if total != int(result.shots):
        raise ValueError("counts must sum to shots")
    return counts


def evaluate_result(result: HardwareResult, success_key: str = "target") -> HardwareEvaluation:
    if result.shots <= 0:
        raise ValueError("shots must be positive")
    counts = _validated_counts(result)
    successes = int(counts.get(success_key, 0))
    objective = 1.0 - successes / float(result.shots)
    return HardwareEvaluation(
        candidate_id=result.candidate_id,
        objective=float(min(1.0, max(0.0, objective))),
        shots=result.shots,
        counts=counts,
        metadata=dict(result.metadata),
    )


def write_batch_bundle(
    candidates,
    out_dir: Path,
    shots: int,
    metadata: dict | None = None,
) -> dict[str, Path]:
    if shots <= 0:
        raise ValueError("shots must be positive")
    candidate_list = list(candidates)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / "batch_manifest.json"
    candidates_path = out_dir / "candidates.csv"
    pulse_payloads_path = out_dir / "pulse_payloads.jsonl"

    manifest = {
        "schema_version": 1,
        "backend_contract": "batch_hardware_adapter",
        "candidate_count": len(candidate_list),
        "shots_per_candidate": int(shots),
        "total_planned_shots": len(candidate_list) * int(shots),
        "objective_proxy": OBJECTIVE_PROXY,
        "metadata": dict(metadata or {}),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    with candidates_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("candidate_id", "pulse_dim", "shots", "metadata_json"),
        )
        writer.writeheader()
        for candidate in candidate_list:
            pulse = np.asarray(candidate.pulse_parameters, dtype=float)
            writer.writerow(
                {
                    "candidate_id": candidate.candidate_id,
                    "pulse_dim": int(pulse.size),
                    "shots": int(shots),
                    "metadata_json": json.dumps(dict(candidate.metadata or {}), sort_keys=True),
                }
            )

    with pulse_payloads_path.open("w") as handle:
        for candidate in candidate_list:
            handle.write(json.dumps(_candidate_payload(candidate), sort_keys=True) + "\n")

    return {
        "manifest": manifest_path,
        "candidates": candidates_path,
        "pulse_payloads": pulse_payloads_path,
    }


def write_results_jsonl(results, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for result in results:
            handle.write(json.dumps(_result_payload(result), sort_keys=True) + "\n")
    return path


def read_results_jsonl(path: Path) -> list[HardwareResult]:
    results = []
    with Path(path).open() as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            results.append(
                HardwareResult(
                    job_id=str(payload["job_id"]),
                    candidate_id=str(payload["candidate_id"]),
                    shots=int(payload["shots"]),
                    counts={str(key): int(value) for key, value in payload["counts"].items()},
                    metadata=dict(payload.get("metadata", {})),
                )
            )
    return results


def summarize_evaluations(evaluations) -> dict:
    evaluation_list = list(evaluations)
    total_shots = sum(int(evaluation.shots) for evaluation in evaluation_list)
    if not evaluation_list:
        return {
            "candidate_count": 0,
            "total_shots": 0,
            "best_candidate_id": None,
            "best_objective": None,
            "mean_objective": None,
            "objective_proxy": OBJECTIVE_PROXY,
        }
    best = min(evaluation_list, key=lambda evaluation: evaluation.objective)
    return {
        "candidate_count": len(evaluation_list),
        "total_shots": total_shots,
        "best_candidate_id": best.candidate_id,
        "best_objective": float(best.objective),
        "mean_objective": float(np.mean([evaluation.objective for evaluation in evaluation_list])),
        "objective_proxy": OBJECTIVE_PROXY,
    }


class DryRunBatchBackend:
    def __init__(self, true_system, seed: int = 0, success_key: str = "target") -> None:
        self._oracle = QueryOnlyDevice(true_system, seed=seed)
        self._success_key = success_key
        self._jobs: dict[str, HardwareJob] = {}
        self._results: dict[str, HardwareResult] = {}

    @property
    def query_count(self) -> int:
        return self._oracle.query_count

    @property
    def shot_count(self) -> int:
        return self._oracle.shot_count

    def submit_batch(
        self,
        candidates: list[HardwareCandidate],
        shots: int,
        metadata: dict | None = None,
    ) -> list[HardwareJob]:
        if shots <= 0:
            raise ValueError("shots must be positive")
        batch_metadata = dict(metadata or {})
        jobs = []
        for candidate in candidates:
            job_id = f"dryrun-{len(self._jobs):06d}"
            noisy_infidelity = self._oracle.query(candidate.pulse_parameters, shots)
            successes = int(round((1.0 - noisy_infidelity) * int(shots)))
            successes = max(0, min(int(shots), successes))
            counts = {
                self._success_key: successes,
                "other": int(shots) - successes,
            }
            result_metadata = {
                **batch_metadata,
                **dict(candidate.metadata or {}),
                "backend": "dry-run",
                "real_hardware": False,
            }
            job = HardwareJob(
                job_id=job_id,
                candidate_id=candidate.candidate_id,
                shots=int(shots),
                metadata=result_metadata,
            )
            self._jobs[job_id] = job
            self._results[job_id] = HardwareResult(
                job_id=job_id,
                candidate_id=candidate.candidate_id,
                shots=int(shots),
                counts=counts,
                metadata=result_metadata,
            )
            jobs.append(job)
        return jobs

    def collect_results(self, job_ids: list[str]) -> list[HardwareResult]:
        return [self._results[job_id] for job_id in job_ids]
