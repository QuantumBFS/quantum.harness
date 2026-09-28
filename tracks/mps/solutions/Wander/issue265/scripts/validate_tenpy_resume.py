#!/usr/bin/env python3
"""Compare an interrupted/resumed TeNPy run with an uninterrupted twin."""

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


def main() -> None:
    root = ROOT / "results_research_program" / "tenpy_smoke"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resumed",
        type=Path,
        default=root / "resume_validation.npz",
    )
    parser.add_argument(
        "--uninterrupted",
        type=Path,
        default=root / "resume_validation_uninterrupted.npz",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=root / "resume_validation",
    )
    parser.add_argument(
        "--fcs-resumed",
        type=Path,
        default=root / "resume_fcs_validation.npz",
    )
    parser.add_argument(
        "--fcs-uninterrupted",
        type=Path,
        default=root / "resume_fcs_validation.pre_resume.npz",
    )
    parser.add_argument(
        "--interruption-after-saved-time",
        type=float,
        default=0.25,
        help="Last saved physical time before the interrupted process ended.",
    )
    args = parser.parse_args()
    resumed = load_research_dataset(args.resumed)
    uninterrupted = load_research_dataset(args.uninterrupted)
    np.testing.assert_allclose(resumed.x, uninterrupted.x)
    np.testing.assert_allclose(resumed.t, uninterrupted.t)
    metrics = {
        "u_max_abs": float(np.max(np.abs(resumed.u - uninterrupted.u))),
        "m_max_abs": float(np.max(np.abs(resumed.m - uninterrupted.m))),
        "current_max_abs": float(
            np.max(np.abs(resumed.current - uninterrupted.current))
        ),
    }
    fcs_checkpoint_loaded = (
        args.fcs_resumed.exists() and args.fcs_uninterrupted.exists()
    )
    if fcs_checkpoint_loaded:
        fcs_resumed = load_research_dataset(args.fcs_resumed)
        fcs_uninterrupted = load_research_dataset(args.fcs_uninterrupted)
        for name in ("m", "u", "current", "czz", "fcs_logZ"):
            metrics[f"fcs_{name}_max_abs"] = float(
                np.max(
                    np.abs(
                        getattr(fcs_resumed, name)
                        - getattr(fcs_uninterrupted, name)
                    )
                )
            )
    threshold = 1e-13
    status = (
        "pass" if max(metrics.values()) < threshold else "fail"
    )
    summary = {
        "status": status,
        "resumed": str(args.resumed.resolve()),
        "uninterrupted": str(args.uninterrupted.resolve()),
        "interruption_after_saved_time": float(
            args.interruption_after_saved_time
        ),
        "fcs_checkpoint_loaded": fcs_checkpoint_loaded,
        "threshold": threshold,
        "metrics": metrics,
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    (args.outdir / "REPORT.md").write_text(
        "\n".join(
            [
                "# TeNPy checkpoint/resume validation",
                "",
                f"**Status:** `{status}`",
                "",
                "The first run was interrupted after the checkpoint at "
                f"`t={args.interruption_after_saved_time:g}`, resumed from "
                "HDF5, and compared with an uninterrupted twin.",
                "",
                "A separate checkpoint containing the physical MPS plus three "
                "positive FCS counting-field branches was also reloaded and "
                "compared with its pre-reload dataset.",
                "",
                "| Array | max absolute difference |",
                "|---|---:|",
                *[
                    f"| {name} | {value:.6e} |"
                    for name, value in metrics.items()
                ],
                "",
            ]
        )
    )
    print(json.dumps(summary, ensure_ascii=False))
    if status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
