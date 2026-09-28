#!/usr/bin/env python3
"""Validate spin flip, conservation, current sign, and Czz for paired smoke data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_dataset import load_research_dataset


def _continuity_residual(
    m: np.ndarray,
    current: np.ndarray,
    t: np.ndarray,
) -> dict[str, float]:
    if current.shape != (t.size, m.shape[1] - 1):
        raise ValueError("Current must live on the L-1 open-chain bonds")
    dt = np.diff(t)
    if not np.allclose(dt, dt[0], rtol=0.0, atol=1e-13):
        raise ValueError("Continuity validation requires uniform output times")
    dmdt = (m[2:] - m[:-2]) / (2.0 * dt[0])
    divergence = np.zeros_like(dmdt)
    divergence[:, 0] = current[1:-1, 0]
    divergence[:, -1] = -current[1:-1, -1]
    divergence[:, 1:-1] = (
        current[1:-1, 1:] - current[1:-1, :-1]
    )
    residual = dmdt + divergence
    derivative_norm = max(float(np.linalg.norm(dmdt)), 1e-30)
    return {
        "rms": float(np.sqrt(np.mean(residual**2))),
        "maximum_absolute": float(np.max(np.abs(residual))),
        "relative_l2": float(np.linalg.norm(residual) / derivative_norm),
    }


def validate_pair(up_path: Path, down_path: Path) -> dict[str, object]:
    up = load_research_dataset(up_path)
    down = load_research_dataset(down_path)
    if up.m is None or down.m is None:
        raise ValueError("Both datasets need physical magnetization")
    if up.current is None or down.current is None:
        raise ValueError("Both datasets need local spin current")
    if up.czz is None or down.czz is None:
        raise ValueError("Both datasets need connected Czz")
    np.testing.assert_allclose(up.x, down.x)
    np.testing.assert_allclose(up.t, down.t)

    spin_flip_m = float(np.max(np.abs(up.m + down.m)))
    spin_flip_current = float(np.max(np.abs(up.current + down.current)))
    spin_flip_czz = float(np.max(np.abs(up.czz - down.czz)))
    drift_up = float(
        np.max(np.abs(np.sum(up.m, axis=1) - np.sum(up.m[0])))
    )
    drift_down = float(
        np.max(np.abs(np.sum(down.m, axis=1) - np.sum(down.m[0])))
    )
    continuity_up = _continuity_residual(up.m, up.current, up.t)
    continuity_down = _continuity_residual(down.m, down.current, down.t)
    thresholds = {
        "spin_flip_absolute": 1e-10,
        "magnetization_drift_absolute": 1e-10,
        "continuity_relative_l2": 2e-3,
    }
    checks = {
        "magnetization_spin_flip": (
            spin_flip_m < thresholds["spin_flip_absolute"]
        ),
        "current_spin_flip": (
            spin_flip_current < thresholds["spin_flip_absolute"]
        ),
        "czz_spin_flip": spin_flip_czz < thresholds["spin_flip_absolute"],
        "magnetization_conservation": (
            max(drift_up, drift_down)
            < thresholds["magnetization_drift_absolute"]
        ),
        "lattice_continuity_equation": (
            max(
                continuity_up["relative_l2"],
                continuity_down["relative_l2"],
            )
            < thresholds["continuity_relative_l2"]
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "inputs": {"up": str(up_path.resolve()), "down": str(down_path.resolve())},
        "thresholds": thresholds,
        "checks": checks,
        "metrics": {
            "spin_flip_m_max_abs": spin_flip_m,
            "spin_flip_current_max_abs": spin_flip_current,
            "spin_flip_czz_max_abs": spin_flip_czz,
            "total_magnetization_drift_up": drift_up,
            "total_magnetization_drift_down": drift_down,
            "continuity_up": continuity_up,
            "continuity_down": continuity_down,
        },
    }


def _report(summary: dict[str, object]) -> str:
    metrics = summary["metrics"]
    continuity_up = metrics["continuity_up"]
    continuity_down = metrics["continuity_down"]
    checks = summary["checks"]
    lines = [
        "# TeNPy high-temperature backend validation",
        "",
        f"**Status:** `{summary['status']}`",
        "",
        "This is a small-chain implementation test, not a hydrodynamic result.",
        "",
        "## Exact/equivariant checks",
        "",
        "| Check | Result |",
        "|---|---:|",
        *[
            f"| {name} | {'pass' if passed else 'fail'} |"
            for name, passed in checks.items()
        ],
        "",
        "## Numerical metrics",
        "",
        f"- max spin-flip defect in magnetization: "
        f"`{metrics['spin_flip_m_max_abs']:.6e}`",
        f"- max spin-flip defect in current: "
        f"`{metrics['spin_flip_current_max_abs']:.6e}`",
        f"- max spin-flip defect in connected Czz: "
        f"`{metrics['spin_flip_czz_max_abs']:.6e}`",
        f"- total magnetization drift (up/down): "
        f"`{metrics['total_magnetization_drift_up']:.6e}` / "
        f"`{metrics['total_magnetization_drift_down']:.6e}`",
        f"- continuity relative L2 (up/down): "
        f"`{continuity_up['relative_l2']:.6e}` / "
        f"`{continuity_down['relative_l2']:.6e}`",
        "",
        "The continuity residual uses a centred finite difference between "
        "saved output times; it therefore includes measurement-time "
        "discretization in addition to TEBD error.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    smoke_root = ROOT / "results_research_program" / "tenpy_smoke"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--up",
        type=Path,
        default=smoke_root
        / "amp_mu005_up__convergence__coarse__smoke.npz",
    )
    parser.add_argument(
        "--down",
        type=Path,
        default=smoke_root
        / "amp_mu005_down__convergence__coarse__smoke.npz",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=smoke_root / "validation",
    )
    args = parser.parse_args()
    summary = validate_pair(args.up, args.down)
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    (args.outdir / "REPORT.md").write_text(_report(summary))
    print(json.dumps(summary, ensure_ascii=False))
    if summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
