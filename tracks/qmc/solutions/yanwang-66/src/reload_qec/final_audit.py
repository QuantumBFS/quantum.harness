"""Build the public, seed-free preflight for the single holdout query."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from .confirmation_cycle import ANALYSIS_SCHEMA as CONFIRMATION_ANALYSIS_SCHEMA
from .confirmation_run import (
    FROZEN_CANDIDATE_COMMIT,
    FROZEN_CANDIDATE_TREE_SHA256,
)
from .dev_validator import _candidate_tree_sha256
from .discovery import ANALYSIS_SCHEMA as DISCOVERY_ANALYSIS_SCHEMA
from .sensitivity_cycle import FINAL_ANALYSIS_SCHEMA


PREFLIGHT_SCHEMA = "q66-public-holdout-preflight-v1"
NEGATIVE_CONTROL_SCHEMA = "q66-negative-control-report-v2"
EXPECTED_CONTROLS = {
    "background-escape",
    "cheater",
    "env-escape",
    "timeout",
    "wrong-answer",
}


class FinalAuditError(RuntimeError):
    """Raised when a publication gate is not supported by public evidence."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    if not isinstance(value, dict):
        raise FinalAuditError(f"JSON artifact is not an object: {path}")
    return value


def _verify_flat_analysis(
    root: Path, expected_payloads: set[str]
) -> tuple[dict[str, Any], str]:
    checksum_path = root / "analysis-checksums.sha256"
    entries: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        if (
            separator != "  "
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not name
            or name in entries
            or "/" in name
            or "\\" in name
        ):
            raise FinalAuditError(f"invalid analysis checksum: {checksum_path}")
        entries[name] = digest
    if set(entries) != expected_payloads:
        raise FinalAuditError(f"analysis checksum coverage changed: {root}")
    for name, digest in entries.items():
        path = root / name
        if not path.is_file() or _sha256(path) != digest:
            raise FinalAuditError(f"analysis checksum mismatch: {path}")
    return _json_object(root / "analysis-summary.json"), _sha256(checksum_path)


def _audit_discovery(root: Path) -> dict[str, Any]:
    summary, manifest_sha256 = _verify_flat_analysis(
        root,
        {
            "analysis-summary.json",
            "continuation-plan.json",
            "discovery-cells.parquet",
            "discovery-comparisons.parquet",
            "logical-failures.packbits.npy",
            "logical-failure-shots.npy",
        },
    )
    if (
        summary.get("schema_version") != DISCOVERY_ANALYSIS_SCHEMA
        or summary.get("status") != "final-discovery"
        or summary.get("cells") != 2_240
        or summary.get("comparisons") != 1_960
        or summary.get("bootstrap_resamples_per_comparison") != 20_000
        or summary.get("next_phase_groups") != 0
        or summary.get("next_phase_cells") != 0
        or summary.get("cell_sampling_status", {}).get("continue", 0) != 0
    ):
        raise FinalAuditError("discovery publication gate is not final")
    return {
        "root": str(root),
        "analysis_checksums_sha256": manifest_sha256,
        "matrix_sha256": summary["initial_matrix_sha256"],
        "total_cell_shots": summary["total_cell_shots"],
        "cell_sampling_status": summary["cell_sampling_status"],
    }


def _audit_confirmation(root: Path) -> dict[str, Any]:
    summary, manifest_sha256 = _verify_flat_analysis(
        root,
        {
            "analysis-summary.json",
            "confirmation-cells.parquet",
            "confirmation-comparisons.parquet",
            "continuation-plan.json",
        },
    )
    if (
        summary.get("schema_version") != CONFIRMATION_ANALYSIS_SCHEMA
        or summary.get("status") != "final-confirmation"
        or summary.get("cells") != 40
        or summary.get("comparisons") != 32
        or summary.get("bootstrap_resamples_per_comparison") != 20_000
        or summary.get("next_phase_groups") != 0
        or summary.get("next_phase_cells") != 0
        or summary.get("cell_sampling_status", {}).get("continue", 0) != 0
        or summary.get("comparison_precision_status", {}).get("continue", 0) != 0
        or summary.get("required_precision_fraction") != 0.8
        or summary.get("precision_fraction_gate_met") is not True
    ):
        raise FinalAuditError("confirmation publication gate is not final")
    return {
        "root": str(root),
        "analysis_checksums_sha256": manifest_sha256,
        "matrix_sha256": summary["initial_matrix_sha256"],
        "total_cell_shots": summary["total_cell_shots"],
        "cell_sampling_status": summary["cell_sampling_status"],
        "comparison_precision_status": summary["comparison_precision_status"],
        "precision_fraction": summary["precision_fraction"],
    }


def _audit_sensitivity(root: Path) -> dict[str, Any]:
    summary, manifest_sha256 = _verify_flat_analysis(
        root,
        {
            "analysis-summary.json",
            "sensitivity-cells.parquet",
            "sensitivity-comparisons.parquet",
            "sensitivity-costs.parquet",
            "sensitivity-pareto.parquet",
        },
    )
    if (
        summary.get("schema_version") != FINAL_ANALYSIS_SCHEMA
        or summary.get("status") != "final-cost-sensitivity"
        or summary.get("cells") != 192
        or summary.get("comparisons") != 192
        or summary.get("bootstrap_resamples_per_comparison") != 20_000
        or summary.get("next_phase_groups") != 0
        or summary.get("sampling_status", {}).get("continue", 0) != 0
        or summary.get("cost_rows") != 2_160
        or summary.get("pareto_rows") != 240
        or summary.get("pareto_authorized") is not True
    ):
        raise FinalAuditError("cost-sensitivity publication gate is not final")
    return {
        "root": str(root),
        "analysis_checksums_sha256": manifest_sha256,
        "matrix_sha256": summary["sensitivity_matrix_sha256"],
        "discovery_matrix_sha256": summary["discovery_matrix_sha256"],
        "total_cell_shots": summary["total_cell_shots"],
        "sampling_status": summary["sampling_status"],
    }


def _audit_negative_controls(path: Path) -> dict[str, Any]:
    report = _json_object(path)
    controls = report.get("controls")
    if (
        report.get("schema_version") != NEGATIVE_CONTROL_SCHEMA
        or report.get("status") != "passed"
        or not isinstance(controls, dict)
        or set(controls) != EXPECTED_CONTROLS
    ):
        raise FinalAuditError("v2 negative-control report changed")
    for name, row in controls.items():
        if (
            not isinstance(row, dict)
            or row.get("status") != "rejected-as-expected"
            or row.get("process_cleanup", {}).get("process_group_cleared") is not True
        ):
            raise FinalAuditError(f"negative control did not pass: {name}")
    background = controls["background-escape"]["process_cleanup"]
    if (
        background.get("background_processes_detected") is not True
        or "SIGTERM" not in background.get("background_process_signals", [])
    ):
        raise FinalAuditError("background-escape cleanup evidence changed")
    return {
        "report": str(path),
        "report_sha256": _sha256(path),
        "slurm_job_id": report["slurm_job_id"],
        "controls": sorted(controls),
    }


def _audit_science_gate(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="ascii")
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Status" in line:
            continue
        fields = [field.strip() for field in line.strip("|").split("|")]
        if len(fields) == 3:
            rows.append(fields)
    if len(rows) != 15:
        raise FinalAuditError("science-gate table shape changed")
    allowed = {"passed", "unspent-ready"}
    failures = [(gate, status) for gate, status, _ in rows if status not in allowed]
    if failures:
        raise FinalAuditError(f"science gates remain open: {failures}")
    return {"path": str(path), "sha256": _sha256(path), "gate_count": len(rows)}


def _audit_report(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="ascii")
    forbidden = ("Pending artifact", "Required final entries", "[final", "[passed")
    if not text.startswith("# Dynamic Atom-Reload Policies") or any(
        token in text for token in forbidden
    ):
        raise FinalAuditError("final report still contains a placeholder")
    if "Status: complete pre-holdout draft." not in text:
        raise FinalAuditError("report is not marked complete pre-holdout")
    return {"path": str(path), "sha256": _sha256(path)}


def audit_public_gates(
    *,
    candidate_root: Path,
    discovery_analysis: Path,
    confirmation_analysis: Path,
    sensitivity_analysis: Path,
    negative_controls_report: Path,
    independent_evidence: Path,
    report_path: Path,
    science_gate_path: Path,
    holdout_spend_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    job_id = os.environ.get("SLURM_JOB_ID")
    if not job_id:
        raise FinalAuditError("public final audit must execute inside Slurm")
    if out_dir.exists():
        raise FinalAuditError(f"public audit output exists: {out_dir}")
    candidate_root = candidate_root.resolve(strict=True)
    tree_sha256 = _candidate_tree_sha256(candidate_root)
    if tree_sha256 != FROZEN_CANDIDATE_TREE_SHA256:
        raise FinalAuditError("accepted candidate tree changed")
    if holdout_spend_path.exists():
        raise FinalAuditError("holdout query budget is already spent")
    independent_evidence = independent_evidence.resolve(strict=True)
    discovery = _audit_discovery(discovery_analysis.resolve(strict=True))
    confirmation = _audit_confirmation(confirmation_analysis.resolve(strict=True))
    sensitivity = _audit_sensitivity(sensitivity_analysis.resolve(strict=True))
    if sensitivity["discovery_matrix_sha256"] != discovery["matrix_sha256"]:
        raise FinalAuditError("cost and discovery matrix identities differ")
    negative_controls = _audit_negative_controls(
        negative_controls_report.resolve(strict=True)
    )
    report = _audit_report(report_path.resolve(strict=True))
    science_gate = _audit_science_gate(science_gate_path.resolve(strict=True))
    preflight = {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "holdout-ready",
        "slurm_job_id": job_id,
        "candidate_commit": FROZEN_CANDIDATE_COMMIT,
        "candidate_tree_sha256": tree_sha256,
        "discovery": discovery,
        "confirmation": confirmation,
        "cost_sensitivity": sensitivity,
        "negative_controls": negative_controls,
        "independent_evidence": {
            "path": str(independent_evidence),
            "sha256": _sha256(independent_evidence),
        },
        "report": report,
        "science_gate": science_gate,
        "holdout_query_budget": {"consumed": 0, "authorized": 1},
        "holdout_spend_path": str(holdout_spend_path),
        "contains_private_holdout_inputs": False,
    }
    out_dir.mkdir(parents=True)
    path = out_dir / "public-preflight.json"
    _canonical_json(path, preflight)
    (out_dir / "public-preflight.json.sha256").write_text(
        f"{_sha256(path)}  {path.name}\n", encoding="ascii"
    )
    return preflight


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--discovery-analysis", type=Path, required=True)
    parser.add_argument("--confirmation-analysis", type=Path, required=True)
    parser.add_argument("--sensitivity-analysis", type=Path, required=True)
    parser.add_argument("--negative-controls-report", type=Path, required=True)
    parser.add_argument("--independent-evidence", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--science-gate", type=Path, required=True)
    parser.add_argument("--holdout-spend", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = audit_public_gates(
        candidate_root=args.candidate_root,
        discovery_analysis=args.discovery_analysis,
        confirmation_analysis=args.confirmation_analysis,
        sensitivity_analysis=args.sensitivity_analysis,
        negative_controls_report=args.negative_controls_report,
        independent_evidence=args.independent_evidence,
        report_path=args.report,
        science_gate_path=args.science_gate,
        holdout_spend_path=args.holdout_spend,
        out_dir=args.out,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
