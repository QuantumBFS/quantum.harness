"""Immutable shard, manifest, aggregate, and checksum writers."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pymatching
import stim

from . import __version__
from .config import SimulationRequest
from .geometry import Geometry
from .simulate import SimulationBatch


MANIFEST_SCHEMA = "q66-run-manifest-v1"
INPUT_KEYS = (
    "shot_id",
    "detection_events",
    "syndrome_valid_mask",
    "missing_mask",
    "erasure_mask",
    "loss_mask",
    "reload_request_mask",
    "reload_mask",
    "reload_failure_mask",
)
LABEL_KEYS = (
    "shot_id",
    "logical_observable",
    "decoder_prediction",
    "logical_failure",
    "catastrophic_loss",
    "reload_reset_fault_mask",
)


def _wilson_interval(failures: int, shots: int) -> tuple[float, float]:
    if shots <= 0 or not 0 <= failures <= shots:
        raise ValueError("invalid binomial counts")
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


def _array_schema(batch: SimulationBatch) -> dict[str, dict[str, Any]]:
    result = {}
    for key in set(INPUT_KEYS) | set(LABEL_KEYS):
        array = getattr(batch, key)
        result[key] = {
            "dtype": str(array.dtype),
            "shape_per_shot": list(array.shape[1:]),
        }
    return dict(sorted(result.items()))


def _canonical_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class RunWriter:
    out_dir: Path
    request: SimulationRequest
    geometry: Geometry
    started_at: float = field(default_factory=time.time)
    shard_files: list[dict[str, Any]] = field(default_factory=list)
    total_shots: int = 0
    total_failures: int = 0
    total_catastrophic: int = 0
    total_losses: int = 0
    total_reload_requests: int = 0
    total_reloads: int = 0
    total_reload_failures: int = 0
    total_missing_site_boundaries: int = 0
    distinct_graphs_accumulated: int = 0
    first_schema_batch: SimulationBatch | None = None

    def initialize(self) -> None:
        if self.out_dir.exists() and any(self.out_dir.iterdir()):
            raise FileExistsError(f"output directory is not empty: {self.out_dir}")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._log("run initialized")

    def write_batch(self, shard_index: int, batch: SimulationBatch) -> None:
        if self.first_schema_batch is None:
            self.first_schema_batch = batch
        input_path = self.out_dir / f"shots-{shard_index:05d}.npz"
        label_path = self.out_dir / f"labels-{shard_index:05d}.npz"
        np.savez_compressed(
            input_path,
            **{key: getattr(batch, key) for key in INPUT_KEYS},
        )
        np.savez_compressed(
            label_path,
            **{key: getattr(batch, key) for key in LABEL_KEYS},
        )
        self.shard_files.append(
            {
                "index": shard_index,
                "shot_start": int(batch.shot_id[0]),
                "shot_stop": int(batch.shot_id[-1]) + 1,
                "inputs": input_path.name,
                "labels": label_path.name,
            }
        )
        self.total_shots += len(batch.shot_id)
        self.total_failures += int(np.count_nonzero(batch.logical_failure))
        self.total_catastrophic += int(np.count_nonzero(batch.catastrophic_loss))
        self.total_losses += int(np.count_nonzero(batch.loss_mask))
        self.total_reload_requests += int(np.count_nonzero(batch.reload_request_mask))
        self.total_reloads += int(np.count_nonzero(batch.reload_mask))
        self.total_reload_failures += int(np.count_nonzero(batch.reload_failure_mask))
        self.total_missing_site_boundaries += int(np.count_nonzero(batch.missing_mask))
        self.distinct_graphs_accumulated += batch.distinct_graphs
        self._log(
            f"wrote shard={shard_index} shots={len(batch.shot_id)} "
            f"failures={int(np.count_nonzero(batch.logical_failure))}"
        )

    def finalize(self) -> dict[str, Any]:
        if self.first_schema_batch is None or self.total_shots != self.request.shots:
            raise RuntimeError(
                f"wrote {self.total_shots} shots, expected {self.request.shots}"
            )
        elapsed = time.time() - self.started_at
        lower, upper = _wilson_interval(self.total_failures, self.total_shots)
        compressed_bytes = sum(
            path.stat().st_size
            for path in self.out_dir.glob("*.npz")
            if path.is_file()
        )
        aggregate = {
            "run_id": self.request.run_id,
            "shots": self.total_shots,
            "logical_failures": self.total_failures,
            "logical_error_rate": self.total_failures / self.total_shots,
            "wilson_95_lower": lower,
            "wilson_95_upper": upper,
            "catastrophic_shots": self.total_catastrophic,
            "loss_events": self.total_losses,
            "reload_requests": self.total_reload_requests,
            "reload_successes": self.total_reloads,
            "reload_failures": self.total_reload_failures,
            "missing_site_boundaries": self.total_missing_site_boundaries,
            "wall_seconds": elapsed,
            "shots_per_second": self.total_shots / elapsed,
            "compressed_npz_bytes": compressed_bytes,
            "bytes_per_shot": compressed_bytes / self.total_shots,
            "distinct_graphs_accumulated": self.distinct_graphs_accumulated,
        }
        pd.DataFrame([aggregate]).to_parquet(
            self.out_dir / "aggregates.parquet", index=False
        )
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "run_id": self.request.run_id,
            "status": "completed",
            "request": self.request.as_dict(),
            "instance": {
                "instance_id": self.geometry.instance_id,
                "provenance": self.geometry.provenance,
                "site_order": [site.site_id for site in self.geometry.sites],
                "check_order": [
                    check.check_id for check in self.geometry.relevant_checks
                ],
            },
            "decoder": {
                "name": "mask-conditioned-pymatching",
                "pymatching_version": pymatching.__version__,
                "data_probability": 2.0 * self.request.p / 3.0,
                "measurement_probability": self.request.p_m,
                "erasure_weight": 0.0,
            },
            "environment": {
                "mode": "locked-venv-slurm",
                "environment_lock_sha256": self.request.environment_lock_sha256,
                "container_hash": None,
                "python": platform.python_version(),
                "platform": platform.platform(),
                "numpy": np.__version__,
                "stim": stim.__version__,
                "reload_qec": __version__,
                "slurm_job_id": os.environ.get("SLURM_JOB_ID", "not-under-slurm"),
            },
            "source_commit": self.request.source_commit,
            "shot_range": [
                self.request.shot_start,
                self.request.shot_start + self.request.shots,
            ],
            "input_keys": list(INPUT_KEYS),
            "label_keys": list(LABEL_KEYS),
            "array_schema": _array_schema(self.first_schema_batch),
            "shards": self.shard_files,
            "aggregate": aggregate,
            "artifacts": [
                "manifest.json",
                "aggregates.parquet",
                "run.log",
                "checksums.sha256",
            ],
        }
        _canonical_json(self.out_dir / "manifest.json", manifest)
        self._log("run finalized")
        checksum_paths = sorted(
            path
            for path in self.out_dir.iterdir()
            if path.is_file() and path.name != "checksums.sha256"
        )
        checksum_text = "".join(
            f"{_sha256(path)}  {path.name}\n" for path in checksum_paths
        )
        (self.out_dir / "checksums.sha256").write_text(
            checksum_text, encoding="ascii"
        )
        return manifest

    def _log(self, message: str) -> None:
        with (self.out_dir / "run.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{time.time():.6f} {message}\n")
