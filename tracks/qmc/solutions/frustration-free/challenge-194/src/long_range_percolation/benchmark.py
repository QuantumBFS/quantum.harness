from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Mapping, Sequence
import uuid


BENCHMARK_SCHEMA = "challenge-194-benchmark-v1"
WORKER_SCHEMA = "challenge-194-benchmark-worker-v1"
BENCHMARK_LENGTHS = (2**10, 2**14, 2**18)
BENCHMARK_SIGMAS = (0.8, 0.9, 1.0, 1.1)
BENCHMARK_KAPPAS = tuple(
    value for value in (0.25 * 1.25**j for j in range(32)) if value <= 6.0
)
STEADY_RUNS = 5
WALL_LIMIT_SECONDS = 120.0
RSS_LIMIT_BYTES = 4 * 1024**3
GATE_LENGTH = 2**18
QUADRATIC_MAX_LENGTH = 256
BACKENDS = ("quadratic", "geometric", "poisson-numba")
WORKER_MODES = ("compile", "steady", "measure-observables")
ONE_THREAD_ENVIRONMENT = {
    "NUMBA_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
}

_MAX_REPORT_BYTES = 16 * 1024 * 1024
_MAX_VALIDATION_BYTES = 256 * 1024 * 1024
_TIMING_FIELDS = {
    "startup",
    "cache_load_warmup",
    "compile",
    "sampling",
    "observable",
    "artifact_serialization",
    "wall",
    "cpu",
}
_METRIC_FIELDS = {
    "events",
    "unique_edges",
    "unions",
    "duplicates",
    "total_probes",
    "maximum_probe",
    "rehashes",
    "bytes",
}
_RUNTIME_CAPABILITY_FIELDS = {
    "schema_version",
    "python",
    "implementation",
    "platform",
    "machine",
    "numpy",
    "scipy",
    "h5py",
    "numba",
    "llvmlite",
    "cpu_name",
    "cpu_features",
    "threading_layer",
    "numba_disable_jit",
    "fastmath",
    "boundscheck",
}


@dataclass(frozen=True)
class BenchmarkProtocol:
    lengths: tuple[int, ...]
    sigmas: tuple[float, ...]
    kappas: tuple[float, ...]
    steady_runs: int
    wall_limit_seconds: float
    rss_limit_bytes: int
    gate_length: int
    backends: tuple[str, ...]
    quadratic_max_length: int
    validation_report: Path | None
    name: str

    @classmethod
    def production_v1(cls) -> BenchmarkProtocol:
        return cls(
            lengths=BENCHMARK_LENGTHS,
            sigmas=BENCHMARK_SIGMAS,
            kappas=BENCHMARK_KAPPAS,
            steady_runs=STEADY_RUNS,
            wall_limit_seconds=WALL_LIMIT_SECONDS,
            rss_limit_bytes=RSS_LIMIT_BYTES,
            gate_length=GATE_LENGTH,
            backends=BACKENDS,
            quadratic_max_length=QUADRATIC_MAX_LENGTH,
            validation_report=None,
            name="production-v1",
        )

    @classmethod
    def reduced(
        cls,
        *,
        lengths: Sequence[int],
        sigmas: Sequence[float],
        kappas: Sequence[float],
        steady_runs: int,
        gate_length: int,
        wall_limit_seconds: float,
        rss_limit_bytes: int,
        backends: Sequence[str] = ("poisson-numba",),
        validation_report: Path | None = None,
    ) -> BenchmarkProtocol:
        return cls(
            lengths=tuple(lengths),
            sigmas=tuple(float(value) for value in sigmas),
            kappas=tuple(float(value) for value in kappas),
            steady_runs=steady_runs,
            wall_limit_seconds=float(wall_limit_seconds),
            rss_limit_bytes=rss_limit_bytes,
            gate_length=gate_length,
            backends=tuple(backends),
            quadratic_max_length=QUADRATIC_MAX_LENGTH,
            validation_report=validation_report,
            name="reduced",
        )

    def __post_init__(self) -> None:
        if (
            not self.lengths
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 2
                or value % 2
                for value in self.lengths
            )
            or tuple(sorted(set(self.lengths))) != self.lengths
        ):
            raise ValueError("benchmark lengths must be sorted unique even integers")
        if (
            not self.sigmas
            or any(not math.isfinite(value) or value <= 0.0 for value in self.sigmas)
            or len(set(self.sigmas)) != len(self.sigmas)
        ):
            raise ValueError("benchmark sigmas must be unique finite positive values")
        if (
            not self.kappas
            or any(not math.isfinite(value) or value < 0.0 for value in self.kappas)
            or any(
                right <= left for left, right in zip(self.kappas, self.kappas[1:])
            )
        ):
            raise ValueError("benchmark kappas must be sorted unique finite values")
        if (
            isinstance(self.steady_runs, bool)
            or not isinstance(self.steady_runs, int)
            or self.steady_runs < 1
        ):
            raise ValueError("steady_runs must be a positive integer")
        if (
            not math.isfinite(self.wall_limit_seconds)
            or self.wall_limit_seconds <= 0.0
        ):
            raise ValueError("wall limit must be finite and positive")
        if (
            isinstance(self.rss_limit_bytes, bool)
            or not isinstance(self.rss_limit_bytes, int)
            or self.rss_limit_bytes < 1
        ):
            raise ValueError("RSS limit must be a positive integer")
        if self.gate_length not in self.lengths:
            raise ValueError("gate length must be a benchmark length")
        if (
            not self.backends
            or len(set(self.backends)) != len(self.backends)
            or any(value not in BACKENDS for value in self.backends)
        ):
            raise ValueError("benchmark backends are invalid")
        if self.validation_report is not None and not isinstance(
            self.validation_report, Path
        ):
            raise ValueError("validation_report must be a pathlib.Path")

    @property
    def is_production(self) -> bool:
        frozen = BenchmarkProtocol.production_v1()
        return (
            self.lengths == frozen.lengths
            and self.sigmas == frozen.sigmas
            and self.kappas == frozen.kappas
            and self.steady_runs == frozen.steady_runs
            and self.wall_limit_seconds == frozen.wall_limit_seconds
            and self.rss_limit_bytes == frozen.rss_limit_bytes
            and self.gate_length == frozen.gate_length
            and self.backends == frozen.backends
            and self.quadratic_max_length == frozen.quadratic_max_length
            and self.name == frozen.name
        )

    def require_production(self) -> None:
        if not self.is_production:
            raise ValueError("benchmark protocol is not the frozen production protocol")

    def to_document(self) -> dict[str, object]:
        return {
            "name": self.name,
            "lengths": list(self.lengths),
            "sigmas": [value.hex() for value in self.sigmas],
            "kappas": [value.hex() for value in self.kappas],
            "steady_runs": self.steady_runs,
            "wall_limit_seconds": self.wall_limit_seconds.hex(),
            "rss_limit_bytes": self.rss_limit_bytes,
            "gate_length": self.gate_length,
            "backends": list(self.backends),
            "quadratic_max_length": self.quadratic_max_length,
        }


def canonical_report_bytes(report: Mapping[str, object]) -> bytes:
    try:
        return (
            json.dumps(
                report,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as error:
        raise RuntimeError("benchmark report is not canonical finite JSON") from error


def _read_regular_bounded(
    path: Path,
    description: str,
    *,
    maximum_bytes: int = _MAX_REPORT_BYTES,
) -> bytes:
    if not isinstance(path, Path):
        raise RuntimeError(f"{description} path must be a pathlib.Path")
    try:
        metadata = path.lstat()
    except OSError as error:
        raise RuntimeError(f"unable to inspect {description}") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError(f"{description} must be a regular non-symlink file")
    if metadata.st_size > maximum_bytes:
        raise RuntimeError(f"{description} exceeds the byte-size limit")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RuntimeError(f"unable to open {description}") from error
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != metadata.st_dev
            or opened.st_ino != metadata.st_ino
            or opened.st_size > maximum_bytes
        ):
            raise RuntimeError(f"{description} identity changed")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            block = os.read(descriptor, min(remaining, 64 * 1024))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        payload = b"".join(chunks)
        final = os.fstat(descriptor)
        if (
            final.st_dev,
            final.st_ino,
            final.st_size,
            final.st_mtime_ns,
            final.st_ctime_ns,
        ) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        ):
            raise RuntimeError(f"{description} mutated while reading")
        if len(payload) > maximum_bytes:
            raise RuntimeError(f"{description} exceeds the byte-size limit")
        return payload
    finally:
        os.close(descriptor)


def load_correctness_report(
    path: Path, *, production: bool = False
) -> dict[str, object]:
    payload = _read_regular_bounded(
        path,
        "validation report",
        maximum_bytes=_MAX_VALIDATION_BYTES,
    )
    try:
        report = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as error:
        raise RuntimeError("validation report is malformed JSON") from error
    if not isinstance(report, dict):
        raise RuntimeError("validation report must be a JSON object")
    if report.get("schema_version") != "challenge-194-validation-v1":
        raise RuntimeError("validation report schema is invalid")
    checks = report.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or any(
            not isinstance(check, dict) or check.get("passed") is not True
            for check in checks
        )
        or report.get("passed") is not True
    ):
        raise RuntimeError("validation report did not pass every correctness check")
    source = report.get("source")
    if not isinstance(source, dict) or source.get("clean_tree") is not True:
        raise RuntimeError("validation report provenance is not from a clean tree")
    if production:
        from .validation import ValidationProtocol, validate_report_payload

        revision = source.get("source_revision")
        if (
            not isinstance(revision, str)
            or len(revision) != 40
            or any(character not in "0123456789abcdef" for character in revision)
        ):
            raise RuntimeError("validation report source revision is malformed")
        capability = report.get("runtime_capability")
        if (
            not isinstance(capability, dict)
            or capability.get("schema_version") != "challenge-194-runtime-v1"
        ):
            raise RuntimeError("validation report runtime provenance is malformed")
        try:
            validate_report_payload(report, ValidationProtocol.production_v1())
        except (TypeError, ValueError, RuntimeError) as error:
            raise RuntimeError(
                "validation report does not match the frozen correctness protocol"
            ) from error
    canonical_report_bytes(report)
    return report


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[7]


def _git(*arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=_repository_root(),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError(f"unable to collect Git provenance: {error}") from error
    return completed.stdout.strip()


def _provenance(production: bool, validation: Mapping[str, object]) -> dict[str, object]:
    challenge_root = Path(__file__).resolve().parents[2]
    lock = challenge_root / "uv.lock"
    lock_payload = _read_regular_bounded(lock, "uv.lock")
    validation_revision = str(
        (validation.get("source") or {}).get("source_revision", "")
    )
    if not production:
        return {
            "source_revision": validation_revision,
            "clean_tree": None,
            "validation_source_revision": validation_revision,
            "uv_lock_sha256": hashlib.sha256(lock_payload).hexdigest(),
        }
    revision = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    if production:
        if status:
            raise RuntimeError("production benchmark requires a clean repository")
        try:
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", validation_revision, revision],
                cwd=_repository_root(),
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            raise RuntimeError(
                "validation report revision is stale or not an ancestor"
            ) from error
    return {
        "source_revision": revision,
        "clean_tree": not bool(status),
        "validation_source_revision": validation_revision,
        "uv_lock_sha256": hashlib.sha256(lock_payload).hexdigest(),
    }


def _host_evidence() -> dict[str, object]:
    uname = os.uname()
    return {
        "platform": " ".join(
            (uname.sysname, uname.release, uname.version, uname.machine)
        ),
        "machine": uname.machine,
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "cpu_count": os.cpu_count(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "numba", "llvmlite", "h5py")
        },
        "one_thread_environment": dict(ONE_THREAD_ENVIRONMENT),
        "rss_source": (
            "resource.getrusage(RUSAGE_SELF).ru_maxrss*1024"
            if sys.platform.startswith("linux")
            else "unavailable"
        ),
        "affinity_source": (
            "os.sched_getaffinity/os.sched_setaffinity"
            if sys.platform.startswith("linux")
            else "unavailable"
        ),
    }


def _worker_command(
    *,
    mode: str,
    backend: str,
    length: int,
    sigma: float,
    kappas: tuple[float, ...],
    run_id: str,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "long_range_percolation.benchmark",
        "--worker-mode",
        mode,
        "--backend",
        backend,
        "--length",
        str(length),
        "--sigma-hex",
        sigma.hex(),
        "--kappas-hex",
        ",".join(value.hex() for value in kappas),
        "--run-id",
        run_id,
    ]


def _parse_one_json(stdout: str) -> dict[str, object]:
    try:
        decoder = json.JSONDecoder()
        value, end = decoder.raw_decode(stdout)
        if stdout[end:].strip():
            raise RuntimeError("worker did not emit exactly one JSON object")
    except (json.JSONDecodeError, RecursionError) as error:
        raise RuntimeError("worker did not emit exactly one JSON object") from error
    if not isinstance(value, dict):
        raise RuntimeError("worker did not emit exactly one JSON object")
    return value


def validate_worker_payload(
    payload: Mapping[str, object],
    *,
    expected_mode: str,
    expected_backend: str,
    expected_length: int,
    expected_sigma: float,
    expected_kappas: tuple[float, ...],
    expected_run_id: str,
) -> None:
    if not isinstance(payload, Mapping) or payload.get("schema_version") != WORKER_SCHEMA:
        raise RuntimeError("worker schema mismatch")
    expected = {
        "run_id": expected_run_id,
        "mode": expected_mode,
        "backend": expected_backend,
        "length": expected_length,
        "sigma": expected_sigma.hex(),
        "kappas": [value.hex() for value in expected_kappas],
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise RuntimeError("worker identity mismatch")
    if payload.get("status") not in ("passed", "failed"):
        raise RuntimeError("worker status is invalid")
    timings = payload.get("timings_ns")
    if (
        not isinstance(timings, Mapping)
        or set(timings) != _TIMING_FIELDS
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in timings.values()
        )
    ):
        raise RuntimeError("worker timings are malformed")
    metrics = payload.get("metrics")
    if (
        not isinstance(metrics, Mapping)
        or set(metrics) != _METRIC_FIELDS
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in metrics.values()
        )
    ):
        raise RuntimeError("worker metrics are malformed")
    rss = payload.get("peak_rss_bytes")
    cpu = payload.get("selected_cpu")
    affinity = payload.get("affinity")
    if (
        isinstance(rss, bool)
        or not isinstance(rss, int)
        or rss <= 0
        or isinstance(cpu, bool)
        or not isinstance(cpu, int)
        or not isinstance(affinity, list)
        or affinity != [cpu]
    ):
        raise RuntimeError("worker required RSS or affinity telemetry is unavailable")
    warmup = payload.get("warmup")
    if (
        not isinstance(warmup, Mapping)
        or warmup.get("length") != 2
        or warmup.get("completed_before_timing") is not True
    ):
        raise RuntimeError("worker warmup evidence is malformed")
    runtime = payload.get("runtime_capability")
    if (
        not isinstance(runtime, Mapping)
        or set(runtime) != _RUNTIME_CAPABILITY_FIELDS
        or runtime.get("schema_version") != "challenge-194-runtime-v1"
        or runtime.get("numba_disable_jit") is not False
        or runtime.get("fastmath") is not False
        or runtime.get("boundscheck") is not True
    ):
        raise RuntimeError("worker runtime provenance is malformed")
    process = payload.get("process")
    if (
        not isinstance(process, Mapping)
        or isinstance(process.get("pid"), bool)
        or not isinstance(process.get("pid"), int)
    ):
        raise RuntimeError("worker process evidence is malformed")
    canonical_report_bytes(payload)


def _failed_run(
    *,
    mode: str,
    backend: str,
    length: int,
    sigma: float,
    run_id: str,
    kind: str,
    detail: str,
    stdout: str,
    stderr: str,
    exit_status: int | None,
) -> dict[str, object]:
    return {
        "schema_version": WORKER_SCHEMA,
        "run_id": run_id,
        "mode": mode,
        "backend": backend,
        "length": length,
        "sigma": sigma.hex(),
        "status": "failed",
        "failure": {"kind": kind, "detail": detail},
        "stdout": stdout,
        "stderr": stderr,
        "exit_status": exit_status,
    }


def _captured_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="backslashreplace")
    return value


def _run_worker_process(
    *,
    mode: str,
    backend: str,
    length: int,
    sigma: float,
    kappas: tuple[float, ...],
    run_id: str,
    cache_dir: Path,
    timeout_seconds: float,
) -> dict[str, object]:
    command = _worker_command(
        mode=mode,
        backend=backend,
        length=length,
        sigma=sigma,
        kappas=kappas,
        run_id=run_id,
    )
    environment = os.environ.copy()
    environment.update(ONE_THREAD_ENVIRONMENT)
    environment["NUMBA_CACHE_DIR"] = str(cache_dir)
    environment["CHALLENGE194_PARENT_LAUNCH_NS"] = str(time.perf_counter_ns())
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return _failed_run(
            mode=mode,
            backend=backend,
            length=length,
            sigma=sigma,
            run_id=run_id,
            kind="timeout",
            detail=f"parent wall timeout after {timeout_seconds.hex()} seconds",
            stdout=_captured_text(error.stdout),
            stderr=_captured_text(error.stderr),
            exit_status=None,
        )
    except OSError as error:
        return _failed_run(
            mode=mode,
            backend=backend,
            length=length,
            sigma=sigma,
            run_id=run_id,
            kind="spawn-failure",
            detail=f"{type(error).__name__}: {error}",
            stdout="",
            stderr="",
            exit_status=None,
        )
    if completed.returncode != 0:
        stdout = _captured_text(completed.stdout)
        stderr = _captured_text(completed.stderr)
        failure_kind = (
            "allocation-failure"
            if "MemoryError" in stderr or "cannot allocate memory" in stderr.lower()
            else "nonzero-exit"
        )
        return _failed_run(
            mode=mode,
            backend=backend,
            length=length,
            sigma=sigma,
            run_id=run_id,
            kind=failure_kind,
            detail=f"worker exited with status {completed.returncode}",
            stdout=stdout,
            stderr=stderr,
            exit_status=completed.returncode,
        )
    payload = _parse_one_json(completed.stdout)
    validate_worker_payload(
        payload,
        expected_mode=mode,
        expected_backend=backend,
        expected_length=length,
        expected_sigma=sigma,
        expected_kappas=kappas,
        expected_run_id=run_id,
    )
    result = dict(payload)
    result["stdout"] = completed.stdout
    result["stderr"] = completed.stderr
    result["exit_status"] = completed.returncode
    return result


def _make_read_only(directory: Path) -> None:
    for root, directories, files in os.walk(directory):
        for name in files:
            os.chmod(Path(root) / name, 0o444)
        for name in directories:
            os.chmod(Path(root) / name, 0o555)
    os.chmod(directory, 0o555)


def _make_writable(directory: Path) -> None:
    if not directory.exists():
        return
    for root, directories, files in os.walk(directory):
        os.chmod(root, 0o755)
        for name in directories:
            os.chmod(Path(root) / name, 0o755)
        for name in files:
            os.chmod(Path(root) / name, 0o644)


def aggregate_steady_runs(runs: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if not runs or any(run.get("status") != "passed" for run in runs):
        return {
            "run_count": len(runs),
            "passed_run_count": sum(run.get("status") == "passed" for run in runs),
            "median_wall_seconds": None,
            "max_wall_seconds": None,
            "median_cpu_seconds": None,
            "max_cpu_seconds": None,
            "median_peak_rss_bytes": None,
            "max_peak_rss_bytes": None,
            "metric_aggregates": {},
            "raw": [dict(run) for run in runs],
        }
    walls = sorted(
        int(run["timings_ns"]["wall"]) / 1e9  # type: ignore[index]
        for run in runs
    )
    rss = sorted(int(run["peak_rss_bytes"]) for run in runs)
    cpu = sorted(
        int(run["timings_ns"]["cpu"]) / 1e9  # type: ignore[index]
        for run in runs
    )
    middle = len(walls) // 2
    if len(walls) % 2:
        median_wall = walls[middle]
        median_cpu = cpu[middle]
        median_rss: float | int = rss[middle]
    else:
        median_wall = (walls[middle - 1] + walls[middle]) / 2.0
        median_cpu = (cpu[middle - 1] + cpu[middle]) / 2.0
        median_rss = (rss[middle - 1] + rss[middle]) / 2.0
    metric_values = {
        name: [int(run["metrics"][name]) for run in runs]  # type: ignore[index]
        for name in sorted(_METRIC_FIELDS)
    }
    metric_aggregates: dict[str, dict[str, float | int]] = {}
    for name, values in metric_values.items():
        ordered = sorted(values)
        if len(ordered) % 2:
            median: float | int = ordered[middle]
        else:
            median = (ordered[middle - 1] + ordered[middle]) / 2.0
        metric_aggregates[name] = {
            "median": median,
            "maximum": ordered[-1],
        }
    return {
        "run_count": len(runs),
        "passed_run_count": len(runs),
        "median_wall_seconds": median_wall,
        "max_wall_seconds": max(walls),
        "median_cpu_seconds": median_cpu,
        "max_cpu_seconds": max(cpu),
        "median_peak_rss_bytes": median_rss,
        "max_peak_rss_bytes": max(rss),
        "raw_metrics": metric_values,
        "metric_aggregates": metric_aggregates,
        "raw": [dict(run) for run in runs],
    }


def evaluate_gate(
    *,
    aggregates: Sequence[Mapping[str, object]],
    sigmas: tuple[float, ...],
    gate_length: int,
    wall_limit_seconds: float,
    rss_limit_bytes: int,
    correctness_passed: bool,
) -> dict[str, object]:
    cells: list[dict[str, object]] = []
    for sigma in sigmas:
        matches = [
            value
            for value in aggregates
            if value.get("backend") == "poisson-numba"
            and value.get("length") == gate_length
            and value.get("sigma") == sigma.hex()
        ]
        aggregate = matches[0] if len(matches) == 1 else {}
        wall = aggregate.get("max_wall_seconds")
        rss = aggregate.get("max_peak_rss_bytes")
        complete = aggregate.get("run_count") == aggregate.get("passed_run_count")
        wall_passed = (
            complete
            and isinstance(wall, (int, float))
            and not isinstance(wall, bool)
            and wall <= wall_limit_seconds
        )
        rss_passed = (
            complete
            and isinstance(rss, int)
            and not isinstance(rss, bool)
            and rss <= rss_limit_bytes
        )
        cells.append(
            {
                "sigma": sigma.hex(),
                "length": gate_length,
                "max_wall_seconds": wall,
                "wall_limit_seconds": wall_limit_seconds.hex(),
                "wall_passed": wall_passed,
                "max_peak_rss_bytes": rss,
                "rss_limit_bytes": rss_limit_bytes,
                "rss_passed": rss_passed,
                "passed": wall_passed and rss_passed,
            }
        )
    return {
        "correctness_passed": correctness_passed,
        "cells": cells,
        "passed": correctness_passed
        and len(cells) == len(sigmas)
        and all(cell["passed"] for cell in cells),
    }


def _benchmark_cells(
    protocol: BenchmarkProtocol,
) -> list[tuple[str, int, float]]:
    cells: list[tuple[str, int, float]] = []
    for backend in protocol.backends:
        lengths = (
            (protocol.quadratic_max_length,)
            if backend == "quadratic"
            else protocol.lengths
        )
        for length in lengths:
            for sigma in protocol.sigmas:
                cells.append((backend, length, sigma))
    return cells


def _publish_immutable(
    output: Path, report: Mapping[str, object]
) -> None:
    from .artifacts import _publish_json_once

    if not isinstance(output, Path):
        raise ValueError("output must be a pathlib.Path")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise RuntimeError("refusing to publish through a symlink")
    if output.exists():
        raise FileExistsError(f"immutable artifact already exists: {output}")
    try:
        _publish_json_once(output, dict(report), BENCHMARK_SCHEMA)
    except FileExistsError as error:
        raise FileExistsError(
            f"immutable artifact already exists: {output}"
        ) from error


def run_benchmark(
    protocol: BenchmarkProtocol, output: Path
) -> dict[str, object]:
    if not isinstance(protocol, BenchmarkProtocol):
        raise ValueError("protocol must be a BenchmarkProtocol")
    if protocol.validation_report is None:
        raise RuntimeError("validation report is required")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"immutable artifact already exists: {output}")
    correctness = load_correctness_report(
        protocol.validation_report, production=protocol.is_production
    )
    provenance = _provenance(protocol.is_production, correctness)
    correctness_payload = _read_regular_bounded(
        protocol.validation_report,
        "validation report",
        maximum_bytes=_MAX_VALIDATION_BYTES,
    )
    all_runs: list[dict[str, object]] = []
    aggregates: list[dict[str, object]] = []
    runtime_identity: Mapping[str, object] | None = None
    with tempfile.TemporaryDirectory(prefix="challenge-194-benchmark-") as root_name:
        root = Path(root_name)
        try:
            compile_cache = root / "compile"
            compile_cache.mkdir()
            compile_backend = (
                "poisson-numba"
                if "poisson-numba" in protocol.backends
                else protocol.backends[0]
            )
            compile_id = uuid.uuid4().hex
            compile_run = _run_worker_process(
                mode="compile",
                backend=compile_backend,
                length=protocol.gate_length,
                sigma=protocol.sigmas[0],
                kappas=protocol.kappas,
                run_id=compile_id,
                cache_dir=compile_cache,
                timeout_seconds=protocol.wall_limit_seconds + 120.0,
            )
            all_runs.append(compile_run)
            compile_passed = compile_run.get("status") == "passed"
            if compile_passed:
                runtime_identity = compile_run.get("runtime_capability")  # type: ignore[assignment]
                if (
                    protocol.is_production
                    and runtime_identity != correctness.get("runtime_capability")
                ):
                    raise RuntimeError(
                        "worker runtime provenance does not match correctness report"
                    )
                if compile_backend == "poisson-numba" and not any(
                    path.is_file() for path in compile_cache.rglob("*")
                ):
                    raise RuntimeError("compile worker did not populate the Numba cache")
            for cell_index, (backend, length, sigma) in enumerate(
                _benchmark_cells(protocol)
            ):
                steady: list[dict[str, object]] = []
                if compile_passed:
                    for run_index in range(protocol.steady_runs):
                        steady_cache = root / f"steady-{cell_index}-{run_index}"
                        shutil.copytree(compile_cache, steady_cache)
                        _make_read_only(steady_cache)
                        steady_id = uuid.uuid4().hex
                        run = _run_worker_process(
                            mode="steady",
                            backend=backend,
                            length=length,
                            sigma=sigma,
                            kappas=protocol.kappas,
                            run_id=steady_id,
                            cache_dir=steady_cache,
                            timeout_seconds=protocol.wall_limit_seconds + 30.0,
                        )
                        steady.append(run)
                        all_runs.append(run)
                        if (
                            run.get("status") == "passed"
                            and run.get("runtime_capability") != runtime_identity
                        ):
                            raise RuntimeError("worker runtime provenance mismatch")
                        successful_pids = [
                            value.get("process", {}).get("pid")
                            for value in all_runs
                            if value.get("status") == "passed"
                        ]
                        if len(successful_pids) != len(set(successful_pids)):
                            raise RuntimeError(
                                "benchmark workers were not fresh subprocesses"
                            )
                        _make_writable(steady_cache)
                aggregate = aggregate_steady_runs(steady)
                aggregates.append(
                    {
                        "backend": backend,
                        "length": length,
                        "sigma": sigma.hex(),
                        **aggregate,
                    }
                )
        finally:
            _make_writable(root)
    gate = evaluate_gate(
        aggregates=aggregates,
        sigmas=protocol.sigmas,
        gate_length=protocol.gate_length,
        wall_limit_seconds=protocol.wall_limit_seconds,
        rss_limit_bytes=protocol.rss_limit_bytes,
        correctness_passed=bool(correctness["passed"]),
    )
    infrastructure_passed = all(
        run.get("status") == "passed"
        or (
            run.get("mode") == "steady"
            and run.get("failure", {}).get("kind")
            in ("timeout", "allocation-failure")
        )
        for run in all_runs
    )
    report: dict[str, object] = {
        "schema_version": BENCHMARK_SCHEMA,
        "protocol": protocol.to_document(),
        "correctness": {
            "path": str(protocol.validation_report),
            "sha256": hashlib.sha256(correctness_payload).hexdigest(),
            "passed": correctness["passed"],
            "check_count": len(correctness["checks"]),
        },
        "provenance": provenance,
        "host": _host_evidence(),
        "worker_runtime_capability": dict(runtime_identity or {}),
        "runs": all_runs,
        "aggregates": aggregates,
        "gate": gate,
        "infrastructure_passed": infrastructure_passed,
        "passed": infrastructure_passed and bool(gate["passed"]),
    }
    payload = canonical_report_bytes(report)
    if not infrastructure_passed and any(
        run.get("failure", {}).get("kind") not in ("timeout", "nonzero-exit")
        for run in all_runs
        if run.get("status") == "failed"
    ):
        raise RuntimeError("benchmark infrastructure failed before complete measurement")
    _publish_immutable(output, report)
    return report


def _pin_one_cpu() -> tuple[int, list[int]]:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("CPU affinity telemetry is required and unavailable")
    if not hasattr(os, "sched_getaffinity") or not hasattr(os, "sched_setaffinity"):
        raise RuntimeError("CPU affinity telemetry is required and unavailable")
    available = sorted(os.sched_getaffinity(0))
    if not available:
        raise RuntimeError("CPU affinity set is empty")
    selected = available[0]
    try:
        os.sched_setaffinity(0, {selected})
    except OSError as error:
        raise RuntimeError("unable to pin benchmark worker to one CPU") from error
    actual = sorted(os.sched_getaffinity(0))
    if actual != [selected]:
        raise RuntimeError("benchmark worker affinity pin did not take effect")
    return selected, actual


def _peak_rss_bytes() -> int:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("peak RSS telemetry is required and unavailable")
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (ImportError, OSError, ValueError) as error:
        raise RuntimeError("peak RSS telemetry is required and unavailable") from error
    result = int(value) * 1024
    if result <= 0:
        raise RuntimeError("peak RSS telemetry is invalid")
    return result


def _basic_graph_observables(labels, edges) -> tuple[int, int]:
    import numpy as np

    counts = np.bincount(labels)
    component_count = int(counts.size)
    checksum = int(
        np.sum(counts.astype(np.int64) * counts.astype(np.int64), dtype=np.int64)
    )
    return component_count, checksum + int(edges.shape[0])


def _execute_backend(
    backend: str,
    length: int,
    sigma: float,
    kappas: tuple[float, ...],
    *,
    warmup: bool,
) -> tuple[dict[str, int], int, int]:
    import numpy as np

    if backend == "poisson-numba":
        from .alias import build_distance_alias
        from .kernel import periodic_kernel
        from .poisson_sweep import run_poisson_numba
        from .trajectory import TrajectoryRequest

        kernel = periodic_kernel(length, sigma)
        digest = hashlib.sha256(kernel.tobytes(order="C")).hexdigest()
        alias = build_distance_alias(length, sigma, kernel, digest)
        request = TrajectoryRequest(
            length=length,
            sigma=sigma,
            sigma_grid_id=f"benchmark-{sigma.hex()}",
            kappas=np.asarray(kappas, dtype=np.float64),
            master_seed=194_100_000 if warmup else 194_200_000,
            phase="benchmark",
            replica=0,
            kernel_sha256=digest,
        )
        started = time.perf_counter_ns()
        result = run_poisson_numba(request, kernel, alias)
        sampling_ns = time.perf_counter_ns() - started
        observable_started = time.perf_counter_ns()
        final_components = int(result.observables[-1, 1])
        unions = length - final_components
        _ = float(result.observables[:, 4].sum())
        observable_ns = time.perf_counter_ns() - observable_started
        metrics = {
            "events": result.event_count,
            "unique_edges": result.event_count - result.duplicate_count,
            "unions": unions,
            "duplicates": result.duplicate_count,
            "total_probes": int(result.hash_diagnostics[2]),
            "maximum_probe": int(result.hash_diagnostics[3]),
            "rehashes": int(result.hash_diagnostics[4]),
            "bytes": int(
                kernel.nbytes
                + alias.probability.nbytes
                + alias.alias.nbytes
                + alias.multiplicity.nbytes
                + alias.class_weight.nbytes
                + result.observables.nbytes
                + result.terminal_counters.nbytes
                + result.draw_counts.nbytes
                + result.hash_diagnostics.nbytes
            ),
        }
        return metrics, sampling_ns, observable_ns

    from .geometric import sample_geometric
    from .model import ModelSpec
    from .oracle import sample_quadratic

    rng = np.random.default_rng(194_200_000 if not warmup else 194_100_000)
    events = 0
    unique_edges = 0
    unions = 0
    byte_count = 0
    observable_ns = 0
    sampling_started = time.perf_counter_ns()
    sampler = sample_quadratic if backend == "quadratic" else sample_geometric
    for kappa in kappas:
        sample = sampler(
            ModelSpec(length=length, sigma=sigma, kappa=kappa),
            rng,
        )
        events += int(sample.edges.shape[0])
        unique_edges += int(sample.edges.shape[0])
        observable_started = time.perf_counter_ns()
        components, _ = _basic_graph_observables(sample.labels, sample.edges)
        observable_ns += time.perf_counter_ns() - observable_started
        unions += length - components
        byte_count += sample.edges.nbytes + sample.labels.nbytes
    sampling_ns = time.perf_counter_ns() - sampling_started - observable_ns
    return (
        {
            "events": events,
            "unique_edges": unique_edges,
            "unions": unions,
            "duplicates": 0,
            "total_probes": 0,
            "maximum_probe": 0,
            "rehashes": 0,
            "bytes": byte_count,
        },
        sampling_ns,
        observable_ns,
    )


def _worker_main(arguments: argparse.Namespace) -> int:
    launch_text = os.environ.get("CHALLENGE194_PARENT_LAUNCH_NS")
    entered = time.perf_counter_ns()
    startup_ns = 0
    if launch_text is not None:
        try:
            startup_ns = max(0, entered - int(launch_text))
        except ValueError:
            startup_ns = 0
    selected_cpu, affinity = _pin_one_cpu()
    import_started = time.perf_counter_ns()
    from .runtime import runtime_capability

    sigma = float.fromhex(arguments.sigma_hex)
    kappas = tuple(
        float.fromhex(value) for value in arguments.kappas_hex.split(",") if value
    )
    warmup_started = time.perf_counter_ns()
    warmup_metrics, _, _ = _execute_backend(
        arguments.backend, 2, sigma, kappas, warmup=True
    )
    warmup_finished = time.perf_counter_ns()
    import_and_warmup_ns = warmup_finished - import_started
    if arguments.worker_mode == "compile":
        compile_ns = import_and_warmup_ns
        cache_load_warmup_ns = 0
    else:
        compile_ns = 0
        cache_load_warmup_ns = import_and_warmup_ns
    metrics = warmup_metrics
    sampling_ns = 0
    observable_ns = 0
    serialization_ns = 0
    wall_ns = 0
    cpu_ns = 0
    if arguments.worker_mode != "compile":
        wall_started = time.perf_counter_ns()
        cpu_started = time.process_time_ns()
        metrics, sampling_ns, observable_ns = _execute_backend(
            arguments.backend,
            arguments.length,
            sigma,
            kappas,
            warmup=False,
        )
        if arguments.worker_mode == "measure-observables":
            observable_ns += sampling_ns
            sampling_ns = 0
        serialization_started = time.perf_counter_ns()
        json.dumps(metrics, sort_keys=True, separators=(",", ":"))
        serialization_ns = time.perf_counter_ns() - serialization_started
        cpu_ns = time.process_time_ns() - cpu_started
        wall_ns = time.perf_counter_ns() - wall_started
    payload = {
        "schema_version": WORKER_SCHEMA,
        "run_id": arguments.run_id,
        "mode": arguments.worker_mode,
        "backend": arguments.backend,
        "length": arguments.length,
        "sigma": sigma.hex(),
        "kappas": [value.hex() for value in kappas],
        "status": "passed",
        "failure": None,
        "timings_ns": {
            "startup": startup_ns,
            "cache_load_warmup": cache_load_warmup_ns,
            "compile": compile_ns,
            "sampling": sampling_ns,
            "observable": observable_ns,
            "artifact_serialization": serialization_ns,
            "wall": wall_ns,
            "cpu": cpu_ns,
        },
        "metrics": metrics,
        "peak_rss_bytes": _peak_rss_bytes(),
        "selected_cpu": selected_cpu,
        "affinity": affinity,
        "warmup": {"length": 2, "completed_before_timing": True},
        "runtime_capability": runtime_capability(),
        "process": {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "python": sys.executable,
            "platform": platform.platform(),
        },
    }
    sys.stdout.buffer.write(canonical_report_bytes(payload))
    sys.stdout.flush()
    return 0


def cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen Challenge 194 production performance gate."
    )
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker-mode", choices=WORKER_MODES, required=True)
    parser.add_argument("--backend", choices=BACKENDS, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--sigma-hex", required=True)
    parser.add_argument("--kappas-hex", required=True)
    parser.add_argument("--run-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--worker-mode" in arguments:
        return _worker_main(_worker_parser().parse_args(arguments))
    parsed = cli_parser().parse_args(arguments)
    frozen = BenchmarkProtocol.production_v1()
    protocol = BenchmarkProtocol(
        lengths=frozen.lengths,
        sigmas=frozen.sigmas,
        kappas=frozen.kappas,
        steady_runs=frozen.steady_runs,
        wall_limit_seconds=frozen.wall_limit_seconds,
        rss_limit_bytes=frozen.rss_limit_bytes,
        gate_length=frozen.gate_length,
        backends=frozen.backends,
        quadratic_max_length=frozen.quadratic_max_length,
        validation_report=parsed.validation_report,
        name=frozen.name,
    )
    try:
        report = run_benchmark(protocol, parsed.output)
    except Exception as error:
        print(
            f"benchmark infrastructure failure: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print(
        f"benchmark passed={report['passed']} output={parsed.output}",
        flush=True,
    )
    if not report["infrastructure_passed"]:
        return 1
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
