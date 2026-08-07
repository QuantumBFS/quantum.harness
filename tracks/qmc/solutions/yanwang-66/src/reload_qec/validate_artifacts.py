"""Independent artifact/timeline checks for completed experiment runs."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .analyze import verify_checksums
from .artifacts import INPUT_KEYS, LABEL_KEYS, MANIFEST_SCHEMA
from .config import SimulationRequest
from .geometry import Geometry
from .graph import MatchingGraph
from .simulate import Simulator
from .stats import paired_comparison


class ValidationError(ValueError):
    """Raised on the first concrete artifact contract violation."""


@dataclass(frozen=True)
class ValidatedRun:
    run_dir: Path
    manifest: dict[str, Any]
    request: SimulationRequest
    geometry: Geometry
    inputs: dict[str, np.ndarray]
    labels: dict[str, np.ndarray]


PILOT_NAMES = ("00-none", "01-immediate", "02-periodic-d", "03-threshold-005")
MANIFEST_KEYS = {
    "schema_version",
    "run_id",
    "status",
    "request",
    "instance",
    "decoder",
    "environment",
    "source_commit",
    "shot_range",
    "input_keys",
    "label_keys",
    "array_schema",
    "shards",
    "aggregate",
    "artifacts",
}


def _require_binary(name: str, array: np.ndarray) -> None:
    if array.dtype != np.uint8 or np.any(array > 1):
        raise ValidationError(f"{name} must be binary uint8")


def _checksum_names(run_dir: Path) -> set[str]:
    names: list[str] = []
    for line in (run_dir / "checksums.sha256").read_text(encoding="ascii").splitlines():
        _, separator, name = line.partition("  ")
        if separator != "  ":
            raise ValidationError(f"invalid checksum entry {line!r}")
        names.append(name)
    if len(names) != len(set(names)):
        raise ValidationError("checksum file contains duplicate artifact names")
    return set(names)


def _load_shards(
    run_dir: Path, manifest: dict[str, Any], request: SimulationRequest
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    input_parts = {key: [] for key in INPUT_KEYS}
    label_parts = {key: [] for key in LABEL_KEYS}
    expected_shards = math.ceil(request.shots / request.shard_size)
    shards = manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != expected_shards:
        raise ValidationError(
            f"manifest has {len(shards) if isinstance(shards, list) else 'invalid'} "
            f"shards; expected {expected_shards}"
        )
    expected_checksum_names = {"manifest.json", "aggregates.parquet", "run.log"}
    for shard_index, shard in enumerate(shards):
        expected_start = request.shot_start + shard_index * request.shard_size
        expected_stop = min(
            request.shot_start + request.shots,
            expected_start + request.shard_size,
        )
        expected_input_name = f"shots-{shard_index:05d}.npz"
        expected_label_name = f"labels-{shard_index:05d}.npz"
        expected_shard = {
            "index": shard_index,
            "shot_start": expected_start,
            "shot_stop": expected_stop,
            "inputs": expected_input_name,
            "labels": expected_label_name,
        }
        if shard != expected_shard:
            raise ValidationError(
                f"shard {shard_index} metadata differs from requested shot range"
            )
        expected_checksum_names.update({expected_input_name, expected_label_name})
        shard_shots = expected_stop - expected_start
        with np.load(run_dir / shard["inputs"], allow_pickle=False) as payload:
            if set(payload.files) != set(INPUT_KEYS):
                raise ValidationError(
                    f"input keys for shard {shard['index']} are {sorted(payload.files)}"
                )
            for key in INPUT_KEYS:
                array = np.asarray(payload[key])
                if array.ndim == 0 or array.shape[0] != shard_shots:
                    raise ValidationError(
                        f"input {key} for shard {shard_index} has {array.shape}"
                    )
                input_parts[key].append(array)
        with np.load(run_dir / shard["labels"], allow_pickle=False) as payload:
            if set(payload.files) != set(LABEL_KEYS):
                raise ValidationError(
                    f"label keys for shard {shard['index']} are {sorted(payload.files)}"
                )
            for key in LABEL_KEYS:
                array = np.asarray(payload[key])
                if array.ndim == 0 or array.shape[0] != shard_shots:
                    raise ValidationError(
                        f"label {key} for shard {shard_index} has {array.shape}"
                    )
                label_parts[key].append(array)
    if _checksum_names(run_dir) != expected_checksum_names:
        raise ValidationError(
            "checksum file does not cover exactly the immutable run files"
        )
    inputs = {key: np.concatenate(parts, axis=0) for key, parts in input_parts.items()}
    labels = {key: np.concatenate(parts, axis=0) for key, parts in label_parts.items()}
    return inputs, labels


def _validate_array_contract(run: ValidatedRun) -> None:
    shots = run.request.shots
    rounds = run.request.rounds
    n_sites = run.geometry.n_sites
    n_checks = len(run.geometry.relevant_checks)
    input_shapes = {
        "shot_id": (shots,),
        "detection_events": (shots, rounds + 1, n_checks),
        "syndrome_valid_mask": (shots, rounds, n_checks),
        "missing_mask": (shots, rounds + 1, n_sites),
        "erasure_mask": (shots, rounds, n_sites),
        "loss_mask": (shots, rounds, n_sites),
        "reload_request_mask": (shots, rounds, n_sites),
        "reload_mask": (shots, rounds + 1, n_sites),
        "reload_failure_mask": (shots, rounds + 1, n_sites),
    }
    label_shapes = {
        "shot_id": (shots,),
        "logical_observable": (shots, 1),
        "decoder_prediction": (shots, 1),
        "logical_failure": (shots,),
        "catastrophic_loss": (shots,),
        "reload_reset_fault_mask": (shots, rounds + 1, n_sites),
    }
    expected_schema: dict[str, dict[str, Any]] = {}
    for namespace, arrays, shapes in (
        ("input", run.inputs, input_shapes),
        ("label", run.labels, label_shapes),
    ):
        for key, expected_shape in shapes.items():
            array = arrays[key]
            expected_dtype = np.dtype(np.uint64 if key == "shot_id" else np.uint8)
            if array.shape != expected_shape:
                raise ValidationError(
                    f"{namespace} {key} shape {array.shape} != {expected_shape}"
                )
            if array.dtype != expected_dtype:
                raise ValidationError(
                    f"{namespace} {key} dtype {array.dtype} != {expected_dtype}"
                )
            expected_schema[key] = {
                "dtype": str(expected_dtype),
                "shape_per_shot": list(expected_shape[1:]),
            }
    if run.manifest.get("array_schema") != dict(sorted(expected_schema.items())):
        raise ValidationError("manifest array schema differs from loaded arrays")
    for key, value in {**run.inputs, **run.labels}.items():
        if key != "shot_id":
            _require_binary(key, value)


def _expected_policy_request(
    request: SimulationRequest, round_index: int, detected: np.ndarray
) -> np.ndarray:
    count = int(np.count_nonzero(detected))
    policy = request.policy
    if policy.name == "none":
        fires = False
    elif policy.name == "immediate":
        fires = count > 0
    elif policy.name == "periodic":
        assert policy.interval is not None
        fires = count > 0 and (round_index + 1) % policy.interval == 0
    elif policy.name == "threshold":
        assert policy.fraction is not None
        fires = count >= math.ceil(policy.fraction * len(detected))
    else:
        raise ValidationError(f"unsupported policy {policy.name!r}")
    return (
        detected.astype(np.uint8)
        if fires
        else np.zeros(len(detected), dtype=np.uint8)
    )


def _validate_timeline(run: ValidatedRun, geometry: Geometry) -> None:
    request = run.request
    inputs = run.inputs
    labels = run.labels
    shots = request.shots
    rounds = request.rounds
    n_sites = geometry.n_sites
    if np.any(
        labels["reload_reset_fault_mask"] & (inputs["reload_mask"] == 0)
    ):
        raise ValidationError("reset fault appears without successful reload")

    for shot_index in range(shots):
        state = np.zeros(n_sites, dtype=np.uint8)  # 0 active, 1 detected, 2 reloading
        due = np.full(n_sites, -1, dtype=np.int64)
        for boundary in range(rounds + 1):
            success = inputs["reload_mask"][shot_index, boundary].astype(bool)
            failure = inputs["reload_failure_mask"][shot_index, boundary].astype(bool)
            if np.any(success & failure):
                raise ValidationError("reload success and failure overlap")
            due_now = due == boundary
            if not np.array_equal(success | failure, due_now):
                raise ValidationError(
                    f"shot {shot_index} boundary {boundary}: "
                    "completion schedule mismatch"
                )
            state[success] = 0
            state[failure] = 1
            due[success | failure] = -1
            expected_missing = (state != 0).astype(np.uint8)
            if not np.array_equal(
                inputs["missing_mask"][shot_index, boundary], expected_missing
            ):
                raise ValidationError(
                    f"shot {shot_index} boundary {boundary}: missing mask mismatch"
                )
            if boundary == rounds:
                break
            losses = inputs["loss_mask"][shot_index, boundary].astype(bool)
            if np.any(losses & (state != 0)):
                raise ValidationError(
                    f"shot {shot_index} round {boundary}: loss on inactive site"
                )
            expected_erasure = expected_missing | losses.astype(np.uint8)
            if not np.array_equal(
                inputs["erasure_mask"][shot_index, boundary], expected_erasure
            ):
                raise ValidationError(
                    f"shot {shot_index} round {boundary}: erasure mask mismatch"
                )
            state[losses] = 1
            detected = state == 1
            expected_request = _expected_policy_request(
                request, boundary, detected
            )
            observed_request = inputs["reload_request_mask"][shot_index, boundary]
            if not np.array_equal(observed_request, expected_request):
                raise ValidationError(
                    f"shot {shot_index} round {boundary}: policy request mismatch"
                )
            requested = observed_request.astype(bool)
            state[requested] = 2
            due[requested] = boundary + request.reload.delay_rounds + 1

    expected_validity = np.empty_like(inputs["syndrome_valid_mask"])
    for check_index, site_id in enumerate(geometry.relevant_ancilla_site_ids):
        expected_validity[:, :, check_index] = 1 - inputs["erasure_mask"][:, :, site_id]
    if not np.array_equal(inputs["syndrome_valid_mask"], expected_validity):
        raise ValidationError(
            "syndrome validity does not match relevant ancilla erasures"
        )


def _validate_manifest_contract(
    manifest: dict[str, Any], request: SimulationRequest, geometry: Geometry
) -> None:
    if set(manifest) != MANIFEST_KEYS:
        raise ValidationError("manifest top-level keys differ from the frozen contract")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValidationError("manifest schema mismatch")
    if manifest.get("status") != "completed":
        raise ValidationError("run manifest is not completed")
    if manifest.get("request") != request.as_dict():
        raise ValidationError("manifest request is not canonical")
    if manifest.get("run_id") != request.run_id:
        raise ValidationError("manifest run ID differs from request")
    if manifest.get("source_commit") != request.source_commit:
        raise ValidationError("manifest source commit differs from request")
    if manifest.get("shot_range") != [
        request.shot_start,
        request.shot_start + request.shots,
    ]:
        raise ValidationError("manifest shot range differs from request")
    if manifest.get("input_keys") != list(INPUT_KEYS):
        raise ValidationError("manifest input keys mismatch")
    if manifest.get("label_keys") != list(LABEL_KEYS):
        raise ValidationError("manifest label keys mismatch")
    if manifest.get("artifacts") != [
        "manifest.json",
        "aggregates.parquet",
        "run.log",
        "checksums.sha256",
    ]:
        raise ValidationError("manifest artifact list mismatch")
    expected_instance = {
        "instance_id": geometry.instance_id,
        "provenance": geometry.provenance,
        "site_order": [site.site_id for site in geometry.sites],
        "check_order": [check.check_id for check in geometry.relevant_checks],
    }
    if manifest.get("instance") != expected_instance:
        raise ValidationError("manifest instance identity/order mismatch")

    decoder = manifest.get("decoder")
    if not isinstance(decoder, dict) or set(decoder) != {
        "name",
        "pymatching_version",
        "data_probability",
        "measurement_probability",
        "erasure_weight",
    }:
        raise ValidationError("manifest decoder contract mismatch")
    if decoder["name"] != "mask-conditioned-pymatching":
        raise ValidationError("unexpected decoder name")
    if not isinstance(decoder["pymatching_version"], str):
        raise ValidationError("missing PyMatching version")
    expected_decoder_values = {
        "data_probability": 2.0 * request.p / 3.0,
        "measurement_probability": request.p_m,
        "erasure_weight": 0.0,
    }
    for key, expected in expected_decoder_values.items():
        if not math.isclose(float(decoder[key]), expected, rel_tol=1e-15, abs_tol=0.0):
            raise ValidationError(f"manifest decoder {key} mismatch")

    environment = manifest.get("environment")
    expected_environment_keys = {
        "mode",
        "environment_lock_sha256",
        "container_hash",
        "python",
        "platform",
        "numpy",
        "stim",
        "reload_qec",
        "slurm_job_id",
    }
    if (
        not isinstance(environment, dict)
        or set(environment) != expected_environment_keys
    ):
        raise ValidationError("manifest environment contract mismatch")
    if environment["mode"] != "locked-venv-slurm":
        raise ValidationError("run did not use the locked Slurm environment")
    if environment["environment_lock_sha256"] != request.environment_lock_sha256:
        raise ValidationError("run environment lock differs from request")
    if environment["container_hash"] is not None:
        raise ValidationError("unexpected container provenance in locked-venv run")
    if environment["slurm_job_id"] in {None, "not-under-slurm"}:
        raise ValidationError("run manifest does not identify a Slurm job")


def _wilson_interval(failures: int, shots: int) -> tuple[float, float]:
    z = 1.959963984540054
    rate = failures / shots
    denominator = 1.0 + z * z / shots
    center = (rate + z * z / (2.0 * shots)) / denominator
    half_width = (
        z
        * ((rate * (1.0 - rate) / shots + z * z / (4.0 * shots * shots)) ** 0.5)
        / denominator
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)


def _validate_aggregate(run: ValidatedRun, graph: MatchingGraph) -> None:
    frame = pd.read_parquet(run.run_dir / "aggregates.parquet")
    manifest_aggregate = run.manifest.get("aggregate")
    if not isinstance(manifest_aggregate, dict):
        raise ValidationError("manifest aggregate is not an object")
    if len(frame) != 1 or set(frame.columns) != set(manifest_aggregate):
        raise ValidationError("aggregate parquet schema/row count mismatch")
    parquet_aggregate = frame.iloc[0].to_dict()
    for key, manifest_value in manifest_aggregate.items():
        parquet_value = parquet_aggregate[key]
        if isinstance(manifest_value, float):
            if not math.isclose(
                float(parquet_value), manifest_value, rel_tol=1e-15, abs_tol=0.0
            ):
                raise ValidationError(f"manifest/parquet aggregate mismatch: {key}")
        elif parquet_value != manifest_value:
            raise ValidationError(f"manifest/parquet aggregate mismatch: {key}")

    failures = int(np.count_nonzero(run.labels["logical_failure"]))
    lower, upper = _wilson_interval(failures, run.request.shots)
    expected_values: dict[str, int | float | str] = {
        "run_id": run.request.run_id,
        "shots": run.request.shots,
        "logical_failures": failures,
        "logical_error_rate": failures / run.request.shots,
        "wilson_95_lower": lower,
        "wilson_95_upper": upper,
        "catastrophic_shots": int(
            np.count_nonzero(run.labels["catastrophic_loss"])
        ),
        "loss_events": int(np.count_nonzero(run.inputs["loss_mask"])),
        "reload_requests": int(
            np.count_nonzero(run.inputs["reload_request_mask"])
        ),
        "reload_successes": int(np.count_nonzero(run.inputs["reload_mask"])),
        "reload_failures": int(
            np.count_nonzero(run.inputs["reload_failure_mask"])
        ),
        "missing_site_boundaries": int(
            np.count_nonzero(run.inputs["missing_mask"])
        ),
    }
    compressed_bytes = sum(
        (run.run_dir / shard[key]).stat().st_size
        for shard in run.manifest["shards"]
        for key in ("inputs", "labels")
    )
    expected_values["compressed_npz_bytes"] = compressed_bytes
    expected_values["bytes_per_shot"] = compressed_bytes / run.request.shots

    offset = 0
    distinct_graphs = 0
    for shard in run.manifest["shards"]:
        shard_shots = shard["shot_stop"] - shard["shot_start"]
        condition_keys = {
            graph.condition_key(
                run.inputs["erasure_mask"][shot_index],
                run.inputs["reload_mask"][shot_index],
            )
            for shot_index in range(offset, offset + shard_shots)
        }
        distinct_graphs += len(condition_keys)
        offset += shard_shots
    expected_values["distinct_graphs_accumulated"] = distinct_graphs

    expected_keys = set(expected_values) | {"wall_seconds", "shots_per_second"}
    if set(manifest_aggregate) != expected_keys:
        raise ValidationError("aggregate fields differ from the frozen contract")
    for key, expected in expected_values.items():
        observed = manifest_aggregate[key]
        if isinstance(expected, float):
            if not math.isclose(float(observed), expected, rel_tol=1e-12, abs_tol=0.0):
                raise ValidationError(f"aggregate value mismatch: {key}")
        elif observed != expected:
            raise ValidationError(f"aggregate value mismatch: {key}")
    wall_seconds = float(manifest_aggregate["wall_seconds"])
    shots_per_second = float(manifest_aggregate["shots_per_second"])
    if not math.isfinite(wall_seconds) or wall_seconds <= 0.0:
        raise ValidationError("aggregate wall time is not positive and finite")
    if not math.isclose(
        shots_per_second,
        run.request.shots / wall_seconds,
        rel_tol=1e-12,
        abs_tol=0.0,
    ):
        raise ValidationError("aggregate throughput does not match wall time")


def _validate_exact_replay(run: ValidatedRun) -> None:
    simulator = Simulator(run.request, run.geometry)
    offset = 0
    for shard in run.manifest["shards"]:
        shot_ids = np.arange(
            shard["shot_start"], shard["shot_stop"], dtype=np.uint64
        )
        expected = simulator.simulate(shot_ids)
        shard_shots = len(shot_ids)
        observed_slice = slice(offset, offset + shard_shots)
        for namespace, keys in (
            (run.inputs, INPUT_KEYS),
            (run.labels, LABEL_KEYS),
        ):
            for key in keys:
                observed = namespace[key][observed_slice]
                replayed = getattr(expected, key)
                if not np.array_equal(observed, replayed):
                    raise ValidationError(
                        f"exact replay mismatch in shard {shard['index']}: {key}"
                    )
        offset += shard_shots
    if offset != run.request.shots:
        raise ValidationError("exact replay did not cover every requested shot")


def validate_run(run_dir: Path) -> ValidatedRun:
    verify_checksums(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="ascii"))
    request = SimulationRequest.from_dict(manifest["request"])
    geometry = Geometry.load(
        request.instance_file,
        distance=request.distance,
        rounds=request.rounds,
        basis=request.basis,
    )
    _validate_manifest_contract(manifest, request, geometry)
    inputs, labels = _load_shards(run_dir, manifest, request)
    expected_ids = np.arange(
        request.shot_start,
        request.shot_start + request.shots,
        dtype=np.uint64,
    )
    if not np.array_equal(inputs["shot_id"], expected_ids):
        raise ValidationError("input shot IDs are not the requested contiguous range")
    if not np.array_equal(labels["shot_id"], expected_ids):
        raise ValidationError("label shot IDs differ from requested range")
    run = ValidatedRun(run_dir, manifest, request, geometry, inputs, labels)
    _validate_array_contract(run)
    _validate_timeline(run, geometry)
    observable = labels["logical_observable"].reshape(-1)
    prediction = labels["decoder_prediction"].reshape(-1)
    expected_failure = np.bitwise_xor(observable, prediction)
    if not np.array_equal(expected_failure, labels["logical_failure"].reshape(-1)):
        raise ValidationError(
            "logical failure does not equal observable XOR prediction"
        )
    graph = MatchingGraph(
        geometry,
        p=request.p,
        p_m=request.p_m,
        p_reset=request.reload.reset_error_probability,
    )
    _validate_exact_replay(run)
    _validate_aggregate(run, graph)
    return run


def _paired_request_view(request: SimulationRequest) -> dict[str, Any]:
    value = request.as_dict()
    return {key: item for key, item in value.items() if key not in {"run_id", "policy"}}


def validate_pilot(pilot_root: Path, request_root: Path) -> dict[str, Any]:
    expected_requests = {
        name: SimulationRequest.load(request_root / f"{name}.json")
        for name in PILOT_NAMES
    }
    runs = {name: validate_run(pilot_root / name) for name in PILOT_NAMES}
    for name, run in runs.items():
        if run.request.as_dict() != expected_requests[name].as_dict():
            raise ValidationError(
                f"run request differs from frozen pilot request: {name}"
            )
        if run.manifest["environment"]["slurm_job_id"] != pilot_root.name:
            raise ValidationError(f"run came from the wrong Slurm pilot job: {name}")
    paired_view = _paired_request_view(runs["00-none"].request)
    for name in PILOT_NAMES[1:]:
        if _paired_request_view(runs[name].request) != paired_view:
            raise ValidationError(f"pilot request is not paired with baseline: {name}")
        if not np.array_equal(
            runs[name].inputs["shot_id"], runs["00-none"].inputs["shot_id"]
        ):
            raise ValidationError(f"pilot shot IDs are not paired: {name}")

    immediate = runs["01-immediate"]
    threshold = runs["03-threshold-005"]
    threshold_fraction = threshold.request.policy.fraction
    if threshold_fraction is None or math.ceil(
        threshold_fraction * threshold.geometry.n_sites
    ) != 1:
        raise ValidationError(
            "pilot threshold policy is not the one-loss equivalence case"
        )
    for key in INPUT_KEYS:
        if not np.array_equal(immediate.inputs[key], threshold.inputs[key]):
            raise ValidationError(f"immediate/threshold input mismatch: {key}")
    for key in LABEL_KEYS:
        if not np.array_equal(immediate.labels[key], threshold.labels[key]):
            raise ValidationError(f"immediate/threshold label mismatch: {key}")
    comparisons = {}
    baseline = runs["00-none"]
    comparison_keys = {
        "schema_version",
        "baseline_run_id",
        "candidate_run_id",
        "baseline_policy",
        "candidate_policy",
        "orientation",
        "bootstrap_resamples",
        "bootstrap_seed",
        "comparison",
        "interpretation",
    }
    for candidate in PILOT_NAMES[1:]:
        path = pilot_root / "comparisons" / f"{candidate}-vs-none.json"
        value = json.loads(path.read_text(encoding="ascii"))
        if set(value) != comparison_keys or value.get(
            "schema_version"
        ) != "q66-paired-comparison-v1":
            raise ValidationError(f"comparison schema mismatch: {candidate}")
        if value.get("baseline_run_id") != baseline.manifest["run_id"]:
            raise ValidationError(f"comparison baseline mismatch: {candidate}")
        if value.get("candidate_run_id") != runs[candidate].manifest["run_id"]:
            raise ValidationError(f"comparison candidate mismatch: {candidate}")
        if value.get("baseline_policy") != baseline.request.policy.as_dict():
            raise ValidationError(f"comparison baseline policy mismatch: {candidate}")
        if value.get("candidate_policy") != runs[candidate].request.policy.as_dict():
            raise ValidationError(f"comparison candidate policy mismatch: {candidate}")
        if value.get("orientation") != "candidate_minus_baseline":
            raise ValidationError(f"comparison orientation mismatch: {candidate}")
        if value.get("interpretation") != "pilot-descriptive-only-no-fdr-claim":
            raise ValidationError(f"comparison interpretation mismatch: {candidate}")
        bootstrap_resamples = value.get("bootstrap_resamples")
        bootstrap_seed = value.get("bootstrap_seed")
        if type(bootstrap_resamples) is not int or bootstrap_resamples < 1:
            raise ValidationError(f"invalid bootstrap count: {candidate}")
        if type(bootstrap_seed) is not int:
            raise ValidationError(f"invalid bootstrap seed: {candidate}")
        expected_comparison = paired_comparison(
            baseline.labels["logical_failure"],
            runs[candidate].labels["logical_failure"],
            bootstrap_resamples=bootstrap_resamples,
            bootstrap_seed=bootstrap_seed,
        ).as_dict()
        if value.get("comparison") != expected_comparison:
            raise ValidationError(f"paired statistics mismatch: {candidate}")
        comparisons[candidate] = value["comparison"]
    bytes_per_shot = {
        name: float(run.manifest["aggregate"]["bytes_per_shot"])
        for name, run in runs.items()
    }
    wall_seconds = {
        name: float(run.manifest["aggregate"]["wall_seconds"])
        for name, run in runs.items()
    }
    shots_per_second = {
        name: float(run.manifest["aggregate"]["shots_per_second"])
        for name, run in runs.items()
    }
    return {
        "schema_version": "q66-pilot-validation-v1",
        "status": "passed",
        "slurm_job_id": pilot_root.name,
        "runs": {name: run.manifest["run_id"] for name, run in runs.items()},
        "comparisons": comparisons,
        "exact_replay": "passed-for-every-shard-and-array",
        "compressed_bytes_per_shot": bytes_per_shot,
        "wall_seconds": wall_seconds,
        "shots_per_second": shots_per_second,
        "note": "pilot evidence only; discovery remains unauthorized",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--request-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = validate_pilot(args.pilot_root, args.request_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="ascii"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
