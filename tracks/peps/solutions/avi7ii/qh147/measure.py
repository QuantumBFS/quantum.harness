from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

from .checkpoint import load_checkpoint
from .contract import BoundaryContractor


@dataclass(frozen=True)
class MeasurementResult:
    dense_count: int
    public_count: int
    dense_path: Path
    public_path: Path
    manifest_path: Path


def local_polynomial_derivative(
    beta,
    values,
    *,
    degree: int = 3,
    window: int = 5,
) -> np.ndarray:
    beta = np.asarray(beta, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if beta.ndim != 1 or values.ndim != 1 or beta.shape != values.shape:
        raise ValueError("beta and values must be equal one-dimensional arrays")
    if degree < 1 or window < degree + 1 or window % 2 == 0:
        raise ValueError("derivative window must be odd and exceed the degree")
    if len(beta) < window:
        raise ValueError("derivative grid is smaller than the fit window")
    if not np.isfinite(beta).all() or not np.isfinite(values).all():
        raise ValueError("derivative inputs must be finite")
    if np.any(np.diff(beta) <= 0):
        raise ValueError("beta grid must be strictly increasing")

    result = np.empty_like(values)
    half = window // 2
    for index, center in enumerate(beta):
        start = min(max(index - half, 0), len(beta) - window)
        stop = start + window
        coefficients = np.polynomial.polynomial.polyfit(
            beta[start:stop] - center,
            values[start:stop],
            degree,
        )
        result[index] = coefficients[1]
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty measurement table")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def measure_chain(
    checkpoint_root: Path,
    output: Path,
    *,
    expected_config_sha256: str,
    j: float,
    h: float,
    chi: int,
    cutoff: float,
    contractor_factory=None,
    delta_beta: float = 0.025,
    beta_stop: float = 1.0,
    public_step: float = 0.1,
) -> MeasurementResult:
    checkpoint_root = Path(checkpoint_root)
    output = Path(output)
    if chi < 1:
        raise ValueError("measurement chi must be positive")
    if not math.isfinite(cutoff) or cutoff < 0:
        raise ValueError("measurement cutoff must be finite and non-negative")
    for name, value in (
        ("delta beta", delta_beta),
        ("beta stop", beta_stop),
        ("public step", public_step),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    steps = round(beta_stop / delta_beta)
    public_stride = round(public_step / delta_beta)
    if not math.isclose(steps * delta_beta, beta_stop, abs_tol=1e-12):
        raise ValueError("beta stop must be an exact delta-beta multiple")
    if not math.isclose(
        public_stride * delta_beta,
        public_step,
        abs_tol=1e-12,
    ):
        raise ValueError("public step must be an exact delta-beta multiple")
    if output.name != f"chi-{chi}":
        raise ValueError("measurement output must end in chi-<value>")

    existing_manifest = output / "manifest.json"
    if existing_manifest.exists():
        existing = json.loads(existing_manifest.read_text(encoding="utf-8"))
        if (
            existing.get("config_sha256") != expected_config_sha256
            or existing.get("chi") != chi
        ):
            raise ValueError("measurement output belongs to another configuration")

    contractor_builder = contractor_factory or (
        lambda requested_chi, requested_cutoff: BoundaryContractor(
            chi=requested_chi,
            cutoff=requested_cutoff,
        )
    )
    contractor = contractor_builder(chi, cutoff)
    rows = []
    mode = None
    for step in range(1, steps + 1):
        beta = round(step * delta_beta, 12)
        path = checkpoint_root / f"beta-{beta:.6f}"
        if not (path / "metadata.json").is_file():
            raise ValueError(f"missing checkpoint at beta {beta:g}")
        checkpoint = load_checkpoint(
            path,
            expected_config_sha256=expected_config_sha256,
        )
        if mode is None:
            mode = checkpoint.mode
        elif checkpoint.mode != mode:
            raise ValueError("measurement checkpoint modes are inconsistent")
        point = contractor.thermodynamic_point(
            checkpoint.pepo,
            j=j,
            h=h,
            log_scale=checkpoint.log_scale,
        ).as_floats()
        hermiticity = float(contractor.hermiticity_residual(checkpoint.pepo))
        if not all(
            math.isfinite(value)
            for value in (point.z, point.u, hermiticity)
        ):
            raise FloatingPointError("measurement diagnostic is non-finite")
        rows.append(
            {
                "beta": beta,
                "z": point.z,
                "f": -point.z / beta,
                "u": point.u,
                "c": 0.0,
                "hermiticity_residual": hermiticity,
                "mode": mode,
                "chi": chi,
                "cutoff": cutoff,
            }
        )

    beta_values = np.array([row["beta"] for row in rows], dtype=np.float64)
    energy_values = np.array([row["u"] for row in rows], dtype=np.float64)
    derivative = local_polynomial_derivative(beta_values, energy_values)
    specific_heat = -(beta_values**2) * derivative
    for row, value in zip(rows, specific_heat, strict=True):
        row["c"] = float(value)

    public_rows = [
        row for index, row in enumerate(rows, start=1) if index % public_stride == 0
    ]
    dense_path = output / "dense.csv"
    public_path = output / "thermodynamics.csv"
    manifest_path = output / "manifest.json"
    _atomic_csv(dense_path, rows)
    _atomic_csv(public_path, public_rows)
    _atomic_json(
        manifest_path,
        {
            "status": "success",
            "config_sha256": expected_config_sha256,
            "mode": mode,
            "chi": chi,
            "cutoff": cutoff,
            "dense_count": len(rows),
            "public_count": len(public_rows),
            "dense_sha256": _sha256(dense_path),
            "thermodynamics_sha256": _sha256(public_path),
        },
    )
    return MeasurementResult(
        dense_count=len(rows),
        public_count=len(public_rows),
        dense_path=dense_path,
        public_path=public_path,
        manifest_path=manifest_path,
    )
