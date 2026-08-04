"""Tests for the compiled response-complex manuscript audit."""

from __future__ import annotations

import json
from pathlib import Path

from run_susy_hodge_geometric_eth_v7 import sha256
from verify_susy_hodge_manuscript_v7 import verify_manuscript


def test_manuscript_audit_checks_activation_hashes_and_pdf(tmp_path: Path) -> None:
    main = tmp_path / "main.tex"
    results = tmp_path / "results_v7.tex"
    figure = tmp_path / "figure.pdf"
    pdf = tmp_path / "main.pdf"
    archive = tmp_path / "archive.pdf"
    log = tmp_path / "main.log"
    supplement = tmp_path / "supplement.tex"
    supplement_pdf = tmp_path / "supplement.pdf"
    supplement_archive = tmp_path / "supplement-archive.pdf"
    supplement_log = tmp_path / "supplement.log"
    manifest = tmp_path / "assets.json"
    output = tmp_path / "audit.json"
    main.write_text(r"\input{generated/results_v7.tex}", encoding="utf-8")
    supplement.write_text(
        r"\input{generated/results_v7.tex}", encoding="utf-8"
    )
    results.write_text(
        "\n".join(
            (
                r"\newif\ifheldoutcomplete",
                r"\heldoutcompletetrue",
                r"\newcommand{\HeldoutBranch}{hodge\_resolved\_geometric\_eth}",
            )
        ),
        encoding="utf-8",
    )
    figure.write_bytes(b"%PDF-1.4\n" + b"x" * 2048 + b"\n%%EOF\n")
    pdf.write_bytes(b"%PDF-1.4\n" + b"y" * 2048 + b"\n%%EOF\n")
    archive.write_bytes(pdf.read_bytes())
    log.write_text("Output written on main.pdf", encoding="utf-8")
    supplement_pdf.write_bytes(
        b"%PDF-1.4\n" + b"z" * 2048 + b"\n%%EOF\n"
    )
    supplement_archive.write_bytes(supplement_pdf.read_bytes())
    supplement_log.write_text(
        "Output written on supplement.pdf", encoding="utf-8"
    )
    manifest.write_text(
        json.dumps(
            {
                "version": "v7",
                "selected_branch": "hodge_resolved_geometric_eth",
                "prediction_sha256": "a" * 64,
                "outputs": {
                    results.name: sha256(results),
                    figure.name: sha256(figure),
                },
                "checks": {"assets": True},
                "passed": True,
            }
        ),
        encoding="utf-8",
    )

    payload = verify_manuscript(
        asset_manifest_json=manifest,
        main_tex=main,
        results_tex=results,
        figure_pdf=figure,
        main_pdf=pdf,
        archive_pdf=archive,
        main_log=log,
        supplement_tex=supplement,
        supplement_pdf=supplement_pdf,
        supplement_archive_pdf=supplement_archive,
        supplement_log=supplement_log,
        output_json=output,
    )

    assert payload["passed"]

    results.write_text(
        results.read_text(encoding="utf-8")
        + "\n"
        + r"\heldoutcompletefalse",
        encoding="utf-8",
    )
    rejected = verify_manuscript(
        asset_manifest_json=manifest,
        main_tex=main,
        results_tex=results,
        figure_pdf=figure,
        main_pdf=pdf,
        archive_pdf=archive,
        main_log=log,
        supplement_tex=supplement,
        supplement_pdf=supplement_pdf,
        supplement_archive_pdf=supplement_archive,
        supplement_log=supplement_log,
        output_json=output,
    )
    assert not rejected["passed"]
    assert not rejected["checks"]["heldout_result_enabled"]
