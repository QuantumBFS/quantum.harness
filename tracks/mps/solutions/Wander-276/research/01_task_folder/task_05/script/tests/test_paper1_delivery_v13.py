"""Fail-closed contract tests for the Paper-I v13 delivery verifier."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from PIL import Image


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import verify_paper1_prb_v13 as delivery


REPO = Path(__file__).resolve().parents[4]


def test_tracked_v1_v12_tree_is_byte_sealed() -> None:
    result = delivery.verify_immutable_v1_v12(REPO)

    assert result["passed"] is True
    assert result["baseline"] == delivery.IMMUTABLE_BASE_REVISION
    assert result["sealed_artifact_count"] >= 300
    assert result["changed"] == []
    assert result["missing"] == []


def test_deliberately_tampered_source_hash_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "registered.json"
    source.write_text('{"gate": false}\n', encoding="utf-8")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_text('{"gate": true}\n', encoding="utf-8")

    result = delivery.verify_hash_contract(
        tmp_path,
        {"registered.json": expected},
    )

    assert result["passed"] is False
    assert result["mismatched"] == ["registered.json"]


def test_deliberately_deleted_figure_is_rejected() -> None:
    manifest_path = REPO / delivery.FIGURE_MANIFEST_RELATIVE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corrupted = deepcopy(manifest)
    corrupted["figures"]["4"]["outputs"]["pdf"]["path"] = (
        "overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures/"
        "deliberately_deleted_figure_v13.pdf"
    )

    result = delivery.verify_figure_manifest(REPO, corrupted)

    assert result["passed"] is False
    assert result["figures"]["4"]["outputs"]["pdf"]["exists"] is False


def test_outlined_font_figures_still_pass_vector_content_gate() -> None:
    figure_root = REPO / delivery.MANUSCRIPT_RELATIVE / "figures"

    assert delivery._pdf_has_vector_content(
        figure_root / "figure_3_geometric_hierarchy_v13.pdf"
    )
    assert delivery._pdf_has_vector_content(
        figure_root / "figure_4_independent_channels_v13.pdf"
    )


def test_raster_only_pdf_fails_vector_content_gate(tmp_path: Path) -> None:
    raster_pdf = tmp_path / "raster-only.pdf"
    Image.new("RGB", (160, 120), "white").save(raster_pdf, format="PDF")

    assert delivery._pdf_has_vector_content(raster_pdf) is False


def test_deliberately_inserted_positive_overclaim_is_rejected() -> None:
    prose = (
        "We establish universal Geometric ETH, demonstrate thermalization and "
        "extract Lyapunov behavior from an independent ensemble."
    )

    hits = delivery._positive_claim_hits(prose)

    assert hits
    assert "universal Geometric ETH" in hits[0]


def test_established_independent_ensemble_claim_is_rejected() -> None:
    hits = delivery._positive_claim_hits(
        "An independent disorder ensemble has been established."
    )

    assert hits == ["An independent disorder ensemble has been established."]


def test_absent_claim_boundary_sentences_fail_closed(tmp_path: Path) -> None:
    manuscript = tmp_path / delivery.MANUSCRIPT_RELATIVE
    manuscript.mkdir(parents=True)
    filler = " ".join(["finite-rank"] * 90)
    (manuscript / "main.tex").write_text(
        rf"\begin{{abstract}}{filler}\end{{abstract}}" + "\n",
        encoding="utf-8",
    )
    (manuscript / "sections").mkdir()

    result = delivery.verify_claim_boundaries(tmp_path)

    assert result["passed"] is False
    assert not all(result["required_negative_boundaries"].values())


def test_manually_altered_empirical_macro_is_rejected(tmp_path: Path) -> None:
    registry = json.loads(
        (REPO / delivery.REGISTRY_RELATIVE).read_text(encoding="utf-8")
    )
    import make_paper1_prb_assets_v13 as assets

    manuscript = tmp_path / delivery.MANUSCRIPT_RELATIVE
    generated = manuscript / "generated"
    sections = manuscript / "sections"
    generated.mkdir(parents=True)
    sections.mkdir()
    (manuscript / "main.tex").write_text("", encoding="utf-8")
    renderers = {
        "results_v13.tex": assets.render_results,
        "evidence_matrix_v13.tex": assets.render_evidence_matrix,
        "model_table_v13.tex": assets.render_model_table,
    }
    for filename, renderer in renderers.items():
        (generated / filename).write_text(renderer(registry), encoding="utf-8")
    results = generated / "results_v13.tex"
    results.write_text(
        results.read_text(encoding="utf-8").replace(
            r"\newcommand{\MooreReadNSixRank}{120}",
            r"\newcommand{\MooreReadNSixRank}{121}",
        ),
        encoding="utf-8",
    )

    result = delivery.verify_generated_assets(tmp_path, registry)

    assert result["passed"] is False
    assert result["files"]["results_v13.tex"]["matches_registry_renderer"] is False


def test_undefined_citation_and_overfull_box_are_rejected() -> None:
    log = "\n".join(
        [
            "LaTeX Warning: Citation `missing' on page 1 undefined on input line 4.",
            r"Overfull \hbox (9.0pt too wide) in paragraph at lines 8--10",
        ]
    )

    result = delivery.verify_latex_log_text(log)

    assert result["passed"] is False
    assert result["undefined_references_or_citations"] == 1
    assert result["overfull_boxes"] == 1


def test_mismatched_archived_pdf_is_rejected(tmp_path: Path) -> None:
    archived = tmp_path / delivery.DELIVERY_PDFS["main"]
    archived.parent.mkdir(parents=True)
    archived.write_bytes(b"%PDF-original")
    expected = hashlib.sha256(archived.read_bytes()).hexdigest()
    archived.write_bytes(b"%PDF-corrupt")
    previous = {"documents": {"main": {"sha256": expected}}}

    result = delivery.verify_existing_archive(tmp_path, previous)

    assert result["passed"] is False
    assert result["documents"]["main"]["passed"] is False


def test_atomic_audit_keeps_mode_and_timestamp_on_identical_second_run(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "nested" / "audit.json"
    first = delivery.write_audit_atomic(
        destination,
        {"generated_utc": "2026-08-21T01:00:00+00:00", "passed": True},
    )
    second = delivery.write_audit_atomic(
        destination,
        {"generated_utc": "2026-08-21T02:00:00+00:00", "passed": True},
    )

    assert first["generated_utc"] == second["generated_utc"]
    assert stat.S_IMODE(destination.stat().st_mode) == 0o644
    assert not list(destination.parent.glob(f".{destination.name}.*.tmp"))


def test_output_atomic_copy_is_mode_0644(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    destination = tmp_path / "delivery" / "paper.pdf"
    source.write_bytes(b"%PDF-fixture")

    delivery._atomic_copy(source, destination)

    assert destination.read_bytes() == source.read_bytes()
    assert stat.S_IMODE(destination.stat().st_mode) == 0o644


def test_long_form_main_page_contract_accepts_20_through_26_pages() -> None:
    for pages in range(20, 27):
        passed, label = delivery.page_count_contract(pages, main=True)
        assert passed is True
        assert "detailed PRB long form" in label


def test_long_form_main_page_contract_rejects_shorter_and_longer_pdfs() -> None:
    for pages in (0, 1, 14, 18, 19, 27, 40):
        passed, _ = delivery.page_count_contract(pages, main=True)
        assert passed is False


def test_supplement_page_contract_remains_open_ended_and_nonempty() -> None:
    assert delivery.page_count_contract(0, main=False)[0] is False
    assert delivery.page_count_contract(1, main=False)[0] is True
    assert delivery.page_count_contract(50, main=False)[0] is True


def test_verifier_has_no_pyyaml_dependency() -> None:
    source = (SCRIPT_ROOT / "verify_paper1_prb_v13.py").read_text(encoding="utf-8")

    assert "import yaml" not in source
    assert "from yaml" not in source


def test_one_command_script_is_fail_fast_and_has_no_upload() -> None:
    path = SCRIPT_ROOT / "run_paper1_prb_delivery_v13.sh"
    source = path.read_text(encoding="utf-8")

    subprocess.run(["bash", "-n", str(path)], check=True)
    assert "set -euo pipefail" in source
    assert "test_paper1_delivery_v13.py" in source
    assert "verify_paper1_prb_v13.py" in source
    assert "latexmk" not in source  # compilation is owned by the verifier
    assert not any(token in source for token in ("git push", "gh pr", "curl ", "wget "))
