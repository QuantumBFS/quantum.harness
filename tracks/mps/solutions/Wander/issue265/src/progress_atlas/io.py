"""Load the immutable local SCNet snapshot used by the atlas."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def load_final_datasets(snapshot_root: Path) -> dict[str, dict[str, np.ndarray]]:
    result = {}
    for path in sorted((snapshot_root / "final").glob("*.npz")):
        result[path.stem] = load_npz(path)
    return result


def latest_progress_record(path: Path) -> dict:
    records = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith("{"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "t" in record and "job_id" in record:
            records.append(record)
    if not records:
        raise ValueError(f"no progress record in {path}")
    return records[-1]


def load_partial_progress(snapshot_root: Path) -> dict[str, dict]:
    result = {}
    for path in sorted((snapshot_root / "logs").glob("*.out")):
        try:
            record = latest_progress_record(path)
        except ValueError:
            continue
        record["log_path"] = str(path)
        result[record["job_id"]] = record
    return result
