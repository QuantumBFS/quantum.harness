"""Isolated-process execution for fair VQE training comparisons."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from vqetape.training_spec import (
    VQETrainingRequest,
    VQETrainingResult,
)


class TrainingWorkerError(RuntimeError):
    """Raised when an isolated training process fails."""


def run_training_fresh_process(
    request: VQETrainingRequest,
    *,
    timeout_seconds: float = 900,
) -> VQETrainingResult:
    """Execute one request with fresh JAX and allocator state."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    with tempfile.TemporaryDirectory(
        prefix="vqetape-training-"
    ) as directory:
        root = Path(directory)
        request_path = root / "request.json"
        result_path = root / "result.json"
        cache_path = root / "jax-cache"
        request_path.write_text(
            json.dumps(
                request.to_dict(),
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        environment = dict(os.environ)
        environment["JAX_COMPILATION_CACHE_DIR"] = str(
            cache_path
        )
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "vqetape.training_worker",
                    "--request",
                    str(request_path),
                    "--output",
                    str(result_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise TrainingWorkerError(
                "training worker exceeded "
                f"{timeout_seconds:g} seconds"
            ) from exc
        if completed.returncode != 0:
            details = completed.stderr.strip()
            if completed.stdout.strip():
                details = (
                    f"{details}\n{completed.stdout.strip()}"
                ).strip()
            raise TrainingWorkerError(
                "training worker exited with status "
                f"{completed.returncode}: {details}"
            )
        if not result_path.exists():
            raise TrainingWorkerError(
                "training worker produced no result"
            )
        payload = json.loads(
            result_path.read_text(encoding="utf-8")
        )
        worker_pid = payload.pop("worker_pid", None)
        parent_pid = payload.pop("parent_pid", None)
        if worker_pid is None or worker_pid == os.getpid():
            raise TrainingWorkerError(
                "training worker did not run in a fresh process"
            )
        if parent_pid != os.getpid():
            raise TrainingWorkerError(
                "training worker parent identity mismatch"
            )
        return VQETrainingResult.from_dict(payload)
