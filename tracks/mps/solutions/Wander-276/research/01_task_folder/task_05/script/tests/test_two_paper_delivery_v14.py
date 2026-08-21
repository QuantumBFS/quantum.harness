"""Cross-paper release contract for the v13/v14 back-to-back package."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import verify_two_paper_delivery_v14 as delivery


REPO = Path(__file__).resolve().parents[4]


def test_checked_in_manifest_matches_a_fresh_audit() -> None:
    expected = delivery.build_manifest(REPO)
    observed = json.loads((REPO / delivery.MANIFEST_PATH).read_text())

    assert observed == expected
    assert observed["passed"] is True
    assert observed["papers"]["paper_i"]["delivery_branch"] == "passed"
    assert observed["papers"]["paper_ii"]["delivery_branch"] == "random_channel_failure"


def test_paper_ii_positive_title_is_fail_closed() -> None:
    manifest = delivery.build_manifest(REPO)
    paper = manifest["papers"]["paper_ii"]

    assert paper["positive_title_gate"] is False
    assert paper["title"] == delivery.PAPER_II_FALLBACK_TITLE
    assert delivery.PAPER_II_POSITIVE_TITLE not in paper["title"]


def test_tampered_delivery_audit_is_rejected() -> None:
    path = REPO / delivery.PAPER_II_AUDIT
    audit = json.loads(path.read_text())
    tampered = deepcopy(audit)
    tampered["selected_branch"] = "channel_law_validated"

    result = delivery.validate_paper_ii(REPO, tampered)

    assert result["passed"] is False
    assert "registered failure branch changed" in result["errors"]


def test_manifest_preserves_the_scientific_nonclaims() -> None:
    manifest = delivery.build_manifest(REPO)
    boundaries = manifest["shared_claim_boundary"]

    assert boundaries["asymptotic_geometric_eth_established"] is False
    assert boundaries["universal_geometric_eth_established"] is False
    assert boundaries["independent_cross_model_ensemble_established"] is False
    assert boundaries["black_hole_theorem_established"] is False


def test_all_four_archived_pdfs_match_their_registered_hashes() -> None:
    manifest = delivery.build_manifest(REPO)
    for paper in manifest["papers"].values():
        for document in paper["documents"].values():
            assert document["exists"] is True
            assert document["hash_matches_audit"] is True
            assert len(document["sha256"]) == 64
