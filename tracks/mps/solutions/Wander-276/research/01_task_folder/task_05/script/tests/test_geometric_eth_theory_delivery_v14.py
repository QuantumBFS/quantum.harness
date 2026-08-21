"""Fail-closed contracts for the Paper-II v14 delivery."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import verify_geometric_eth_theory_v14 as delivery


REPO = Path(__file__).resolve().parents[4]


def test_current_title_gate_fails_closed_to_descriptive_title() -> None:
    result = delivery.verify_title_gate(REPO)

    assert result["passed"] is True
    assert result["gate_value"] is False
    assert result["branch"] == "random_channel_failure"
    assert result["selected_title"] == delivery.SELECTED_TITLE


def test_tampered_figure_hash_is_rejected() -> None:
    manifest = json.loads((REPO / delivery.FIGURE_MANIFEST).read_text())
    corrupted = deepcopy(manifest)
    corrupted["figures"]["figure_6_effective_channel_test_v14"]["outputs"][
        "pdf"
    ]["sha256"] = "0" * 64

    result = delivery.verify_figure_manifest(REPO, corrupted)

    assert result["passed"] is False
    assert result["mismatched"] == [
        "overleaf_sync/geometric_eth_theory/figures/"
        "figure_6_effective_channel_test_v14.pdf"
    ]


def test_generated_inputs_match_in_memory_rebuild() -> None:
    result = delivery.verify_generated_inputs(REPO)

    assert result["passed"] is True
    assert result["files_checked"] == 2


def test_all_manuscript_citations_are_in_bib_and_primary_audit() -> None:
    result = delivery.verify_citations(REPO)

    assert result["passed"] is True
    assert result["citation_count"] >= 40
    assert result["missing_from_bibliography"] == []
    assert result["missing_from_audit"] == []


def test_latex_gate_rejects_bookmark_and_layout_warnings() -> None:
    text = "\n".join(
        [
            "LaTeX Warning: Reference `x' undefined",
            r"Overfull \hbox (2.0pt too wide)",
            "Package hyperref Warning: Token not allowed in a PDF string",
        ]
    )

    result = delivery.verify_latex_log_text(text)

    assert result["passed"] is False
    assert result["undefined"] == 1
    assert result["overfull"] == 1
    assert result["pdf_string_warnings"] == 1


def test_page_contract_accepts_current_long_form_shape() -> None:
    assert delivery.page_count_contract(18, main=True)[0] is True
    assert delivery.page_count_contract(14, main=True)[0] is False
    assert delivery.page_count_contract(23, main=True)[0] is False
    assert delivery.page_count_contract(7, main=False)[0] is True
    assert delivery.page_count_contract(0, main=False)[0] is False


def test_delivery_names_do_not_assert_failed_positive_title() -> None:
    for path in delivery.DELIVERY_PDFS.values():
        lowered = path.name.lower()
        assert "the_geometric_eth" not in lowered
        assert "geometric_response" in lowered


def test_one_command_runner_is_fail_fast_and_has_no_publish_side_effect() -> None:
    path = SCRIPT_ROOT / "run_geometric_eth_theory_delivery_v14.sh"
    source = path.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(path)], check=True)
    assert "set -euo pipefail" in source
    assert "verify_geometric_eth_theory_v14.py" in source
    assert not any(token in source for token in ("git push", "gh pr", "curl ", "wget "))


def test_altered_prediction_or_theorem_hash_is_rejected() -> None:
    gate = json.loads((REPO / delivery.GATE).read_text())
    hashes = deepcopy(gate["source_hashes"])
    first = next(iter(hashes))
    hashes[first] = "0" * 64

    result = delivery.verify_hashes(REPO, hashes)

    assert result["passed"] is False
    assert result["mismatched"] == [first]


def test_unsupported_gravitational_claim_is_rejected() -> None:
    result = delivery.verify_claim_text(
        "A prospective test failed. There is no asymptotic, universal result. "
        "We do not prove thermalization or black-hole Geometric ETH. "
        "N_{\\rm eff} alone does not close the data. "
        "Black holes satisfy Geometric ETH."
    )

    assert result["passed"] is False
    assert result["positive_overclaim_hits"] == [
        "black holes satisfy geometric eth"
    ]


def test_mismatched_archived_pdf_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / delivery.OUTPUT
    output.mkdir(parents=True)
    main = output / "main.pdf"
    supplement = output / "supplement.pdf"
    main.write_bytes(b"main")
    supplement.write_bytes(b"supplement")
    audit = {
        "documents": {
            "main": {
                "delivery_path": str(main.relative_to(tmp_path)),
                "delivery_sha256": "0" * 64,
            },
            "supplement": {
                "delivery_path": str(supplement.relative_to(tmp_path)),
                "delivery_sha256": delivery.sha256_file(supplement),
            },
        }
    }
    (output / "delivery_audit_v14.json").write_text(json.dumps(audit))

    result = delivery.verify_existing_archives(tmp_path)

    assert result["passed"] is False
    assert result["documents"]["main"]["passed"] is False


def test_unchanged_audit_is_not_rewritten(tmp_path: Path) -> None:
    audit = {"schema": "test", "passed": True}
    delivery.write_audit(tmp_path, audit)
    path = tmp_path / delivery.DELIVERY_AUDIT
    before = path.stat().st_mtime_ns

    delivery.write_audit(tmp_path, audit)

    assert path.stat().st_mtime_ns == before


def test_render_gate_records_one_hash_per_page() -> None:
    for relative in delivery.DELIVERY_PDFS.values():
        path = REPO / relative
        render = delivery._render_gate(path, 180)
        assert len(render["page_hashes"]) == render["rendered_pages"]
        assert all(len(page["sha256"]) == 64 for page in render["page_hashes"])
