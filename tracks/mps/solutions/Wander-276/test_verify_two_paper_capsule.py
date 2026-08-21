"""Regression tests for the self-contained Issue #276 capsule audit."""

from __future__ import annotations

from copy import deepcopy

import json

import verify_two_paper_capsule as capsule


def test_capsule_report_passes() -> None:
    report = capsule.build_report()

    assert report["passed"] is True
    assert all(report["checks"].values())


def test_hash_checker_fails_closed_on_a_wrong_hash() -> None:
    record = {"README.md": "0" * 64}

    result = capsule.check_hashes(capsule.SOLUTION_ROOT, record)

    assert result["passed"] is False
    assert result["mismatched"][0]["path"] == "README.md"


def test_positive_geometric_eth_claim_cannot_be_inferred_from_report() -> None:
    report = deepcopy(capsule.build_report())

    assert report["checks"]["paper_ii_failure_branch_preserved"] is True
    assert report["checks"]["shared_nonclaims_preserved"] is True


def test_pr_body_branch_tamper_is_rejected() -> None:
    texts = {
        relative: (capsule.SOLUTION_ROOT / relative).read_text(encoding="utf-8")
        for relative in capsule.PUBLIC_DOCUMENT_TOKENS
    }
    texts["PR_BODY.md"] = texts["PR_BODY.md"].replace(
        "random_channel_failure", "channel_law_validated"
    )

    result = capsule.validate_documentation_texts(texts)

    assert result["passed"] is False
    assert "random_channel_failure" in result["missing_tokens"]["PR_BODY.md"]


def test_team_tamper_is_rejected() -> None:
    texts = {
        relative: (capsule.SOLUTION_ROOT / relative).read_text(encoding="utf-8")
        for relative in capsule.PUBLIC_DOCUMENT_TOKENS
    }
    texts["README.md"] = texts["README.md"].replace(
        "Chenxi Wan, Yedi Shen, Junkai Wang", "Unregistered Team"
    )

    result = capsule.validate_documentation_texts(texts)

    assert result["passed"] is False
    assert "README.md" in result["missing_tokens"]


def test_issue_placeholder_is_rejected() -> None:
    texts = {
        relative: (capsule.SOLUTION_ROOT / relative).read_text(encoding="utf-8")
        for relative in capsule.PUBLIC_DOCUMENT_TOKENS
    }
    texts["PR_BODY.md"] += "\n<NEW_ISSUE_NUMBER>\n"

    result = capsule.validate_documentation_texts(texts)

    assert result["passed"] is False
    assert result["placeholders"]["PR_BODY.md"] == ["<NEW_ISSUE_NUMBER>"]


def test_v1_v12_seal_has_all_237_capsule_artifacts() -> None:
    payload = json.loads(capsule.V1_V12_SEAL.read_text(encoding="utf-8"))

    result = capsule.validate_v1_v12_manifest(payload)

    assert result["passed"] is True
    assert len(result["files"]) == 237


def test_v1_v12_seal_count_tamper_is_rejected() -> None:
    payload = json.loads(capsule.V1_V12_SEAL.read_text(encoding="utf-8"))
    payload["sealed_artifact_count"] = 236

    result = capsule.validate_v1_v12_manifest(payload)

    assert result["passed"] is False
    assert result["checks"]["declared_count"] is False
