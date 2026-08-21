#!/usr/bin/env python3
"""Run one deterministic, compressed Haar-MIPT Slurm array cell."""

from __future__ import annotations

import os

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

try:
    from haar_mipt_production import trajectory_seed
    from haar_mipt_transfer import run_trajectory
except ImportError:
    from scripts.haar_mipt_production import trajectory_seed
    from scripts.haar_mipt_transfer import run_trajectory


def trajectory_entropy_fit(record: Mapping) -> dict:
    """Fit cumulative measurement-record entropy per site linearly in time."""
    width = int(record["L"])
    steps = int(record["record_steps"])
    cumulative = np.asarray(record["cumulative_record_cost"], dtype=float)
    times = np.arange(1, steps + 1, dtype=float)
    design = np.column_stack((np.ones_like(times), times))
    coefficients, _, _, _ = np.linalg.lstsq(
        design, cumulative / width, rcond=None
    )
    return {"intercept": float(coefficients[0]), "slope": float(coefficients[1])}


@dataclass(frozen=True)
class BatchResult:
    batch_path: Path
    manifest_path: Path
    resumed: bool


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _write_json_atomic(value, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_cell(run_spec: Mapping, selector: int) -> dict:
    selector = int(selector)
    cells = list(run_spec.get("cells", ()))
    if selector < 1 or selector > len(cells):
        raise ValueError("cell selector must be one-based and within the run spec")
    return dict(cells[selector - 1])


def _metadata(run_spec: Mapping, cell: Mapping) -> dict:
    return {
        "run_id": run_spec["run_id"],
        "settings": dict(run_spec.get("settings", {})),
        "provenance": dict(run_spec.get("provenance", {})),
        "cell_id": cell["cell_id"],
        "params": dict(cell["params"]),
    }


def validate_batch(path: Path, expected_metadata: Mapping | None = None) -> dict:
    with np.load(path, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"].item()))
        count = int(data["sample_index"].size)
        if count <= 0 or data["seed"].shape != (count,):
            raise ValueError("batch identity arrays have inconsistent lengths")
        steps = int(metadata["settings"]["record_multiplier"]) * int(metadata["params"]["L"])
        if data["cumulative_record_cost"].shape != (count, steps):
            raise ValueError("batch cumulative-cost array has the wrong shape")
        if np.any(~np.isfinite(data["cumulative_record_cost"])):
            raise ValueError("batch cumulative costs are not finite")
        if np.unique(data["sample_index"]).size != count:
            raise ValueError("batch contains duplicate sample indices")
        if expected_metadata is not None and _canonical_json(metadata) != _canonical_json(expected_metadata):
            raise ValueError("batch metadata does not match the run cell")
    return metadata


def iter_batch_records(path: Path):
    path = Path(path)
    with np.load(path, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"].item()))
        settings, params = metadata["settings"], metadata["params"]
        for position, sample_index in enumerate(data["sample_index"]):
            yield {
                "schema_version": 1,
                "L": int(params["L"]),
                "p": float(settings["p"]),
                "initial_family": str(params["initial_family"]),
                "sample_index": int(sample_index),
                "seed": int(data["seed"][position]),
                "burn_in_steps": int(settings["burn_in_multiplier"]) * int(params["L"]),
                "record_steps": int(settings["record_multiplier"]) * int(params["L"]),
                "record_cost": float(data["record_cost"][position]),
                "cumulative_record_cost": data["cumulative_record_cost"][position].tolist(),
                "runtime_seconds": float(data["runtime_seconds"][position]),
                "gate_count": int(data["gate_count"][position]),
                "attempted_measurements": int(data["attempted_measurements"][position]),
                "outcome_counts": data["outcome_counts"][position].astype(int).tolist(),
            }


def _write_batch_atomic(records: list[dict], metadata: Mapping, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    arrays = {
        "metadata_json": np.asarray(_canonical_json(metadata)),
        "sample_index": np.asarray([r["sample_index"] for r in records], dtype=np.int64),
        "seed": np.asarray([r["seed"] for r in records], dtype=np.uint64),
        "record_cost": np.asarray([r["record_cost"] for r in records], dtype=float),
        "cumulative_record_cost": np.asarray([r["cumulative_record_cost"] for r in records], dtype=float),
        "runtime_seconds": np.asarray([r["runtime_seconds"] for r in records], dtype=float),
        "gate_count": np.asarray([r["gate_count"] for r in records], dtype=np.int64),
        "attempted_measurements": np.asarray([r["attempted_measurements"] for r in records], dtype=np.int64),
        "outcome_counts": np.asarray([r["outcome_counts"] for r in records], dtype=np.int64),
    }
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    validate_batch(temporary, metadata)
    os.replace(temporary, path)


def run_cell(run_spec: Mapping, selector: int, trajectory_runner=run_trajectory) -> BatchResult:
    cell = select_cell(run_spec, selector)
    settings, params = dict(run_spec["settings"]), dict(cell["params"])
    metadata = _metadata(run_spec, cell)
    cell_dir = Path(run_spec["run_dir"]) / "cells" / cell["cell_id"]
    batch_path, manifest_path = cell_dir / "batch.npz", cell_dir / "manifest.json"
    if batch_path.is_file() and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_batch(batch_path, metadata)
        if manifest.get("status") == "success" and manifest.get("artifact_sha256") == _sha256(batch_path):
            return BatchResult(batch_path, manifest_path, True)

    L = int(params["L"])
    family = str(params["initial_family"])
    block = int(params.get("block_index", 0))
    per_cell = int(settings["samples_per_cell"])
    total = int(settings["samples_per_family_width"])
    start, stop = block * per_cell, min((block + 1) * per_cell, total)
    if start < 0 or stop <= start:
        raise ValueError("cell has an empty sample range")
    records, slopes, started = [], [], time.monotonic()
    progress_every = max(1, (stop - start) // 25)
    for completed, sample_index in enumerate(range(start, stop), start=1):
        seed = trajectory_seed(settings["base_seed"], L, family, sample_index)
        record = dict(trajectory_runner(
            L=L, p=float(settings["p"]), seed=seed, initial_family=family,
            burn_in_steps=int(settings["burn_in_multiplier"]) * L,
            record_steps=int(settings["record_multiplier"]) * L,
        ))
        record["sample_index"] = sample_index
        records.append(record)
        slopes.append(trajectory_entropy_fit(record)["slope"])
        if completed % progress_every == 0 or completed == stop - start:
            elapsed = time.monotonic() - started
            remaining = elapsed * ((stop - start) / completed - 1.0)
            print(
                f"{cell['cell_id']} {completed}/{stop-start} elapsed={elapsed:.1f}s "
                f"remaining={remaining:.1f}s mean_slope={np.mean(slopes):.9f}",
                flush=True,
            )

    _write_batch_atomic(records, metadata, batch_path)
    manifest = {
        "status": "success",
        "cell_id": cell["cell_id"],
        "samples_expected": stop - start,
        "samples_valid": len(records),
        "artifact": batch_path.name,
        "artifact_sha256": _sha256(batch_path),
        "sample_index_start": start,
        "sample_index_stop": stop,
        "mean_runtime_seconds": float(np.mean([r["runtime_seconds"] for r in records])),
        "mean_entropy_density_slope": float(np.mean(slopes)),
        **metadata,
    }
    _write_json_atomic(manifest, manifest_path)
    return BatchResult(batch_path, manifest_path, False)


def main() -> int:
    spec_path = os.environ.get("HARNESS_RUN_SPEC")
    selector = os.environ.get("SLURM_ARRAY_TASK_ID", os.environ.get("HARNESS_CELL_INDEX"))
    if not spec_path or not selector:
        raise SystemExit("HARNESS_RUN_SPEC and SLURM_ARRAY_TASK_ID are required")
    with Path(spec_path).open(encoding="utf-8") as handle:
        run_spec = json.load(handle)
    run_cell(run_spec, int(selector))
    return 0


if __name__ == "__main__":
    sys.exit(main())
