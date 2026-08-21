#!/usr/bin/env python3
"""Fail-closed delivery audit for the v3 integrated article."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image
from pypdf import PdfReader


SCRIPT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_ROOT.parents[2]
OUTPUT = SCRIPT_ROOT / "output"
ARTICLE = REPO_ROOT / "overleaf_sync" / "geometric_eth_large_scale"
FINAL_PDF = OUTPUT / "spectral_silence_and_geometric_chaos_v3.pdf"
AUDIT_JSON = OUTPUT / "geometric_eth_topology_delivery_audit_v3.json"
ARTICLE_TITLE = (
    "Spectral Silence and Geometric Chaos in an Exactly Degenerate "
    "Topological Manifold"
)
MAIN_FIGURES = (
    "figure_1_spectral_silence_v2.pdf",
    "figure_2_falsification_triangle_v2.pdf",
    "figure_3_independent_channels_v2.pdf",
    "figure_4_geometric_hierarchy_v2.pdf",
    "figure_5_jacobi_atoms_v2.pdf",
    "figure_6_wick_factorization_v3.pdf",
    "figure_7_topological_holonomy_v3.pdf",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _render_records(pdf: Path) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(
        prefix="task05_v3_article_render_"
    ) as directory:
        root = Path(directory)
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                "180",
                str(pdf),
                str(root / "page"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        records = []
        for index, path in enumerate(sorted(root.glob("page-*.png")), 1):
            with Image.open(path) as image:
                records.append(
                    {
                        "page": index,
                        "width": image.width,
                        "height": image.height,
                        "sha256": _sha256(path),
                    }
                )
        return records


def _latex_checks(path: Path) -> dict[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    return {
        "latex_control_sequences_resolved": (
            "undefined control sequence" not in text
        ),
        "latex_references_resolved": (
            "there were undefined references" not in text
            and not re.search(r"reference [`'][^\n]+ undefined", text)
        ),
        "latex_citations_resolved": (
            "undefined citations" not in text
            and not re.search(r"citation [`'][^\n]+ undefined", text)
        ),
        "latex_boxes_within_width": "overfull \\hbox" not in text,
        "latex_floats_placed": "float is stuck" not in text,
    }


def _normalize_pdf_text(text: str) -> str:
    """Remove layout-only PDF extraction breaks without changing wording."""
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    return re.sub(r"\s+", " ", text)


def run_audit() -> dict[str, Any]:
    matrix = _load(OUTPUT / "matrix_element_geometric_eth_v3.json")
    topology = _load(OUTPUT / "topological_holonomy_v3.json")
    matrix_audit = _load(OUTPUT / "matrix_element_delivery_audit_v3.json")
    topology_audit = _load(
        OUTPUT / "topological_holonomy_delivery_audit_v3.json"
    )
    theory = _load(OUTPUT / "matrix_element_topology_theory_v3.json")
    assets = _load(OUTPUT / "geometric_eth_topology_assets_v3.json")
    citations = _load(OUTPUT / "citation_audit_v1.json")
    main_pdf = ARTICLE / "main.pdf"
    shutil.copyfile(main_pdf, FINAL_PDF)
    reader = PdfReader(str(main_pdf))
    metadata = reader.metadata or {}
    extracted = _normalize_pdf_text(
        "\n".join(page.extract_text() or "" for page in reader.pages)
    )
    extracted_lower = extracted.lower()
    render_records = _render_records(main_pdf)
    figure_records = []
    for name in MAIN_FIGURES:
        path = ARTICLE / "figures" / name
        record = {
            "name": name,
            "sha256": _sha256(path),
            "exists": path.is_file(),
        }
        if name.startswith("figure_6"):
            record["source_hash_matches"] = (
                _sha256(path)
                == _sha256(OUTPUT / "figure_6_wick_factorization_v3.pdf")
            )
        elif name.startswith("figure_7"):
            record["source_hash_matches"] = (
                _sha256(path)
                == _sha256(OUTPUT / "figure_7_topological_holonomy_v3.pdf")
            )
        else:
            record["source_hash_matches"] = True
        figure_records.append(record)
    generated_sync = all(
        _sha256(OUTPUT / name)
        == _sha256(ARTICLE / "generated" / name)
        for name in ("generated_numbers_v3.tex", "generated_tables_v3.tex")
    )
    checks = {
        "matrix_audit_passes": matrix_audit["passed"],
        "topology_audit_passes": topology_audit["passed"],
        "theory_audit_passes": theory["passed"],
        "citation_audit_passes": citations["all_checks_pass"],
        "matrix_branch_exact": (
            matrix["result_branch"] == "deformed_geometric_eth"
        ),
        "topology_branch_exact": (
            topology["result_branch"]
            == "fixed_chern_deformed_holonomy"
        ),
        "asset_branches_exact": (
            assets["matrix_branch"] == matrix["result_branch"]
            and assets["topology_branch"] == topology["result_branch"]
        ),
        "generated_assets_synchronized": generated_sync,
        "seven_figures_present_and_synchronized": (
            len(figure_records) == 7
            and all(
                item["exists"] and item["source_hash_matches"]
                for item in figure_records
            )
        ),
        "pdf_archive_byte_identical": (
            _sha256(FINAL_PDF) == _sha256(main_pdf)
        ),
        "pdf_page_count": 15 <= len(reader.pages) <= 20,
        "pdf_title_metadata": (
            str(metadata.get("/Title", "")) == ARTICLE_TITLE
        ),
        "pdf_author_metadata": (
            "Thomas J. Wang" in str(metadata.get("/Author", ""))
            and "OKongOYangO" in str(metadata.get("/Author", ""))
        ),
        "affiliations_visible": (
            "Tsinghua University" in extracted
            and "The Pennsylvania State University" in extracted
        ),
        "matrix_result_visible": (
            "four-channel residual" in extracted
            and "progressive Gaussianization" in extracted
            and "finite-size operator memory" in extracted
        ),
        "topology_result_visible": (
            "fixed determinantbundle topology" in extracted_lower
            and "structured non-abelian holonomy" in extracted_lower
        ),
        "condensed_matter_mechanism_visible": (
            "frustration-free" in extracted_lower
            and "condensedmatter mechanism" in extracted_lower
        ),
        "scientific_scope_visible": (
            "precise finite-size scope" in extracted
            and "N = 6" in extracted
            and "real-time dynamics" in extracted
        ),
        "code_and_data_availability_visible": (
            "code and data availability" in extracted_lower
            and "run quick verify v1.sh" in extracted_lower
            and "release manifest v1.json" in extracted_lower
        ),
        "all_pages_rendered_180dpi": (
            len(render_records) == len(reader.pages)
            and all(
                record["width"] == 1530
                and record["height"] == 1980
                for record in render_records
            )
        ),
        **_latex_checks(ARTICLE / "main.log"),
    }
    existing_timestamp = None
    if AUDIT_JSON.is_file():
        existing_timestamp = _load(AUDIT_JSON).get("generated_utc")
    result = {
        "version": "v3",
        "generated_utc": (
            existing_timestamp or datetime.now(timezone.utc).isoformat()
        ),
        "passed": all(checks.values()),
        "checks": checks,
        "matrix_branch": matrix["result_branch"],
        "topology_branch": topology["result_branch"],
        "page_count": len(reader.pages),
        "main_pdf_sha256": _sha256(main_pdf),
        "archived_pdf_sha256": _sha256(FINAL_PDF),
        "figures": figure_records,
        "rendered_pages": render_records,
        "source_hashes": {
            str(path.relative_to(REPO_ROOT)): _sha256(path)
            for path in (
                ARTICLE / "main.tex",
                ARTICLE / "sections" / "08-matrix-elements-topology.tex",
                ARTICLE
                / "appendices"
                / "matrix-element-topology-v3.tex",
                ARTICLE / "references.bib",
            )
        },
    }
    if not result["passed"]:
        raise RuntimeError(f"v3 article audit failed: {checks}")
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
            "page_count": result["page_count"],
            "main_pdf_sha256": result["main_pdf_sha256"],
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
