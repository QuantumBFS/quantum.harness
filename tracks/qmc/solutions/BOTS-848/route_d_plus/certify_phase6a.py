"""Profile and independently certify the Route D+ Phase 6A coordinate backend."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import jax
import jsonschema
import numpy as np

from route_d_plus.coordinate import (
    CoordinateAmplitudeCache,
    compact_reproducing_quadrature,
    scalar_laughlin_amplitudes,
    scalar_laughlin_amplitudes_kernel,
    scalar_tower_amplitudes,
)
from route_d_plus.tensor import quadrature_reconstruction_error
from route_d_plus.vmc import (
    block_estimate,
    coulomb_potential,
    delayed_acceptance_chain,
    random_configuration,
)

SCHEMA_VERSION = "challenge-15-route-d-plus-phase6a-v1"
READBACK_SCHEMA_VERSION = "challenge-15-route-d-plus-phase6a-readback-v1"
N_ELECTRONS = 6
TWO_Q = 15
RANKS = (2, 3, 4)
BACKEND_TOLERANCE = 1.0e-10
RECONSTRUCTION_TOLERANCE = 1.0e-12
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def timed_call(function: Any, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    started = time.perf_counter()
    value = function(*args, **kwargs)
    return value, time.perf_counter() - started


def source_hashes(repo_root: Path) -> dict[str, str]:
    relative_paths = (
        "tracks/qmc/solutions/BOTS-848/route_d_plus/coordinate.py",
        "tracks/qmc/solutions/BOTS-848/route_d_plus/vmc.py",
        "tracks/qmc/solutions/BOTS-848/route_d_plus/certify_phase6a.py",
        "tracks/qmc/solutions/BOTS-848/route_d_plus/phase6a.schema.json",
    )
    return {
        relative: sha256_file(repo_root / relative)
        for relative in relative_paths
    }


def _gpu_environment() -> dict[str, Any]:
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Phase 6A must run inside a Slurm allocation")
    jax.config.update("jax_enable_x64", True)
    devices = jax.devices()
    if not devices or devices[0].platform != "gpu":
        raise RuntimeError("Phase 6A requires a JAX GPU allocation")
    if not jax.config.read("jax_enable_x64"):
        raise RuntimeError("Phase 6A requires JAX x64 mode")
    return {
        "jax_device": str(devices[0]),
        "jax_platform": devices[0].platform,
        "jax_x64_enabled": True,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "hostname": platform.node(),
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "slurm_cluster_name": os.environ.get("SLURM_CLUSTER_NAME"),
    }


def _require_clean_source(repo_root: Path) -> dict[str, Any]:
    commit = git_output(repo_root, "rev-parse", "HEAD")
    tree = git_output(repo_root, "rev-parse", "HEAD^{tree}")
    dirty = bool(git_output(repo_root, "status", "--porcelain"))
    if len(commit) != 40 or len(tree) != 40 or dirty:
        raise RuntimeError("Phase 6A requires a clean committed source revision")
    return {
        "git_commit": commit,
        "git_tree": tree,
        "git_dirty": False,
        "source_sha256": source_hashes(repo_root),
    }


def _forbidden_modules_loaded() -> list[str]:
    return sorted(
        name
        for name in sys.modules
        if name.startswith(FORBIDDEN_MODULE_PREFIXES)
    )


def collect_profile(repo_root: Path, *, seed: int) -> dict[str, Any]:
    """Run the isolated Phase 6A profile inside one Slurm GPU allocation."""

    source = _require_clean_source(repo_root)
    environment = _gpu_environment()
    loaded_forbidden = _forbidden_modules_loaded()
    if loaded_forbidden:
        raise RuntimeError(
            f"Phase 6A loaded forbidden ED modules: {loaded_forbidden}"
        )
    started = time.perf_counter()
    rng = np.random.default_rng(seed)
    configurations = [
        random_configuration(rng, N_ELECTRONS) for _ in range(2)
    ]
    quadrature = compact_reproducing_quadrature(TWO_Q)
    reconstruction_error = quadrature_reconstruction_error(
        TWO_Q, quadrature
    )

    backend_records = []
    production_values = []
    for index, configuration in enumerate(configurations):
        proof, proof_seconds = timed_call(
            scalar_laughlin_amplitudes_kernel,
            configuration,
            quadrature,
            ranks=RANKS,
        )
        production, production_seconds = timed_call(
            scalar_laughlin_amplitudes,
            configuration,
            ranks=RANKS,
        )
        errors = np.abs(production - proof) / np.maximum(1.0, np.abs(proof))
        backend_records.append(
            {
                "configuration": index,
                "maximum_relative_error": float(np.max(errors)),
                "proof_wall_seconds": proof_seconds,
                "production_wall_seconds": production_seconds,
            }
        )
        production_values.append(production)

    tower_timings = []
    for configuration in configurations:
        _, seconds = timed_call(
            scalar_tower_amplitudes,
            configuration,
            ranks=RANKS,
        )
        tower_timings.append(seconds)

    cache = CoordinateAmplitudeCache(max_entries=4096)
    cached_cold, cache_cold_seconds = timed_call(
        cache.channels,
        configurations[0],
        total_l=0,
        ranks=RANKS,
    )
    cached_hit, cache_hit_seconds = timed_call(
        cache.channels,
        configurations[0],
        total_l=0,
        ranks=RANKS,
    )
    cache_batch, cache_batch_seconds = timed_call(
        cache.batch,
        np.stack(
            (configurations[0], configurations[1], configurations[0])
        ),
        total_l=0,
        ranks=RANKS,
    )
    cache_error = max(
        float(np.max(np.abs(cached_cold - production_values[0]))),
        float(np.max(np.abs(cached_hit - production_values[0]))),
        float(np.max(np.abs(cache_batch[0] - production_values[0]))),
        float(np.max(np.abs(cache_batch[1] - production_values[1]))),
        float(np.max(np.abs(cache_batch[2] - production_values[0]))),
    )

    delayed_cache = CoordinateAmplitudeCache(max_entries=32768)

    def identity_evaluator(configuration: np.ndarray) -> np.ndarray:
        return delayed_cache.channels(
            configuration,
            total_l=0,
            ranks=(),
        )

    delayed_started = time.perf_counter()
    delayed_results = [
        delayed_acceptance_chain(
            identity_evaluator,
            identity_evaluator,
            n_particles=N_ELECTRONS,
            coefficients=np.empty(0, dtype=np.complex128),
            seed=seed + 100 + chain,
            sample_steps=32,
            proposal_sweeps=1,
            delta_max=0.35,
            global_rotation_interval=8,
        )
        for chain in range(2)
    ]
    delayed_seconds = time.perf_counter() - delayed_started
    delayed_energies = np.stack(
        [
            coulomb_potential(result.samples, TWO_Q)
            for result in delayed_results
        ]
    )
    delayed_statistics = block_estimate(delayed_energies, block_size=4)
    delayed_channel_error = 0.0
    for result in delayed_results:
        readback_channels = delayed_cache.batch(
            result.samples,
            total_l=0,
            ranks=(),
        )
        delayed_channel_error = max(
            delayed_channel_error,
            float(
                np.max(
                    np.abs(readback_channels - result.channel_values)
                )
            ),
        )
    correction_acceptance = float(
        np.mean(
            [result.correction_acceptance for result in delayed_results]
        )
    )
    mother_acceptance = float(
        np.mean([result.mother_acceptance for result in delayed_results])
    )
    ess_per_second = (
        delayed_statistics["effective_sample_size"] / delayed_seconds
    )
    finite_timings = all(
        math.isfinite(value) and value > 0.0
        for value in (
            cache_cold_seconds,
            cache_hit_seconds,
            cache_batch_seconds,
            delayed_seconds,
            *tower_timings,
            *(
                record["proof_wall_seconds"]
                for record in backend_records
            ),
            *(
                record["production_wall_seconds"]
                for record in backend_records
            ),
        )
    )
    gates = {
        "strict_lll_quadrature": (
            reconstruction_error < RECONSTRUCTION_TOLERANCE
        ),
        "continuous_backend_agreement": all(
            record["maximum_relative_error"] < BACKEND_TOLERANCE
            for record in backend_records
        ),
        "cache_exact": cache_error < 1.0e-14,
        "delayed_acceptance_equivalence": (
            abs(correction_acceptance - 1.0) < 1.0e-14
            and delayed_channel_error < 1.0e-14
        ),
        "finite_performance": (
            finite_timings
            and math.isfinite(ess_per_second)
            and ess_per_second > 0.0
        ),
        "gpu_allocation": environment["jax_platform"] == "gpu",
        "clean_source": not source["git_dirty"],
        "blind_boundary": not loaded_forbidden,
    }
    maximum_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_electrons": N_ELECTRONS,
        "two_q": TWO_Q,
        "generator_ranks": list(RANKS),
        "random_seed": seed,
        "continuous_configurations": len(configurations),
        "quadrature": {
            "kind": "compact-LLL-reproducing",
            "n_theta": quadrature.n_theta,
            "n_phi": quadrature.n_phi,
            "size": quadrature.size,
            "reconstruction_error": reconstruction_error,
            "tolerance": RECONSTRUCTION_TOLERANCE,
        },
        "backend_cross_validation": {
            "metric": "abs(prod-kernel)/max(1,abs(kernel))",
            "tolerance": BACKEND_TOLERANCE,
            "records": backend_records,
        },
        "amplitude_cost": {
            "ground_mean_wall_seconds": float(
                np.mean(
                    [
                        record["production_wall_seconds"]
                        for record in backend_records
                    ]
                )
            ),
            "tower_wall_seconds": tower_timings,
            "tower_mean_wall_seconds": float(np.mean(tower_timings)),
        },
        "cache_profile": {
            "key_fields": [
                "N",
                "two_q",
                "L",
                "M",
                "word_id",
                "configuration_digest",
            ],
            "cold_wall_seconds": cache_cold_seconds,
            "hit_wall_seconds": cache_hit_seconds,
            "batch_wall_seconds": cache_batch_seconds,
            "maximum_value_error": cache_error,
            "entries": cache.entries,
            "hits": cache.hits,
            "misses": cache.misses,
        },
        "delayed_acceptance": {
            "chains": 2,
            "samples_per_chain": 32,
            "proposal_sweeps": 1,
            "wall_seconds": delayed_seconds,
            "correction_acceptance": correction_acceptance,
            "mother_acceptance": mother_acceptance,
            "maximum_channel_readback_error": delayed_channel_error,
            "effective_sample_size": delayed_statistics[
                "effective_sample_size"
            ],
            "integrated_autocorrelation_time": delayed_statistics[
                "integrated_autocorrelation_time"
            ],
            "r_hat": delayed_statistics["r_hat"],
            "ess_per_second": ess_per_second,
        },
        "runtime": {
            "profile_wall_seconds": time.perf_counter() - started,
            "maximum_rss_kib": maximum_rss,
        },
        "gates": gates,
        "passed": all(gates.values()),
        "forbidden_modules_loaded": loaded_forbidden,
        **source,
        **environment,
    }


def _require_slurm_evidence(
    path: Path,
    *,
    slurm_job_id: str,
) -> None:
    text = path.read_text(encoding="utf-8")
    if (
        slurm_job_id not in text
        or "COMPLETED" not in text
        or "0:0" not in text
    ):
        raise RuntimeError(
            "Slurm evidence must identify the job and prove COMPLETED 0:0"
        )


def finalize_certificate(
    *,
    repo_root: Path,
    raw_result_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    slurm_evidence_path: Path,
) -> dict[str, Any]:
    """Attach immutable job/log evidence after the profile process exits."""

    raw = json.loads(raw_result_path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != SCHEMA_VERSION or not raw.get("passed"):
        raise RuntimeError("raw Phase 6A profile did not pass")
    if raw.get("git_commit") != git_output(repo_root, "rev-parse", "HEAD"):
        raise RuntimeError("raw profile source revision is not checked out")
    if git_output(repo_root, "status", "--porcelain"):
        raise RuntimeError("Phase 6A finalization requires a clean worktree")
    _require_slurm_evidence(
        slurm_evidence_path,
        slurm_job_id=raw["slurm_job_id"],
    )
    evidence = {
        "raw_result_path": str(raw_result_path.resolve()),
        "raw_result_sha256": sha256_file(raw_result_path),
        "stdout_path": str(stdout_path.resolve()),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_path": str(stderr_path.resolve()),
        "stderr_sha256": sha256_file(stderr_path),
        "slurm_evidence_path": str(slurm_evidence_path.resolve()),
        "slurm_evidence_sha256": sha256_file(slurm_evidence_path),
        "slurm_state": "COMPLETED",
        "slurm_exit_code": "0:0",
    }
    payload = {**raw, "evidence": evidence}
    schema_path = Path(__file__).with_name("phase6a.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    ).validate(payload)
    return payload


def verify_certificate(
    *,
    repo_root: Path,
    certificate_path: Path,
) -> dict[str, Any]:
    """Independently read back schema, source, job, and log hashes."""

    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    schema_path = Path(__file__).with_name("phase6a.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    ).validate(certificate)
    evidence = certificate["evidence"]
    checks = {
        "certificate_passed": certificate["passed"] is True,
        "git_commit": (
            certificate["git_commit"]
            == git_output(repo_root, "rev-parse", "HEAD")
        ),
        "git_clean": not bool(
            git_output(repo_root, "status", "--porcelain")
        ),
        "source_hashes": source_hashes(repo_root)
        == certificate["source_sha256"],
        "raw_result_hash": (
            sha256_file(Path(evidence["raw_result_path"]))
            == evidence["raw_result_sha256"]
        ),
        "stdout_hash": (
            sha256_file(Path(evidence["stdout_path"]))
            == evidence["stdout_sha256"]
        ),
        "stderr_hash": (
            sha256_file(Path(evidence["stderr_path"]))
            == evidence["stderr_sha256"]
        ),
        "slurm_evidence_hash": (
            sha256_file(Path(evidence["slurm_evidence_path"]))
            == evidence["slurm_evidence_sha256"]
        ),
    }
    _require_slurm_evidence(
        Path(evidence["slurm_evidence_path"]),
        slurm_job_id=certificate["slurm_job_id"],
    )
    return {
        "schema_version": READBACK_SCHEMA_VERSION,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "certificate_path": str(certificate_path.resolve()),
        "certificate_sha256": sha256_file(certificate_path),
        "schema_path": str(schema_path.resolve()),
        "schema_sha256": sha256_file(schema_path),
        "git_commit": certificate["git_commit"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--repo-root", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--seed", type=int, default=60_851)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--repo-root", type=Path, required=True)
    finalize.add_argument("--raw-result", type=Path, required=True)
    finalize.add_argument("--stdout-log", type=Path, required=True)
    finalize.add_argument("--stderr-log", type=Path, required=True)
    finalize.add_argument("--slurm-evidence", type=Path, required=True)
    finalize.add_argument("--output", type=Path, required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--repo-root", type=Path, required=True)
    verify.add_argument("--certificate", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    if args.command == "run":
        payload = collect_profile(repo_root, seed=args.seed)
    elif args.command == "finalize":
        payload = finalize_certificate(
            repo_root=repo_root,
            raw_result_path=args.raw_result.resolve(),
            stdout_path=args.stdout_log.resolve(),
            stderr_path=args.stderr_log.resolve(),
            slurm_evidence_path=args.slurm_evidence.resolve(),
        )
    else:
        payload = verify_certificate(
            repo_root=repo_root,
            certificate_path=args.certificate.resolve(),
        )
    write_json(args.output.resolve(), payload)
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
