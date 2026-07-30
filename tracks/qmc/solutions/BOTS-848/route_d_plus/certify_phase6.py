"""Run and certify blind N=6 Route D+ D+0 training."""

from __future__ import annotations

import argparse
import builtins
import concurrent.futures
import contextlib
import datetime as dt
import hashlib
import io
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

import jax
import jsonschema

from route_d_plus.symmetry import verify_checkpoint_symmetry
from route_d_plus.train_dplus0 import (
    calibrate_architecture,
    train_seed,
    write_checkpoint,
)

SCHEMA_VERSION = "challenge-15-route-d-plus-phase6-v1"
ATTEMPT_SCHEMA_VERSION = "challenge-15-route-d-plus-phase6-attempt-v1"
PHASE5_SCHEMA_VERSION = "challenge-15-route-d-plus-phase5-v1"
SEEDS = (848, 1848, 2848)
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_against_schema(
    payload: dict[str, Any],
    schema_path: Path,
) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    ).validate(payload)


def all_finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(all_finite(item) for item in value)
    return True


def git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        capture_output=True,
        check=True,
        cwd=repo_root,
        text=True,
    )
    return completed.stdout.strip()


def require_phase5_certificate(path: Path) -> dict[str, Any]:
    certificate = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": PHASE5_SCHEMA_VERSION,
        "target_n_electrons": 6,
        "target_two_q": 15,
        "generator_ranks": [2, 3, 4],
        "passed": True,
        "git_dirty": False,
    }
    mismatches = {
        key: (certificate.get(key), value)
        for key, value in expected.items()
        if certificate.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"Phase 5 certificate mismatch: {mismatches}")
    return certificate


def forbidden_source_references() -> list[str]:
    module_root = Path(__file__).resolve().parent
    paths = [
        module_root / "coordinate.py",
        module_root / "vmc.py",
        module_root / "train_dplus0.py",
        module_root / "certify_phase6.py",
    ]
    findings = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for prefix in FORBIDDEN_MODULE_PREFIXES:
            if prefix in text and path.name != "certify_phase6.py":
                findings.append(f"{path.name}:{prefix}")
    return findings


@contextlib.contextmanager
def blind_training_audit() -> Any:
    """Deny and record forbidden imports/file opens throughout training."""

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
            raise RuntimeError(f"forbidden ED import during training: {name}")
        return original_import(name, globals, locals, fromlist, level)

    def check_path(file: Any) -> None:
        if isinstance(file, (str, os.PathLike)):
            normalized = str(Path(file).resolve()).lower()
            if any(marker in normalized for marker in FORBIDDEN_PATH_MARKERS):
                events.append({"operation": "open", "target": normalized})
                raise RuntimeError(
                    f"forbidden ED artifact access during training: {file}"
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


def _train_seed_worker(
    request: tuple[int, dict[str, Any], str],
) -> tuple[int, dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    seed, architecture, architecture_sha256 = request
    with blind_training_audit() as events:
        checkpoint, result = train_seed(
            seed,
            architecture=architecture,
            architecture_sha256=architecture_sha256,
        )
    loaded = sorted(
        name
        for name in sys.modules
        if name.startswith(FORBIDDEN_MODULE_PREFIXES)
    )
    events.extend(
        {"operation": "loaded-module", "target": name}
        for name in loaded
    )
    return seed, checkpoint, result, events


def collect_certificate(
    *,
    repo_root: Path,
    phase5_certificate_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    phase5 = require_phase5_certificate(phase5_certificate_path)
    commit = git_output(repo_root, "rev-parse", "HEAD")
    dirty = bool(git_output(repo_root, "status", "--porcelain"))
    if len(commit) != 40 or dirty:
        raise RuntimeError("Phase 6 requires a clean committed source revision")
    jax.config.update("jax_enable_x64", True)
    devices = jax.devices()
    if not devices or devices[0].platform != "gpu":
        raise RuntimeError("Phase 6 must run inside a JAX GPU allocation")
    if not jax.config.read("jax_enable_x64"):
        raise RuntimeError("Phase 6 requires JAX x64 mode")
    source_findings = forbidden_source_references()
    loaded_forbidden = sorted(
        name
        for name in sys.modules
        if name.startswith(FORBIDDEN_MODULE_PREFIXES)
    )
    if source_findings or loaded_forbidden:
        raise RuntimeError(
            f"blind-training boundary violated: {source_findings}, "
            f"{loaded_forbidden}"
        )

    started = time.perf_counter()
    checkpoints = []
    seed_results = []
    with blind_training_audit() as calibration_events:
        architecture = calibrate_architecture(60_860)
        architecture_schema_path = Path(__file__).with_name(
            "architecture.schema.json"
        )
        checkpoint_schema_path = Path(__file__).with_name(
            "checkpoint.schema.json"
        )
        symmetry_schema_path = Path(__file__).with_name(
            "symmetry.schema.json"
        )
        validate_against_schema(
            architecture,
            architecture_schema_path,
        )
        architecture_path = output_path.parent / "architecture.json"
        write_checkpoint(architecture_path, architecture)
        architecture_sha256 = sha256_file(architecture_path)
    print("phase6 shared architecture frozen", flush=True)
    requests = [
        (seed, architecture, architecture_sha256) for seed in SEEDS
    ]
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=len(SEEDS),
        mp_context=multiprocessing.get_context("spawn"),
    ) as executor:
        worker_outputs = list(executor.map(_train_seed_worker, requests))
    audit_events = list(calibration_events)
    for seed, checkpoint, result, worker_events in sorted(worker_outputs):
        audit_events.extend(worker_events)
        print(f"phase6 seed {seed}: training complete", flush=True)
        with blind_training_audit() as finalization_events:
            validate_against_schema(
                checkpoint,
                checkpoint_schema_path,
            )
            seed_dir = output_path.parent / "seeds" / f"seed-{seed}"
            checkpoint_path = seed_dir / "checkpoint.json"
            write_checkpoint(checkpoint_path, checkpoint)
            symmetry = verify_checkpoint_symmetry(
                architecture,
                checkpoint,
            )
            validate_against_schema(symmetry, symmetry_schema_path)
            symmetry_path = seed_dir / "symmetry-certificate.json"
            write_json_atomic(symmetry_path, symmetry)
        audit_events.extend(finalization_events)
        checkpoints.append(
            {
                "seed": seed,
                "path": str(checkpoint_path.resolve()),
                "sha256": sha256_file(checkpoint_path),
                "selection": "final_update",
                "architecture_sha256": architecture_sha256,
                "schema_path": str(checkpoint_schema_path.resolve()),
                "schema_sha256": sha256_file(checkpoint_schema_path),
                "symmetry_path": str(symmetry_path.resolve()),
                "symmetry_sha256": sha256_file(symmetry_path),
                "symmetry_schema_sha256": sha256_file(
                    symmetry_schema_path
                ),
            }
        )
        seed_results.append(result)
        print(
            f"phase6 seed {seed}: checkpoint "
            f"{checkpoints[-1]['sha256']}",
            flush=True,
        )
    loaded_forbidden_after = sorted(
        name
        for name in sys.modules
        if name.startswith(FORBIDDEN_MODULE_PREFIXES)
    )
    audit_path = output_path.parent / "blind-access-audit.json"
    write_json_atomic(
        audit_path,
        {
            "forbidden_module_prefixes": list(
                FORBIDDEN_MODULE_PREFIXES
            ),
            "forbidden_path_markers": list(FORBIDDEN_PATH_MARKERS),
            "denied_events": audit_events,
            "loaded_forbidden_before": loaded_forbidden,
            "loaded_forbidden_after": loaded_forbidden_after,
        },
    )

    finite_results = all_finite(seed_results) and all_finite(architecture)
    gates = {
        "three_seed_training": len(seed_results) == 3
        and [result["seed"] for result in seed_results] == list(SEEDS),
        "identity_initialization": all(
            0.0 < result["initialization_norm"] < 2.0e-2
            for result in seed_results
        ),
        "finite_statistics": finite_results,
        "sampling_acceptance": all(
            0.05 <= result[sector]["correction_acceptance"] <= 1.0
            and 0.20 <= result[sector]["mother_acceptance"] <= 0.80
            for result in seed_results
            for sector in ("final_ground", "final_tower")
        ),
        "effective_samples": all(
            result[sector]["effective_sample_size"] >= 32.0
            and result[sector]["ess_per_second"] > 0.0
            and result[sector]["r_hat"] < 1.2
            for result in seed_results
            for sector in ("final_ground", "final_tower")
        ),
        "gap_precision": all(
            result["final_gap_standard_error"] <= 5.0e-3
            for result in seed_results
        ),
        "rotation_invariance": all(
            result[sector]["global_rotation_residual"] < 1.0e-7
            for result in seed_results
            for sector in ("final_ground", "final_tower")
        ),
        "checkpoint_symmetry": all(
            checkpoint["symmetry_sha256"]
            and checkpoint["symmetry_schema_sha256"]
            for checkpoint in checkpoints
        ),
        "blind_training": (
            not source_findings
            and not loaded_forbidden
            and not loaded_forbidden_after
            and not audit_events
        ),
        "shared_frozen_architecture": all(
            result["architecture_sha256"] == architecture_sha256
            and checkpoint["architecture_sha256"] == architecture_sha256
            for result, checkpoint in zip(
                seed_results, checkpoints, strict=True
            )
        ),
        "combined_state_averaged_sr": all(
            all(
                record["metric_structure"]
                == "equal-weight-block-diagonal-shared-solve"
                for record in result["trace"]
            )
            for result in seed_results
        ),
        "final_checkpoint_selection": all(
            checkpoint["selection"] == "final_update"
            for checkpoint in checkpoints
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_electrons": 6,
        "two_q": 15,
        "ansatz": "D+0-linear-scalar",
        "seeds": list(SEEDS),
        "seed_results": seed_results,
        "checkpoints": checkpoints,
        "architecture": {
            "path": str(architecture_path.resolve()),
            "sha256": architecture_sha256,
            "retained_generators": architecture[
                "retained_generators"
            ],
            "selection_rule": architecture["selection_rule"],
            "schema_path": str(architecture_schema_path.resolve()),
            "schema_sha256": sha256_file(architecture_schema_path),
        },
        "blind_access_audit": {
            "path": str(audit_path.resolve()),
            "sha256": sha256_file(audit_path),
            "denied_events": len(audit_events),
        },
        "gates": gates,
        "passed": all(gates.values()),
        "ed_accessed": bool(audit_events or loaded_forbidden_after),
        "forbidden_module_prefixes": list(FORBIDDEN_MODULE_PREFIXES),
        "forbidden_modules_loaded": loaded_forbidden,
        "forbidden_source_references": source_findings,
        "runtime_seconds": time.perf_counter() - started,
        "jax_device": str(devices[0]),
        "jax_platform": devices[0].platform,
        "jax_x64_enabled": jax.config.read("jax_enable_x64"),
        "git_commit": commit,
        "git_dirty": dirty,
        "hostname": platform.node(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_cluster_name": os.environ.get("SLURM_CLUSTER_NAME"),
        "phase5_certificate_path": str(
            phase5_certificate_path.resolve()
        ),
        "phase5_certificate_sha256": sha256_file(
            phase5_certificate_path
        ),
        "phase5_git_commit": phase5["git_commit"],
    }


def validate_certificate(payload: dict[str, Any]) -> None:
    schema_path = Path(__file__).with_name("phase6.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    ).validate(payload)


def validate_attempt(payload: dict[str, Any]) -> None:
    schema_path = Path(__file__).with_name("phase6-attempt.schema.json")
    validate_against_schema(payload, schema_path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--phase5-certificate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    collected = collect_certificate(
        repo_root=arguments.repo_root.resolve(),
        phase5_certificate_path=arguments.phase5_certificate.resolve(),
        output_path=output,
    )
    attempt = {**collected, "schema_version": ATTEMPT_SCHEMA_VERSION}
    validate_attempt(attempt)
    attempt_path = output.parent / "phase6-attempt.json"
    write_json_atomic(attempt_path, attempt)
    if not collected["passed"]:
        print(json.dumps(attempt, indent=2, sort_keys=True))
        return 1
    validate_certificate(collected)
    write_json_atomic(output, collected)
    print(json.dumps(collected, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
