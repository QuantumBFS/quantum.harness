#!/usr/bin/env python3
"""Fail-closed integrity audit for the self-contained Issue #276 capsule."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable


SOLUTION_ROOT = Path(__file__).resolve().parent
RESEARCH_ROOT = SOLUTION_ROOT / "research"
SCRIPT_ROOT = RESEARCH_ROOT / "01_task_folder/task_05/script"
PAPER_I_AUDIT = SCRIPT_ROOT / "output/paper1_prb_v13/delivery_audit_v13.json"
PAPER_II_AUDIT = SCRIPT_ROOT / "output/geometric_eth_theory_v14/delivery_audit_v14.json"
COMBINED_MANIFEST = (
    SCRIPT_ROOT / "output/two_paper_delivery_v14/two_paper_manifest_v14.json"
)
V1_V12_SEAL = SOLUTION_ROOT / "v1_v12_seal_manifest.json"
V1_V12_SEAL_SHA256 = "ee88feab8b51247680a3efb2f52f8e6ca7c5479d5c114addd74a085fead25174"
V1_V12_SOURCE_REVISION = "73a8a67c4e1886bffc6f00482d8fd96122922abd"

REQUIRED_DOCUMENTATION = (
    "README.md",
    "PR_BODY.md",
    "research/README.md",
    "research/01_task_folder/task_05/README.md",
    "research/docs/2026-08-21-two-paper-reviewer-guide.md",
    "research/docs/2026-08-21-two-paper-reproducibility.md",
    "research/docs/2026-08-21-two-paper-submission-checklist.md",
    "research/docs/CITATION-two-paper-v14.cff",
)

DOCUMENT_HASHES = {
    "README.md": "9be6461a39a4815d78fd7c84415e18be90792a5a68c246d432c9ce08eb18fc82",
    "PR_BODY.md": "9597021ef27acc8d38c32899e513af5e495af9ef3167e653e40633e53c50ecb3",
    "research/docs/2026-08-21-two-paper-reviewer-guide.md": (
        "4d63df682c4ed4325f5361cc6dd2f560733965d73dcd0d0dce2d898d4aabba10"
    ),
    "research/docs/2026-08-21-two-paper-reproducibility.md": (
        "2e0c1f06ced66bf15e5d9be5471152d41d38208bdd6d7a320fcd32947c564679"
    ),
    "research/docs/2026-08-21-two-paper-submission-checklist.md": (
        "9010ff9ecf86d5c6884fcbe64d00cda69941a69d13f03dd82563a089dec1e945"
    ),
    "research/docs/CITATION-two-paper-v14.cff": (
        "2b47daef6c54e57dbc9261d80dff3ee0c9878b7b805f86c94c94320392505280"
    ),
}

PUBLIC_DOCUMENT_TOKENS = {
    "README.md": (
        "Issue #276",
        "Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe",
        "Geometric Response of Exactly Degenerate Quantum State Bundles",
        "random_channel_failure",
        "257b1c10e75f7104d4a70afbd3b9c9056e197036a5f4c216f3789af8c513746a",
        "45984eed2daa8df1c741a5924287664a3c0b9508389be8681232a91ed54c0d20",
        "Chenxi Wan, Yedi Shen, Junkai Wang",
        "WangTheoPhys@outlook.com",
        "Not established here: asymptotic or universal Geometric ETH",
    ),
    "PR_BODY.md": (
        "Related issue: #276",
        "Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe",
        "Geometric Response of Exactly Degenerate Quantum State Bundles",
        "random_channel_failure",
        "257b1c10e75f7104d4a70afbd3b9c9056e197036a5f4c216f3789af8c513746a",
        "45984eed2daa8df1c741a5924287664a3c0b9508389be8681232a91ed54c0d20",
        "Chenxi Wan, Yedi Shen, Junkai Wang",
        "WangTheoPhys@outlook.com",
        "does not claim an established asymptotic or universal Geometric ETH",
    ),
    "research/docs/2026-08-21-two-paper-reviewer-guide.md": (
        "random-channel confidence intervals do not enter the development band",
        "Is Geometric ETH established asymptotically? | No",
        "Is a black-hole or thermalization theorem claimed? | No",
    ),
    "research/docs/2026-08-21-two-paper-reproducibility.md": (
        "Frozen-artifact manuscript rebuilds",
        "Paper II scientific recalculation",
        "random_channel_failure",
    ),
    "research/docs/2026-08-21-two-paper-submission-checklist.md": (
        "Reuse the existing Quantum Harness Issue #276",
        "update open PR #283",
    ),
    "research/docs/CITATION-two-paper-v14.cff": (
        "Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe",
        "Geometric Response of Exactly Degenerate Quantum State Bundles",
    ),
}

EXPECTED_TITLES = {
    "paper_i": "Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe",
    "paper_ii": "Geometric Response of Exactly Degenerate Quantum State Bundles",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_hashes(root: Path, records: dict[str, str]) -> dict[str, Any]:
    missing: list[str] = []
    mismatched: list[dict[str, str]] = []
    for relative, expected in sorted(records.items()):
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        observed = sha256(path)
        if observed != expected:
            mismatched.append(
                {"path": relative, "expected": expected, "observed": observed}
            )
    return {
        "passed": not missing and not mismatched,
        "checked_count": len(records),
        "missing": missing,
        "mismatched": mismatched,
    }


def paper_i_hash_records(audit: dict[str, Any]) -> dict[str, str]:
    records: dict[str, str] = {}
    registry = audit["registry"]
    records[registry["path"]] = registry["sha256"]
    records.update(registry["required_source_hashes"]["observed_hashes"])
    records.update(audit["figures"]["source_hashes"]["observed_hashes"])
    for figure in audit["figures"]["figures"].values():
        for output in figure["outputs"].values():
            records[output["path"]] = output["sha256"]
    for document in audit["documents"].values():
        records[document["path"]] = document["sha256"]
    generated_root = "overleaf_sync/exactly_degenerate_quantum_chaos_prb/generated"
    for name, record in audit["generated_assets"]["files"].items():
        records[f"{generated_root}/{name}"] = record["sha256"]
    return records


def large_files(root: Path, maximum_bytes: int = 50 * 1024 * 1024) -> list[dict[str, Any]]:
    failures = []
    for path in root.rglob("*"):
        if path.is_file() and path.stat().st_size > maximum_bytes:
            failures.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                }
            )
    return failures


def missing_files(root: Path, paths: Iterable[str]) -> list[str]:
    return [relative for relative in paths if not (root / relative).is_file()]


def validate_documentation_texts(texts: dict[str, str]) -> dict[str, Any]:
    missing_tokens: dict[str, list[str]] = {}
    placeholders: dict[str, list[str]] = {}
    forbidden_placeholders = ("<NEW_ISSUE_NUMBER>", "<PLACEHOLDER>", "TBD")
    for relative, tokens in PUBLIC_DOCUMENT_TOKENS.items():
        text = texts.get(relative, "")
        absent = [token for token in tokens if token not in text]
        if absent:
            missing_tokens[relative] = absent
        found = [token for token in forbidden_placeholders if token in text]
        if found:
            placeholders[relative] = found
    return {
        "passed": not missing_tokens and not placeholders,
        "missing_tokens": missing_tokens,
        "placeholders": placeholders,
    }


def validate_v1_v12_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = payload.get("files", {})
    checks = {
        "schema": payload.get("schema")
        == "quantum_harness_wander_276_v1_v12_capsule_seal",
        "source_revision": payload.get("source_revision") == V1_V12_SOURCE_REVISION,
        "declared_count": payload.get("sealed_artifact_count") == 237,
        "actual_count": isinstance(files, dict) and len(files) == 237,
        "hash_format": isinstance(files, dict)
        and all(
            isinstance(path, str)
            and isinstance(digest, str)
            and len(digest) == 64
            and set(digest) <= set("0123456789abcdef")
            for path, digest in files.items()
        ),
    }
    return {"passed": all(checks.values()), "checks": checks, "files": files}


def build_report() -> dict[str, Any]:
    sys.path.insert(0, str(SCRIPT_ROOT))
    import verify_two_paper_delivery_v14 as combined  # noqa: PLC0415

    paper_i = json.loads(PAPER_I_AUDIT.read_text(encoding="utf-8"))
    paper_ii = json.loads(PAPER_II_AUDIT.read_text(encoding="utf-8"))
    checked_in_manifest = json.loads(COMBINED_MANIFEST.read_text(encoding="utf-8"))
    v1_v12_payload = json.loads(V1_V12_SEAL.read_text(encoding="utf-8"))
    rebuilt_manifest = combined.build_manifest(RESEARCH_ROOT)

    paper_i_hashes = check_hashes(RESEARCH_ROOT, paper_i_hash_records(paper_i))
    paper_ii_hashes = check_hashes(RESEARCH_ROOT, paper_ii["source_hashes"])
    docs_missing = missing_files(SOLUTION_ROOT, REQUIRED_DOCUMENTATION)
    documentation_hashes = check_hashes(SOLUTION_ROOT, DOCUMENT_HASHES)
    documentation_texts = {
        relative: (SOLUTION_ROOT / relative).read_text(encoding="utf-8")
        for relative in PUBLIC_DOCUMENT_TOKENS
        if (SOLUTION_ROOT / relative).is_file()
    }
    documentation_semantics = validate_documentation_texts(documentation_texts)
    v1_v12_manifest = validate_v1_v12_manifest(v1_v12_payload)
    v1_v12_hashes = check_hashes(RESEARCH_ROOT, v1_v12_manifest["files"])
    v1_v12_seal_file_matches = sha256(V1_V12_SEAL) == V1_V12_SEAL_SHA256
    oversized = large_files(SOLUTION_ROOT)

    boundaries = checked_in_manifest.get("shared_claim_boundary", {})
    nonclaims_pass = all(
        boundaries.get(key) is False
        for key in (
            "asymptotic_geometric_eth_established",
            "universal_geometric_eth_established",
            "independent_cross_model_ensemble_established",
            "black_hole_theorem_established",
        )
    )
    titles_pass = {
        key: checked_in_manifest.get("papers", {}).get(key, {}).get("title") == title
        for key, title in EXPECTED_TITLES.items()
    }
    branch_pass = (
        checked_in_manifest.get("papers", {})
        .get("paper_ii", {})
        .get("delivery_branch")
        == "random_channel_failure"
        and checked_in_manifest.get("papers", {})
        .get("paper_ii", {})
        .get("positive_title_gate")
        is False
    )

    checks = {
        "combined_manifest_rebuild": checked_in_manifest == rebuilt_manifest,
        "combined_manifest_passed": checked_in_manifest.get("passed") is True,
        "paper_i_audit_passed": paper_i.get("passed") is True,
        "paper_i_registered_hashes": paper_i_hashes["passed"],
        "paper_ii_audit_passed": paper_ii.get("passed") is True,
        "paper_ii_registered_hashes": paper_ii_hashes["passed"],
        "paper_ii_failure_branch_preserved": branch_pass,
        "titles_match_registered_branches": all(titles_pass.values()),
        "shared_nonclaims_preserved": nonclaims_pass,
        "required_documentation_present": not docs_missing,
        "documentation_hashes_frozen": documentation_hashes["passed"],
        "documentation_semantics_registered": documentation_semantics["passed"],
        "v1_v12_manifest_registered": (
            v1_v12_manifest["passed"] and v1_v12_seal_file_matches
        ),
        "v1_v12_artifacts_byte_sealed": v1_v12_hashes["passed"],
        "no_file_exceeds_50_mib": not oversized,
    }
    return {
        "schema": "quantum_harness_issue_276_two_paper_capsule_v14",
        "passed": all(checks.values()),
        "checks": checks,
        "details": {
            "paper_i_hashes": paper_i_hashes,
            "paper_ii_hashes": paper_ii_hashes,
            "titles": titles_pass,
            "missing_documentation": docs_missing,
            "documentation_hashes": documentation_hashes,
            "documentation_semantics": documentation_semantics,
            "v1_v12_manifest": {
                "path": V1_V12_SEAL.relative_to(SOLUTION_ROOT).as_posix(),
                "sha256": sha256(V1_V12_SEAL),
                "expected_sha256": V1_V12_SEAL_SHA256,
                "validation": {
                    "passed": v1_v12_manifest["passed"],
                    "checks": v1_v12_manifest["checks"],
                },
            },
            "v1_v12_hashes": v1_v12_hashes,
            "oversized_files": oversized,
            "combined_manifest_sha256": sha256(COMBINED_MANIFEST),
        },
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
