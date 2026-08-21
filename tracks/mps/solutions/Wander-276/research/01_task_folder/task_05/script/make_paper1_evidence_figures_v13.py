#!/usr/bin/env python3
"""Assemble the audited seven-figure package for Paper I v13."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.colors import ListedColormap
from matplotlib.font_manager import findfont


VERSION = "v13"
SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO = SCRIPT_ROOT.parents[2]
DEFAULT_PREVIEW_ROOT = SCRIPT_ROOT / "output" / "paper1_prb_v13"
DEFAULT_FIGURE_ROOT = (
    DEFAULT_REPO / "overleaf_sync" / "exactly_degenerate_quantum_chaos_prb" / "figures"
)
DEFAULT_MANIFEST = DEFAULT_PREVIEW_ROOT / "figure_manifest_v13.json"

# Immutable source contracts.  Figure 1 and the generated v13 registry are
# verified from their own manifests/content because they are produced earlier
# in the same additive release.
SOURCE_HASHES: dict[str, str] = {
    "01_task_folder/task_05/script/output/figure_1_spectral_silence_v2.pdf": "b3c5967fb225d6a3adaa52adff34017bec1034111fa9cc669d33af661aa70d8a",
    "01_task_folder/task_05/script/output/figure_4_geometric_hierarchy_v2.pdf": "56367dc2c3d2cd1c9d9c5af0e5b6a1b62bb635c8d9115dffb71d2f633b5aeef2",
    "01_task_folder/task_05/script/output/figure_3_independent_channels_v2.pdf": "28bad44f157c0fdc418d9c56ba218e245890d6e3bea327bcd8ff5f0dfa145d95",
    "01_task_folder/task_05/script/output/figure_7_topological_holonomy_v3.pdf": "11e101309d975a61a3efedb1025c2552149c7f1a6f72433594f4adb1c0a16258",
    "01_task_folder/task_05/script/output/spectral_silence_v2.json": "5a2da65d83ded56a0fbebb23f69d5c26bd41382ebaa5f32a333fb239bffd5778",
    "01_task_folder/task_05/script/output/spectral_silence_statistics_v2.json": "2808020357176fa6f60d0280c509e2dea18b8d472c8a9090f8b6f619a1dfe706",
    "01_task_folder/task_05/script/output/spectral_silence_statistics_v2.npz": "ef2bf7bdfea65e595def17d8b08ac0786a86afeb4e57aea71c7472504b7c773e",
    "01_task_folder/task_05/script/output/matrix_element_geometric_eth_v3.json": "bbacad6f795559f417c1e39c034a6fe51669fd509a983099c10965fb68ee34a3",
    "01_task_folder/task_05/script/output/matrix_element_geometric_eth_v3.npz": "c817a758fd03710483883840758a28ba2d5d9c74270a8f30ad71874a6336262c",
    "01_task_folder/task_05/script/output/continuum_lll_replication_inference_v6.json": "21ac615ff44ddc466a1feb5c3d6f411bde9c3d34f06fb9dc570b6e77766193b6",
    "01_task_folder/task_05/script/output/topological_holonomy_v3.json": "ff15e7cd2f947b43da5a5973bb82c50319b164877883d187c7c46b2a073823c6",
    "01_task_folder/task_05/script/output/topological_holonomy_v3.npz": "f459fa37facf82c6f67c44f4961749095fb0817516ff16d6ca6814bbaf952208",
    "01_task_folder/task_05/script/output/cross_mechanism_geometric_eth_v12.json": "18933c332747e9a134536dc06fceed5751e5575595e315e50c2f0d93e6005b86",
    "01_task_folder/task_05/script/output/paper1_prb_v13/centered_complete_covariance_v13.json": "ea75047473001032c1875a02944329d3db054e788945f7882d88154a7a1ee3fc",
    "01_task_folder/task_05/script/output/xcube_v11/xcube_geometric_control_v11.json": "c75f8a27b263d71aaf1535ed0ab54f248c67335836c3543e1b95642d1ee3cc84",
}

COPY_SOURCES = {
    "2": "01_task_folder/task_05/script/output/figure_1_spectral_silence_v2.pdf",
    "3": "01_task_folder/task_05/script/output/figure_4_geometric_hierarchy_v2.pdf",
    "4": "01_task_folder/task_05/script/output/figure_3_independent_channels_v2.pdf",
    "6": "01_task_folder/task_05/script/output/figure_7_topological_holonomy_v3.pdf",
}

OUTPUT_STEMS = {
    "2": "figure_2_spectral_silence_v13",
    "3": "figure_3_geometric_hierarchy_v13",
    "4": "figure_4_independent_channels_v13",
    "5": "figure_5_wick_parent_dependence_v13",
    "6": "figure_6_fixed_chern_holonomy_v13",
    "7": "figure_7_cross_mechanism_v13",
}

CAPTION_DATA: dict[str, dict[str, Any]] = {
    "2": {
        "claim": "Exact energy degeneracy makes connected spectral statistics silent while projector geometry remains resolved.",
        "panels": ["energy SFF", "curvature spectra", "curvature SFF", "long-range residual"],
        "uncertainty_unit": "complete physical panel against registered finite-Jacobi ensembles",
    },
    "3": {
        "claim": "Local curvature correlations become compatible before the form-factor ramp, while long-range memory survives.",
        "panels": ["residual flow", "local/ramp onset", "registered ramp window", "number-variance memory"],
        "uncertainty_unit": "complete orbit or ensemble draw as registered in spectral_silence_statistics_v2",
    },
    "4": {
        "claim": "Intrafiber spectral scrambling and off-fiber projector motion are independent response channels.",
        "panels": ["PHP interpolation", "fixed projector", "off-fiber interpolation", "two-axis classification"],
        "uncertainty_unit": "registered interpolation endpoint ensemble",
    },
    "5": {
        "claim": "The historical separable proper-complex two-pairing Wick null leaves a finite residual in the lattice FCI, while the continuum-LLL no-refit law fails across tangent classes.",
        "panels": ["lattice-FCI separable proper-complex Wick residual", "residual to the two-pairing null", "continuum-LLL tangent classes", "sealed no-refit residual"],
        "uncertainty_unit": "24 physical panels against the restricted separable proper-complex two-pairing null for the lattice FCI; complete-panel bootstrap and registered prediction intervals for continuum LLL",
        "limitation": "The v3 lattice statistic uses the historical two-pairing null. The two parents are compared through the same normalized four-channel observable, not pooled into one uncertainty estimate.",
    },
    "6": {
        "claim": "Chern number and the exact spectrum remain fixed while non-Abelian Wilson-loop statistics change without reaching CUE.",
        "panels": ["fixed Chern and gap", "determinant winding", "Wilson gap ratio", "Wilson form factor"],
        "uncertainty_unit": "registered isospectral deformation and CUE reference draws",
    },
    "7": {
        "claim": "With exact population centering and a frozen 12/12 whitening split, the Bonferroni-corrected directional gate is positive only at finite-rank Moore-Read N6; lattice SUSY is not resolved.",
        "panels": ["historical two-pairing residuals", "centered covariance: finite-rank N6-only; lattice SUSY not resolved", "exact-population-centered and whitened primary estimates", "exact X-cube controls"],
        "panel_a_statistic": "The v9/v10 local_R4 data use the historical separable proper-complex two-pairing residual R4^(2pair).",
        "panel_c_statistic": "The centered-whitened complete cumulant uses exact population centering; only the 2x2 channel whitening map is fitted on the 12-panel training half before evaluation on 12 disjoint inference panels.",
        "population_mean_contract": "Moore-Read uses the exact uniform average over all torus guiding-density anchors (zero); lattice SUSY uses exact enumeration of the registered ordered local-coordinate channel marginals.",
        "inference_contract": "The reverse split is descriptive and not pooled. Bonferroni family alpha = 0.05; per-case alpha = 0.01 over five registered primary cases, using a one-sided Student-t11 finite-sample reference.",
        "uncertainty_unit": "Directional estimate plus or minus delete-one jackknife standard error over the 12 primary inference tangent panels.",
        "limitation": "finite-rank boundary: N6-only denotes the displayed Moore-Read rank-120 case; the other four registered primary cases do not pass. Moore-Read N6 Student-t11 one-sided p = 0.00272 and familywise lower = 0.03916.",
    },
}

REVIEWED_VISUAL_AUDIT = {
    "1": "Reviewed in Task 4 at original resolution; block labels, response chain, and four textured classes are unclipped.",
    "2": "The vector-safe v13 title correction is legible at 100% double-column width; all four source panels remain unclipped.",
    "3": "Heat map, onset markers, and long-range residual labels remain distinguishable at 100% width.",
    "4": "The two interpolation axes and fixed-projector control are legible; line style and marker shape supplement color.",
    "5": "The historical separable proper-complex two-pairing null is named explicitly; all four recomposed panels are unclipped and the two parents are not visually pooled.",
    "6": "Chern, winding, Wilson-gap, and Wilson-SFF panels remain legible; the CUE band does not obscure data markers.",
    "7": "The 2x2 recomposition keeps model names readable; panel (a) retains the historical two-pairing residual, panel (b) reports finite-rank N6-only and lattice SUSY not resolved, and panel (c) marks the sole passing primary case with a filled star while open family-specific markers denote failures.",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def _record_path(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _verify_sources(
    repo_root: Path,
    expected_source_hashes: dict[str, str] | None,
) -> dict[str, str]:
    expected = dict(SOURCE_HASHES)
    if expected_source_hashes:
        unknown = set(expected_source_hashes).difference(expected)
        if unknown:
            raise RuntimeError(f"unknown source hash override: {sorted(unknown)}")
        expected.update(expected_source_hashes)
    actual: dict[str, str] = {}
    for relative, registered_hash in expected.items():
        path = repo_root / relative
        if not path.is_file():
            raise RuntimeError(f"missing source artifact: {relative}")
        digest = _sha256(path)
        if digest != registered_hash:
            raise RuntimeError(
                f"source hash mismatch for {relative}: expected {registered_hash}, got {digest}"
            )
        actual[relative] = digest
    return actual


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp" + destination.suffix)
    shutil.copyfile(source, temporary)
    temporary.replace(destination)


def _outline_fonts(source: Path, destination: Path) -> None:
    """Convert PDF fonts to vector outlines without rasterizing the artwork."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.font-outline.pdf")
    temporary.unlink(missing_ok=True)
    subprocess.run(
        [
            "gs",
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-dNoOutputFonts",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.7",
            "-dAutoRotatePages=/None",
            "-dOmitInfoDate=true",
            "-dOmitID=true",
            f"-sOutputFile={temporary}",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = temporary.read_bytes()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    stable_uuid = (
        f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-"
        f"{digest[16:20]}-{digest[20:32]}"
    ).encode("ascii")
    payload, replacements = re.subn(
        rb"(?<=xmpMM:DocumentID='uuid:)[0-9a-fA-F-]{36}(?=')",
        stable_uuid,
        payload,
    )
    if replacements != 1:
        raise RuntimeError(
            f"expected one Ghostscript XMP document identifier, found {replacements}"
        )
    temporary.write_bytes(payload)
    temporary.replace(destination)


def _correct_figure_2_title(source: Path, destination: Path) -> None:
    """Replace one over-broad title while preserving the source PDF as vector art."""

    try:
        import fitz
    except ImportError as error:  # pragma: no cover - environment contract
        alternate_python = shutil.which("python3")
        if alternate_python is None or Path(alternate_python).resolve() == Path(sys.executable).resolve():
            raise RuntimeError(
                "PyMuPDF is required for the Figure 2 vector text correction"
            ) from error
        subprocess.run(
            [
                alternate_python,
                str(Path(__file__).resolve()),
                "--correct-figure-2-source",
                str(source),
                "--correct-figure-2-destination",
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return

    old_title = "Ramp universal, long range nonuniversal"
    new_title = "Finite-D ramp agreement, long-range excess"
    document = fitz.open(source)
    matches = [
        (page, rectangle)
        for page in document
        for rectangle in page.search_for(old_title)
    ]
    if len(matches) != 1:
        document.close()
        raise RuntimeError(
            f"expected one Figure 2 title match, found {len(matches)}"
        )
    page, rectangle = matches[0]
    page_number = page.number
    page.add_redact_annot(rectangle, fill=(1.0, 1.0, 1.0))
    page.apply_redactions(images=0, graphics=0, text=0)
    replacement_box = fitz.Rect(
        rectangle.x0,
        rectangle.y0 - 2.0,
        page.rect.width - 8.0,
        rectangle.y1 + 5.0,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    redacted = destination.with_name(f".{destination.stem}.redacted.pdf")
    outlined = destination.with_name(f".{destination.stem}.outlined.pdf")
    temporary = destination.with_name(f".{destination.stem}.corrected.pdf")
    for path in (redacted, outlined, temporary):
        path.unlink(missing_ok=True)
    document.save(
        redacted,
        garbage=4,
        clean=True,
        deflate=True,
        no_new_id=True,
        preserve_metadata=True,
    )
    document.close()
    try:
        _outline_fonts(redacted, outlined)
        outlined_document = fitz.open(outlined)
        outlined_page = outlined_document[page_number]
        outlined_page.insert_font(
            fontname="FSerif",
            fontfile=findfont("DejaVu Serif"),
        )
        unused_height = outlined_page.insert_textbox(
            replacement_box,
            new_title,
            fontname="FSerif",
            fontsize=8.6,
            color=(0.0, 0.0, 0.0),
            align=fitz.TEXT_ALIGN_LEFT,
            overlay=True,
        )
        if unused_height < 0:
            outlined_document.close()
            raise RuntimeError(
                "corrected Figure 2 title does not fit its vector text box"
            )
        outlined_document.save(
            temporary,
            garbage=4,
            clean=True,
            deflate=True,
            no_new_id=True,
            preserve_metadata=True,
        )
        outlined_document.close()
        temporary.replace(destination)
    finally:
        for path in (redacted, outlined, temporary):
            path.unlink(missing_ok=True)


def _render_preview(pdf_path: Path, png_path: Path) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    base = png_path.with_name(png_path.stem + ".rendering")
    rendered = Path(str(base) + ".png")
    if rendered.exists():
        rendered.unlink()
    subprocess.run(
        [
            "pdftoppm",
            "-png",
            "-r",
            "300",
            "-singlefile",
            str(pdf_path),
            str(base),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if not rendered.is_file():
        raise RuntimeError(f"pdftoppm did not create preview for {pdf_path}")
    rendered.replace(png_path)


def _pdf_dimensions_inches(pdf_path: Path) -> list[float]:
    output = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    match = re.search(r"Page size:\s+([0-9.]+) x ([0-9.]+) pts", output)
    if match is None:
        raise RuntimeError(f"cannot read PDF dimensions: {pdf_path}")
    return [round(float(match.group(1)) / 72.0, 4), round(float(match.group(2)) / 72.0, 4)]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _figure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.4,
            "axes.labelsize": 7.5,
            "axes.titlesize": 8.1,
            "axes.titleweight": "normal",
            "legend.fontsize": 6.4,
            "xtick.labelsize": 6.8,
            "ytick.labelsize": 6.8,
            "axes.linewidth": 0.75,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _panel_label(axis: Axes, label: str) -> None:
    axis.text(
        -0.14,
        1.04,
        f"({label})",
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.2,
        fontweight="bold",
        clip_on=False,
    )


def _metadata(title: str, source_hashes: dict[str, str]) -> dict[str, Any]:
    source_digest = hashlib.sha256(
        json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    timestamp = datetime(2026, 8, 17, tzinfo=timezone.utc)
    return {
        "Title": title,
        "Author": "Chaos of Quantum Geometry collaboration",
        "Subject": f"Source contract SHA-256: {source_digest}",
        "CreationDate": timestamp,
        "ModDate": timestamp,
    }


def _recompose_figure_5(repo_root: Path, output_pdf: Path) -> None:
    output = repo_root / "01_task_folder/task_05/script/output"
    lattice = _load_json(output / "matrix_element_geometric_eth_v3.json")
    continuum = _load_json(output / "continuum_lll_replication_inference_v6.json")
    if lattice.get("result_branch") != "deformed_geometric_eth":
        raise RuntimeError("unexpected lattice-FCI v3 result branch")
    if continuum.get("branch") != "parent_dependent_geometry":
        raise RuntimeError("unexpected continuum-LLL v6 result branch")
    if not all(lattice.get("checks", {}).values()) or not all(
        continuum.get("checks", {}).values()
    ):
        raise RuntimeError("Figure 5 source checks do not all pass")

    cases = sorted(lattice["cases"], key=lambda item: int(item["N"]))
    particle = np.asarray([item["N"] for item in cases], dtype=float)
    physical = np.asarray([item["physical_R4_median"] for item in cases], dtype=float)
    physical_interval = np.asarray([item["physical_R4_interval"] for item in cases], dtype=float)
    structured = np.asarray([item["structured_R4"] for item in cases], dtype=float)
    gaussian = np.asarray([item["gaussian_R4_interval"] for item in cases], dtype=float)

    prediction_cases = continuum["scores"]["common_plateau_external"]["cases"]
    classes = list(continuum["configuration"]["classes"])
    class_labels = {
        "guiding_density": "guiding density",
        "magnetic_bond": "magnetic bond",
        "magnetic_current": "magnetic current",
    }
    colors = {
        "guiding_density": "#2A5C8A",
        "magnetic_bond": "#D56A1F",
        "magnetic_current": "#148A82",
    }
    markers = {"guiding_density": "o", "magnetic_bond": "s", "magnetic_current": "D"}

    _figure_style()
    figure, axes = plt.subplots(2, 2, figsize=(7.0, 5.6), constrained_layout=True)
    navy, orange, teal, grey, pale = "#294F76", "#D56A1F", "#238C91", "#6E7781", "#DDE6EF"

    axis = axes[0, 0]
    _panel_label(axis, "a")
    axis.fill_between(
        particle,
        gaussian[:, 0],
        gaussian[:, 2],
        color=pale,
        label="two-pairing Gaussian 95%",
    )
    axis.plot(
        particle,
        gaussian[:, 1],
        "-",
        color=grey,
        lw=1.1,
        label="two-pairing Gaussian median",
    )
    axis.errorbar(
        particle,
        physical,
        yerr=np.vstack((physical - physical_interval[:, 0], physical_interval[:, 1] - physical)),
        fmt="o-",
        color=orange,
        lw=1.35,
        ms=3.8,
        capsize=2.0,
        label="local-density panels",
    )
    axis.plot(particle, structured, "D--", color=teal, lw=1.15, ms=3.4, label="Fourier panel")
    axis.set_xticks(particle)
    axis.set_xlabel("particle number $N$")
    axis.set_ylabel("historical four-channel residual $R_4$")
    axis.set_title("Lattice FCI: separable proper-complex Wick residual")
    axis.legend(frameon=False, loc="upper right")
    axis.grid(alpha=0.18, lw=0.5)

    axis = axes[0, 1]
    _panel_label(axis, "b")
    axis.axhline(0.0, color="#555555", lw=0.7)
    axis.plot(particle, physical - gaussian[:, 1], "o-", color=orange, lw=1.35, ms=3.8, label="local density")
    axis.plot(particle, structured - gaussian[:, 1], "D--", color=teal, lw=1.15, ms=3.4, label="Fourier")
    axis.set_xticks(particle)
    axis.set_xlabel("particle number $N$")
    axis.set_ylabel(r"$R_4-\mathrm{median}(R_4^{\mathrm{2pair}})$")
    axis.set_title("Residual to the two-pairing null")
    axis.legend(frameon=False)
    axis.grid(alpha=0.18, lw=0.5)

    axis = axes[1, 0]
    _panel_label(axis, "c")
    offsets = np.linspace(-0.08, 0.08, len(classes))
    for offset, operator_class in zip(offsets, classes, strict=True):
        selected = sorted(
            (item for item in prediction_cases if item["operator_class"] == operator_class),
            key=lambda item: int(item["N"]),
        )
        x = np.asarray([item["N"] for item in selected], dtype=float) + offset
        y = np.asarray([item["observed_delta4"] for item in selected], dtype=float)
        intervals = np.asarray(
            [item["complete_panel_observation_interval_secondary"] for item in selected],
            dtype=float,
        )
        axis.errorbar(
            x,
            y,
            yerr=np.vstack((y - intervals[:, 0], intervals[:, 1] - y)),
            fmt=markers[operator_class] + "-",
            color=colors[operator_class],
            lw=1.1,
            ms=3.5,
            capsize=1.8,
            label=class_labels[operator_class],
        )
    axis.set_xticks((3, 4, 5))
    axis.set_xlabel("particle number $N$")
    axis.set_ylabel(r"continuum connected excess $\Delta_4$")
    axis.set_title("Continuum LLL: three physical tangent classes")
    axis.legend(frameon=False, ncol=1)
    axis.grid(alpha=0.18, lw=0.5)

    axis = axes[1, 1]
    _panel_label(axis, "d")
    axis.axhline(0.0, color="#555555", lw=0.75)
    covered = 0
    total = 0
    for offset, operator_class in zip(offsets, classes, strict=True):
        selected = sorted(
            (item for item in prediction_cases if item["operator_class"] == operator_class),
            key=lambda item: int(item["N"]),
        )
        x = np.asarray([item["N"] for item in selected], dtype=float) + offset
        observed = np.asarray([item["observed_delta4"] for item in selected], dtype=float)
        predicted = np.asarray([item["predicted_delta4"] for item in selected], dtype=float)
        residual = observed - predicted
        intervals = np.asarray(
            [item["complete_panel_observation_interval_secondary"] for item in selected],
            dtype=float,
        )
        axis.errorbar(
            x,
            residual,
            yerr=np.vstack((observed - intervals[:, 0], intervals[:, 1] - observed)),
            fmt=markers[operator_class] + "-",
            color=colors[operator_class],
            lw=1.1,
            ms=3.5,
            capsize=1.8,
            label=class_labels[operator_class],
        )
        covered += sum(bool(item["registered_covered"]) for item in selected)
        total += len(selected)
    axis.set_xticks((3, 4, 5))
    axis.set_xlabel("particle number $N$")
    axis.set_ylabel("observed $-$ registered prediction")
    axis.set_title("Continuum LLL: registered no-refit law")
    axis.text(
        0.50,
        0.03,
        f"registered point coverage: {covered}/{total}\nerror bars: observation bootstrap",
        transform=axis.transAxes,
        ha="center",
        va="bottom",
        fontsize=5.9,
        color="#8B2E2E",
    )
    axis.grid(alpha=0.18, lw=0.5)

    source_hashes = {
        relative: SOURCE_HASHES[relative]
        for relative in (
            "01_task_folder/task_05/script/output/matrix_element_geometric_eth_v3.json",
            "01_task_folder/task_05/script/output/matrix_element_geometric_eth_v3.npz",
            "01_task_folder/task_05/script/output/continuum_lll_replication_inference_v6.json",
        )
    }
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_pdf, format="pdf", metadata=_metadata("Wick residuals and parent dependence", source_hashes))
    plt.close(figure)


def _recompose_figure_7(repo_root: Path, output_pdf: Path) -> str:
    output = repo_root / "01_task_folder/task_05/script/output"
    registry_path = output / "paper1_prb_v13/evidence_registry_v13.json"
    corrected_path = output / "paper1_prb_v13/centered_complete_covariance_v13.json"
    registry = _load_json(registry_path)
    corrected = _load_json(corrected_path)
    cross = _load_json(output / "cross_mechanism_geometric_eth_v12.json")
    if registry.get("claims", {}).get("asymptotic_geometric_eth") is not False:
        raise RuntimeError("Figure 7 requires a false asymptotic-Geometric-ETH gate")
    if cross.get("all_checks_pass") is not True:
        raise RuntimeError("cross-mechanism v12 source checks do not pass")
    protocol = corrected.get("protocol", {})
    if (
        corrected.get("schema") != "paper1_centered_complete_covariance_v13"
        or corrected.get("version") != "v13"
        or protocol.get("entrywise_mean")
        != "exact_registered_finite_ensemble_population_mean"
        or protocol.get("channel_whitening") != "training_2x2_Gram_only"
        or protocol.get("familywise_method") != "Bonferroni"
        or protocol.get("family_alpha") != 0.05
        or protocol.get("per_case_alpha") != 0.01
        or protocol.get("primary_case_family_size") != 5
        or protocol.get("reverse_split_role")
        != "descriptive_replication_not_pooled"
    ):
        raise RuntimeError("unexpected centered complete-covariance v13 protocol")
    corrected_models = corrected.get("models", {})
    expected_gates = {
        "moore_read_N4": False,
        "moore_read_N6": True,
        "lattice_susy_m1": False,
        "lattice_susy_m2": False,
        "lattice_susy_m3": False,
    }
    if (
        set(corrected_models) != set(expected_gates)
        or corrected.get("corrected_primary_positive_directional_gate")
        != expected_gates
    ):
        raise RuntimeError("centered complete-covariance primary gate set changed")
    for model_key, expected_gate in expected_gates.items():
        statistic = corrected_models[model_key].get(
            "centered_whitened_complete_cumulant", {}
        )
        primary = statistic.get("primary", {})
        reverse = statistic.get("reverse_descriptive", {})
        summary = primary.get("summary", {})
        audit = primary.get("transform_audit", {})
        expected_mean = (
            "exact_uniform_average_over_all_torus_guiding_density_anchors"
            if model_key.startswith("moore_read")
            else "exact_enumeration_of_ordered_local_coordinate_channel_marginals"
        )
        if (
            statistic.get("statistic") != "centered_whitened_complete_cumulant"
            or primary.get("inferential_role") != "primary_frozen_12_12_split"
            or primary.get("claim_eligible") is not True
            or primary.get("family_alpha") != 0.05
            or primary.get("per_case_alpha") != 0.01
            or primary.get("familywise_method")
            != "Bonferroni_over_registered_primary_cases_with_Student_t11"
            or primary.get("student_t_degrees_of_freedom") != 11
            or primary.get("gate_for_claim") is not expected_gate
            or (primary.get("familywise_one_sided_interval_low", 0.0) > 0.0)
            is not expected_gate
            or reverse.get("inferential_role")
            != "descriptive_replication_not_pooled"
            or reverse.get("claim_eligible") is not False
            or summary.get("realization_count") != 12
            or summary.get("pairing_count") != 3
            or audit.get("training_count") != 12
            or audit.get("inference_count") != 12
            or audit.get("population_mean_exact_for_registered_finite_ensemble")
            is not True
            or audit.get("centering_not_estimated_from_training_panels") is not True
            or audit.get("channel_whitener_fitted_only_on_training") is not True
            or audit.get("population_mean_provenance") != expected_mean
            or not all(summary.get("checks", {}).values())
        ):
            raise RuntimeError(
                f"centered complete-covariance audit failed for {model_key}"
            )
    n6_familywise_low = float(
        corrected_models["moore_read_N6"]["centered_whitened_complete_cumulant"]
        ["primary"]["familywise_one_sided_interval_low"]
    )
    if not np.isclose(n6_familywise_low, 0.039160542331358184, atol=5e-15, rtol=0.0):
        raise RuntimeError("Moore-Read N6 familywise lower bound changed")
    models = registry["models"]

    _figure_style()
    figure, axes = plt.subplots(2, 2, figsize=(7.0, 5.6), constrained_layout=True)
    navy, red, purple, grey = "#1769AA", "#C62828", "#6A1B9A", "#4D5963"

    axis = axes[0, 0]
    _panel_label(axis, "a")
    moore = sorted(models["moore_read"]["cases"], key=lambda item: item["fiber_rank"])
    lattice = sorted(models["lattice_susy"]["cases"], key=lambda item: item["fiber_rank"])
    mr_rank = np.asarray([item["fiber_rank"] for item in moore], dtype=float)
    mr_median = np.asarray([item["local_R4_median"] for item in moore], dtype=float)
    mr_range = np.asarray([item["local_R4"] for item in moore], dtype=float)
    axis.errorbar(
        mr_rank,
        mr_median,
        yerr=np.vstack((mr_median - mr_range.min(axis=1), mr_range.max(axis=1) - mr_median)),
        fmt="o-",
        color=navy,
        lw=1.2,
        ms=3.8,
        capsize=2,
        label="Moore–Read: two local panels",
    )
    ls_rank = np.asarray([item["fiber_rank"] for item in lattice], dtype=float)
    axis.plot(ls_rank, [item["local_R4"] for item in lattice], "s-", color=red, lw=1.15, ms=3.5, label="lattice SUSY: local")
    axis.plot(ls_rank, [item["isotropic_R4"] for item in lattice], "s--", markerfacecolor="white", color=red, lw=1.05, ms=3.5, label="lattice SUSY: isotropic")
    axis.set_xscale("log", base=2)
    axis.set_xlabel("degenerate-fiber rank $D$")
    axis.set_ylabel(r"historical two-pairing residual $R_4^{\mathrm{2pair}}$")
    axis.set_title("Opened finite-size responses")
    axis.legend(frameon=False, loc="best")
    axis.grid(alpha=0.18, lw=0.5)

    axis = axes[0, 1]
    _panel_label(axis, "b")
    row_keys = ["laughlin", "moore_read", "lattice_susy", "susy_syk", "xcube"]
    row_labels = ["Laughlin", "Moore–Read", "lattice SUSY", "SUSY SYK", "X-cube"]
    columns = [
        "exact fiber +\nresponse",
        "production",
        "centered complete\ncovariance",
        "independent\nensemble",
    ]
    values = np.zeros((5, 4), dtype=int)
    labels: list[list[str]] = []
    for row, key in enumerate(row_keys):
        model = models[key]
        if key == "xcube":
            values[row] = 3
            labels.append(["exact", "exact", "exact control", "not applicable"])
            continue
        production = bool(model["production_complete"])
        independent = bool(model["independent_ensemble_complete"])
        if key == "moore_read":
            covariance_value = 2
            covariance_label = "finite-rank\nN6-only"
        elif key == "lattice_susy":
            covariance_value = 0
            covariance_label = "not\nresolved"
        else:
            covariance_value = 0
            covariance_label = "not tested"
        values[row] = [
            1,
            1 if production else 0,
            covariance_value,
            1 if independent else 0,
        ]
        labels.append(
            [
                "established",
                "complete" if production else "pending",
                covariance_label,
                "complete" if independent else "pending",
            ]
        )
    cmap = ListedColormap(["#E0E0E0", "#2C78B8", "#E9A126", "#6A1B9A"])
    axis.imshow(values, aspect="auto", vmin=-0.5, vmax=3.5, cmap=cmap)
    axis.set_xticks(range(4), columns, rotation=24, ha="right")
    axis.set_yticks(range(5), row_labels)
    for row in range(5):
        for column in range(4):
            axis.text(
                column,
                row,
                labels[row][column],
                ha="center",
                va="center",
                fontsize=5.6,
                color="white" if values[row, column] in {1, 3} else "#20252A",
            )
    axis.set_xticks(np.arange(-0.5, 4, 1), minor=True)
    axis.set_yticks(np.arange(-0.5, 5, 1), minor=True)
    axis.grid(which="minor", color="white", lw=1.1)
    axis.tick_params(which="minor", bottom=False, left=False)
    axis.set_title("Evidence gates are reported separately")

    axis = axes[1, 0]
    _panel_label(axis, "c")
    case_order = (
        ("moore_read_N4", "MR N4, D=42", "o", navy),
        ("moore_read_N6", "MR N6, D=120", "o", navy),
        ("lattice_susy_m1", "LS m1, D=2", "s", red),
        ("lattice_susy_m2", "LS m2, D=4", "s", red),
        ("lattice_susy_m3", "LS m3, D=8", "s", red),
    )
    covariance_rows: list[tuple[str, float, float, str, str, bool]] = []
    for case_key, label, marker, color in case_order:
        primary = corrected_models[case_key][
            "centered_whitened_complete_cumulant"
        ]["primary"]
        summary = primary["summary"]
        covariance_rows.append(
            (
                label,
                float(summary["directional_estimate"]),
                float(summary["standard_error"]),
                marker,
                color,
                bool(primary["gate_for_claim"]),
            )
        )
    y = np.arange(len(covariance_rows))
    for index, (
        label,
        estimate,
        standard_error,
        marker,
        color,
        passed,
    ) in enumerate(covariance_rows):
        axis.errorbar(
            estimate,
            index,
            xerr=standard_error,
            fmt="*" if passed else marker,
            markerfacecolor="#E9A126" if passed else "white",
            markeredgecolor="#20252A" if passed else color,
            color="#20252A" if passed else color,
            capsize=2,
            ms=7 if passed else 4,
        )
    axis.axvline(0.0, color="#555555", lw=0.7)
    axis.set_yticks(y, [item[0] for item in covariance_rows])
    axis.invert_yaxis()
    axis.set_xlabel(r"directional estimate $\pm$ jackknife SE")
    axis.set_title(
        "Exact-population-centered complete cumulant\n"
        "primary 12/12 split; training-only $2\\times2$ whitening"
    )
    axis.text(
        0.98,
        0.54,
        "filled star: finite-rank N6-only pass\n"
        "open markers: gate not passed\n"
        "Bonferroni: family alpha=0.05, per-case=0.01\n"
        f"N6 familywise lower={n6_familywise_low:.5f}",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=5.45,
        color="#3F474F",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.86, "pad": 1.5},
    )
    axis.grid(axis="x", alpha=0.18, lw=0.5)

    axis = axes[1, 1]
    _panel_label(axis, "d")
    xcube = models["xcube"]
    x = np.arange(2)
    curvature = [float(xcube["coefficient_curvature"]), float(xcube["transport_curvature_eigenvalue"])]
    variance = [0.0, float(xcube["transport_connected_variance"])]
    axis.axhline(0.0, color="#777777", lw=0.7)
    axis.plot(x, curvature, "D-", color=purple, lw=1.25, ms=4.2, label="distinct curvature eigenvalue")
    axis.plot(x, variance, "o--", color=grey, lw=1.05, ms=3.8, label="connected variance")
    axis.set_xticks(x, ["coefficient\nreweighting", "unitary\ntransport"])
    axis.set_ylabel("X-cube geometric observable")
    axis.set_ylim(-0.58, 0.10)
    axis.set_title("Exact structured control")
    axis.legend(frameon=False, loc="lower left")
    axis.grid(axis="y", alpha=0.18, lw=0.5)

    registry_hash = _sha256(registry_path)
    source_hashes = {
        "01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json": registry_hash,
        **{
            relative: SOURCE_HASHES[relative]
            for relative in (
                "01_task_folder/task_05/script/output/cross_mechanism_geometric_eth_v12.json",
                "01_task_folder/task_05/script/output/paper1_prb_v13/centered_complete_covariance_v13.json",
                "01_task_folder/task_05/script/output/xcube_v11/xcube_geometric_control_v11.json",
            )
        },
    }
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_pdf, format="pdf", metadata=_metadata("Cross-mechanism evidence gates", source_hashes))
    plt.close(figure)
    return registry_hash


def _figure_one_record(repo_root: Path, visual_note: str) -> dict[str, Any]:
    manifest_path = repo_root / "01_task_folder/task_05/script/output/paper1_prb_v13/figure_1_protection_mixing_v13.json"
    manifest = _load_json(manifest_path)
    pdf = repo_root / manifest["outputs"]["pdf"]["path"]
    png = repo_root / manifest["outputs"]["png"]["path"]
    if _sha256(pdf) != manifest["outputs"]["pdf"]["sha256"]:
        raise RuntimeError("Figure 1 PDF hash no longer matches its manifest")
    if _sha256(png) != manifest["outputs"]["png"]["sha256"]:
        raise RuntimeError("Figure 1 PNG hash no longer matches its manifest")
    registry_path = repo_root / "01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json"
    if _canonical_json_hash(_load_json(registry_path)) != manifest["source_hash"]:
        raise RuntimeError("Figure 1 source registry no longer matches its manifest")
    return {
        "mode": "generated_separately",
        "source_hashes": {
            "01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json": _sha256(registry_path)
        },
        "outputs": manifest["outputs"],
        "dimensions_inches": manifest["dimensions_inches"],
        "dpi": manifest["dpi"],
        "vector_pdf": True,
        "caption_data": manifest["caption_data"],
        "visual_audit": visual_note,
    }


def assemble_figures(
    repo_root: Path,
    *,
    figure_root: Path | None = None,
    preview_root: Path | None = None,
    manifest_path: Path | None = None,
    expected_source_hashes: dict[str, str] | None = None,
    visual_audit_notes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Assemble Figures 1--7 and write a fail-closed provenance manifest."""

    repo_root = Path(repo_root).resolve()
    figure_root = Path(figure_root) if figure_root is not None else (
        repo_root / "overleaf_sync/exactly_degenerate_quantum_chaos_prb/figures"
    )
    preview_root = Path(preview_root) if preview_root is not None else (
        repo_root / "01_task_folder/task_05/script/output/paper1_prb_v13"
    )
    manifest_path = Path(manifest_path) if manifest_path is not None else preview_root / "figure_manifest_v13.json"
    verified_hashes = _verify_sources(repo_root, expected_source_hashes)
    visual = visual_audit_notes or {str(index): "not recorded" for index in range(1, 8)}

    records: dict[str, dict[str, Any]] = {"1": _figure_one_record(repo_root, visual.get("1", "not recorded"))}
    registry_hash: str | None = None
    for number in ("2", "3", "4", "5", "6", "7"):
        stem = OUTPUT_STEMS[number]
        destination_pdf = figure_root / f"{stem}.pdf"
        destination_png = preview_root / f"{stem}.png"
        if number == "2":
            source_pdf = repo_root / COPY_SOURCES[number]
            _correct_figure_2_title(source_pdf, destination_pdf)
            mode = "vector_text_correction"
        elif number in {"3", "4"}:
            source_pdf = repo_root / COPY_SOURCES[number]
            _outline_fonts(source_pdf, destination_pdf)
            mode = "vector_font_outlines"
        elif number in COPY_SOURCES:
            source_pdf = repo_root / COPY_SOURCES[number]
            _atomic_copy(source_pdf, destination_pdf)
            mode = "copied_byte_preserving"
        elif number == "5":
            _recompose_figure_5(repo_root, destination_pdf)
            mode = "recomposed"
        else:
            registry_hash = _recompose_figure_7(repo_root, destination_pdf)
            mode = "recomposed"
        _render_preview(destination_pdf, destination_png)

        if number in {"2", "3", "4"}:
            source_paths = {
                COPY_SOURCES[number],
                "01_task_folder/task_05/script/output/spectral_silence_v2.json",
                "01_task_folder/task_05/script/output/spectral_silence_statistics_v2.json",
                "01_task_folder/task_05/script/output/spectral_silence_statistics_v2.npz",
            }
        elif number == "5":
            source_paths = {
                "01_task_folder/task_05/script/output/matrix_element_geometric_eth_v3.json",
                "01_task_folder/task_05/script/output/matrix_element_geometric_eth_v3.npz",
                "01_task_folder/task_05/script/output/continuum_lll_replication_inference_v6.json",
            }
        elif number == "6":
            source_paths = {
                COPY_SOURCES[number],
                "01_task_folder/task_05/script/output/topological_holonomy_v3.json",
                "01_task_folder/task_05/script/output/topological_holonomy_v3.npz",
            }
        else:
            if registry_hash is None:
                raise AssertionError("Figure 7 registry hash was not produced")
            source_paths = {
                "01_task_folder/task_05/script/output/cross_mechanism_geometric_eth_v12.json",
                "01_task_folder/task_05/script/output/paper1_prb_v13/centered_complete_covariance_v13.json",
                "01_task_folder/task_05/script/output/xcube_v11/xcube_geometric_control_v11.json",
            }
        source_hashes = {relative: verified_hashes[relative] for relative in sorted(source_paths)}
        if number == "7":
            source_hashes[
                "01_task_folder/task_05/script/output/paper1_prb_v13/evidence_registry_v13.json"
            ] = registry_hash
        if {_record_path(repo_root, destination_pdf), _record_path(repo_root, destination_png)}.intersection(source_hashes):
            raise RuntimeError(f"Figure {number} source/output path collision")

        records[number] = {
            "mode": mode,
            "source_hashes": source_hashes,
            "outputs": {
                "pdf": {"path": _record_path(repo_root, destination_pdf), "sha256": _sha256(destination_pdf)},
                "png": {"path": _record_path(repo_root, destination_png), "sha256": _sha256(destination_png)},
            },
            "dimensions_inches": _pdf_dimensions_inches(destination_pdf),
            "dpi": 300,
            "vector_pdf": True,
            "caption_data": CAPTION_DATA[number],
            "visual_audit": visual.get(number, "not recorded"),
        }
        if number == "2":
            records[number]["source_transform"] = {
                "kind": "single_vector_text_correction",
                "from": "Ramp universal, long range nonuniversal",
                "to": "Finite-D ramp agreement, long-range excess",
                "source_pdf_unchanged": True,
                "font_policy": "source fonts outlined; corrected title uses embedded TrueType",
            }
        elif number in {"3", "4"}:
            records[number]["source_transform"] = {
                "kind": "vector_font_outlines",
                "source_pdf_unchanged": True,
                "reason": "remove Type 3 fonts without rasterizing plotted artwork",
            }
        if mode == "copied_byte_preserving" and records[number]["outputs"]["pdf"]["sha256"] != verified_hashes[COPY_SOURCES[number]]:
            raise RuntimeError(f"Figure {number} copy is not byte preserving")

    checks = {
        "exactly_seven_records": list(records) == [str(index) for index in range(1, 8)],
        "all_source_hashes_nonempty": all(record["source_hashes"] for record in records.values()),
        "all_vector_pdf": all(record["vector_pdf"] for record in records.values()),
        "all_previews_300_dpi": all(record["dpi"] == 300 for record in records.values()),
        "no_source_output_collisions": all(
            set(record["source_hashes"]).isdisjoint(
                {record["outputs"]["pdf"]["path"], record["outputs"]["png"]["path"]}
            )
            for record in records.values()
        ),
    }
    payload = {
        "version": VERSION,
        "figures": records,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }
    if not payload["all_checks_pass"]:
        raise RuntimeError("Figure v13 package checks failed")
    _atomic_json(manifest_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--figure-root", type=Path, default=DEFAULT_FIGURE_ROOT)
    parser.add_argument("--preview-root", type=Path, default=DEFAULT_PREVIEW_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--record-reviewed",
        action="store_true",
        help="write the canonical original-resolution visual-audit notes after inspection",
    )
    parser.add_argument(
        "--correct-figure-2-source",
        type=Path,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--correct-figure-2-destination",
        type=Path,
        help=argparse.SUPPRESS,
    )
    arguments = parser.parse_args()
    correction_arguments = (
        arguments.correct_figure_2_source,
        arguments.correct_figure_2_destination,
    )
    if any(correction_arguments):
        if not all(correction_arguments):
            parser.error("both internal Figure 2 correction paths are required")
        _correct_figure_2_title(*correction_arguments)
        return
    payload = assemble_figures(
        arguments.repo_root,
        figure_root=arguments.figure_root,
        preview_root=arguments.preview_root,
        manifest_path=arguments.manifest,
        visual_audit_notes=REVIEWED_VISUAL_AUDIT if arguments.record_reviewed else None,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
