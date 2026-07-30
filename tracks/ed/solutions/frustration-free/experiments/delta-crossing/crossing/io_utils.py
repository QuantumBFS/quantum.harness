"""I/O utilities: deterministic filenames, checkpoint/resume, CSV/metadata output."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np


def _encode_float(value: float, precision: int = 10) -> str:
    """Deterministic, filename-safe float encoding.

    >>> _encode_float(-0.5)
    'm0p5000000000'
    >>> _encode_float(1.0)
    '1p0000000000'
    """
    rounded = round(value, precision)
    s = f"{rounded:+.{precision}f}"
    s = s.replace("+", "").replace("-", "m").replace(".", "p")
    return s


def result_path(results_dir: Path, L: int, T: float, dt: float) -> Path:
    """Deterministic checkpoint path for a single (L, T, dt) run."""
    stem = f"crossing_L{L}_T{_encode_float(T)}_dt{_encode_float(dt)}"
    return results_dir / f"{stem}.npz"


# CSV field names
CSV_FIELDS = [
    "L", "U", "Delta", "delta0", "T", "dt",
    "E_i", "E_f", "F_GS", "P_ex",
    "max_norm_error", "residual_i", "residual_f",
    "wall_time_s", "n_steps", "converged",
]

DT_CONVERGENCE_FIELDS = [
    "L", "T", "dt", "P_ex", "max_norm_error", "wall_time_s", "n_steps",
]


def save_result(result: dict, path: Path) -> None:
    """Save a per-(L, T, dt) result dict as compressed NPZ."""
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {}
    for key, value in result.items():
        if isinstance(value, (int, float, bool, str)):
            arrays[key] = np.array(value)
        elif isinstance(value, np.ndarray):
            arrays[key] = value
        else:
            arrays[key] = np.array(value)
    np.savez_compressed(path, **arrays)


def load_result(path: Path) -> dict | None:
    """Load a checkpoint result dict, or None if missing/corrupt."""
    if not path.exists():
        return None
    try:
        data = np.load(path, allow_pickle=False)
        result = {}
        for key in data.files:
            arr = data[key]
            if arr.ndim == 0:
                val = arr.item()
                result[key] = val
            else:
                result[key] = arr
        data.close()
        return result
    except Exception:
        return None


def write_csv(results: list[dict], path: Path, fields: list[str] | None = None) -> None:
    """Write a list of result dicts to CSV."""
    if fields is None:
        fields = CSV_FIELDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)


def write_metadata(results_dir: Path, config: dict) -> None:
    """Write config as formatted JSON metadata."""
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "metadata.json").write_text(
        json.dumps(config, indent=2) + "\n"
    )
