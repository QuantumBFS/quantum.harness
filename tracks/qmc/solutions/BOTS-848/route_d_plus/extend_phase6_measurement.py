"""Extend blind Phase 6 statistics on immutable trained checkpoints."""

from __future__ import annotations

import argparse
import builtins
import concurrent.futures
import contextlib
import datetime as dt
import hashlib
import io
import itertools
import json
import math
import multiprocessing
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np

from route_d_plus.train_dplus0 import (
    N_ELECTRONS,
    TWO_Q,
    _make_whitened_evaluator,
    ground_mother_channels,
    ground_raw_channels,
    tower_mother_channels,
    tower_raw_channels,
)
from route_d_plus.vmc import (
    block_estimate,
    coulomb_potential,
    delayed_acceptance_chain,
    metropolis_chain,
)

SCHEMA_VERSION = "challenge-15-route-d-plus-phase6-measurement-v1"
MEASUREMENT_ATTEMPT_VERSION = (
    "challenge-15-route-d-plus-phase6-measurement-attempt-v1"
)
TASK_SCHEMA_VERSION = (
    "challenge-15-route-d-plus-phase6-measurement-task-v1"
)
ATTEMPT_SCHEMA_VERSION = "challenge-15-route-d-plus-phase6-attempt-v1"
SEEDS = (848, 1848, 2848)
SECTORS = ("ground", "tower")
CHAINS = 4
SAMPLES_PER_CHAIN = 2048
MEASUREMENT_CHUNK = 128
WARMUP_STEPS = 64
PROPOSAL_SWEEPS = 2
FORBIDDEN_MODULE_PREFIXES = (
    "benchmark_v0.ed_oracle",
    "benchmark_v0.fock_ed",
    "benchmark_v0.projected_nqs",
    "benchmark_v0.nqs_benchmark",
)
FORBIDDEN_PATH_MARKERS = (
    "/ed/",
    "ed_oracle",
    "fock_ed",
    "projected_nqs",
    "nqs_benchmark",
)
MODULE_ROOT = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def validate(payload: dict[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    ).validate(payload)


def git_output(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def artifact(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


@contextlib.contextmanager
def blind_measurement_audit() -> Any:
    """Deny ED imports and file access throughout one chain measurement."""

    events: list[dict[str, str]] = []
    original_import = builtins.__import__
    original_open = builtins.open
    original_io_open = io.open

    def audited_import(
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if name.startswith(FORBIDDEN_MODULE_PREFIXES):
            events.append({"operation": "import", "target": name})
            raise RuntimeError(f"forbidden ED import during measurement: {name}")
        return original_import(name, globals, locals, fromlist, level)

    def check_path(file: Any) -> None:
        if isinstance(file, (str, os.PathLike)):
            normalized = str(Path(file).resolve()).lower()
            if any(marker in normalized for marker in FORBIDDEN_PATH_MARKERS):
                events.append({"operation": "open", "target": normalized})
                raise RuntimeError(
                    f"forbidden ED artifact access during measurement: {file}"
                )

    def audited_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        check_path(file)
        return original_open(file, *args, **kwargs)

    def audited_io_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        check_path(file)
        return original_io_open(file, *args, **kwargs)

    builtins.__import__ = audited_import
    builtins.open = audited_open
    io.open = audited_io_open
    try:
        yield events
    finally:
        builtins.__import__ = original_import
        builtins.open = original_open
        io.open = original_io_open


def coefficients(checkpoint: dict[str, Any], sector: str) -> np.ndarray:
    payload = checkpoint[f"{sector}_coefficients"]
    return np.asarray(payload["real"]) + 1.0j * np.asarray(payload["imag"])


def _fresh_start(
    *,
    evaluator: Any,
    coefficients_value: np.ndarray,
    sector: str,
    seed: int,
) -> tuple[np.ndarray, float, dict[str, float]]:
    mother = metropolis_chain(
        ground_mother_channels,
        n_particles=N_ELECTRONS,
        coefficients=np.empty(0, dtype=np.complex128),
        seed=seed,
        burn_in_sweeps=128,
        sample_sweeps=1,
        delta_max=0.35,
        global_rotation_interval=4,
    )
    configuration = mother.samples[-1]
    delta_max = float(mother.delta_max)
    tower_acceptance = 1.0
    if sector == "tower":
        tower = delayed_acceptance_chain(
            ground_mother_channels,
            tower_mother_channels,
            n_particles=N_ELECTRONS,
            coefficients=np.empty(0, dtype=np.complex128),
            seed=seed + 10_000,
            sample_steps=WARMUP_STEPS,
            proposal_sweeps=PROPOSAL_SWEEPS,
            delta_max=delta_max,
            initial_configuration=configuration,
            global_rotation_interval=4,
        )
        configuration = tower.samples[-1]
        tower_acceptance = float(tower.correction_acceptance)
    dressed = delayed_acceptance_chain(
        ground_mother_channels,
        evaluator,
        n_particles=N_ELECTRONS,
        coefficients=coefficients_value,
        seed=seed + 20_000,
        sample_steps=WARMUP_STEPS,
        proposal_sweeps=PROPOSAL_SWEEPS,
        delta_max=delta_max,
        initial_configuration=configuration,
        global_rotation_interval=4,
    )
    return (
        dressed.samples[-1],
        delta_max,
        {
            "mother_acceptance": float(mother.acceptance),
            "tower_correction_acceptance": tower_acceptance,
            "dressed_correction_acceptance": float(
                dressed.correction_acceptance
            ),
        },
    )


def measure_task(request: dict[str, Any]) -> dict[str, Any]:
    seed = int(request["seed"])
    sector = str(request["sector"])
    chain = int(request["chain"])
    architecture = request["architecture"]
    checkpoint = request["checkpoint"]
    measurement_seed = (
        7_000_000
        + 100_000 * SEEDS.index(seed)
        + 10_000 * SECTORS.index(sector)
        + chain
    )
    mean = np.asarray(architecture["centering_mean"], dtype=np.float64)
    whitening = np.asarray(architecture["whitening"], dtype=np.float64)
    raw_evaluator = (
        ground_raw_channels if sector == "ground" else tower_raw_channels
    )
    evaluator = _make_whitened_evaluator(raw_evaluator, mean, whitening)
    coefficient_vector = coefficients(checkpoint, sector)
    started = time.perf_counter()
    with blind_measurement_audit() as audit_events:
        configuration, delta_max, warmup = _fresh_start(
            evaluator=evaluator,
            coefficients_value=coefficient_vector,
            sector=sector,
            seed=measurement_seed,
        )
        energies: list[float] = []
        correction_acceptances = []
        mother_acceptances = []
        rotation_residuals = []
        chunks = SAMPLES_PER_CHAIN // MEASUREMENT_CHUNK
        for chunk in range(chunks):
            result = delayed_acceptance_chain(
                ground_mother_channels,
                evaluator,
                n_particles=N_ELECTRONS,
                coefficients=coefficient_vector,
                seed=measurement_seed + 30_000 + chunk,
                sample_steps=MEASUREMENT_CHUNK,
                proposal_sweeps=PROPOSAL_SWEEPS,
                delta_max=delta_max,
                initial_configuration=configuration,
                global_rotation_interval=4,
            )
            configuration = result.samples[-1]
            energies.extend(
                coulomb_potential(result.samples, TWO_Q).tolist()
            )
            correction_acceptances.append(
                float(result.correction_acceptance)
            )
            mother_acceptances.append(float(result.mother_acceptance))
            rotation_residuals.append(
                float(result.global_rotation_residual)
            )
            print(
                f"measurement seed={seed} sector={sector} chain={chain} "
                f"chunk={chunk + 1}/{chunks}",
                flush=True,
            )
    loaded_forbidden = sorted(
        name
        for name in sys.modules
        if name.startswith(FORBIDDEN_MODULE_PREFIXES)
    )
    payload = {
        "schema_version": TASK_SCHEMA_VERSION,
        "seed": seed,
        "sector": sector,
        "chain": chain,
        "measurement_seed": measurement_seed,
        "samples": SAMPLES_PER_CHAIN,
        "measurement_chunk": MEASUREMENT_CHUNK,
        "warmup_steps": WARMUP_STEPS,
        "proposal_sweeps": PROPOSAL_SWEEPS,
        "producer_source_revision": checkpoint["source_revision"],
        "measurement_source_revision": request[
            "measurement_source_revision"
        ],
        "architecture_sha256": request["architecture_sha256"],
        "checkpoint_sha256": request["checkpoint_sha256"],
        "warmup": warmup,
        "correction_acceptance": float(
            np.mean(correction_acceptances)
        ),
        "mother_acceptance": float(np.mean(mother_acceptances)),
        "global_rotation_residual": float(max(rotation_residuals)),
        "energy_samples": energies,
        "runtime_seconds": time.perf_counter() - started,
        "blind_audit_events": audit_events,
        "forbidden_modules_loaded": loaded_forbidden,
        "ed_accessed": bool(audit_events or loaded_forbidden),
        "passed": not audit_events and not loaded_forbidden,
    }
    validate(payload, MODULE_ROOT / "phase6-measurement-task.schema.json")
    return payload


def sector_statistics(
    tasks: list[dict[str, Any]],
    *,
    aggregate_wall_seconds: float,
) -> dict[str, Any]:
    ordered = sorted(tasks, key=lambda item: item["chain"])
    chains = np.asarray(
        [task["energy_samples"] for task in ordered],
        dtype=np.float64,
    )
    statistics = block_estimate(chains, block_size=2)
    blocks = chains.reshape(CHAINS, SAMPLES_PER_CHAIN // 2, 2).mean(
        axis=2
    )
    statistics.update(
        {
            "correction_acceptance": float(
                np.mean(
                    [task["correction_acceptance"] for task in ordered]
                )
            ),
            "mother_acceptance": float(
                np.mean([task["mother_acceptance"] for task in ordered])
            ),
            "per_chain_correction_acceptance": [
                task["correction_acceptance"] for task in ordered
            ],
            "per_chain_mother_acceptance": [
                task["mother_acceptance"] for task in ordered
            ],
            "global_rotation_residual": float(
                max(
                    task["global_rotation_residual"] for task in ordered
                )
            ),
            "block_size": 2,
            "block_means": blocks.tolist(),
            "wall_seconds": aggregate_wall_seconds,
            "ess_per_second": (
                statistics["effective_sample_size"]
                / aggregate_wall_seconds
            ),
        }
    )
    return statistics


def collect(
    *,
    repo_root: Path,
    attempt_path: Path,
    output_path: Path,
    workers: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    revision = git_output(repo_root, "rev-parse", "HEAD")
    source_tree = git_output(repo_root, "rev-parse", "HEAD^{tree}")
    if git_output(repo_root, "status", "--porcelain"):
        raise RuntimeError("measurement extension requires a clean worktree")
    attempt = load_json(attempt_path)
    validate(attempt, MODULE_ROOT / "phase6-attempt.schema.json")
    if attempt["schema_version"] != ATTEMPT_SCHEMA_VERSION:
        raise RuntimeError("unsupported Phase 6 attempt")
    failed = sorted(
        gate for gate, passed in attempt["gates"].items() if not passed
    )
    if failed != ["gap_precision"]:
        raise RuntimeError(
            "measurement extension only permits a sole gap_precision failure"
        )
    if (
        attempt["ed_accessed"]
        or attempt["forbidden_modules_loaded"]
        or attempt["forbidden_source_references"]
    ):
        raise RuntimeError("input attempt violated the blind boundary")

    architecture_path = Path(attempt["architecture"]["path"])
    architecture = load_json(architecture_path)
    architecture_sha256 = sha256_file(architecture_path)
    if architecture_sha256 != attempt["architecture"]["sha256"]:
        raise RuntimeError("architecture hash mismatch")
    producer_revision = attempt["git_commit"]
    if architecture["source_revision"] != producer_revision:
        raise RuntimeError("architecture producer revision mismatch")
    checkpoint_by_seed: dict[int, dict[str, Any]] = {}
    checkpoint_reference_by_seed: dict[int, dict[str, Any]] = {}
    for reference in attempt["checkpoints"]:
        checkpoint_path = Path(reference["path"])
        if sha256_file(checkpoint_path) != reference["sha256"]:
            raise RuntimeError("checkpoint hash mismatch")
        checkpoint = load_json(checkpoint_path)
        if (
            checkpoint["source_revision"] != producer_revision
            or checkpoint["architecture_sha256"] != architecture_sha256
        ):
            raise RuntimeError("checkpoint provenance mismatch")
        checkpoint_by_seed[reference["seed"]] = checkpoint
        checkpoint_reference_by_seed[reference["seed"]] = reference

    requests = []
    for seed, sector, chain in itertools.product(
        SEEDS, SECTORS, range(CHAINS)
    ):
        reference = checkpoint_reference_by_seed[seed]
        requests.append(
            {
                "seed": seed,
                "sector": sector,
                "chain": chain,
                "architecture": architecture,
                "architecture_sha256": architecture_sha256,
                "checkpoint": checkpoint_by_seed[seed],
                "checkpoint_sha256": reference["sha256"],
                "measurement_source_revision": revision,
            }
        )
    task_started = time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
    ) as executor:
        task_payloads = list(executor.map(measure_task, requests))
    task_wall_seconds = time.perf_counter() - task_started

    task_references = []
    for payload in task_payloads:
        task_dir = (
            output_path.parent
            / "tasks"
            / f"seed-{payload['seed']}"
            / payload["sector"]
            / f"chain-{payload['chain']}"
        )
        task_path = task_dir / "task-certificate.json"
        stdout_path = task_dir / "stdout.txt"
        stderr_path = task_dir / "stderr.txt"
        write_json(task_path, payload)
        write_text(
            stdout_path,
            json.dumps(
                {
                    "seed": payload["seed"],
                    "sector": payload["sector"],
                    "chain": payload["chain"],
                    "samples": payload["samples"],
                    "runtime_seconds": payload["runtime_seconds"],
                    "passed": payload["passed"],
                },
                sort_keys=True,
            )
            + "\nPHASE6_MEASUREMENT_TASK=passed\n",
        )
        write_text(stderr_path, "")
        task_references.append(
            {
                "seed": payload["seed"],
                "sector": payload["sector"],
                "chain": payload["chain"],
                "certificate": artifact(task_path),
                "stdout": artifact(stdout_path),
                "stderr": artifact(stderr_path),
            }
        )

    seed_results = []
    for seed in SEEDS:
        sectors = {}
        for sector in SECTORS:
            selected = [
                payload
                for payload in task_payloads
                if payload["seed"] == seed
                and payload["sector"] == sector
            ]
            sectors[sector] = sector_statistics(
                selected,
                aggregate_wall_seconds=task_wall_seconds,
            )
        gap = sectors["tower"]["mean"] - sectors["ground"]["mean"]
        gap_error = float(
            np.hypot(
                sectors["tower"]["standard_error"],
                sectors["ground"]["standard_error"],
            )
        )
        seed_results.append(
            {
                "seed": seed,
                "ground": sectors["ground"],
                "tower": sectors["tower"],
                "gap": gap,
                "gap_standard_error": gap_error,
            }
        )

    exact_tasks = {
        (seed, sector, chain)
        for seed, sector, chain in itertools.product(
            SEEDS, SECTORS, range(CHAINS)
        )
    }
    observed_tasks = {
        (item["seed"], item["sector"], item["chain"])
        for item in task_payloads
    }
    gates = {
        "sole_input_failure_gap_precision": True,
        "immutable_input_hashes": True,
        "exact_task_set": observed_tasks == exact_tasks,
        "task_schemas_valid": len(task_payloads) == len(exact_tasks),
        "blind_measurement": all(
            task["passed"]
            and not task["ed_accessed"]
            and not task["blind_audit_events"]
            and not task["forbidden_modules_loaded"]
            for task in task_payloads
        ),
        "finite_statistics": all(
            math.isfinite(float(result[key]))
            for result in seed_results
            for key in ("gap", "gap_standard_error")
        ),
        "sampling_acceptance": all(
            all(
                0.05 <= acceptance <= 1.0
                for acceptance in result[sector][
                    "per_chain_correction_acceptance"
                ]
            )
            and all(
                0.25 <= acceptance <= 0.70
                for acceptance in result[sector][
                    "per_chain_mother_acceptance"
                ]
            )
            for result in seed_results
            for sector in SECTORS
        ),
        "effective_samples": all(
            result[sector]["effective_sample_size"] >= 32.0
            and result[sector]["ess_per_second"] > 0.0
            and result[sector]["r_hat"] < 1.2
            for result in seed_results
            for sector in SECTORS
        ),
        "gap_precision": all(
            result["gap_standard_error"] <= 5.0e-3
            for result in seed_results
        ),
        "three_seed_consistency": all(
            abs(left["gap"] - right["gap"])
            <= 3.0
            * math.hypot(
                left["gap_standard_error"],
                right["gap_standard_error"],
            )
            for left, right in itertools.combinations(seed_results, 2)
        ),
        "rotation_invariance": all(
            result[sector]["global_rotation_residual"] < 1.0e-7
            for result in seed_results
            for sector in SECTORS
        ),
        "checkpoint_coefficients_unchanged": all(
            sha256_file(Path(reference["path"])) == reference["sha256"]
            for reference in attempt["checkpoints"]
        ),
        "clean_measurement_source": True,
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "producer_source_revision": producer_revision,
        "measurement_source_revision": revision,
        "measurement_source_tree": source_tree,
        "measurement_source_clean": True,
        "input_attempt": artifact(attempt_path),
        "architecture": {
            **artifact(architecture_path),
            "schema_path": attempt["architecture"]["schema_path"],
            "schema_sha256": attempt["architecture"]["schema_sha256"],
        },
        "checkpoints": [
            {
                "seed": reference["seed"],
                **artifact(Path(reference["path"])),
                "schema_path": reference["schema_path"],
                "schema_sha256": reference["schema_sha256"],
            }
            for reference in attempt["checkpoints"]
        ],
        "protocol": {
            "seeds": list(SEEDS),
            "sectors": list(SECTORS),
            "chains_per_sector": CHAINS,
            "samples_per_chain": SAMPLES_PER_CHAIN,
            "measurement_chunk": MEASUREMENT_CHUNK,
            "warmup_steps": WARMUP_STEPS,
            "proposal_sweeps": PROPOSAL_SWEEPS,
            "selection_rule": (
                "extend-sole-gap-precision-failure-without-ed-or-retraining"
            ),
        },
        "tasks": sorted(
            task_references,
            key=lambda item: (
                item["seed"],
                item["sector"],
                item["chain"],
            ),
        ),
        "seed_results": seed_results,
        "gates": gates,
        "task_wall_seconds": task_wall_seconds,
        "runtime_seconds": time.perf_counter() - started,
        "jax_device": os.environ["ROUTE_D_PLUS_JAX_DEVICE"],
        "jax_platform": "gpu",
        "jax_x64_enabled": True,
        "hostname": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_cluster_name": os.environ.get("SLURM_CLUSTER_NAME"),
        "ed_accessed": False,
        "passed": all(gates.values()),
    }
    attempt_payload = {
        **payload,
        "schema_version": MEASUREMENT_ATTEMPT_VERSION,
    }
    validate(
        attempt_payload,
        MODULE_ROOT / "phase6-measurement-attempt.schema.json",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=24)
    args = parser.parse_args()
    if args.workers <= 0:
        raise ValueError("workers must be positive")
    import jax

    jax.config.update("jax_enable_x64", True)
    devices = jax.devices()
    if not devices or devices[0].platform != "gpu":
        raise RuntimeError("measurement extension requires a JAX GPU allocation")
    if not jax.config.read("jax_enable_x64"):
        raise RuntimeError("measurement extension requires JAX x64")
    os.environ["ROUTE_D_PLUS_JAX_DEVICE"] = str(devices[0])
    output = args.output.resolve()
    payload = collect(
        repo_root=args.repo_root.resolve(),
        attempt_path=args.attempt.resolve(),
        output_path=output,
        workers=args.workers,
    )
    measurement_attempt = {
        **payload,
        "schema_version": MEASUREMENT_ATTEMPT_VERSION,
    }
    write_json(
        output.parent / "phase6-measurement-attempt.json",
        measurement_attempt,
    )
    if not payload["passed"]:
        print(json.dumps(measurement_attempt, indent=2, sort_keys=True))
        return 1
    validate(payload, MODULE_ROOT / "phase6-measurement.schema.json")
    write_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
