"""Checkpoint, CSV, and NPZ I/O for gap landscape data."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from .gaps import GapPointResult


def _encode_float(value: float) -> str:
    """Deterministic filename-safe float encoding."""
    text = f"{value:+.10f}"
    return text.replace(".", "p").replace("+", "").replace("-", "m")


def checkpoint_path(results_dir: Path, delta: float, Delta: float, L: int) -> Path:
    """Deterministic per-point checkpoint filename."""
    d_stem = _encode_float(delta)
    D_stem = _encode_float(Delta)
    return results_dir / f"gap_L{L}_delta{d_stem}_Delta{D_stem}.npz"


def save_checkpoint(result: GapPointResult, path: Path) -> None:
    """Save a single point as compressed NPZ."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        L=np.array([result.L]),
        delta=np.array([result.delta]),
        Delta=np.array([result.Delta]),
        U=np.array([result.U]),
        E0_half=np.array([result.E0_half]),
        E1_half=np.array([result.E1_half]),
        E0_triplet=np.array([result.E0_triplet]),
        E0_charge_up=np.array([result.E0_charge_up]),
        E0_charge_down=np.array([result.E0_charge_down]),
        Delta_MB=np.array([result.Delta_MB]),
        Delta_s=np.array([result.Delta_s]),
        Delta_c=np.array([result.Delta_c]),
        residuals_json=json.dumps(result.residuals),
        converged_json=json.dumps(result.converged),
        dimensions_json=json.dumps(result.dimensions),
        wall_time_s=np.array([result.wall_time_s]),
        method=np.array([result.method]),
    )


def load_checkpoint(path: Path) -> GapPointResult | None:
    """Load a checkpoint, or None if missing/corrupt."""
    if not path.exists():
        return None
    try:
        data = np.load(path, allow_pickle=False)
        return GapPointResult(
            L=int(data["L"][0]),
            delta=float(data["delta"][0]),
            Delta=float(data["Delta"][0]),
            U=float(data["U"][0]),
            E0_half=float(data["E0_half"][0]),
            E1_half=float(data["E1_half"][0]),
            E0_triplet=float(data["E0_triplet"][0]),
            E0_charge_up=float(data["E0_charge_up"][0]),
            E0_charge_down=float(data["E0_charge_down"][0]),
            Delta_MB=float(data["Delta_MB"][0]),
            Delta_s=float(data["Delta_s"][0]),
            Delta_c=float(data["Delta_c"][0]),
            residuals=json.loads(str(data["residuals_json"])),
            converged=json.loads(str(data["converged_json"])),
            dimensions=json.loads(str(data["dimensions_json"])),
            wall_time_s=float(data["wall_time_s"][0]),
            method=str(data["method"][0]),
        )
    except Exception:
        return None


CSV_FIELDS = [
    "L", "delta", "Delta", "U",
    "E0_half", "E1_half", "E0_triplet", "E0_charge_up", "E0_charge_down",
    "Delta_MB", "Delta_s", "Delta_c",
    "residual_half", "residual_triplet", "residual_charge_up", "residual_charge_down",
    "converged", "method", "wall_time_s",
]


def write_csv(results: list[GapPointResult], path: Path) -> None:
    """Write merged CSV (one row per (δ, Δ) point)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow({
                "L": r.L, "delta": r.delta, "Delta": r.Delta, "U": r.U,
                "E0_half": r.E0_half, "E1_half": r.E1_half,
                "E0_triplet": r.E0_triplet,
                "E0_charge_up": r.E0_charge_up,
                "E0_charge_down": r.E0_charge_down,
                "Delta_MB": r.Delta_MB, "Delta_s": r.Delta_s,
                "Delta_c": r.Delta_c,
                "residual_half": r.residuals.get("half", -1),
                "residual_triplet": r.residuals.get("triplet", -1),
                "residual_charge_up": r.residuals.get("charge_up", -1),
                "residual_charge_down": r.residuals.get("charge_down", -1),
                "converged": all(r.converged.values()) if r.converged else False,
                "method": r.method, "wall_time_s": r.wall_time_s,
            })


def write_grid_npz(
    results: list[GapPointResult],
    delta_grid: np.ndarray,
    Delta_grid: np.ndarray,
    path: Path,
) -> None:
    """Write structured grid NPZ with 2D gap maps."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n_d = len(delta_grid)
    n_D = len(Delta_grid)

    # build maps, assuming results are in row-major (delta-slow, Delta-fast) order
    def _make_map(attr: str) -> np.ndarray:
        m = np.full((n_d, n_D), np.nan)
        for i, r in enumerate(results):
            id_d = i // n_D
            iD = i % n_D
            if id_d < n_d and iD < n_D:
                m[id_d, iD] = getattr(r, attr)
        return m

    np.savez_compressed(
        path,
        delta_values=delta_grid,
        Delta_values=Delta_grid,
        Delta_MB=_make_map("Delta_MB"),
        Delta_s=_make_map("Delta_s"),
        Delta_c=_make_map("Delta_c"),
        E0_half=_make_map("E0_half"),
        L=np.array([results[0].L]) if results else np.array([0]),
        U=np.array([results[0].U]) if results else np.array([0]),
    )


def write_metadata(results_dir: Path, config: dict) -> None:
    """Write run metadata JSON."""
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "metadata.json").write_text(json.dumps(config, indent=2) + "\n")
