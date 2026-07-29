"""Command-line entry point for Route A occupation-autoregressive training."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import platform
import socket
import tempfile
import time
from numbers import Integral
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from benchmark_v0.lll_coulomb import (
    antisymmetrized_pair_matrix,
    coulomb_integrals,
)
from scalable_v1.audit import freeze_manifest, sha256_file
from scalable_v1.protocol import ProtocolConfig, load_protocol
from scalable_v1.resources import peak_rss_bytes
from scalable_v1.routes.occupation_autoregressive.adapter import OccupationState
from scalable_v1.routes.occupation_autoregressive.constraints import FeasibilityTable
from scalable_v1.routes.occupation_autoregressive.model import AutoregressiveNQS
from scalable_v1.routes.occupation_autoregressive.operators import (
    PreparedPairOperator,
)
from scalable_v1.routes.occupation_autoregressive.train import (
    FeatureStateError,
    ReducedTrainingConfig,
    TrainingArtifacts,
    run_reduced_training,
)
from scalable_v1.routes.occupation_autoregressive.tower import LadderTower


COMPARISON_SHA = "5aa9219f4cd24bc2274f0514b621c2f9b47cead7"
PROTOCOL_SHA256 = (
    "2435cd2e72ffae88117ee194f45b15451c8653dafa755b732005b6a199251d38"
)
A03_SMOKE_UPDATES = 16
A03_SMOKE_SEED = 848
N8_DERIVED_ADAPTER_BATCH_SIZE = 16
ROUTE = "occupation_autoregressive"
ATTEMPT = "s02a-a05"
SOLUTION_ROOT = Path(__file__).resolve().parent


def _route_source_files() -> list[Path]:
    package = (
        SOLUTION_ROOT
        / "scalable_v1"
        / "routes"
        / "occupation_autoregressive"
    )
    return [Path(__file__).resolve(), *sorted(package.glob("*.py"))]


def _terminal_npz(path: Path, label: str) -> dict[str, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            if len(archive.files) != len(set(archive.files)):
                raise ValueError(f"{label} contains duplicate fields")
            return {
                name: np.asarray(archive[name]).copy()
                for name in archive.files
            }
    except (OSError, ValueError) as error:
        raise ValueError(f"invalid {label} NPZ artifact") from error


def _terminal_scalar(
    archive: dict[str, np.ndarray],
    *,
    label: str,
    field: str,
    kind: str,
) -> int | str:
    if field not in archive:
        raise ValueError(f"{label} {field} is missing")
    array = np.asarray(archive[field])
    if array.shape != ():
        raise ValueError(f"{label} {field} must be a scalar")
    value = array.item()
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f"{label} {field} must be a finite integer scalar")
        return int(value)
    if kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"{label} {field} must be a string scalar")
        return value
    raise AssertionError(f"unsupported terminal scalar kind: {kind}")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate training log JSON key: {key}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite training log JSON constant: {value}")


def _terminal_training_records(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise ValueError("invalid training log artifact") from error
    if not lines or any(not line.strip() for line in lines):
        raise ValueError("training log must contain non-empty JSONL records")
    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            record = json.loads(
                line,
                object_pairs_hook=_unique_json_object,
                parse_constant=_reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("invalid training log JSONL") from error
        if not isinstance(record, dict):
            raise ValueError("training log records must be JSON objects")
        records.append(record)
    return records


def _validate_terminal_training_artifacts(
    *,
    artifacts: TrainingArtifacts,
    observed: dict[str, Path],
    final_update: int,
    training_seed: int,
    protocol_sha256: str,
) -> None:
    wrapper_hashes = (
        ("checkpoint", observed["checkpoint"], artifacts.checkpoint_sha256),
        (
            "optimizer state",
            observed["optimizer_state"],
            artifacts.optimizer_state_sha256,
        ),
        ("training log", observed["training_log"], artifacts.training_log_sha256),
    )
    for label, path, expected_hash in wrapper_hashes:
        if not path.is_file():
            raise ValueError(f"{label} artifact is missing")
        if sha256_file(path) != expected_hash:
            raise ValueError(f"{label} SHA-256 mismatch")

    checkpoint = _terminal_npz(observed["checkpoint"], "checkpoint")
    checkpoint_expected = {
        "selected_update": ("integer", final_update),
        "completed_update": ("integer", final_update),
        "selection_rule": ("string", "final_update"),
        "training_seed": ("integer", training_seed),
        "protocol_sha256": ("string", protocol_sha256),
    }
    for field, (kind, expected) in checkpoint_expected.items():
        value = _terminal_scalar(
            checkpoint,
            label="checkpoint",
            field=field,
            kind=kind,
        )
        if value != expected:
            raise ValueError(f"checkpoint {field} mismatch")

    optimizer = _terminal_npz(observed["optimizer_state"], "optimizer")
    optimizer_expected = {
        "update": ("integer", final_update),
        "training_seed": ("integer", training_seed),
        "protocol_sha256": ("string", protocol_sha256),
    }
    for field, (kind, expected) in optimizer_expected.items():
        value = _terminal_scalar(
            optimizer,
            label="optimizer",
            field=field,
            kind=kind,
        )
        if value != expected:
            raise ValueError(f"optimizer {field} mismatch")

    records = _terminal_training_records(observed["training_log"])
    selected = [record for record in records if record.get("selected") is True]
    if len(selected) != 1 or selected[0] is not records[-1]:
        raise ValueError("training log selected final record mismatch")
    final_record = selected[0]
    update = final_record.get("update")
    if isinstance(update, bool) or not isinstance(update, int) or update != final_update:
        raise ValueError("training log final update mismatch")
    record_seed = final_record.get("training_seed")
    if (
        isinstance(record_seed, bool)
        or not isinstance(record_seed, int)
        or record_seed != training_seed
    ):
        raise ValueError("training log training_seed mismatch")
    if final_record.get("selection_rule") != "final_update":
        raise ValueError("training log selection_rule mismatch")


def freeze_training_run(
    *,
    run_dir: Path,
    artifacts: TrainingArtifacts,
    protocol: ProtocolConfig,
    training_seed: int,
) -> Path:
    """Freeze only a real final-update training artifact set."""

    if not isinstance(artifacts, TrainingArtifacts):
        raise TypeError("artifacts must be TrainingArtifacts")
    final_update = int(protocol.training["optimizer_updates"])
    if (
        isinstance(artifacts.selected_update, bool)
        or not isinstance(artifacts.selected_update, Integral)
        or int(artifacts.selected_update) != final_update
    ):
        raise ValueError("only the frozen final update may receive a manifest")
    if (
        isinstance(training_seed, bool)
        or not isinstance(training_seed, Integral)
        or int(training_seed) not in protocol.training["seeds"]
    ):
        raise ValueError("training_seed must be frozen by the protocol")
    training_seed = int(training_seed)
    output_dir = Path(run_dir).resolve()
    expected = {
        "checkpoint": output_dir / "checkpoint.npz",
        "optimizer_state": output_dir / "optimizer-state.npz",
        "training_log": output_dir / "training.jsonl",
    }
    observed = {
        "checkpoint": Path(artifacts.checkpoint).resolve(),
        "optimizer_state": Path(artifacts.optimizer_state).resolve(),
        "training_log": Path(artifacts.training_log).resolve(),
    }
    if observed != expected:
        raise ValueError("training artifact paths do not match the frozen names")
    _validate_terminal_training_artifacts(
        artifacts=artifacts,
        observed=observed,
        final_update=final_update,
        training_seed=training_seed,
        protocol_sha256=protocol.sha256,
    )
    return freeze_manifest(
        run_dir=output_dir,
        project_root=SOLUTION_ROOT,
        route=ROUTE,
        attempt=ATTEMPT,
        protocol=protocol,
        selected_update=final_update,
        training_seed=training_seed,
        source_files=_route_source_files(),
        artifact_files=observed,
    )


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        descriptor = -1
        with handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _finite_counts(values: np.ndarray) -> dict[str, int]:
    array = np.asarray(values)
    if np.iscomplexobj(array):
        components = np.concatenate((array.real.reshape(-1), array.imag.reshape(-1)))
    else:
        components = np.asarray(array, dtype=np.float64).reshape(-1)
    return {
        "finite": int(np.count_nonzero(np.isfinite(components))),
        "nan": int(np.count_nonzero(np.isnan(components))),
        "inf": int(np.count_nonzero(np.isinf(components))),
    }


def _record_stage(
    stages: dict[str, list[dict[str, float | int]]],
    name: str,
    operation: Callable[[], Any],
) -> Any:
    started = time.perf_counter()
    value = operation()
    elapsed = time.perf_counter() - started
    stages.setdefault(name, []).append(
        {
            "wall_seconds": elapsed,
            "peak_rss_bytes": peak_rss_bytes(),
        }
    )
    return value


def _smoke_size(
    *,
    n_electrons: int,
    two_q: int,
    seed: int,
    batch_size: int,
    warmups: int,
    repetitions: int,
    protocol: ProtocolConfig,
) -> dict[str, Any]:
    stages: dict[str, list[dict[str, float | int]]] = {}
    capacity = protocol.capacity["routes"][ROUTE]
    table = _record_stage(
        stages,
        "support_dynamic_program",
        lambda: FeasibilityTable.build(
            n_electrons=n_electrons,
            two_q=two_q,
            target_m2=0,
        ),
    )
    model = _record_stage(
        stages,
        "model_initialization",
        lambda: AutoregressiveNQS.initialize(
            n_electrons=n_electrons,
            two_q=two_q,
            target_m2=0,
            width=capacity["hidden_width"],
            layers=capacity["hidden_layers"],
            seed=seed,
            max_trainable_parameters=protocol.capacity["max_trainable_parameters"],
        ),
    )
    operator = _record_stage(
        stages,
        "sparse_operator_preparation",
        lambda: _prepared_operator(two_q),
    )
    tower = _record_stage(
        stages,
        "tower_construction",
        lambda: LadderTower.from_m0(
            logpsi=lambda state: model.logpsi(state, "excited"),
            log_score=lambda state: model.log_derivative(state, "excited"),
            n_electrons=n_electrons,
            two_q=two_q,
            l=2,
        ),
    )
    ground = OccupationState(
        label="n8_smoke_ground",
        l=0,
        m=0,
        model=model,
        operator=operator,
        burn_in_steps=0,
        direct_sector="ground",
    )
    excited_m0 = OccupationState(
        label="n8_smoke_tower_m0",
        l=2,
        m=0,
        model=model,
        operator=operator,
        burn_in_steps=0,
        direct_sector="excited",
    )
    excited_m1 = OccupationState(
        label="n8_smoke_tower_m1",
        l=2,
        m=1,
        model=model,
        operator=operator,
        burn_in_steps=2,
        direct_sector=None,
        tower=tower,
        component=tower[1],
    )
    counters = {"finite": 0, "nan": 0, "inf": 0}
    measured_samples = 0

    def workload(repetition: int, *, record: bool) -> None:
        nonlocal measured_samples
        active_stages = stages if record else {}
        repetition_seed = seed + 10_000 * n_electrons + repetition
        ground_batch = _record_stage(
            active_stages,
            "model_sample",
            lambda: ground.sample(batch_size, repetition_seed),
        )
        log_values = _record_stage(
            active_stages,
            "adapter_logpsi_batch",
            lambda: ground.logpsi(ground_batch.configs),
        )
        energy_values = _record_stage(
            active_stages,
            "sparse_local_energy_batch",
            lambda: ground.local_energy(ground_batch.configs),
        )
        l2_values = _record_stage(
            active_stages,
            "sparse_local_l2_batch",
            lambda: ground.local_l2(ground_batch.configs),
        )
        excited_batch = _record_stage(
            active_stages,
            "tower_m0_sample",
            lambda: excited_m0.sample(batch_size, repetition_seed + 1),
        )
        tower_values = _record_stage(
            active_stages,
            "tower_adapter_logpsi_batch",
            lambda: excited_m0.logpsi(excited_batch.configs),
        )
        derived_batch = _record_stage(
            active_stages,
            "tower_m1_sparse_sample",
            lambda: excited_m1.sample(
                N8_DERIVED_ADAPTER_BATCH_SIZE,
                repetition_seed + 2,
            ),
        )
        derived_values = _record_stage(
            active_stages,
            "tower_m1_logpsi_batch",
            lambda: excited_m1.logpsi(derived_batch.configs),
        )
        if record:
            measured_samples += 2 * batch_size + N8_DERIVED_ADAPTER_BATCH_SIZE
            for values in (log_values, energy_values, l2_values, tower_values, derived_values):
                observed = _finite_counts(values)
                for key in counters:
                    counters[key] += observed[key]

    for warmup in range(warmups):
        workload(warmup, record=False)
    measured_totals: list[float] = []
    for repetition in range(repetitions):
        started = time.perf_counter()
        workload(warmups + repetition, record=True)
        measured_totals.append(time.perf_counter() - started)
    measured_peaks = [
        int(record["peak_rss_bytes"])
        for name, records in stages.items()
        if name not in {
            "support_dynamic_program",
            "model_initialization",
            "sparse_operator_preparation",
            "tower_construction",
        }
        for record in records
    ]
    return {
        "n_electrons": n_electrons,
        "two_q": two_q,
        "support_count": int(table.counts[(0, n_electrons, 0)]),
        "parameter_count": model.parameter_count,
        "tower_components": list(tower),
        "batch_size": batch_size,
        "warmup_repetitions": warmups,
        "measured_repetitions": repetitions,
        "measured_total_seconds": measured_totals,
        "measured_peak_rss_bytes": max(measured_peaks),
        "measured_sample_count": measured_samples,
        "finite_counters": counters,
        "stages": stages,
    }


def _prepared_operator(two_q: int) -> PreparedPairOperator:
    integrals = coulomb_integrals(two_q)
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    return PreparedPairOperator.build(pairs, pair_matrix, two_q)


def _run_n8_smoke(*, run_dir: Path, protocol: ProtocolConfig) -> Path:
    smoke = protocol.smoke_n8
    output = Path(run_dir).resolve()
    result_path = output / "n8-smoke.json"
    if result_path.exists():
        raise FileExistsError("run directory already contains n8-smoke.json")
    output.mkdir(parents=True, exist_ok=True)
    n6 = _smoke_size(
        n_electrons=protocol.physics["n_electrons"],
        two_q=protocol.physics["two_q"],
        seed=smoke["seed"],
        batch_size=smoke["batch_size"],
        warmups=smoke["warmup_repetitions"],
        repetitions=smoke["measured_repetitions"],
        protocol=protocol,
    )
    n8 = _smoke_size(
        n_electrons=smoke["n_electrons"],
        two_q=smoke["two_q"],
        seed=smoke["seed"],
        batch_size=smoke["batch_size"],
        warmups=smoke["warmup_repetitions"],
        repetitions=smoke["measured_repetitions"],
        protocol=protocol,
    )
    n6_time = float(np.median(n6["measured_total_seconds"]))
    n8_time = float(np.median(n8["measured_total_seconds"]))
    time_ratio = n8_time / n6_time
    memory_ratio = n8["measured_peak_rss_bytes"] / n6["measured_peak_rss_bytes"]
    nan_count = n6["finite_counters"]["nan"] + n8["finite_counters"]["nan"]
    inf_count = n6["finite_counters"]["inf"] + n8["finite_counters"]["inf"]
    complete = bool(
        math.isfinite(time_ratio)
        and time_ratio > 0.0
        and math.isfinite(memory_ratio)
        and memory_ratio > 0.0
        and nan_count == 0
        and inf_count == 0
    )
    payload = {
        "schema": "bots848-occupation-n8-smoke-v1",
        "status": "ok" if complete else "failed",
        "optimizer_updates": 0,
        "seed": smoke["seed"],
        "protocol_sha256": protocol.sha256,
        "device_environment_fingerprint": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "executable": os.path.realpath(os.sys.executable),
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "slurm_partition": os.environ.get("SLURM_JOB_PARTITION"),
            "slurm_node": os.environ.get("SLURMD_NODENAME"),
        },
        "n6": n6,
        "n8": n8,
        "n8_to_n6_time_ratio": time_ratio,
        "n8_to_n6_memory_ratio": memory_ratio,
        "finite_counters": {
            "nan": nan_count,
            "inf": inf_count,
            "finite": n6["finite_counters"]["finite"]
            + n8["finite_counters"]["finite"],
        },
        "sample_counts": {
            "n6_measured": n6["measured_sample_count"],
            "n8_measured": n8["measured_sample_count"],
        },
    }
    _atomic_json(result_path, payload)
    return result_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train the Route A occupation-autoregressive candidate",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--smoke-updates", type=int)
    modes.add_argument("--n8-smoke", action="store_true")
    parser.add_argument("--training-seed", type=int, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.n8_smoke:
        if arguments.training_seed != 4848:
            raise FeatureStateError("N=8 smoke A05.1 is frozen to training seed 4848")
        protocol = load_protocol()
        if protocol.sha256 != PROTOCOL_SHA256:
            raise ValueError("scalable-v1 protocol SHA-256 mismatch")
        result_path = _run_n8_smoke(run_dir=arguments.run_dir, protocol=protocol)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "mode": "a05.1-n8-no-training-smoke",
                    "optimizer_updates": 0,
                    "result_path": str(result_path),
                    "result_sha256": sha256_file(result_path),
                    "protocol_sha256": protocol.sha256,
                },
                sort_keys=True,
                allow_nan=False,
            ),
            flush=True,
        )
        return 0
    if arguments.smoke_updates is None:
        raise FeatureStateError(
            "full tower-aware training remains reserved for A05.2 three-seed freeze"
        )
    if arguments.smoke_updates != A03_SMOKE_UPDATES:
        raise ValueError("A03 reduced smoke must use exactly 16 updates")
    if arguments.training_seed != A03_SMOKE_SEED:
        raise ValueError("A03 reduced smoke is frozen to training seed 848")

    protocol = load_protocol()
    if protocol.sha256 != PROTOCOL_SHA256:
        raise ValueError("scalable-v1 protocol SHA-256 mismatch")
    physics = protocol.physics
    training = protocol.training
    capacity = protocol.capacity["routes"]["occupation_autoregressive"]
    if training["batch_size_per_sector"] != 512:
        raise ValueError("A03 reduced smoke requires 512 samples per M=0 sector")

    model = AutoregressiveNQS.initialize(
        n_electrons=physics["n_electrons"],
        two_q=physics["two_q"],
        target_m2=0,
        width=capacity["hidden_width"],
        layers=capacity["hidden_layers"],
        seed=arguments.training_seed,
        max_trainable_parameters=protocol.capacity["max_trainable_parameters"],
    )
    integrals = coulomb_integrals(physics["two_q"])
    pairs, pair_matrix = antisymmetrized_pair_matrix(integrals)
    operator = PreparedPairOperator.build(
        pairs,
        pair_matrix,
        physics["two_q"],
    )
    config = ReducedTrainingConfig(
        training_seed=arguments.training_seed,
        updates=arguments.smoke_updates,
        batch_size_per_sector=training["batch_size_per_sector"],
        learning_rate=training["learning_rate"],
        beta1=training["beta1"],
        beta2=training["beta2"],
        epsilon=training["epsilon"],
        gradient_clip_norm=training["gradient_clip_norm"],
        checkpoint_interval=training["checkpoint_interval"],
        protocol_sha256=protocol.sha256,
        comparison_sha=COMPARISON_SHA,
    )
    artifacts = run_reduced_training(
        model=model,
        operator=operator,
        config=config,
        run_dir=arguments.run_dir,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": "a03-reduced-m0-smoke",
                "training_seed": arguments.training_seed,
                "updates": arguments.smoke_updates,
                "batch_size_per_sector": training["batch_size_per_sector"],
                "ground_sector": "M=0",
                "excited_sector": "M=0",
                "selection_rule": "final_update",
                "selected_update": artifacts.selected_update,
                "checkpoint_sha256": artifacts.checkpoint_sha256,
                "optimizer_state_sha256": artifacts.optimizer_state_sha256,
                "training_log_sha256": artifacts.training_log_sha256,
                "protocol_sha256": protocol.sha256,
                "comparison_sha": COMPARISON_SHA,
            },
            sort_keys=True,
            allow_nan=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FeatureStateError as error:
        raise SystemExit(f"feature state error: {error}") from error
