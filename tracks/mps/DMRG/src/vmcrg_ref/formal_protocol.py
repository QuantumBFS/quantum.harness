"""Deterministic formal-protocol freeze after the N3 measured pilot."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .artifacts import (
    atomic_write_json,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from .issue28_protocol import Issue28Protocol, load_issue28_protocol
from .issue28_validation import scientific_round_gates_pass
from .issue28_workflow import (
    current_code_sha256,
    gauge_spec_sha256,
    read_verified_stage_manifest,
)
from .objective import objective_protocol_from_mapping
from .training_protocol import load_training_protocol


_ROOT = Path(__file__).resolve().parents[2]
_PILOT_CONFIG = _ROOT / "config" / "issue28_pilot_v1.json"

_FORMAL_AUTOCORRELATION = {
    "chains": 8,
    "thermal_sweeps": 1000,
    "measurements": 5000,
    "spacing_sweeps": 1,
    "maximum_lag": 1000,
    "observable": "microscopic_nn_density_times_block_nn_density",
    "estimator": "initial_positive_sequence",
}


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {str(key): _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _hash_without_self(execution: Mapping[str, Any]) -> str:
    payload = {
        key: value
        for key, value in execution.items()
        if key != "formal_execution_sha256"
    }
    return sha256_bytes(canonical_json_bytes(payload))


def _resource_request(chain_report: dict[str, Any]) -> dict[str, Any]:
    rounds = list(chain_report.get("rounds", ()))
    if len(rounds) != 5:
        raise ValueError("N3 pilot report must contain exactly five rounds")
    elapsed = [float(item["resources"]["elapsed_seconds"]) for item in rounds]
    peak_kib = max(
        int(item["resources"].get("peak_rss_kib", 0)) for item in rounds
    )
    threads = max(int(item["resources"].get("threads", 1)) for item in rounds)
    if min(elapsed) <= 0.0 or peak_kib <= 0 or threads <= 0:
        raise ValueError("N3 pilot resource measurements are incomplete")
    output_bytes = int(chain_report["resources"].get("output_bytes", 0))
    measured = dict(chain_report.get("resources", {}))
    backend = str(measured.get("backend", "slurm"))
    if backend not in ("local", "slurm"):
        raise ValueError("N3 pilot backend is not recognized")
    if backend == "local":
        execution_policy = measured.get("execution_policy")
        if execution_policy != "LOCAL_COMPUTE_DEVIATION":
            raise ValueError("local N3 pilot is missing the compute deviation marker")
        workers = int(measured.get("workers_per_bundle", threads))
        maximum_parallel = int(measured.get("max_parallel_bundles", 0))
        host = measured.get("host")
        if workers <= 0 or workers > 8 or maximum_parallel not in (1, 2):
            raise ValueError("local N3 worker or concurrency provenance is invalid")
        if not isinstance(host, dict) or not str(host.get("node", "")):
            raise ValueError("local N3 host provenance is missing")
        return {
            "wall_seconds_per_round": max(60, int(math.ceil(max(elapsed) * 1.5))),
            "memory_mib": max(512, int(math.ceil(peak_kib / 1024.0 * 1.5))),
            "cpus_per_task": workers,
            "workers_per_bundle": workers,
            "max_parallel_bundles": maximum_parallel,
            "estimated_output_mib_per_bundle": max(
                1,
                int(math.ceil(output_bytes / (1024.0 * 1024.0) * 1.25)),
            ),
            "hardware_class": "matched_local_host",
            "execution_policy": "LOCAL_COMPUTE_DEVIATION",
            "backend": "local",
            "host": host,
            "resource_margin": 1.5,
            "partition": None,
            "partition_freeze_rule": "host_provenance_frozen_after_local_preflight",
        }
    return {
        "wall_seconds_per_round": max(60, int(math.ceil(max(elapsed) * 1.5))),
        "memory_mib": max(512, int(math.ceil(peak_kib / 1024.0 * 1.5))),
        "cpus_per_task": threads,
        "workers_per_bundle": threads,
        "max_parallel_bundles": 1,
        "estimated_output_mib_per_bundle": max(
            1,
            int(math.ceil(output_bytes / (1024.0 * 1024.0) * 1.25)),
        ),
        "hardware_class": "matched_slurm_partition",
        "execution_policy": "SLURM",
        "backend": "slurm",
        "resource_margin": 1.5,
        "partition": None,
        "partition_freeze_rule": "ratify_after_queue_probe_before_submission",
    }


def _formal_objective(value: dict[str, Any]) -> dict[str, Any]:
    ladder = [float(item) for item in value["lambda_ladder"]]
    return {
        "estimator": value["estimator"],
        "neural_lambda_ladder": ladder,
        "linear_lambda_ladder": ladder,
        "chains_per_bridge": int(value["chains_per_bridge"]),
        "thermal_sweeps": int(value["thermal_sweeps"]),
        "measurements": int(value["measurements"]),
        "spacing_sweeps": int(value["spacing_sweeps"]),
        "root_tolerance": float(value["root_tolerance"]),
        "minimum_bar_overlap": float(value["minimum_bar_overlap"]),
        "minimum_kish_ess_fraction": float(value["minimum_kish_ess_fraction"]),
        "maximum_closure_z": float(value["maximum_closure_z"]),
        "jackknife_unit": value["jackknife_unit"],
        "common_zero_bias_anchor": True,
        "independent_nonzero_streams": True,
        "unidentifiable_classification": value["unidentifiable_classification"],
        "bootstrap_hierarchy": list(value["bootstrap_hierarchy"]),
    }


def _round_scientific_gates(record: Mapping[str, Any]) -> Mapping[str, Any]:
    direct = record.get("scientific_gates")
    if isinstance(direct, Mapping):
        return direct
    manifest = record.get("manifest")
    if isinstance(manifest, Mapping):
        nested = manifest.get("scientific_gates")
        if isinstance(nested, Mapping):
            return nested
    raise ValueError("N3 pilot round scientific gates are missing")


def freeze_formal_protocol(
    umbrella: str | Path,
    pilot_manifest: str | Path,
    output: str | Path,
    *,
    pilot_config_path: str | Path = _PILOT_CONFIG,
) -> dict[str, Any]:
    destination = Path(output)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite formal protocol: {destination}")
    umbrella_path = Path(umbrella)
    protocol = load_issue28_protocol(umbrella_path)
    pilot_path = Path(pilot_manifest)
    verified = read_verified_stage_manifest(
        pilot_path,
        protocol,
        expected_stage="N3",
        expected_code_sha256=current_code_sha256(),
    )
    if (
        verified["classification"] != "EASY_GOAL_SUCCESS"
        or verified.get("scope") != "N3_STAGE_ONLY"
        or int(verified.get("round", 0)) != protocol.formal_rounds
        or verified.get("scientific_gates", {}).get("round_science") != "PASS"
    ):
        raise ValueError("passing five-round N3 pilot is required before formal freeze")
    if verified.get("bundle_id") in {
        bundle.bundle_id for bundle in protocol.formal_bundles
    }:
        raise ValueError("N3 pilot must not consume a formal seed bundle")
    chain_path = pilot_path.parent / "chain_report.json"
    chain_report = json.loads(chain_path.read_text(encoding="ascii"))
    if (
        chain_report.get("preset") != "pilot"
        or int(chain_report.get("requested_rounds", 0)) != protocol.formal_rounds
        or chain_report.get("classification") != "EASY_GOAL_SUCCESS"
        or chain_report.get("all_round_scientific_gates_pass") is not True
        or int(chain_report.get("rounds_passing_scientific_gates", 0))
        != protocol.formal_rounds
    ):
        raise ValueError("N3 pilot chain report is not freeze-eligible")
    rounds = list(chain_report.get("rounds", ()))
    if len(rounds) != protocol.formal_rounds:
        raise ValueError("N3 pilot chain report must contain five rounds")
    for expected_round, round_record in enumerate(rounds, start=1):
        if int(round_record.get("round", 0)) != expected_round:
            raise ValueError("N3 pilot round sequence is not contiguous")
        if not scientific_round_gates_pass(_round_scientific_gates(round_record)):
            raise ValueError(
                f"N3 pilot round {expected_round} scientific gates did not pass"
            )
    if chain_report.get("postformal_seed_extension_allowed") is not False:
        raise ValueError("N3 pilot changed the fixed-five-seed rule")
    power = dict(chain_report["power"])
    if (
        int(power.get("formal_seed_count", 0)) != 5
        or power.get("postformal_seed_extension_allowed") is not False
    ):
        raise ValueError("N3 pilot power record changed the formal seed count")

    pilot_config = Path(pilot_config_path)
    pilot_value = json.loads(pilot_config.read_text(encoding="ascii"))
    training = dict(pilot_value["training"])
    load_training_protocol(training)
    formal_objective = _formal_objective(dict(pilot_value["objective"]))
    objective_protocol_from_mapping(
        {
            **formal_objective,
            "lambda_ladder": formal_objective["neural_lambda_ladder"],
        },
        site_count=(protocol.physical.length // protocol.physical.block_size) ** 2,
    )
    umbrella_value = json.loads(umbrella_path.read_text(encoding="ascii"))
    pilot_hash = sha256_file(pilot_path)
    execution = {
        "schema_version": 1,
        "locked": True,
        "formal_seed_count": 5,
        "formal_rounds": protocol.formal_rounds,
        "umbrella_sha256": sha256_file(umbrella_path),
        "pilot_manifest_sha256": pilot_hash,
        "pilot_provenance": {
            "pilot_manifest_sha256": pilot_hash,
            "chain_report_sha256": sha256_file(chain_path),
            "pilot_config_sha256": sha256_file(pilot_config),
            "bundle_id": verified["bundle_id"],
        },
        "code_sha256": current_code_sha256(),
        "operator_basis_sha256": protocol.operator_basis_sha256,
        "gauge_spec_sha256": gauge_spec_sha256(protocol),
        "training": training,
        "objective": formal_objective,
        "autocorrelation": dict(_FORMAL_AUTOCORRELATION),
        "resources": _resource_request(chain_report),
        "power": power,
        "postformal_seed_extension_allowed": False,
        "failed_seed_replacement_allowed": False,
        "threshold_change_after_first_formal_output_allowed": False,
        "valid_negative_outcome": (
            "direction_correct_but_confidence_interval_misses_frozen_gate"
        ),
    }
    execution["formal_execution_sha256"] = _hash_without_self(execution)
    value = {**umbrella_value, "formal_execution": execution}
    atomic_write_json(destination, value)
    load_formal_execution_protocol(destination)
    return value


def load_formal_execution_protocol(
    path: str | Path,
) -> tuple[Issue28Protocol, Mapping[str, Any]]:
    source = Path(path)
    protocol = load_issue28_protocol(source)
    value = json.loads(source.read_text(encoding="ascii"))
    execution = value.get("formal_execution")
    if not isinstance(execution, dict) or execution.get("locked") is not True:
        raise ValueError("formal execution protocol is missing or unlocked")
    pilot_hash = execution.get("pilot_manifest_sha256")
    provenance = execution.get("pilot_provenance")
    if (
        not isinstance(provenance, dict)
        or pilot_hash != provenance.get("pilot_manifest_sha256")
    ):
        raise ValueError("formal pilot manifest hash mismatch")
    if not isinstance(pilot_hash, str) or len(pilot_hash) != 64:
        raise ValueError("formal pilot manifest hash is invalid")
    if execution.get("formal_execution_sha256") != _hash_without_self(execution):
        raise ValueError("formal execution payload hash mismatch")
    umbrella_path = _ROOT / "config" / "issue28_easy_v1.json"
    if execution.get("umbrella_sha256") != sha256_file(umbrella_path):
        raise ValueError("formal umbrella protocol hash mismatch")
    if execution.get("code_sha256") != current_code_sha256():
        raise ValueError("formal protocol code hash mismatch")
    if execution.get("operator_basis_sha256") != protocol.operator_basis_sha256:
        raise ValueError("formal protocol operator basis hash mismatch")
    if execution.get("gauge_spec_sha256") != gauge_spec_sha256(protocol):
        raise ValueError("formal protocol gauge specification hash mismatch")
    if (
        int(execution.get("formal_seed_count", 0)) != 5
        or int(execution.get("formal_rounds", 0)) < 5
        or len(protocol.formal_bundles) != 5
    ):
        raise ValueError("formal protocol must retain five seeds and five rounds")
    if (
        execution.get("postformal_seed_extension_allowed") is not False
        or execution.get("failed_seed_replacement_allowed") is not False
        or execution.get("threshold_change_after_first_formal_output_allowed")
        is not False
    ):
        raise ValueError("formal protocol mutation policy changed")
    load_training_protocol(dict(execution["training"]))
    objective = dict(execution["objective"])
    if objective.get("neural_lambda_ladder") != objective.get("linear_lambda_ladder"):
        raise ValueError("formal neural and linear BAR ladders must remain matched")
    objective_protocol_from_mapping(
        {**objective, "lambda_ladder": objective["neural_lambda_ladder"]},
        site_count=(protocol.physical.length // protocol.physical.block_size) ** 2,
    )
    if execution.get("autocorrelation") != _FORMAL_AUTOCORRELATION:
        raise ValueError("formal autocorrelation protocol changed")
    resources = execution.get("resources")
    if not isinstance(resources, dict) or any(
        int(resources.get(key, 0)) <= 0
        for key in ("wall_seconds_per_round", "memory_mib", "cpus_per_task")
    ):
        raise ValueError("formal resource request is invalid")
    backend = resources.get("backend", "slurm")
    if backend not in ("local", "slurm"):
        raise ValueError("formal resource backend is invalid")
    if backend == "local":
        if resources.get("execution_policy") != "LOCAL_COMPUTE_DEVIATION":
            raise ValueError("formal local execution marker changed")
        workers = int(resources.get("workers_per_bundle", 0))
        parallel = int(resources.get("max_parallel_bundles", 0))
        host = resources.get("host")
        if not 1 <= workers <= 8 or parallel not in (1, 2):
            raise ValueError("formal local worker/concurrency request is invalid")
        if not isinstance(host, dict) or not str(host.get("node", "")):
            raise ValueError("formal local host provenance is invalid")
    return protocol, _deep_freeze(execution)
