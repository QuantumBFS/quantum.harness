#!/usr/bin/env python3
"""Fail-closed audit for matrix-element Geometric ETH artifacts."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_matrix_element_geometric_eth_v3 import (
    CHECKPOINT_ROOT,
    OUTPUT_JSON,
    OUTPUT_NPZ,
    SCRIPT_ROOT,
    select_result_branch,
)


OUTPUT_ROOT = SCRIPT_ROOT / "output"
FIGURE_MANIFEST = OUTPUT_ROOT / "figure_manifest_v3.json"
FIGURE_PDF = OUTPUT_ROOT / "figure_6_wick_factorization_v3.pdf"
FIGURE_PNG = OUTPUT_ROOT / "figure_6_wick_factorization_v3.png"
AUDIT_JSON = OUTPUT_ROOT / "matrix_element_delivery_audit_v3.json"
RELEASE_MANIFEST = OUTPUT_ROOT / "release_manifest_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _isolated_task_sources() -> bool:
    for source in SCRIPT_ROOT.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            if any(
                "task_03" in module
                or "task_04" in module
                or "qgeom" in module
                or "gaccess" in module
                for module in modules
            ):
                return False
    return True


def audit_payload(payload: dict[str, Any]) -> dict[str, bool]:
    """Recompute every scientific gate from a loaded result payload."""

    cases = payload["cases"]
    expected = [(3, 8, 16), (4, 10, 25), (5, 12, 36)]
    observed = [
        (case["N"], case["n_flux"], case["rank"])
        for case in cases
    ]
    checks = {
        "registered_sequence": observed == expected,
        "fixed_two_quasiholes": all(
            case["n_flux"] == 2 * case["N"] + 2
            for case in cases
        ),
        "all_runner_checks": all(payload["checks"].values()),
        "all_case_checks": all(
            all(case["checks"].values()) for case in cases
        ),
        "reference_counts": (
            payload["configuration"]["gaussian_samples"] == 2_000
        ),
        "panel_counts": payload["configuration"]["panels"] == 24,
        "panel_size": payload["configuration"]["panel_size"] == 8,
        "kernel_residuals": all(
            case["kernel_residual_norm"]
            < (1e-8 if case["kernel_method"] == "dense" else 5e-7)
            for case in cases
        ),
        "resolvent_residuals": all(
            case["maximum_relative_residual"] < 2e-3
            for case in cases
        ),
        "gauge_invariance": all(
            case["gauge_invariance_error"] < 2e-9
            for case in cases
        ),
        "branch_recomputed": (
            payload["result_branch"] == select_result_branch(payload)
        ),
        "n2_exclusion": (
            payload["excluded_small_case"]["expected_rank"] == 9
            and payload["excluded_small_case"]["observed_rank"] == 12
            and payload["excluded_small_case"]["accepted"] is False
        ),
    }
    if not all(checks.values()):
        raise AssertionError(f"matrix-element payload audit failed: {checks}")
    return checks


def run_audit() -> dict[str, Any]:
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    checks = audit_payload(payload)
    manifest = json.loads(FIGURE_MANIFEST.read_text(encoding="utf-8"))
    figure = manifest["figure_6_wick_factorization_v3"]
    checkpoint_files = sorted(CHECKPOINT_ROOT.glob("N*_site_response_v3.*"))
    previous_audit = (
        json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        if AUDIT_JSON.exists()
        else {}
    )
    if len(checkpoint_files) == 6:
        checkpoint_hashes = {
            str(path.relative_to(SCRIPT_ROOT)): _sha256(path)
            for path in checkpoint_files
        }
        checkpoint_provenance = True
    else:
        checkpoint_hashes = previous_audit.get("checkpoint_hashes", {})
        release = json.loads(RELEASE_MANIFEST.read_text(encoding="utf-8"))
        external_hashes = {
            Path(record["path"]).name: record["sha256"]
            for record in release["external_artifacts"]
            if "matrix_element_v3_checkpoints" in record["path"]
        }
        archived_npz_hashes = {
            Path(path).name: digest
            for path, digest in checkpoint_hashes.items()
            if path.endswith(".npz")
        }
        checkpoint_provenance = (
            len(checkpoint_hashes) == 6
            and external_hashes == archived_npz_hashes
        )
    checks.update(
        {
            "npz_hash": payload["npz_sha256"] == _sha256(OUTPUT_NPZ),
            "figure_source_hash": (
                figure["source_sha256"] == _sha256(OUTPUT_JSON)
            ),
            "figure_pdf_hash": (
                figure["pdf_sha256"] == _sha256(FIGURE_PDF)
            ),
            "figure_png_hash": (
                figure["png_sha256"] == _sha256(FIGURE_PNG)
            ),
            "checkpoint_provenance": checkpoint_provenance,
            "task_isolation": _isolated_task_sources(),
        }
    )
    result = {
        "version": "v3",
        "generated_utc": previous_audit.get(
            "generated_utc", datetime.now(timezone.utc).isoformat()
        ),
        "passed": all(checks.values()),
        "checks": checks,
        "result_branch": payload["result_branch"],
        "registered_cases": [
            [case["N"], case["n_flux"], case["rank"]]
            for case in payload["cases"]
        ],
        "result_sha256": _sha256(OUTPUT_JSON),
        "arrays_sha256": _sha256(OUTPUT_NPZ),
        "checkpoint_hashes": checkpoint_hashes,
        "figure": {
            "pdf": str(FIGURE_PDF.relative_to(SCRIPT_ROOT)),
            "pdf_sha256": _sha256(FIGURE_PDF),
            "png": str(FIGURE_PNG.relative_to(SCRIPT_ROOT)),
            "png_sha256": _sha256(FIGURE_PNG),
        },
    }
    if not result["passed"]:
        raise RuntimeError(f"matrix-element delivery audit failed: {checks}")
    temporary = AUDIT_JSON.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(AUDIT_JSON)
    return result


def main() -> None:
    result = run_audit()
    print(json.dumps(
        {
            "passed": result["passed"],
            "checks": result["checks"],
            "result_branch": result["result_branch"],
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
