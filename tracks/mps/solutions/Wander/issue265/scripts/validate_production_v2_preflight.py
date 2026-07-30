#!/usr/bin/env python3
"""Validate production-v2 source locally and runtime outputs on SCNet."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.production_initial_conditions import (
    production_initial_magnetization,
    production_source_closure,
)
from src.production_v2_manifest import sha256_file
from src.research_dataset import load_research_dataset


def _json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return dict(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError):
        return None


def validate_runtime_outputs(
    *,
    equilibrium_path: Path,
    pulse_pos_path: Path,
    pulse_neg_path: Path,
    equilibrium_before_reload_path: Path,
) -> dict[str, Any]:
    """Check exact null, spin-flip, FCS, and checkpoint properties."""

    equilibrium = load_research_dataset(equilibrium_path)
    positive = load_research_dataset(pulse_pos_path)
    negative = load_research_dataset(pulse_neg_path)
    before = load_research_dataset(equilibrium_before_reload_path)
    if equilibrium.current is None:
        raise ValueError("equilibrium runtime dataset is missing current")
    if equilibrium.fcs_gamma is None or equilibrium.fcs_logZ is None:
        raise ValueError("equilibrium runtime dataset is missing FCS")
    if positive.current is None or negative.current is None:
        raise ValueError("pulse runtime datasets are missing current")
    for left, right in (
        (equilibrium.x, before.x),
        (equilibrium.t, before.t),
        (positive.x, negative.x),
        (positive.t, negative.t),
    ):
        np.testing.assert_array_equal(left, right)
    gamma = np.asarray(equilibrium.fcs_gamma)
    zero = int(np.argmin(np.abs(gamma)))
    metrics = {
        "uniform_initial_magnetization_max_abs": float(
            np.max(np.abs(equilibrium.m[0]))
        ),
        "uniform_mean_magnetization_max_abs": float(
            np.max(np.abs(equilibrium.m))
        ),
        "uniform_mean_current_max_abs": float(
            np.max(np.abs(equilibrium.current))
        ),
        "fcs_zero_gamma_max_abs": float(
            np.max(np.abs(equilibrium.fcs_logZ[:, zero]))
        ),
        "fcs_conjugacy_max_abs": float(
            np.max(
                np.abs(
                    equilibrium.fcs_logZ
                    - np.conj(equilibrium.fcs_logZ[:, ::-1])
                )
            )
        ),
        "pulse_spin_flip_magnetization_max_abs": float(
            np.max(np.abs(positive.m + negative.m))
        ),
        "pulse_spin_flip_current_max_abs": float(
            np.max(np.abs(positive.current + negative.current))
        ),
        "checkpoint_reload_m_max_abs": float(
            np.max(np.abs(equilibrium.m - before.m))
        ),
        "checkpoint_reload_current_max_abs": float(
            np.max(np.abs(equilibrium.current - before.current))
        ),
        "checkpoint_reload_fcs_max_abs": float(
            np.max(np.abs(equilibrium.fcs_logZ - before.fcs_logZ))
        ),
    }
    checks = {
        "uniform_initial": metrics["uniform_initial_magnetization_max_abs"]
        <= 1e-12,
        "uniform_mean": metrics["uniform_mean_magnetization_max_abs"] <= 1e-12,
        "uniform_current": metrics["uniform_mean_current_max_abs"] <= 1e-12,
        "fcs_zero": metrics["fcs_zero_gamma_max_abs"] <= 1e-12,
        "fcs_conjugacy": metrics["fcs_conjugacy_max_abs"] <= 1e-12,
        "pulse_magnetization_spin_flip": metrics[
            "pulse_spin_flip_magnetization_max_abs"
        ]
        <= 2e-10,
        "pulse_current_spin_flip": metrics["pulse_spin_flip_current_max_abs"]
        <= 2e-10,
        "checkpoint_reload": max(
            metrics["checkpoint_reload_m_max_abs"],
            metrics["checkpoint_reload_current_max_abs"],
            metrics["checkpoint_reload_fcs_max_abs"],
        )
        < 1e-13,
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "metrics": metrics,
    }


def evidence_is_current(
    evidence: Mapping[str, Any],
    *,
    root: Path = ROOT,
) -> bool:
    """Return whether every source-closure hash still matches the evidence."""

    recorded = evidence.get("source_closure", {}).get("files", {})
    if not isinstance(recorded, Mapping) or not recorded:
        return False
    return all(
        (root / relative).is_file()
        and sha256_file(root / relative) == expected
        for relative, expected in recorded.items()
    )


def build_preflight_evidence(
    *,
    manifest_path: Path,
    j2_evidence_path: Path,
    fcs_summary_path: Path,
    resume_summary_path: Path,
    runtime: Mapping[str, Any] | None,
    root: Path = ROOT,
) -> dict[str, Any]:
    manifest = _json(manifest_path)
    if manifest is None:
        raise ValueError("production-v2 manifest is missing or invalid")
    summary = manifest.get("summary", {})
    manifest_pass = (
        manifest.get("job_count") == 68
        and summary.get("production_a_logical") == 34
        and summary.get("production_b_logical") == 34
        and summary.get("production_a_execute") == 32
        and summary.get("production_a_reuse") == 2
        and summary.get("production_a_fcs_logical") == 7
        and summary.get("production_b_fcs") == 3
        and summary.get("submission_performed") is False
    )
    closure = production_source_closure(root)
    x = np.arange(8.0)
    uniform = production_initial_magnetization(
        x,
        {
            "profile": "uniform_zero",
            "background_m": 0.0,
            "temperature": "infinite",
        },
    )
    initial_pass = bool(np.array_equal(uniform, np.zeros_like(x)))
    fcs = _json(fcs_summary_path)
    resume = _json(resume_summary_path)
    j2 = _json(j2_evidence_path)
    local_gates = {
        "manifest": {"status": "pass" if manifest_pass else "fail"},
        "source_closure": {"status": "pass" if closure["valid"] else "fail"},
        "uniform_zero_initial_algebra": {
            "status": "pass" if initial_pass else "fail"
        },
        "inherited_fcs_backend": {
            "status": "pass"
            if fcs is not None and fcs.get("status") == "pass"
            else "fail"
        },
        "inherited_checkpoint_backend": {
            "status": "pass"
            if resume is not None and resume.get("status") == "pass"
            else "fail"
        },
        "grouped_j2_local_compatibility": {
            "status": "pass"
            if j2 is not None
            and j2.get("local_gates", {}).get("status") == "pass"
            else "fail"
        },
    }
    local_pass = all(gate["status"] == "pass" for gate in local_gates.values())
    runtime_status = str(runtime.get("status")) if runtime is not None else "pending"
    if local_pass and runtime_status == "pass" and j2 is not None and j2.get("status") == "pass":
        status = "pass"
    elif local_pass:
        status = "local_pass_cluster_pending"
    else:
        status = "local_failed"
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": sha256_file(manifest_path),
        "source_closure": closure,
        "local_gates": local_gates,
        "runtime_compute_gate": (
            dict(runtime)
            if runtime is not None
            else {
                "status": "pending",
                "reason": "production wrapper has not run on a TeNPy compute node",
            }
        ),
        "j2_compute_gate": {
            "status": str(j2.get("status", "missing")) if j2 else "missing"
        },
        "submission_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "results_research_program" / "production_manifest_v2.json",
    )
    parser.add_argument(
        "--j2-evidence",
        type=Path,
        default=ROOT / "results_research_program" / "hpc" / "j2_validation_20260730.json",
    )
    parser.add_argument(
        "--fcs-summary",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "fcs_validation"
        / "summary.json",
    )
    parser.add_argument(
        "--resume-summary",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "resume_validation"
        / "summary.json",
    )
    parser.add_argument("--equilibrium", type=Path)
    parser.add_argument("--pulse-pos", type=Path)
    parser.add_argument("--pulse-neg", type=Path)
    parser.add_argument("--equilibrium-before-reload", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "hpc"
        / "production_v2_validation_20260730.json",
    )
    args = parser.parse_args()
    runtime_paths = (
        args.equilibrium,
        args.pulse_pos,
        args.pulse_neg,
        args.equilibrium_before_reload,
    )
    if any(path is not None for path in runtime_paths) and not all(
        path is not None for path in runtime_paths
    ):
        raise SystemExit("all four runtime paths must be supplied together")
    runtime = (
        validate_runtime_outputs(
            equilibrium_path=args.equilibrium,
            pulse_pos_path=args.pulse_pos,
            pulse_neg_path=args.pulse_neg,
            equilibrium_before_reload_path=args.equilibrium_before_reload,
        )
        if all(path is not None for path in runtime_paths)
        else None
    )
    evidence = build_preflight_evidence(
        manifest_path=args.manifest,
        j2_evidence_path=args.j2_evidence,
        fcs_summary_path=args.fcs_summary,
        resume_summary_path=args.resume_summary,
        runtime=runtime,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(evidence, indent=2) + "\n")
    temporary.replace(args.output)
    print(json.dumps({"status": evidence["status"]}, sort_keys=True))
    if evidence["status"] == "local_failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
