"""Data-driven manuscript and compiled-delivery tests for v12."""

from __future__ import annotations

import json
from pathlib import Path

from make_cross_mechanism_manuscript_assets_v12 import build_manuscript_assets
from verify_cross_mechanism_manuscript_v12 import (
    ARCHIVE_PDF,
    OUTPUT_JSON,
    verify_manuscript,
)


def test_manuscript_assets_are_generated_from_passed_sources(tmp_path) -> None:
    results = tmp_path / "results_v12.tex"
    table = tmp_path / "mechanism_table_v12.tex"
    figure = tmp_path / "cross_mechanism_v12.pdf"
    manifest_path = tmp_path / "manifest.json"
    manifest = build_manuscript_assets(
        results_tex=results,
        table_tex=table,
        figure_target=figure,
        manifest_json=manifest_path,
    )
    assert manifest["passed"] is True
    assert manifest["selected_branch"] == "domain_limited_geometric_eth"
    assert all(manifest["checks"].values())
    text = results.read_text(encoding="utf-8")
    assert r"\newcommand{\MRNFourCumulant}{0.1909}" in text
    assert r"\newcommand{\MRNSixCumulant}{0.1936}" in text
    assert r"\newcommand{\LatticeCumulants}{-0.1640,\,-0.1480,\,0.1687}" in text
    assert figure.read_bytes().startswith(b"%PDF-")
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest


def test_compiled_manuscript_delivery_passes() -> None:
    audit = verify_manuscript()
    assert audit["passed"] is True
    assert all(audit["checks"].values())


def test_reverification_does_not_rewrite_an_unchanged_audit() -> None:
    before = Path(OUTPUT_JSON).read_bytes()
    audit = verify_manuscript()
    assert audit["passed"] is True
    assert Path(OUTPUT_JSON).read_bytes() == before


def test_manuscript_audit_rejects_tampered_archive(tmp_path) -> None:
    archive = tmp_path / "tampered.pdf"
    archive.write_bytes(Path(ARCHIVE_PDF).read_bytes() + b"tampered")
    audit = verify_manuscript(
        archive_pdf=archive,
        output_json=tmp_path / "audit.json",
    )
    assert audit["passed"] is False
    assert audit["checks"]["archived_main_exact"] is False
