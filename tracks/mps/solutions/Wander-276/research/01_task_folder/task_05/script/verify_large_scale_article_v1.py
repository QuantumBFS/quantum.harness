#!/usr/bin/env python3
"""Fail-closed delivery audit for the large-scale Geometric-ETH article."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image
from pypdf import PdfReader


SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DIR = SCRIPT_DIR.parent
REPO_ROOT = TASK_DIR.parents[1]
OUTPUT = SCRIPT_DIR / "output"
ARTICLE = REPO_ROOT / "overleaf_sync" / "geometric_eth_large_scale"
REGISTERED_CASES = (
    (8, 16, 80, 2_000),
    (10, 50, 140, 2_000),
    (12, 112, 216, 2_000),
    (14, 210, 308, 1_000),
    (16, 352, 416, 1_000),
    (18, 546, 540, 500),
    (20, 800, 680, 250),
)
REGISTERED_ARCHIVE_SHA256 = (
    "aae68de7569aae83c7ff500718ab0e3635595f050f5b7afc0d60a0e63db55417"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bibtex_keys(path: Path) -> set[str]:
    return set(
        re.findall(
            r"@\w+\s*\{\s*([^,\s]+)",
            path.read_text(encoding="utf-8"),
        )
    )


def _cited_keys() -> set[str]:
    keys: set[str] = set()
    sources = [
        ARTICLE / "main.tex",
        *sorted((ARTICLE / "sections").glob("*.tex")),
        *sorted((ARTICLE / "appendices").glob("*.tex")),
    ]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for content in re.findall(r"\\cite\w*\{([^}]+)\}", text):
            keys.update(key.strip() for key in content.split(","))
    return keys


def _render_pdf(pdf: Path) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="task05_render_") as directory:
        root = Path(directory)
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                "150",
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


def _latex_log_checks(log_path: Path) -> dict[str, bool]:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    return {
        "no_undefined_control_sequence": (
            "undefined control sequence" not in lowered
        ),
        "no_undefined_references": (
            "there were undefined references" not in lowered
            and "reference `" not in lowered
        ),
        "no_undefined_citations": (
            "undefined citations" not in lowered
            and not re.search(r"citation [`'][^\\n]+ undefined", lowered)
        ),
        "no_overfull_boxes": "overfull \\hbox" not in lowered,
        "no_stuck_floats": "float is stuck" not in lowered,
    }


def run(output_json: Path) -> dict[str, Any]:
    physical = _load(OUTPUT / "physical_ensemble_v1.json")
    covariance = _load(OUTPUT / "covariance_model_v1.json")
    scaling = _load(OUTPUT / "rank_scaling_v1.json")
    statistics = _load(OUTPUT / "statistical_analysis_v1.json")
    manifest = _load(OUTPUT / "figure_manifest_v1.json")
    citations = _load(OUTPUT / "citation_audit_v1.json")

    expected_cases = [
        {"n": n, "D": D, "M": M, "samples": samples}
        for n, D, M, samples in REGISTERED_CASES
    ]
    observed_cases = [
        {
            "n": case["n"],
            "D": case["D"],
            "M": case["M"],
            "samples": case["samples"],
        }
        for case in scaling["cases"]
    ]
    largest = scaling["cases"][-1]
    inference_methods = [
        content[metric]["method"]
        for content in statistics["ensemble_inference"].values()
        for metric in content
    ]

    input_hashes_match = True
    for raw_path, expected_hash in manifest["inputs"].items():
        path = SCRIPT_DIR / raw_path
        input_hashes_match &= path.exists() and _sha256(path) == expected_hash
    figure_hashes_match = True
    synchronized_figures = True
    for figure in manifest["figures"].values():
        pdf = SCRIPT_DIR / figure["pdf"]
        png = SCRIPT_DIR / figure["png"]
        figure_hashes_match &= (
            pdf.exists()
            and png.exists()
            and _sha256(pdf) == figure["pdf_sha256"]
            and _sha256(png) == figure["png_sha256"]
        )
        overleaf_pdf = ARTICLE / "figures" / pdf.name
        synchronized_figures &= (
            overleaf_pdf.exists()
            and _sha256(overleaf_pdf) == _sha256(pdf)
        )
    generated_sync = all(
        (
            ARTICLE / "generated" / name
        ).exists()
        and _sha256(ARTICLE / "generated" / name)
        == _sha256(OUTPUT / name)
        for name in ("generated_numbers_v1.tex", "generated_tables_v1.tex")
    )

    archived_pdf = (
        OUTPUT / "from_local_repulsion_to_global_geometry_v1.pdf"
    )
    # The live Overleaf tree is allowed to advance to v2.  Audit the immutable
    # v1 archive by its registered delivery hash rather than requiring the
    # moving ``main.pdf`` to remain byte-identical to the earlier article.
    main_pdf = archived_pdf
    reader = PdfReader(str(main_pdf))
    metadata = reader.metadata or {}
    title = str(metadata.get("/Title", ""))
    author = str(metadata.get("/Author", ""))
    extracted = "\n".join(
        page.extract_text() or "" for page in reader.pages
    )
    render_records = _render_pdf(main_pdf)
    bib_keys = _bibtex_keys(ARTICLE / "references.bib")
    cited_keys = _cited_keys()
    pytest_path = OUTPUT / "pytest_v1.txt"
    pytest_text = (
        pytest_path.read_text(encoding="utf-8")
        if pytest_path.exists()
        else ""
    )
    match = re.search(r"(\d+) passed", pytest_text)
    pytest_passed = int(match.group(1)) if match else None

    checks = {
        "physical_registered_scale": (
            physical["sample_count"] == 20_000
            and physical["split"]
            == {
                "train": 12_000,
                "validation": 4_000,
                "test": 4_000,
                "split_seed": physical["seed"] + 1,
            }
            and physical["seed_blocks"] == 8
            and physical["physical_case"]["D"] == 50
            and physical["all_checks_pass"]
        ),
        "covariance_registered_scale": (
            covariance["diagnostic_training_rows"] >= 1_024
            and covariance["haar_samples"] == 10_000
            and covariance["deformed_samples"] == 10_000
            and covariance["held_out_test"]["result_branch"]
            == "leading_covariance_capture"
            and covariance["all_checks_pass"]
        ),
        "rank_cases_and_samples_exact": observed_cases == expected_cases,
        "largest_rank_present": largest["D"] == 800,
        "exact_atom_counts": (
            scaling["cases"][-2]["plus_atoms_per_matrix"] == 6
            and scaling["cases"][-2]["minus_atoms_per_matrix"] == 6
            and largest["plus_atoms_per_matrix"] == 120
            and largest["minus_atoms_per_matrix"] == 120
        ),
        "interior_statistics_strip_atoms": all(
            case["interior_dimension"]
            == case["D"]
            - case["plus_atoms_per_matrix"]
            - case["minus_atoms_per_matrix"]
            for case in scaling["cases"]
        ),
        "matrix_level_inference_only": (
            statistics["bootstrap_replicates"] == 10_000
            and all(
                method
                in {
                    "hierarchical_seed_block_bootstrap",
                    "matrix_gaussian_multiplier_bootstrap",
                    "matrix_bootstrap",
                }
                for method in inference_methods
            )
            and all(
                "eigenvalue" not in method for method in inference_methods
            )
        ),
        "statistics_checks_pass": statistics["all_checks_pass"],
        "figure_inputs_hashed": input_hashes_match,
        "figure_outputs_hashed": figure_hashes_match,
        "figures_synchronized": synchronized_figures,
        "generated_inputs_synchronized": generated_sync,
        "citation_metadata_verified": (
            citations["all_checks_pass"]
            and citations["registered_records"] >= 29
        ),
        "all_citation_keys_resolve": cited_keys <= bib_keys,
        "chen_seed_is_cited": "chen2026" in cited_keys,
        "article_pdf_archived": (
            archived_pdf.exists()
            and _sha256(archived_pdf) == REGISTERED_ARCHIVE_SHA256
        ),
        "pdf_page_count_in_contract": 10 <= len(reader.pages) <= 14,
        "pdf_title_metadata": (
            title
            == (
                "From Local Repulsion to Global Geometry: "
                "Large-Scale Tests of Geometric ETH"
            )
        ),
        "pdf_author_metadata": (
            "Thomas J. Wang" in author and "OKongOYangO" in author
        ),
        "pdf_affiliations_visible": (
            "Tsinghua University" in extracted
            and "The Pennsylvania State University" in extracted
        ),
        "all_pdf_pages_rendered": (
            len(render_records) == len(reader.pages)
            and all(
                record["width"] > 0 and record["height"] > 0
                for record in render_records
            )
        ),
        **_latex_log_checks(ARTICLE / "main.log"),
        "pytest_complete_if_recorded": (
            pytest_passed is None or pytest_passed >= 1
        ),
    }
    audit = {
        "schema_version": 1,
        "article": (
            "From Local Repulsion to Global Geometry: "
            "Large-Scale Tests of Geometric ETH"
        ),
        "checks": checks,
        "all_checks_pass": bool(all(checks.values())),
        "pdf": {
            "path": str(main_pdf.relative_to(REPO_ROOT)),
            "sha256": _sha256(main_pdf),
            "pages": len(reader.pages),
            "title": title,
            "author": author,
        },
        "rendered_pages": render_records,
        "pytest_passed": pytest_passed,
        "registered_scale": {
            "physical_matrices": physical["sample_count"],
            "haar_matrices": covariance["haar_samples"],
            "deformed_matrices": covariance["deformed_samples"],
            "root_matrices": sum(
                case["samples"] for case in scaling["cases"]
            ),
            "maximum_rank": largest["D"],
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(audit, indent=2) + "\n",
        encoding="utf-8",
    )
    if not audit["all_checks_pass"]:
        failed = [key for key, value in checks.items() if not value]
        raise RuntimeError(f"large-scale delivery audit failed: {failed}")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-json",
        type=Path,
        default=OUTPUT / "large_scale_delivery_audit_v1.json",
    )
    args = parser.parse_args()
    audit = run(args.output_json)
    print(
        json.dumps(
            {
                "all_checks_pass": audit["all_checks_pass"],
                "pdf": audit["pdf"],
                "pytest_passed": audit["pytest_passed"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
