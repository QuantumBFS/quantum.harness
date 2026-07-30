#!/usr/bin/env python3
"""Assemble the research-program status without opening blinded data."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_protocol import load_decision_rules
from src.research_verdict import evaluate_verdict


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _missing_counts(validation: dict[str, Any]) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in validation.get("counts", {}).items()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--validation",
        type=Path,
        default=ROOT / "results_research_program" / "dataset_validation.json",
    )
    parser.add_argument(
        "--convergence",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "convergence"
        / "summary.json",
    )
    parser.add_argument(
        "--cross-condition",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "cross_condition"
        / "summary.json",
    )
    parser.add_argument(
        "--two-mode",
        type=Path,
        default=ROOT / "results_research_program" / "two_mode" / "summary.json",
    )
    parser.add_argument(
        "--environment-control",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "public_environment_control"
        / "summary.json",
    )
    parser.add_argument(
        "--tenpy-validation",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "validation"
        / "summary.json",
    )
    parser.add_argument(
        "--tenpy-fcs-validation",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "fcs_validation"
        / "summary.json",
    )
    parser.add_argument(
        "--tenpy-exact-validation",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "exact_validation"
        / "summary.json",
    )
    parser.add_argument(
        "--tenpy-resume-validation",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "tenpy_smoke"
        / "resume_validation"
        / "summary.json",
    )
    parser.add_argument(
        "--j2-validation",
        type=Path,
        default=ROOT
        / "results_research_program"
        / "hpc"
        / "j2_validation_20260730.json",
    )
    parser.add_argument(
        "--phase0-evidence",
        type=Path,
        default=ROOT / "results_research_program" / "phase0_evidence.json",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=ROOT / "configs" / "burgers_decision_rules.json",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "results_research_program",
    )
    args = parser.parse_args()

    validation = _load(args.validation)
    convergence = _load(args.convergence)
    cross = _load(args.cross_condition)
    two_mode = _load(args.two_mode)
    environment_control = (
        _load(args.environment_control)
        if args.environment_control.exists()
        else None
    )
    tenpy_validation = (
        _load(args.tenpy_validation)
        if args.tenpy_validation.exists()
        else None
    )
    tenpy_fcs_validation = (
        _load(args.tenpy_fcs_validation)
        if args.tenpy_fcs_validation.exists()
        else None
    )
    tenpy_exact_validation = (
        _load(args.tenpy_exact_validation)
        if args.tenpy_exact_validation.exists()
        else None
    )
    tenpy_resume_validation = (
        _load(args.tenpy_resume_validation)
        if args.tenpy_resume_validation.exists()
        else None
    )
    j2_validation = (
        _load(args.j2_validation)
        if args.j2_validation.exists()
        else None
    )
    phase0 = _load(args.phase0_evidence)
    rules = load_decision_rules(args.rules)

    convergence_records = convergence.get("records", [])
    convergence_floor = max(
        (
            float(record.get("numerical_floor", 0.0))
            for record in convergence_records
            if record.get("status") == "accepted"
        ),
        default=0.0,
    )
    convergence_reason = ",".join(
        sorted({str(record.get("status", "missing")) for record in convergence_records})
    )
    evidence: dict[str, Any] = {
        "phase": "confirmatory_program_pre_unblinding",
        "sources": {
            "validation": str(args.validation.resolve()),
            "convergence": str(args.convergence.resolve()),
            "cross_condition": str(args.cross_condition.resolve()),
            "two_mode": str(args.two_mode.resolve()),
            "environment_control": (
                str(args.environment_control.resolve())
                if environment_control is not None
                else None
            ),
            "tenpy_validation": (
                str(args.tenpy_validation.resolve())
                if tenpy_validation is not None
                else None
            ),
            "tenpy_fcs_validation": (
                str(args.tenpy_fcs_validation.resolve())
                if tenpy_fcs_validation is not None
                else None
            ),
            "tenpy_exact_validation": (
                str(args.tenpy_exact_validation.resolve())
                if tenpy_exact_validation is not None
                else None
            ),
            "tenpy_resume_validation": (
                str(args.tenpy_resume_validation.resolve())
                if tenpy_resume_validation is not None
                else None
            ),
            "tenpy_j2_validation": (
                str(args.j2_validation.resolve())
                if j2_validation is not None
                else None
            ),
            "phase0": str(args.phase0_evidence.resolve()),
            "rules": str(args.rules.resolve()),
        },
        "coverage": {
            "n_primary_conditions": 0,
            "has_both_orientations": False,
            "has_blinded_future_test": False,
            "has_current_observable": False,
            "has_fcs": False,
        },
        "convergence": {
            "status": "tested",
            "accepted": bool(convergence.get("accepted", False)),
            "reason": convergence_reason or "missing",
            "numerical_floor": convergence_floor,
        },
        "universal_scalar": {
            "field_identified": False,
            "controlled_derivation": False,
        },
        "finite_window": dict(phase0.get("finite_window", {})),
        "microscopic_moment": dict(phase0.get("microscopic_moment", {})),
        "two_mode": {"tested": False},
    }

    if cross.get("status") == "evaluated":
        loco = [
            row
            for row in cross.get("loco", [])
            if row.get("model") == "shared_constant"
        ]
        symmetry = cross.get("symmetry_pairs", [])
        specific = cross.get("condition_specific", {})
        coefficients = [
            float(value["a"]) for value in specific.values()
        ]
        evidence["coverage"].update(
            {
                "n_primary_conditions": len(specific),
                "has_both_orientations": bool(symmetry),
            }
        )
        evidence["universal_scalar"].update(
            {
                "spin_flip_defect": float(
                    cross.get("decision_metrics", {}).get(
                        "spin_flip_defect_max", float("nan")
                    )
                ),
                "loco_integrated_max": max(
                    (
                        float(row["integrated_relative_l2"])
                        for row in loco
                    ),
                    default=float("nan"),
                ),
                "loco_endpoint_max": max(
                    (float(row["endpoint_relative_l2"]) for row in loco),
                    default=float("nan"),
                ),
                "coefficient_relative_spread": (
                    float(np.std(coefficients))
                    / max(
                        abs(float(np.mean(coefficients))),
                        1e-30,
                    )
                    if coefficients
                    else float("nan")
                ),
                "a_drift_exponent": float(
                    cross.get("parameter_flow", {}).get(
                        "a_drift_exponent", float("nan")
                    )
                ),
                "D_drift_exponent": float(
                    cross.get("parameter_flow", {}).get(
                        "D_drift_exponent", float("nan")
                    )
                ),
                "late_width_exponent_error": float(
                    cross.get("decision_metrics", {}).get(
                        "late_width_exponent_error_max", float("nan")
                    )
                ),
            }
        )

    if two_mode.get("tested", False):
        evidence["two_mode"] = {
            key: two_mode[key]
            for key in (
                "tested",
                "relative_improvement",
                "paired_ci_low",
                "symmetry_pass",
                "joint_observables_pass",
            )
            if key in two_mode
        }

    verdict = asdict(evaluate_verdict(evidence, rules))
    status = {
        "schema_version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "pre_unblinding": True,
        "dataset_counts": _missing_counts(validation),
        "component_status": {
            "convergence": (
                "accepted" if convergence.get("accepted", False) else "unresolved"
            ),
            "cross_condition": cross.get("status", "missing"),
            "two_mode": two_mode.get("status", "missing"),
            "public_environment_control": (
                "evaluated" if environment_control is not None else "missing"
            ),
            "tenpy_backend": (
                str(tenpy_validation.get("status", "missing"))
                if tenpy_validation is not None
                else "missing"
            ),
            "tenpy_transfer_fcs": (
                str(tenpy_fcs_validation.get("status", "missing"))
                if tenpy_fcs_validation is not None
                else "missing"
            ),
            "tenpy_exact_diagonalization": (
                str(tenpy_exact_validation.get("status", "missing"))
                if tenpy_exact_validation is not None
                else "missing"
            ),
            "tenpy_checkpoint_resume": (
                str(tenpy_resume_validation.get("status", "missing"))
                if tenpy_resume_validation is not None
                else "missing"
            ),
            "tenpy_j2_grouped": (
                str(j2_validation.get("status", "missing"))
                if j2_validation is not None
                else "missing"
            ),
            "phase0_finite_window": phase0.get("finite_window", {}),
        },
        "verdict": verdict,
        "next_gate": (
            "complete_convergence_datasets"
            if not convergence.get("accepted", False)
            else "complete_production_a"
            if cross.get("status") != "evaluated"
            else "freeze_analysis_and_unblind_once"
        ),
    }

    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "final_evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    )
    (args.outdir / "final_verdict.json").write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False) + "\n"
    )
    (args.outdir / "program_status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n"
    )
    report = rf"""# Burgers universality research program

## Current outcome

The confirmatory program is **`{verdict['overall']}`**. This is not a
falsification result: the preregistered tensor-network convergence data have
not yet been generated. Blinded production-B data were not opened.

The legacy public single trajectory still supports the already separated
statement “finite-window scalar surrogate”; that pilot result is retained in
`PILOT_REPORT.md` and is not promoted to a cross-initial-condition law.

## Machine verdict

```json
{json.dumps(verdict, indent=2, ensure_ascii=False)}
```

## Data gates

- Dataset counts: `{json.dumps(status['dataset_counts'], ensure_ascii=False)}`.
- Convergence: `{status['component_status']['convergence']}`.
- Cross-condition audit: `{status['component_status']['cross_condition']}`.
- Two-mode audit: `{status['component_status']['two_mode']}`.
- Public Delta=2 environment control:
  `{status['component_status']['public_environment_control']}`.
- TeNPy high-temperature backend smoke validation:
  `{status['component_status']['tenpy_backend']}`.
- Two-measurement transfer-FCS smoke validation:
  `{status['component_status']['tenpy_transfer_fcs']}`.
- Dense exact-diagonalization cross-check:
  `{status['component_status']['tenpy_exact_diagonalization']}`.
- Interrupted/checkpoint/resume equivalence:
  `{status['component_status']['tenpy_checkpoint_resume']}`.
- Grouped \(J_1\)-\(J_2\) backend exact/symmetry/FCS/resume gate:
  `{status['component_status']['tenpy_j2_grouped']}`.
- Next gate: `{status['next_gate']}`.

## What is proved now

1. A fixed quadratic current for zero-background physical magnetization
   violates spin-flip symmetry.
2. The two-field currents diagonalize algebraically into opposite Burgers
   modes on the equal-coupling fixed-point manifold.
3. The public trajectory satisfies the finite-window moment tangent
   \(A_B/A_W\simeq0.99915\), while the GHD asymptotic amplitude remains a
   future-time test.
4. Missing convergence/current/FCS data produce `unresolved`, never an
   invented preference among scalar, two-mode, or memory theories.
5. The public Delta=2 wall is close to diffusive broadening
   (\(\beta\simeq0.5263\)); its locally accurate Burgers coefficients do not
   transfer to Delta=1, or conversely.
6. The new purification-TEBD backend passes small-chain spin-flip,
   magnetization conservation, lattice-continuity, connected-Czz, and genuine
   two-measurement FCS checks. These are implementation tests, not substitutes
   for the registered \(L=256,384,512\), \(t\le200\) convergence ladder.
7. HDF5 checkpoint/resume was tested by an actual interruption at \(t=0.25\);
   the resumed and uninterrupted arrays agree bit for bit through \(t=0.5\).
8. The \(J_2=0.1\) control has a grouped two-physical-spin
   purification-TEBD implementation. Both wall directions pass local dense
   exact-evolution, spin-flip, continuity, FCS, and checkpoint-resume gates.
9. At \(J_2=0\), grouped and ordinary backends agree below the frozen
   \(2\times10^{-7}\) tolerance. Cluster production remains blocked until the
   independent SCNet compute-node evidence status is exactly `pass`.

## Required external work

Complete the 12 convergence jobs in `manifest.json`. Only if all four
representative conditions pass the frozen profile and width gates should
production A be completed. The launch audit currently marks 29 nearest-
the SCNet compute-node validation evidence. Local long-range implementation
and validation are complete, but local success does not unlock production.
Even after the J2 gate passes, production A must still wait for an accepted
convergence audit. Freeze the analysis tree and then use the one-time
unblinding command for production B.
"""
    (args.outdir / "REPORT.md").write_text(report)
    print(
        json.dumps(
            {
                "overall": verdict["overall"],
                "next_gate": status["next_gate"],
                "pre_unblinding": True,
            }
        )
    )


if __name__ == "__main__":
    main()
