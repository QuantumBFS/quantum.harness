#!/usr/bin/env python3
"""Compare grouped and ungrouped TeNPy representations at J2=0."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_dataset import ResearchDataset, load_research_dataset


def _required_array(dataset: ResearchDataset, name: str) -> np.ndarray:
    value = getattr(dataset, name)
    if value is None:
        raise ValueError(f"{name} is required for representation equivalence")
    return np.asarray(value)


def compare_representations(
    ungrouped: ResearchDataset,
    grouped: ResearchDataset,
    *,
    threshold: float = 2e-7,
) -> dict[str, Any]:
    """Return observable-wise grouped-versus-ungrouped discrepancies."""

    if threshold <= 0.0 or not np.isfinite(threshold):
        raise ValueError("threshold must be positive and finite")
    if ungrouped.condition_id != grouped.condition_id:
        raise ValueError("Representation datasets must share condition_id")
    if abs(float(ungrouped.metadata.get("J2", np.nan))) > 1e-15:
        raise ValueError("Ungrouped equivalence reference must have J2=0")
    if abs(float(grouped.metadata.get("J2", np.nan))) > 1e-15:
        raise ValueError("Grouped equivalence candidate must have J2=0")
    if grouped.metadata.get("backend_layout") != "grouped_range2":
        raise ValueError("Candidate metadata must identify grouped_range2")
    np.testing.assert_allclose(ungrouped.x, grouped.x, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(ungrouped.t, grouped.t, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(
        _required_array(ungrouped, "fcs_gamma"),
        _required_array(grouped, "fcs_gamma"),
        rtol=0.0,
        atol=0.0,
    )

    pairs = {
        "u_max_abs": (
            np.asarray(ungrouped.u),
            np.asarray(grouped.u),
        ),
        "magnetization_max_abs": (
            _required_array(ungrouped, "m"),
            _required_array(grouped, "m"),
        ),
        "current_max_abs": (
            _required_array(ungrouped, "current"),
            _required_array(grouped, "current"),
        ),
        "czz_max_abs": (
            _required_array(ungrouped, "czz"),
            _required_array(grouped, "czz"),
        ),
        "fcs_logZ_max_abs": (
            _required_array(ungrouped, "fcs_logZ"),
            _required_array(grouped, "fcs_logZ"),
        ),
    }
    errors: dict[str, float] = {}
    for name, (reference, candidate) in pairs.items():
        if reference.shape != candidate.shape:
            raise ValueError(
                f"{name} shape mismatch: {reference.shape} != "
                f"{candidate.shape}"
            )
        errors[name] = float(np.max(np.abs(candidate - reference)))
    checks = {
        name: value < threshold for name, value in errors.items()
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "threshold": float(threshold),
        "errors": errors,
        "checks": checks,
    }


def _report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# TeNPy grouped/ungrouped representation equivalence",
            "",
            f"**Status:** `{summary['status']}`",
            "",
            "| Observable | max absolute error | threshold |",
            "|---|---:|---:|",
            *[
                f"| {name} | {value:.6e} | "
                f"{summary['threshold']:.6e} |"
                for name, value in summary["errors"].items()
            ],
            "",
            "Both simulations use the same physical J2=0 Hamiltonian, "
            "initial density matrix, time grid, truncation parameters, and "
            "two-measurement FCS definition. Only the internal site grouping "
            "differs.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ungrouped", type=Path, required=True)
    parser.add_argument("--grouped", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=2e-7)
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "grouped_equivalence",
    )
    args = parser.parse_args()
    summary = compare_representations(
        load_research_dataset(args.ungrouped),
        load_research_dataset(args.grouped),
        threshold=args.threshold,
    )
    summary["inputs"] = {
        "ungrouped": str(args.ungrouped.resolve()),
        "grouped": str(args.grouped.resolve()),
    }
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

