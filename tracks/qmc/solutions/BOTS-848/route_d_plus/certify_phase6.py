"""Run and certify blind N=6 Route D+ D+0 training."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import jax
import jsonschema

from route_d_plus.train_dplus0 import train_seed, write_checkpoint

SCHEMA_VERSION = "challenge-15-route-d-plus-phase6-v1"
PHASE5_SCHEMA_VERSION = "challenge-15-route-d-plus-phase5-v1"
SEEDS = (848, 1848, 2848)
FORBIDDEN_MODULE_PREFIXES = (
    "benchmark_v0.ed_oracle",
    "benchmark_v0.fock_ed",
    "benchmark_v0.projected_nqs",
    "benchmark_v0.nqs_benchmark",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    checkpoint_dir = output_path.parent / "checkpoints"
    for seed in SEEDS:
        print(f"phase6 seed {seed}: training start", flush=True)
        checkpoint, result = train_seed(seed)
        checkpoint_path = checkpoint_dir / f"dplus0-seed-{seed}.json"
        write_checkpoint(checkpoint_path, checkpoint)
        checkpoints.append(
            {
                "seed": seed,
                "path": str(checkpoint_path.resolve()),
                "sha256": sha256_file(checkpoint_path),
                "selection": "final_update",
            }
        )
        seed_results.append(result)
        print(
            f"phase6 seed {seed}: checkpoint {checkpoints[-1]['sha256']}",
            flush=True,
        )

    finite_results = all(
        all(
            math.isfinite(float(result[sector][field]))
            for sector in ("final_ground", "final_tower")
            for field in (
                "mean",
                "standard_error",
                "effective_sample_size",
                "r_hat",
                "correction_acceptance",
                "mother_acceptance",
                "global_rotation_residual",
            )
        )
        for result in seed_results
    )
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
            result[sector]["effective_sample_size"] >= 2.0
            and result[sector]["r_hat"] < 2.0
            for result in seed_results
            for sector in ("final_ground", "final_tower")
        ),
        "rotation_invariance": all(
            result[sector]["global_rotation_residual"] < 1.0e-7
            for result in seed_results
            for sector in ("final_ground", "final_tower")
        ),
        "blind_training": not source_findings and not loaded_forbidden,
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
        "gates": gates,
        "passed": all(gates.values()),
        "ed_accessed": False,
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
    payload = collect_certificate(
        repo_root=arguments.repo_root.resolve(),
        phase5_certificate_path=arguments.phase5_certificate.resolve(),
        output_path=output,
    )
    validate_certificate(payload)
    write_json_atomic(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
