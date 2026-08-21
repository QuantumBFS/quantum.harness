#!/usr/bin/env python3
"""Fail-closed audit for the spectral-silence/geometric-chaos article."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from pypdf import PdfReader


SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DIR = SCRIPT_DIR.parent
REPO_ROOT = TASK_DIR.parents[1]
OUTPUT = SCRIPT_DIR / "output"
ARTICLE = REPO_ROOT / "overleaf_sync" / "geometric_eth_large_scale"
ARTICLE_TITLE = (
    "Spectral Silence and Geometric Chaos in an Exactly Degenerate "
    "Topological Manifold"
)
ARCHIVED_PDF = OUTPUT / "spectral_silence_and_geometric_chaos_v2.pdf"
REGISTERED_ARCHIVE_SHA256 = (
    "5d51ad4997a8cc95fa60fdafa02ef5aa13ad86cd31f10764b61a8f8903c2895c"
)
V2_SOURCES = (
    SCRIPT_DIR / "lgeth" / "form_factors.py",
    SCRIPT_DIR / "lgeth" / "controls.py",
    SCRIPT_DIR / "run_spectral_silence_v2.py",
    SCRIPT_DIR / "run_spectral_silence_statistics_v2.py",
    SCRIPT_DIR / "make_spectral_silence_figures_v2.py",
    Path(__file__).resolve(),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
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


def _tex_sources() -> list[Path]:
    return [
        ARTICLE / "main.tex",
        *sorted((ARTICLE / "sections").glob("*.tex")),
        *sorted((ARTICLE / "appendices").glob("*.tex")),
    ]


def _cited_keys() -> set[str]:
    keys: set[str] = set()
    for source in _tex_sources():
        text = source.read_text(encoding="utf-8")
        for content in re.findall(r"\\cite\w*\{([^}]+)\}", text):
            keys.update(key.strip() for key in content.split(","))
    return keys


def _render_pdf(pdf: Path) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(
        prefix="task05_spectral_silence_render_"
    ) as directory:
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
        records: list[dict[str, Any]] = []
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
            and not re.search(r"reference [`'][^\n]+ undefined", lowered)
        ),
        "no_undefined_citations": (
            "undefined citations" not in lowered
            and not re.search(r"citation [`'][^\n]+ undefined", lowered)
        ),
        "no_overfull_boxes": "overfull \\hbox" not in lowered,
        "no_stuck_floats": "float is stuck" not in lowered,
    }


def _manifest_checks(
    manifest: dict[str, Any],
) -> tuple[bool, bool, bool]:
    input_hashes = all(
        Path(raw_path).is_file()
        and _sha256(Path(raw_path)) == expected_hash
        for raw_path, expected_hash in manifest["inputs"].items()
    )
    figure_hashes = True
    figure_sync = True
    for figure in manifest["figures"].values():
        pdf = Path(figure["pdf"])
        png = Path(figure["png"])
        figure_hashes &= bool(
            pdf.is_file()
            and png.is_file()
            and _sha256(pdf) == figure["pdf_sha256"]
            and _sha256(png) == figure["png_sha256"]
        )
        target = ARTICLE / "figures" / pdf.name
        figure_sync &= bool(
            target.is_file() and _sha256(target) == _sha256(pdf)
        )
    return input_hashes, figure_hashes, figure_sync


def _new_reference_metadata_passes(bib_text: str) -> bool:
    required_fragments = (
        "@article{pandey2020",
        "10.1103/PhysRevX.10.041017",
        "2004.05043",
        "@misc{sharipov2024",
        "2411.11968",
        "@article{chenludwig2018",
        "10.1103/PhysRevB.98.064309",
        "1710.02686",
        "@misc{chen2026",
        "2604.23287",
    )
    return all(fragment in bib_text for fragment in required_fragments)


def run(output_json: Path) -> dict[str, Any]:
    source_json = _load(OUTPUT / "spectral_silence_v2.json")
    statistics_json = _load(
        OUTPUT / "spectral_silence_statistics_v2.json"
    )
    manifest = _load(OUTPUT / "figure_manifest_v2.json")
    physical_v1 = _load(OUTPUT / "physical_ensemble_v1.json")
    covariance_v1 = _load(OUTPUT / "covariance_model_v1.json")
    scaling_v1 = _load(OUTPUT / "rank_scaling_v1.json")
    with (
        np.load(
            OUTPUT / "spectral_silence_v2.npz",
            allow_pickle=False,
        ) as source,
        np.load(
            OUTPUT / "spectral_silence_statistics_v2.npz",
            allow_pickle=False,
        ) as statistics,
    ):
        energy_exact = bool(
            np.array_equal(source["energy_raw"], np.full(121, 50.0))
            and np.array_equal(source["energy_connected"], np.zeros(121))
        )
        structured_control = bool(
            source["structured_spectra"].shape == (24, 50)
            and np.all(source["structured_active_ranks"] == 50)
            and int(np.max(source["structured_unique_counts"])) <= 10
            and np.unique(source["structured_orbit_id"]).size == 12
        )
        geometry_axis = bool(
            source["g_spectra"].shape == (7, 4000, 50)
            and np.all(source["g_active_ranks"] == 50)
            and np.allclose(
                source["g_values"],
                [0.02, 0.05, 0.10, 0.20, 0.40, 0.70, 1.00],
            )
        )
        spectral_axis = bool(
            source["energy_spectra_alpha"].shape == (8, 4000, 50)
            and np.allclose(
                source["alpha_values"],
                [0.0, 0.10, 0.20, 0.35, 0.50, 0.70, 0.85, 1.00],
            )
            and float(np.max(source["projector_distance_alpha"])) < 1e-12
            and float(np.max(source["curvature_error_alpha"])) < 1e-12
        )
        atom_data = bool(
            int(source["rank_D"][-1]) == 800
            and int(source["rank_interior"][-1]) == 560
            and int(source["rank_atom_each"][-1]) == 120
            and abs(
                float(source["rank_interior"][-1])
                / float(source["rank_D"][-1])
                - 0.7
            )
            < 1e-12
        )
        statistics_arrays = bool(
            statistics["g_form_mean"].shape == (7, 121)
            and statistics["energy_gap_ratio_mean"].shape == (8,)
            and statistics["rank_physical_connected_full"].shape
            == (7, 121)
        )

    input_hashes, figure_hashes, figure_sync = _manifest_checks(manifest)
    generated_sync = all(
        (ARTICLE / "generated" / name).is_file()
        and _sha256(ARTICLE / "generated" / name)
        == _sha256(OUTPUT / name)
        for name in (
            "generated_numbers_v2.tex",
            "generated_tables_v2.tex",
        )
    )

    # v2 is an immutable archived delivery.  The live Overleaf tree may advance
    # to later article versions without invalidating this historical audit.
    main_pdf = ARCHIVED_PDF
    reader = PdfReader(str(main_pdf))
    metadata = reader.metadata or {}
    title = str(metadata.get("/Title", ""))
    author = str(metadata.get("/Author", ""))
    extracted = "\n".join(
        page.extract_text() or "" for page in reader.pages
    )
    render_records = _render_pdf(main_pdf)
    source_text = "\n".join(
        path.read_text(encoding="utf-8") for path in _tex_sources()
    )
    bib_path = ARTICLE / "references.bib"
    bib_text = bib_path.read_text(encoding="utf-8")
    bib_keys = _bibtex_keys(bib_path)
    cited_keys = _cited_keys()
    forbidden_task_import = any(
        re.search(r"task_0[0-46-9]", path.read_text(encoding="utf-8"))
        for path in V2_SOURCES
    )

    outcomes = statistics_json["outcomes"]
    physics_hierarchy = bool(
        abs(outcomes["physical_tau_compatibility_onset"] - 0.25) < 1e-12
        and abs(
            outcomes["first_g_with_haar_gap_ratio_interval"] - 0.20
        )
        < 1e-7
        and abs(
            outcomes["first_g_with_registered_jacobi_window"] - 0.40
        )
        < 1e-7
        and abs(
            outcomes["number_variance_compatibility_extent"] - 1.0
        )
        < 1e-12
        and outcomes["number_variance_L8_residual"]["lower"] > 0.0
    )
    endpoint_separation = bool(
        outcomes["energy_gap_ratio_endpoints"]["poisson_upper"]
        < outcomes["energy_gap_ratio_endpoints"]["gue_lower"]
    )
    v1_retained = bool(
        physical_v1["all_checks_pass"]
        and physical_v1["sample_count"] == 20_000
        and covariance_v1["all_checks_pass"]
        and covariance_v1["held_out_test"]["result_branch"]
        == "leading_covariance_capture"
        and scaling_v1["all_checks_pass"]
        and scaling_v1["cases"][-1]["D"] == 800
    )

    pytest_path = OUTPUT / "pytest_v2.txt"
    pytest_text = (
        pytest_path.read_text(encoding="utf-8")
        if pytest_path.exists()
        else ""
    )
    match = re.search(r"(\d+) passed", pytest_text)
    pytest_passed = int(match.group(1)) if match else None

    checks = {
        "source_artifact_passes": bool(source_json["all_checks_pass"]),
        "statistical_artifact_passes": bool(
            statistics_json["all_checks_pass"]
        ),
        "figure_manifest_passes": bool(manifest["all_checks_pass"]),
        "exact_energy_silence": energy_exact,
        "same_rank_structured_control": structured_control,
        "registered_geometry_axis": geometry_axis,
        "registered_spectral_axis": spectral_axis,
        "spectral_endpoint_confidence_separated": endpoint_separation,
        "finite_jacobi_numerics_pass": bool(
            source_json["finite_jacobi"]["mass_error"] < 1e-10
            and source_json["finite_jacobi"]["orthogonality_error"] < 1e-10
            and source_json["finite_jacobi"]["atom_relation_error"] < 1e-12
            and source_json["finite_jacobi"]["raw_atom_closure_error"] < 1e-10
        ),
        "atom_plateau_data_exact": atom_data,
        "registered_hierarchy_resolved": physics_hierarchy,
        "statistical_arrays_complete": statistics_arrays,
        "bootstrap_replicates_exact": (
            statistics_json["bootstrap_replicates"] == 10_000
        ),
        "v1_large_scale_evidence_retained": v1_retained,
        "figure_inputs_hashed": input_hashes,
        "figure_outputs_hashed": figure_hashes,
        "figures_synchronized": figure_sync,
        "generated_inputs_synchronized": generated_sync,
        "all_citation_keys_resolve": cited_keys <= bib_keys,
        "new_reference_metadata_registered": (
            _new_reference_metadata_passes(bib_text)
        ),
        "chen_program_positioned": (
            "chen2026" in cited_keys
            and "pandey2020" in cited_keys
            and "sharipov2024" in cited_keys
            and "chenludwig2018" in cited_keys
        ),
        "no_cross_task_v2_runtime_dependency": not forbidden_task_import,
        "article_pdf_archived": bool(
            ARCHIVED_PDF.is_file()
            and _sha256(ARCHIVED_PDF) == REGISTERED_ARCHIVE_SHA256
        ),
        "pdf_page_count_in_contract": 10 <= len(reader.pages) <= 15,
        "pdf_title_metadata": title == ARTICLE_TITLE,
        "pdf_author_metadata": (
            "Thomas J. Wang" in author and "OKongOYangO" in author
        ),
        "pdf_affiliations_visible": (
            "Tsinghua University" in extracted
            and "The Pennsylvania State University" in extracted
        ),
        "headline_claim_visible": (
            "Exact degeneracy makes the energy spectrum silent"
            in source_text
            and "projector geometry retains" in source_text
        ),
        "time_caveat_visible": (
            "not physical time" in source_text
            and "not an out-of-time-order correlator" in source_text
        ),
        "non_susy_scope_visible": (
            "no SUSY cohomology" in extracted
            and "no gravitational interpretation" in extracted
        ),
        "all_pdf_pages_rendered": (
            len(render_records) == len(reader.pages)
            and all(
                record["width"] == 1275 and record["height"] == 1650
                for record in render_records
            )
        ),
        **_latex_log_checks(ARTICLE / "main.log"),
        "pytest_complete_if_recorded": (
            pytest_passed is None or pytest_passed >= 1
        ),
    }
    audit = {
        "schema_version": 2,
        "article": ARTICLE_TITLE,
        "checks": checks,
        "all_checks_pass": bool(all(checks.values())),
        "pdf": {
            "path": str(main_pdf.relative_to(REPO_ROOT)),
            "archived_path": str(ARCHIVED_PDF.relative_to(REPO_ROOT)),
            "sha256": _sha256(main_pdf),
            "pages": len(reader.pages),
            "title": title,
            "author": author,
        },
        "rendered_pages": render_records,
        "pytest_passed": pytest_passed,
        "registered_scale": {
            "physical_matrices": physical_v1["sample_count"],
            "physical_test_matrices": 4_000,
            "structured_momenta": 24,
            "structured_orbits": 12,
            "geometric_interpolation_matrices": 7 * 4_000,
            "spectral_interpolation_matrices": 8 * 4_000,
            "haar_matrices": covariance_v1["haar_samples"],
            "root_matrices": sum(
                case["samples"] for case in scaling_v1["cases"]
            ),
            "maximum_rank": scaling_v1["cases"][-1]["D"],
            "bootstrap_replicates": (
                statistics_json["bootstrap_replicates"]
            ),
        },
        "supported_conclusion": {
            "energy_connected_sff": 0.0,
            "physical_jacobi_tau_onset": (
                outcomes["physical_tau_compatibility_onset"]
            ),
            "geometric_local_onset": (
                outcomes["first_g_with_haar_gap_ratio_interval"]
            ),
            "geometric_ramp_onset": (
                outcomes["first_g_with_registered_jacobi_window"]
            ),
            "number_variance_compatibility_extent": (
                outcomes["number_variance_compatibility_extent"]
            ),
            "D800_connected_plateau": 0.7,
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(audit, indent=2) + "\n",
        encoding="utf-8",
    )
    if not audit["all_checks_pass"]:
        failed = [key for key, value in checks.items() if not value]
        raise RuntimeError(
            f"spectral-silence delivery audit failed: {failed}"
        )
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-json",
        type=Path,
        default=OUTPUT / "spectral_silence_delivery_audit_v2.json",
    )
    args = parser.parse_args()
    audit = run(args.output_json)
    print(
        json.dumps(
            {
                "all_checks_pass": audit["all_checks_pass"],
                "pdf": audit["pdf"],
                "pytest_passed": audit["pytest_passed"],
                "registered_scale": audit["registered_scale"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
