"""N4 paired five-seed/five-round formal orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .artifacts import canonical_json_bytes, sha256_bytes
from .issue28_protocol import Issue28Protocol, SeedBundle
from .issue28_workflow import read_verified_stage_manifest
from .local_execution import resolve_worker_limit
from .one_round import _child_sequence, _stream_hash


def _formal_bundle(protocol: Issue28Protocol, bundle_id: str) -> SeedBundle:
    matches = [bundle for bundle in protocol.formal_bundles if bundle.bundle_id == bundle_id]
    if len(matches) != 1:
        raise ValueError(f"unknown formal seed bundle: {bundle_id}")
    return matches[0]


def _initial_states(
    protocol: Issue28Protocol,
    bundle: SeedBundle,
    round_index: int,
    walkers: int,
) -> np.ndarray:
    return np.stack(
        [
            np.random.default_rng(
                _child_sequence(
                    bundle.streams["initial_condition"],
                    round_index,
                    walker,
                )
            ).choice(
                np.asarray([-1, 1], dtype=np.int8),
                size=(protocol.physical.length, protocol.physical.length),
            )
            for walker in range(walkers)
        ]
    )


def build_formal_bundle_plan(
    protocol: Issue28Protocol,
    bundle_id: str,
    formal_execution: Mapping[str, Any],
    *,
    backend: str = "slurm",
    workers: int | None = None,
) -> dict[str, Any]:
    if backend not in ("local", "slurm"):
        raise ValueError(f"unknown N4 backend: {backend}")
    bundle = _formal_bundle(protocol, bundle_id)
    if (
        int(formal_execution.get("formal_seed_count", 0)) != 5
        or int(formal_execution.get("formal_rounds", 0)) != protocol.formal_rounds
        or formal_execution.get("postformal_seed_extension_allowed") is not False
        or formal_execution.get("failed_seed_replacement_allowed") is not False
    ):
        raise ValueError("formal execution seed/round mutation policy is invalid")
    training = dict(formal_execution["training"])
    resources = dict(formal_execution["resources"])
    autocorrelation = dict(formal_execution["autocorrelation"])
    walkers = 16
    worker_limit = resolve_worker_limit(
        workers,
        walkers,
    )
    if backend == "local":
        runtime = {
            "backend": "local",
            "execution_policy": "LOCAL_COMPUTE_DEVIATION",
            "workers_per_bundle": worker_limit,
            "max_parallel_bundles": 2,
            "hardware_class": "matched_local_host",
        }
    else:
        runtime = {
            "backend": "slurm",
            "execution_policy": "SLURM",
            "workers_per_bundle": worker_limit,
            "max_parallel_bundles": 1,
            "hardware_class": resources["hardware_class"],
        }
    budget = {
        "walkers": walkers,
        "maximum_updates": int(training["maximum_updates"]),
        "sweeps_per_gradient_batch": int(training["sweeps_per_gradient_batch"]),
        "gradient_accumulation_batches": int(
            training["gradient_accumulation_batches"]
        ),
        "target_samples_per_batch": int(training["target_samples_per_batch"]),
    }
    rounds = []
    for round_index in range(1, protocol.formal_rounds + 1):
        initial = _initial_states(protocol, bundle, round_index, walkers)
        initial_hash = sha256_bytes(
            np.ascontiguousarray(initial).tobytes(order="C")
        )
        arms = {}
        for arm, stream_name, child in (
            ("neural", "neural_training", 0),
            ("linear", "linear_training", 1),
            ("unbiased", "autocorrelation", 2),
        ):
            arms[arm] = {
                "initial_state_sha256": initial_hash,
                "rng_stream_sha256": _stream_hash(
                    bundle.streams[stream_name],
                    round_index,
                    child,
                ),
                "autocorrelation_rng_stream_sha256": _stream_hash(
                    bundle.streams["autocorrelation"],
                    round_index,
                    child,
                ),
                "sampling_budget": dict(budget),
                "threads": worker_limit,
                "hardware_class": runtime["hardware_class"],
            }
        rounds.append(
            {
                "round": round_index,
                "initial_state_sha256": initial_hash,
                "arms": arms,
            }
        )
    plan_payload = {
        "rounds": rounds,
        "resources": resources,
        "autocorrelation": autocorrelation,
        "runtime": runtime,
        "formal_execution_sha256": formal_execution.get(
            "formal_execution_sha256"
        ),
    }
    return {
        "schema_version": 1,
        "stage": "N4",
        "bundle_id": bundle_id,
        "formal_seed_count": 5,
        "rounds": rounds,
        "resources": resources,
        "autocorrelation": autocorrelation,
        "runtime": runtime,
        "formal_execution_sha256": formal_execution.get(
            "formal_execution_sha256"
        ),
        "postformal_seed_extension_allowed": False,
        "failed_seed_replacement_allowed": False,
        "plan_sha256": sha256_bytes(canonical_json_bytes(plan_payload)),
    }


def classify_formal_root(
    root: str | Path,
    protocol: Issue28Protocol,
) -> dict[str, Any]:
    base = Path(root)
    expected = [bundle.bundle_id for bundle in protocol.formal_bundles]
    present = sorted(
        path.name
        for path in base.iterdir()
        if path.is_dir() and (path / "manifest.json").is_file()
    ) if base.is_dir() else []
    missing = sorted(set(expected) - set(present))
    extra = sorted(set(present) - set(expected))
    if missing or extra:
        return {
            "classification": "PROTOCOL_FAILURE",
            "reason": "FORMAL_BUNDLE_SET_MISMATCH",
            "missing_bundles": missing,
            "extra_bundles": extra,
            "replacement_seed_allowed": False,
            "bundles": [],
            "unidentifiable_bundles": [],
        }

    records = []
    unidentifiable = []
    for bundle_id in expected:
        bundle_root = base / bundle_id
        manifest = read_verified_stage_manifest(
            bundle_root / "manifest.json",
            protocol,
            expected_stage="N4",
        )
        if manifest.get("bundle_id") != bundle_id or int(manifest.get("round", 0)) != 5:
            raise ValueError(f"formal bundle manifest identity mismatch: {bundle_id}")
        result = json.loads(
            (bundle_root / "bundle_result.json").read_text(encoding="ascii")
        )
        if (
            result.get("bundle_id") != bundle_id
            or int(result.get("rounds_completed", 0)) != 5
            or result.get("replacement_seed_allowed") is not False
            or result.get("arms") != ["neural", "linear", "unbiased"]
        ):
            raise ValueError(f"formal bundle result contract mismatch: {bundle_id}")
        if result.get("objective_classification") == "UNIDENTIFIABLE_OVERLAP":
            unidentifiable.append(bundle_id)
        records.append(result)
    classifications = [str(item["classification"]) for item in records]
    if "CORRECTNESS_FAILURE" in classifications:
        classification = "CORRECTNESS_FAILURE"
        reason = "FORMAL_CORRECTNESS_FAILURE"
    elif "PROTOCOL_FAILURE" in classifications:
        classification = "PROTOCOL_FAILURE"
        reason = "FORMAL_PROTOCOL_FAILURE"
    elif unidentifiable or "SCIENTIFIC_NEGATIVE" in classifications:
        classification = "SCIENTIFIC_NEGATIVE"
        reason = "FORMAL_SCIENTIFIC_GATES_NOT_MET"
    else:
        classification = "EASY_GOAL_SUCCESS"
        reason = "FIVE_SEEDS_FIVE_ROUNDS_COMPLETE"
    return {
        "classification": classification,
        "reason": reason,
        "missing_bundles": [],
        "extra_bundles": [],
        "replacement_seed_allowed": False,
        "bundles": records,
        "unidentifiable_bundles": unidentifiable,
    }


def run_formal_bundle(
    protocol: Issue28Protocol,
    bundle_id: str,
    output: str | Path,
    backend: str,
    resume: bool,
    *,
    formal_execution: Mapping[str, Any],
    dry_run: bool = False,
    allow_large_local: bool = False,
    workers: int | None = None,
) -> dict[str, Any]:
    if backend not in ("local", "slurm"):
        raise ValueError(f"unknown N4 backend: {backend}")
    if backend == "local" and not allow_large_local:
        raise ValueError("large local N4 requires allow_large_local=True")
    plan = build_formal_bundle_plan(
        protocol,
        bundle_id,
        formal_execution,
        backend=backend,
        workers=workers,
    )
    if dry_run:
        return {**plan, "dry_run": True}
    from .formal_compute import execute_formal_bundle

    return execute_formal_bundle(
        protocol,
        _formal_bundle(protocol, bundle_id),
        Path(output),
        formal_execution,
        plan,
        resume=resume,
        backend=backend,
        workers=workers,
        allow_large_local=allow_large_local,
    )
