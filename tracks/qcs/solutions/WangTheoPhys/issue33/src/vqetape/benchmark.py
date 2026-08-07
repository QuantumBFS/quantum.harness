"""Parent-side fresh-process benchmark orchestration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from vqetape.selection import CandidateResult
from vqetape.spec import (
    ProgramConfig,
    SpatialProgramConfig,
    TFIMVQESpec,
    TensorProgramConfig,
)
from vqetape.subprocess_env import worker_environment


def _invalid_result(
    config: ProgramConfig | TensorProgramConfig | SpatialProgramConfig,
    failure: str,
    parent_pid: int,
) -> CandidateResult:
    return CandidateResult(
        config=config,
        valid=False,
        failure=failure,
        parent_pid=parent_pid,
    )


def benchmark_candidate(
    *,
    spec: TFIMVQESpec,
    config: ProgramConfig,
    seed: int,
    warm_repeats: int,
    timeout_seconds: float,
) -> CandidateResult:
    """Measure one candidate in a clean Python subprocess."""

    parent_pid = os.getpid()
    payload = {
        "program_kind": "statevector",
        "spec": spec.to_dict(),
        "config": config.to_dict(),
        "seed": seed,
        "warm_repeats": warm_repeats,
        "parent_pid": parent_pid,
    }
    with tempfile.TemporaryDirectory(prefix="vqetape-") as directory:
        request_path = Path(directory) / "request.json"
        result_path = Path(directory) / "result.json"
        request_path.write_text(json.dumps(payload), encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "vqetape.worker",
            "--request-json",
            str(request_path),
            "--result-json",
            str(result_path),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=worker_environment(),
            )
        except subprocess.TimeoutExpired:
            return _invalid_result(
                config,
                f"worker timed out after {timeout_seconds:.3f} seconds",
                parent_pid,
            )
        if not result_path.exists():
            detail = completed.stderr.strip() or completed.stdout.strip()
            return _invalid_result(
                config,
                f"worker produced no result (exit={completed.returncode}): {detail}",
                parent_pid,
            )
        try:
            result = CandidateResult.from_dict(
                json.loads(result_path.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return _invalid_result(
                config,
                f"malformed worker result: {type(exc).__name__}: {exc}",
                parent_pid,
            )
        if completed.returncode != 0 and result.valid:
            return _invalid_result(
                config,
                f"worker exited {completed.returncode} despite valid result",
                parent_pid,
            )
        return result


def benchmark_tn_candidate(
    *,
    spec: TFIMVQESpec,
    config: TensorProgramConfig,
    seed: int,
    warm_repeats: int,
    timeout_seconds: float,
) -> CandidateResult:
    """Measure one direct tensor-network candidate in a clean subprocess."""

    parent_pid = os.getpid()
    payload = {
        "program_kind": "direct_tn",
        "spec": spec.to_dict(),
        "config": config.to_dict(),
        "seed": seed,
        "warm_repeats": warm_repeats,
        "parent_pid": parent_pid,
    }
    with tempfile.TemporaryDirectory(prefix="vqetape-tn-") as directory:
        request_path = Path(directory) / "request.json"
        result_path = Path(directory) / "result.json"
        request_path.write_text(json.dumps(payload), encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "vqetape.worker",
            "--request-json",
            str(request_path),
            "--result-json",
            str(result_path),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=worker_environment(),
            )
        except subprocess.TimeoutExpired:
            return _invalid_result(
                config,
                f"worker timed out after {timeout_seconds:.3f} seconds",
                parent_pid,
            )
        if not result_path.exists():
            detail = completed.stderr.strip() or completed.stdout.strip()
            return _invalid_result(
                config,
                f"worker produced no result (exit={completed.returncode}): {detail}",
                parent_pid,
            )
        try:
            result = CandidateResult.from_dict(
                json.loads(result_path.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return _invalid_result(
                config,
                f"malformed worker result: {type(exc).__name__}: {exc}",
                parent_pid,
            )
        if completed.returncode != 0 and result.valid:
            return _invalid_result(
                config,
                f"worker exited {completed.returncode} despite valid result",
                parent_pid,
            )
        return result


def benchmark_spatial_candidate(
    *,
    spec: TFIMVQESpec,
    config: SpatialProgramConfig,
    seed: int,
    warm_repeats: int,
    timeout_seconds: float,
) -> CandidateResult:
    """Measure one spatial-transfer candidate in a clean subprocess."""

    parent_pid = os.getpid()
    payload = {
        "program_kind": "spatial_transfer",
        "spec": spec.to_dict(),
        "config": config.to_dict(),
        "seed": seed,
        "warm_repeats": warm_repeats,
        "parent_pid": parent_pid,
    }
    with tempfile.TemporaryDirectory(
        prefix="vqetape-spatial-"
    ) as directory:
        request_path = Path(directory) / "request.json"
        result_path = Path(directory) / "result.json"
        request_path.write_text(json.dumps(payload), encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "vqetape.worker",
            "--request-json",
            str(request_path),
            "--result-json",
            str(result_path),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=worker_environment(),
            )
        except subprocess.TimeoutExpired:
            return _invalid_result(
                config,
                f"worker timed out after {timeout_seconds:.3f} seconds",
                parent_pid,
            )
        if not result_path.exists():
            detail = completed.stderr.strip() or completed.stdout.strip()
            return _invalid_result(
                config,
                f"worker produced no result "
                f"(exit={completed.returncode}): {detail}",
                parent_pid,
            )
        try:
            result = CandidateResult.from_dict(
                json.loads(result_path.read_text(encoding="utf-8"))
            )
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            return _invalid_result(
                config,
                f"malformed worker result: "
                f"{type(exc).__name__}: {exc}",
                parent_pid,
            )
        if completed.returncode != 0 and result.valid:
            return _invalid_result(
                config,
                f"worker exited {completed.returncode} despite valid result",
                parent_pid,
            )
        return result
