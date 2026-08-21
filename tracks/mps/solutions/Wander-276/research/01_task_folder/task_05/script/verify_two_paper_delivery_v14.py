#!/usr/bin/env python3
"""Fail-closed cross-paper audit for the v13/v14 back-to-back package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PAPER_I_AUDIT = Path(
    "01_task_folder/task_05/script/output/paper1_prb_v13/delivery_audit_v13.json"
)
PAPER_II_AUDIT = Path(
    "01_task_folder/task_05/script/output/geometric_eth_theory_v14/delivery_audit_v14.json"
)
MANIFEST_PATH = Path(
    "01_task_folder/task_05/script/output/two_paper_delivery_v14/"
    "two_paper_manifest_v14.json"
)
DESIGN_PATH = Path("docs/plans/2026-08-17-two-paper-geometric-eth-design.md")
PAPER_I_PLAN = Path(
    "docs/superpowers/plans/2026-08-17-exactly-degenerate-quantum-chaos-prb.md"
)
PAPER_II_PLAN = Path(
    "docs/superpowers/plans/2026-08-17-geometric-eth-theory-paper.md"
)

PAPER_I_TITLE = (
    "Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe"
)
PAPER_II_POSITIVE_TITLE = (
    "The Geometric ETH: Statistical Closure on Degenerate Quantum State Bundles"
)
PAPER_II_FALLBACK_TITLE = (
    "Geometric Response of Exactly Degenerate Quantum State Bundles"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _document_record(repo_root: Path, path: str, expected_hash: str) -> dict[str, Any]:
    absolute = repo_root / path
    observed_hash = sha256(absolute) if absolute.is_file() else None
    return {
        "path": path,
        "exists": absolute.is_file(),
        "sha256": observed_hash,
        "audit_sha256": expected_hash,
        "hash_matches_audit": observed_hash == expected_hash,
    }


def validate_paper_i(repo_root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if audit.get("schema") != "paper1_prb_delivery_audit_v13":
        errors.append("unexpected Paper I audit schema")
    if audit.get("passed") is not True:
        errors.append("Paper I delivery audit did not pass")
    if not all(audit.get("checks", {}).values()):
        errors.append("at least one Paper I delivery check failed")

    documents = {
        name: _document_record(repo_root, record["path"], record["sha256"])
        for name, record in audit.get("documents", {}).items()
    }
    if set(documents) != {"main", "supplement"}:
        errors.append("Paper I document set is incomplete")
    if not all(item["hash_matches_audit"] for item in documents.values()):
        errors.append("Paper I archived PDF hash mismatch")

    return {
        "passed": not errors,
        "errors": errors,
        "title": PAPER_I_TITLE,
        "version": "v13",
        "delivery_branch": "passed",
        "positive_title_gate": True,
        "documents": documents,
        "audit_path": PAPER_I_AUDIT.as_posix(),
        "audit_sha256": sha256(repo_root / PAPER_I_AUDIT),
        "claim": (
            "Finite-size, mechanism-resolved evidence that non-Abelian projector "
            "geometry remains informative under exact spectral degeneracy."
        ),
        "recorded_plan_deviation": {
            "original_page_estimate": "14--18",
            "superseding_human_request": "detailed complete PRB long form",
            "delivery_contract": "20--26",
            "delivered_pages": audit.get("documents", {})
            .get("main", {})
            .get("structure", {})
            .get("pages"),
        },
    }


def validate_paper_ii(repo_root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if audit.get("schema") != "geometric_eth_theory_delivery_v14":
        errors.append("unexpected Paper II audit schema")
    if audit.get("passed") is not True:
        errors.append("Paper II delivery audit did not pass")
    if audit.get("selected_branch") != "random_channel_failure":
        errors.append("registered failure branch changed")
    if audit.get("selected_title") != PAPER_II_FALLBACK_TITLE:
        errors.append("fallback title changed")
    title_gate = audit.get("gates", {}).get("title_gate", {})
    if title_gate.get("gate_value") is not False:
        errors.append("positive title gate must remain false")
    if not all(gate.get("passed") is True for gate in audit.get("gates", {}).values()):
        errors.append("at least one Paper II delivery gate failed")

    documents = {
        name: _document_record(
            repo_root,
            record["delivery_path"],
            record["delivery_sha256"],
        )
        for name, record in audit.get("documents", {}).items()
    }
    if set(documents) != {"main", "supplement"}:
        errors.append("Paper II document set is incomplete")
    if not all(item["hash_matches_audit"] for item in documents.values()):
        errors.append("Paper II archived PDF hash mismatch")

    return {
        "passed": not errors,
        "errors": errors,
        "title": PAPER_II_FALLBACK_TITLE,
        "version": "v14",
        "delivery_branch": "random_channel_failure",
        "positive_title_gate": False,
        "rejected_positive_title": PAPER_II_POSITIVE_TITLE,
        "documents": documents,
        "audit_path": PAPER_II_AUDIT.as_posix(),
        "audit_sha256": sha256(repo_root / PAPER_II_AUDIT),
        "claim": (
            "An exact finite-channel cumulant theorem is proved under stated "
            "independence assumptions; the sealed chiral-index specialization "
            "fails, so N_eff alone is insufficient for the registered ensemble."
        ),
    }


def build_manifest(repo_root: Path) -> dict[str, Any]:
    paper_i_audit = json.loads((repo_root / PAPER_I_AUDIT).read_text(encoding="utf-8"))
    paper_ii_audit = json.loads((repo_root / PAPER_II_AUDIT).read_text(encoding="utf-8"))
    paper_i = validate_paper_i(repo_root, paper_i_audit)
    paper_ii = validate_paper_ii(repo_root, paper_ii_audit)

    plans = {}
    for name, relative in {
        "two_paper_design": DESIGN_PATH,
        "paper_i_implementation": PAPER_I_PLAN,
        "paper_ii_implementation": PAPER_II_PLAN,
    }.items():
        absolute = repo_root / relative
        plans[name] = {"path": relative.as_posix(), "sha256": sha256(absolute)}

    return {
        "schema": "two_paper_geometric_response_delivery_v14",
        "version": "v14",
        "passed": paper_i["passed"] and paper_ii["passed"],
        "papers": {"paper_i": paper_i, "paper_ii": paper_ii},
        "planning_contracts": plans,
        "shared_claim_boundary": {
            "exact_degeneracy_geometry_program_delivered": True,
            "asymptotic_geometric_eth_established": False,
            "universal_geometric_eth_established": False,
            "independent_cross_model_ensemble_established": False,
            "black_hole_theorem_established": False,
            "reason": (
                "Paper I is finite-size and mechanism resolved. Paper II's exact "
                "theorem is conditional, while its preregistered physical closure "
                "test selected random_channel_failure."
            ),
        },
        "reproduction": {
            "paper_i": "bash 01_task_folder/task_05/script/run_paper1_prb_delivery_v13.sh",
            "paper_ii": "bash 01_task_folder/task_05/script/run_geometric_eth_theory_delivery_v14.sh",
            "cross_paper_audit": (
                "python3 01_task_folder/task_05/script/"
                "verify_two_paper_delivery_v14.py"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest(args.repo_root.resolve())
    if args.write:
        path = args.repo_root / MANIFEST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        if not path.exists() or path.read_text(encoding="utf-8") != encoded:
            path.write_text(encoded, encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
