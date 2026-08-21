#!/usr/bin/env python3
"""Fail-closed build and delivery audit for the Paper-I PRB manuscript.

The verifier treats the v1--v12 Git tree and every registered hash as input
evidence.  It rebuilds the v13 registry in memory, regenerates the empirical
TeX assets in memory, checks all seven figure records, compiles both PDFs in
fresh output directories, and records machine-verifiable PDF properties.  A
failed gate is reported in the audit and makes the command exit nonzero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


VERSION = "v13"
# Parent of the first additive v13 commit.  This is the sealed, byte-stable v12
# delivery commit, not the merge-base with a separately advancing main branch.
IMMUTABLE_BASE_REVISION = "0fe3a699c23b0f9edb3ebed03e0626500d8be46a"
SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = SCRIPT_ROOT.parents[2]
TASK_OUTPUT_RELATIVE = Path(
    "01_task_folder/task_05/script/output/paper1_prb_v13"
)
MANUSCRIPT_RELATIVE = Path(
    "overleaf_sync/exactly_degenerate_quantum_chaos_prb"
)
REGISTRY_RELATIVE = TASK_OUTPUT_RELATIVE / "evidence_registry_v13.json"
FIGURE_MANIFEST_RELATIVE = TASK_OUTPUT_RELATIVE / "figure_manifest_v13.json"
AUDIT_RELATIVE = TASK_OUTPUT_RELATIVE / "delivery_audit_v13.json"
CITATION_AUDIT_RELATIVE = Path(
    "docs/literature/2026-08-17-paper1-prb-citation-audit.md"
)
DELIVERY_PDFS = {
    "main": TASK_OUTPUT_RELATIVE / "exactly_degenerate_quantum_chaos_v13.pdf",
    "supplement": (
        TASK_OUTPUT_RELATIVE
        / "exactly_degenerate_quantum_chaos_supplement_v13.pdf"
    ),
}
DELIVERY_LOGS = {
    "main": TASK_OUTPUT_RELATIVE / "main_v13.log",
    "supplement": TASK_OUTPUT_RELATIVE / "supplement_v13.log",
}
GENERATED_ASSETS = {
    "results_v13.tex": "render_results",
    "evidence_matrix_v13.tex": "render_evidence_matrix",
    "model_table_v13.tex": "render_model_table",
}
VERSIONED_ARTIFACT = re.compile(
    r"(?:^|[_/.-])v(?:[1-9]|1[0-2])(?:$|[_/.-])"
)
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
# The human selected a detailed PRB long-form article after the original
# 14--18-page planning estimate.  Keep this delivery contract explicit so a
# later shortening or accidental pagination expansion cannot pass silently.
MAIN_PAGE_MIN = 20
MAIN_PAGE_MAX = 26


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of *path*."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    arguments: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(arguments),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        text=True,
        capture_output=True,
    )
    if check and completed.returncode:
        output = (completed.stdout + "\n" + completed.stderr).strip()
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(arguments)}\n"
            f"{output[-6000:]}"
        )
    return completed


def _safe_repo_path(repo_root: Path, recorded: str) -> Path:
    candidate = Path(recorded)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (repo_root / candidate).resolve()
    root = repo_root.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"recorded path escapes repository: {recorded}") from exc
    return resolved


def _mode_is_0644(path: Path) -> bool:
    return stat.S_IMODE(path.stat().st_mode) == 0o644


def _json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing JSON artifact: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON artifact is not an object: {path}")
    return payload


def verify_hash_contract(
    repo_root: Path,
    expected_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Verify a relative-path/SHA-256 map without trusting absent entries."""

    missing: list[str] = []
    malformed: list[str] = []
    mismatched: list[str] = []
    checked: dict[str, str] = {}
    for recorded in sorted(expected_hashes):
        expected = expected_hashes[recorded]
        if not isinstance(expected, str) or not HASH_RE.fullmatch(expected):
            malformed.append(recorded)
            continue
        try:
            path = _safe_repo_path(repo_root, recorded)
        except RuntimeError:
            malformed.append(recorded)
            continue
        if not path.is_file():
            missing.append(recorded)
            continue
        observed = sha256_file(path)
        checked[recorded] = observed
        if observed != expected:
            mismatched.append(recorded)
    return {
        "passed": not (missing or malformed or mismatched),
        "checked_count": len(checked),
        "missing": missing,
        "malformed": malformed,
        "mismatched": mismatched,
        "observed_hashes": checked,
    }


def verify_immutable_v1_v12(repo_root: Path) -> dict[str, Any]:
    """Compare every tracked v1--v12 artifact with the sealed base commit."""

    exists = _run(
        ["git", "cat-file", "-e", f"{IMMUTABLE_BASE_REVISION}^{{commit}}"],
        cwd=repo_root,
    )
    if exists.returncode:
        return {
            "passed": False,
            "baseline": IMMUTABLE_BASE_REVISION,
            "error": "immutable baseline commit is unavailable",
        }
    tree = _run(
        ["git", "ls-tree", "-r", "--name-only", IMMUTABLE_BASE_REVISION],
        cwd=repo_root,
        check=True,
    ).stdout.splitlines()
    sealed = sorted(path for path in tree if VERSIONED_ARTIFACT.search(path))
    differences = _run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            IMMUTABLE_BASE_REVISION,
            "--",
        ],
        cwd=repo_root,
        check=True,
    ).stdout.splitlines()
    changed = sorted(path for path in differences if VERSIONED_ARTIFACT.search(path))
    missing = [path for path in sealed if not (repo_root / path).is_file()]
    return {
        "passed": bool(sealed) and not changed and not missing,
        "baseline": IMMUTABLE_BASE_REVISION,
        "sealed_artifact_count": len(sealed),
        "changed": changed,
        "missing": missing,
    }


def verify_registry(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Rebuild the registry and compare it byte-semantically with the archive."""

    try:
        from build_paper1_evidence_registry_v13 import (
            REQUIRED_SOURCE_PATHS,
            build_registry,
        )

        path = repo_root / REGISTRY_RELATIVE
        archived = _json_object(path)
        rebuilt = build_registry(repo_root)
        required_hashes = {
            str(REQUIRED_SOURCE_PATHS[source_id]): digest
            for source_id, digest in rebuilt["source_hashes"].items()
        }
        hashes = verify_hash_contract(repo_root, required_hashes)
        false_claims = {
            "asymptotic_geometric_eth": False,
            "universal_geometric_eth": False,
            "thermalization": False,
            "lyapunov_behavior": False,
            "independent_model_operator_class_established": False,
        }
        boundaries = {
            key: archived.get("claims", {}).get(key) == expected
            for key, expected in false_claims.items()
        }
        details = {
            "passed": (
                archived == rebuilt
                and hashes["passed"]
                and all(boundaries.values())
                and _mode_is_0644(path)
            ),
            "path": str(REGISTRY_RELATIVE),
            "sha256": sha256_file(path),
            "matches_rebuild": archived == rebuilt,
            "required_source_hashes": hashes,
            "claim_boundaries": boundaries,
            "mode_0644": _mode_is_0644(path),
        }
        return details, archived
    except Exception as exc:  # Fail closed while preserving a useful audit.
        return {"passed": False, "error": str(exc)}, None


def _pdf_has_vector_content(path: Path) -> bool:
    """Detect substantial vector paths, including text converted to outlines.

    Requiring extractable text would incorrectly reject the delivery-safe
    outlined glyphs used to remove Type-3 and unembedded fonts.  Converting the
    one-page figure to SVG exposes actual path geometry; a raster-only wrapper
    does not satisfy the path-count gate.  Embedded heat maps may coexist with
    the vector axes, labels, and curves.
    """

    with tempfile.TemporaryDirectory(prefix="paper1_vector_") as temporary:
        svg = Path(temporary) / "figure.svg"
        completed = _run(
            ["pdftocairo", "-svg", str(path), str(svg)], cwd=path.parent
        )
        if completed.returncode != 0 or not svg.is_file():
            return False
        content = svg.read_text(encoding="utf-8", errors="replace")
        return content.count("<path") >= 50


def _pdf_page_dimensions_inches(path: Path) -> tuple[float, float]:
    info = _pdf_info(path)
    match = re.search(
        r"([0-9.]+)\s+x\s+([0-9.]+)\s+pts", info.get("Page size", "")
    )
    if not match:
        raise RuntimeError(f"cannot read PDF page dimensions: {path}")
    return float(match.group(1)) / 72.0, float(match.group(2)) / 72.0


def verify_figure_manifest(
    repo_root: Path,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify seven vector PDFs, registered inputs, and 300-dpi previews."""

    try:
        manifest_path = repo_root / FIGURE_MANIFEST_RELATIVE
        payload = dict(manifest) if manifest is not None else _json_object(manifest_path)
        figures = payload.get("figures")
        if not isinstance(figures, dict):
            raise RuntimeError("figure manifest has no figure object")
        exact_ids = list(figures) == [str(index) for index in range(1, 8)]
        records: dict[str, Any] = {}
        all_sources: dict[str, str] = {}
        conflicting_sources: list[str] = []
        all_outputs_ok = True
        from make_paper1_evidence_figures_v13 import CAPTION_DATA

        for number in [str(index) for index in range(1, 8)]:
            record = figures.get(number, {})
            sources = record.get("source_hashes", {})
            if not isinstance(sources, dict) or not sources:
                sources = {}
                all_outputs_ok = False
            for source_path, source_hash in sources.items():
                if (
                    source_path in all_sources
                    and all_sources[source_path] != source_hash
                ):
                    conflicting_sources.append(source_path)
                all_sources[source_path] = source_hash
            output_details: dict[str, Any] = {}
            dimensions = record.get("dimensions_inches")
            dimensions_ok = (
                isinstance(dimensions, list)
                and len(dimensions) == 2
                and all(isinstance(value, (int, float)) and value > 0 for value in dimensions)
            )
            for kind in ("pdf", "png"):
                output = record.get("outputs", {}).get(kind, {})
                recorded_path = output.get("path")
                expected_hash = output.get("sha256")
                if not isinstance(recorded_path, str):
                    output_details[kind] = {"passed": False, "error": "missing path"}
                    all_outputs_ok = False
                    continue
                path = _safe_repo_path(repo_root, recorded_path)
                exists = path.is_file()
                observed = sha256_file(path) if exists else None
                hash_ok = exists and observed == expected_hash
                header_ok = False
                mode_ok = False
                geometry_ok = True
                vector_ok = True
                if exists:
                    mode_ok = _mode_is_0644(path)
                    if kind == "pdf":
                        header_ok = path.read_bytes()[:4] == b"%PDF"
                        vector_ok = _pdf_has_vector_content(path)
                        if dimensions_ok:
                            actual_width, actual_height = _pdf_page_dimensions_inches(path)
                            geometry_ok = (
                                abs(actual_width - float(dimensions[0])) < 0.02
                                and abs(actual_height - float(dimensions[1])) < 0.02
                            )
                    else:
                        header_ok = path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
                        if dimensions_ok:
                            width, height = _png_dimensions(path)
                            expected_width = round(float(dimensions[0]) * 300)
                            expected_height = round(float(dimensions[1]) * 300)
                            geometry_ok = (width, height) == (
                                expected_width,
                                expected_height,
                            )
                passed = bool(
                    exists
                    and hash_ok
                    and header_ok
                    and mode_ok
                    and geometry_ok
                    and vector_ok
                )
                all_outputs_ok = all_outputs_ok and passed
                output_details[kind] = {
                    "passed": passed,
                    "path": recorded_path,
                    "exists": exists,
                    "hash_matches": hash_ok,
                    "sha256": observed,
                    "header_valid": header_ok,
                    "mode_0644": mode_ok,
                    "geometry_300dpi": geometry_ok,
                    "vector_content_present": vector_ok if kind == "pdf" else None,
                }
            records[number] = {
                "passed": all(item.get("passed") for item in output_details.values()),
                "vector_pdf_declared": record.get("vector_pdf") is True,
                "dpi_declared_300": record.get("dpi") == 300,
                "outputs": output_details,
                "caption_matches_registered_builder": (
                    number == "1"
                    or record.get("caption_data") == CAPTION_DATA[number]
                ),
                "caption_has_no_positive_overclaim": not _positive_claim_hits(
                    json.dumps(record.get("caption_data", {}), ensure_ascii=False)
                ),
            }
            records[number]["passed"] = bool(
                records[number]["passed"]
                and records[number]["vector_pdf_declared"]
                and records[number]["dpi_declared_300"]
                and records[number]["caption_matches_registered_builder"]
                and records[number]["caption_has_no_positive_overclaim"]
            )
            all_outputs_ok = all_outputs_ok and records[number]["passed"]
        source_contract = verify_hash_contract(repo_root, all_sources)
        declared_checks = payload.get("checks", {})
        checks_true = (
            isinstance(declared_checks, dict)
            and bool(declared_checks)
            and all(value is True for value in declared_checks.values())
            and payload.get("all_checks_pass") is True
        )
        manifest_mode = _mode_is_0644(manifest_path) if manifest is None else True
        return {
            "passed": bool(
                exact_ids
                and all_outputs_ok
                and source_contract["passed"]
                and not conflicting_sources
                and checks_true
                and manifest_mode
            ),
            "path": str(FIGURE_MANIFEST_RELATIVE),
            "exactly_seven_ordered_records": exact_ids,
            "registered_checks_true": checks_true,
            "mode_0644": manifest_mode,
            "source_hashes": source_contract,
            "conflicting_source_hash_records": sorted(set(conflicting_sources)),
            "figures": records,
        }
    except Exception as exc:
        return {"passed": False, "error": str(exc)}


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"invalid PNG header: {path}")
    return struct.unpack(">II", header[16:24])


def verify_generated_assets(
    repo_root: Path,
    registry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Require empirical TeX values to be exact renderer output."""

    if registry is None:
        return {"passed": False, "error": "registry unavailable"}
    try:
        import make_paper1_prb_assets_v13 as assets

        generated_root = repo_root / MANUSCRIPT_RELATIVE / "generated"
        files: dict[str, Any] = {}
        all_match = True
        for filename, renderer_name in GENERATED_ASSETS.items():
            renderer = getattr(assets, renderer_name)
            expected = renderer(dict(registry))
            path = generated_root / filename
            exists = path.is_file()
            observed = path.read_text(encoding="utf-8") if exists else None
            matches = exists and observed == expected
            mode_ok = exists and _mode_is_0644(path)
            files[filename] = {
                "passed": bool(matches and mode_ok),
                "matches_registry_renderer": matches,
                "mode_0644": mode_ok,
                "sha256": sha256_file(path) if exists else None,
            }
            all_match = all_match and files[filename]["passed"]
        manuscript_sources = [
            repo_root / MANUSCRIPT_RELATIVE / "main.tex",
            *sorted((repo_root / MANUSCRIPT_RELATIVE / "sections").glob("*.tex")),
        ]
        manual_macro_definitions = []
        for path in manuscript_sources:
            text = path.read_text(encoding="utf-8")
            if re.search(r"\\(?:re)?newcommand\{\\(?:MooreRead|Laughlin|LatticeSusy|SusySyk|XCube|Holonomy)", text):
                manual_macro_definitions.append(str(path.relative_to(repo_root)))
        return {
            "passed": all_match and not manual_macro_definitions,
            "files": files,
            "manual_empirical_macro_definitions": manual_macro_definitions,
        }
    except Exception as exc:
        return {"passed": False, "error": str(exc)}


def _strip_tex_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def _positive_claim_hits(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", _strip_tex_comments(text)).strip()
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    hits: list[str] = []
    protected_terms = (
        r"universal\s+Geometric\s+ETH",
        r"asymptotic\s+Geometric\s+ETH",
    )
    negation = re.compile(
        r"\b(?:not|no|never|without|cannot|do not|does not|did not|fails? to|"
        r"unestablished|open|would require|leaves?)\b",
        re.IGNORECASE,
    )
    for sentence in sentences:
        for pattern in protected_terms:
            for match in re.finditer(pattern, sentence, re.IGNORECASE):
                window = sentence[max(0, match.start() - 100) : match.end() + 50]
                if not negation.search(window):
                    hits.append(sentence.strip())
        positive_patterns = (
            r"\bwe\s+(?:show|find|establish|demonstrate|prove|confirm|observe)\b[^.]{0,180}\bthermalization\b",
            r"\bwe\s+(?:show|find|establish|demonstrate|prove|confirm|observe)\b[^.]{0,180}\bLyapunov\b",
            r"\b(?:show|find|observe|establish|demonstrate|prove|confirm|imply)(?:s|ed)?\b[^.]{0,120}\bthermalization\b",
            r"\b(?:show|find|observe|establish|demonstrate|prove|confirm|imply)(?:s|ed)?\b[^.]{0,120}\bLyapunov\b",
            r"\bwe\s+(?:show|find|observe|establish|demonstrate|prove|confirm)\b[^.]{0,160}\bindependent\s+(?:(?:Hamiltonian|disorder|model|operator)[-/ ]*)?(?:ensemble|class)\b",
            r"\bindependent\s+(?:(?:Hamiltonian|disorder|model|operator)[-/ ]*)?(?:ensemble|class)\s+(?:is|are|was|were|has been|have been)\s+(?:established|demonstrated|verified|complete)\b",
        )
        for pattern in positive_patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                prefix = sentence[max(0, match.start() - 60) : match.end()]
                if not negation.search(prefix):
                    hits.append(sentence.strip())
    return sorted(set(hit for hit in hits if hit))


def verify_claim_boundaries(repo_root: Path) -> dict[str, Any]:
    """Reject positive claims outside the registered finite-rank boundary."""

    manuscript = repo_root / MANUSCRIPT_RELATIVE
    main = manuscript / "main.tex"
    section_paths = sorted((manuscript / "sections").glob("*.tex"))
    paths = [main, *section_paths]
    missing = [str(path.relative_to(repo_root)) for path in paths if not path.is_file()]
    if missing:
        return {"passed": False, "missing_sources": missing}
    source_text = {str(path.relative_to(repo_root)): path.read_text(encoding="utf-8") for path in paths}
    combined = "\n".join(source_text.values())
    abstract_match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
        source_text[str(main.relative_to(repo_root))],
        re.DOTALL,
    )
    abstract_text = abstract_match.group(1).strip() if abstract_match else ""
    boundary_patterns = {
        "asymptotic_not_established": r"not an asymptotic\s+Geometric ETH theorem",
        "universal_not_established": r"not a universal\s+Geometric ETH theorem",
        "independent_class_not_established": r"independent model/operator class has not been established",
        "thermalization_not_demonstrated": r"do not demonstrate thermalization",
        "lyapunov_not_demonstrated": r"do not demonstrate thermalization[^.]{0,100}Lyapunov",
    }
    boundaries = {
        name: re.search(pattern, combined, re.IGNORECASE | re.DOTALL) is not None
        for name, pattern in boundary_patterns.items()
    }
    hits: dict[str, list[str]] = {}
    for name, text in source_text.items():
        found = _positive_claim_hits(text)
        if found:
            hits[name] = found
    abstract_nonempty = len(re.sub(r"\\[A-Za-z]+|[{}~]", " ", abstract_text).split()) >= 80
    return {
        "passed": abstract_nonempty and all(boundaries.values()) and not hits,
        "abstract_at_least_80_words": abstract_nonempty,
        "required_negative_boundaries": boundaries,
        "positive_overclaim_hits": hits,
    }


def _tex_sources(repo_root: Path) -> list[Path]:
    manuscript = repo_root / MANUSCRIPT_RELATIVE
    return sorted(path for path in manuscript.rglob("*.tex") if path.is_file())


def _bib_keys(text: str) -> list[str]:
    return re.findall(r"(?m)^\s*@[A-Za-z]+\s*\{\s*([^,\s]+)\s*,", text)


def verify_citations(repo_root: Path) -> dict[str, Any]:
    """Check source citation keys, BibTeX identities, and the primary-source audit."""

    try:
        manuscript = repo_root / MANUSCRIPT_RELATIVE
        bib_path = manuscript / "references.bib"
        bib_text = bib_path.read_text(encoding="utf-8")
        bib_keys = _bib_keys(bib_text)
        duplicates = sorted({key for key in bib_keys if bib_keys.count(key) > 1})
        cited: set[str] = set()
        for path in _tex_sources(repo_root):
            for group in re.findall(r"\\cite[a-zA-Z*]*\s*\{([^}]+)\}", path.read_text(encoding="utf-8")):
                cited.update(key.strip() for key in group.split(",") if key.strip())
        missing = sorted(cited.difference(bib_keys))
        audit_path = repo_root / CITATION_AUDIT_RELATIVE
        audit_exists = audit_path.is_file()
        audit_text = audit_path.read_text(encoding="utf-8") if audit_exists else ""
        absent_from_audit = sorted(key for key in cited if key not in audit_text)
        malformed_doi = sorted(
            value
            for value in re.findall(r"(?i)\bdoi\s*=\s*[\{\"]([^}\"]+)", bib_text)
            if not re.fullmatch(r"10\.\d{4,9}/\S+", value.strip())
        )
        malformed_arxiv = sorted(
            value
            for value in re.findall(r"(?i)\beprint\s*=\s*[\{\"]([^}\"]+)", bib_text)
            if not re.fullmatch(
                r"(?:\d{4}\.\d{4,5}(?:v\d+)?|[A-Za-z.-]+/\d{7}(?:v\d+)?)",
                value.strip(),
            )
        )
        return {
            "passed": not (
                duplicates
                or missing
                or absent_from_audit
                or malformed_doi
                or malformed_arxiv
                or not audit_exists
            ),
            "cited_key_count": len(cited),
            "bib_key_count": len(bib_keys),
            "duplicate_bib_keys": duplicates,
            "missing_bib_keys": missing,
            "citation_audit": str(CITATION_AUDIT_RELATIVE),
            "citation_audit_exists": audit_exists,
            "cited_keys_absent_from_audit": absent_from_audit,
            "malformed_doi": malformed_doi,
            "malformed_arxiv": malformed_arxiv,
        }
    except Exception as exc:
        return {"passed": False, "error": str(exc)}


def verify_latex_log_text(text: str) -> dict[str, Any]:
    """Return fail-closed citation/reference/layout findings from a LaTeX log."""

    patterns = {
        "undefined_references_or_citations": (
            r"LaTeX Warning: (?:Citation|Reference).*undefined|"
            r"There were undefined references|undefined citations"
        ),
        "overfull_boxes": r"Overfull \\[hv]box",
        "fatal_errors": r"^! |Fatal error occurred|Emergency stop",
    }
    findings = {
        name: re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        for name, pattern in patterns.items()
    }
    normalized = {
        name: len(values) if name != "fatal_errors" else len(values)
        for name, values in findings.items()
    }
    normalized["passed"] = not any(normalized.values())
    return normalized


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def verify_existing_archive(
    repo_root: Path,
    previous_audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Detect corruption of an existing archive before a rebuild replaces it."""

    if not previous_audit:
        return {"passed": True, "status": "no_previous_audit"}
    expected_documents = previous_audit.get("documents", {})
    records: dict[str, Any] = {}
    passed = True
    for name, relative in DELIVERY_PDFS.items():
        expected = expected_documents.get(name, {}).get("sha256")
        path = repo_root / relative
        if expected is None:
            records[name] = {"passed": True, "status": "not_previously_archived"}
            continue
        observed = sha256_file(path) if path.is_file() else None
        match = observed == expected
        records[name] = {
            "passed": match,
            "expected_sha256": expected,
            "observed_sha256": observed,
        }
        passed = passed and match
    return {"passed": passed, "documents": records}


def _reproducible_tex_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "SOURCE_DATE_EPOCH": "1786924800",  # 2026-08-17 00:00:00 UTC
            "FORCE_SOURCE_DATE": "1",
            "TZ": "UTC",
        }
    )
    return environment


def build_documents(repo_root: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    """Compile main and supplement in fresh v13-local directories."""

    manuscript = repo_root / MANUSCRIPT_RELATIVE
    output_root = repo_root / TASK_OUTPUT_RELATIVE
    output_root.mkdir(parents=True, exist_ok=True)
    document_details: dict[str, Any] = {}
    built_paths: dict[str, Path] = {}
    environment = _reproducible_tex_environment()
    with tempfile.TemporaryDirectory(prefix=".paper1_build_", dir=output_root) as temporary:
        temporary_root = Path(temporary)
        for name in ("main", "supplement"):
            outdir = temporary_root / name
            outdir.mkdir()
            command = [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                f"-outdir={outdir}",
                f"{name}.tex",
            ]
            completed = _run(command, cwd=manuscript, env=environment)
            pdf = outdir / f"{name}.pdf"
            log = outdir / f"{name}.log"
            log_text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
            log_audit = verify_latex_log_text(log_text)
            compile_ok = completed.returncode == 0 and pdf.is_file() and log.is_file()
            document_details[name] = {
                "passed": compile_ok and log_audit["passed"],
                "latexmk_returncode": completed.returncode,
                "log_audit": log_audit,
                "stderr_tail": completed.stderr[-3000:] if completed.returncode else "",
            }
            if compile_ok:
                canonical_pdf = repo_root / DELIVERY_PDFS[name]
                canonical_log = repo_root / DELIVERY_LOGS[name]
                _atomic_copy(pdf, canonical_pdf)
                _atomic_copy(log, canonical_log)
                built_paths[name] = canonical_pdf
                document_details[name].update(
                    {
                        "pdf": str(DELIVERY_PDFS[name]),
                        "log": str(DELIVERY_LOGS[name]),
                        "sha256": sha256_file(canonical_pdf),
                        "mode_0644": _mode_is_0644(canonical_pdf),
                    }
                )
    return {
        "passed": len(built_paths) == 2
        and all(record["passed"] for record in document_details.values()),
        "documents": document_details,
    }, built_paths


def _pdf_info(path: Path) -> dict[str, str]:
    completed = _run(["pdfinfo", str(path)], cwd=path.parent, check=True)
    fields: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def _font_audit(path: Path) -> dict[str, Any]:
    completed = _run(["pdffonts", str(path)], cwd=path.parent, check=True)
    lines = [line.split() for line in completed.stdout.splitlines()[2:] if line.strip()]
    unembedded: list[str] = []
    type3: list[str] = []
    for columns in lines:
        if len(columns) < 5:
            continue
        name = columns[0]
        lower = [value.lower() for value in columns]
        if "type" in lower and "3" in lower:
            type3.append(name)
        # In pdffonts output, the first yes/no token is the embedded column.
        yes_no = [value for value in lower if value in {"yes", "no"}]
        if not yes_no or yes_no[0] != "yes":
            unembedded.append(name)
    return {
        "passed": bool(lines) and not unembedded and not type3,
        "font_count": len(lines),
        "unembedded_fonts": sorted(set(unembedded)),
        "type3_fonts": sorted(set(type3)),
    }


def _pgm_nonwhite_pixels(path: Path) -> int:
    data = path.read_bytes()
    if not data.startswith(b"P5"):
        raise RuntimeError(f"unexpected PGM encoding: {path}")
    position = 2
    tokens: list[bytes] = []
    while len(tokens) < 3:
        while position < len(data) and chr(data[position]).isspace():
            position += 1
        if position < len(data) and data[position] == ord("#"):
            position = data.find(b"\n", position) + 1
            continue
        end = position
        while end < len(data) and not chr(data[end]).isspace():
            end += 1
        tokens.append(data[position:end])
        position = end
    while position < len(data) and chr(data[position]).isspace():
        position += 1
    width, height, maximum = map(int, tokens)
    pixels = data[position:]
    if maximum != 255 or len(pixels) < width * height:
        raise RuntimeError(f"malformed PGM raster: {path}")
    return sum(value < 248 for value in pixels[: width * height])


def _blank_page_audit(path: Path, page_count: int) -> dict[str, Any]:
    nonwhite: dict[str, int] = {}
    blank: list[int] = []
    with tempfile.TemporaryDirectory(prefix="paper1_blank_") as temporary:
        root = Path(temporary)
        for page in range(1, page_count + 1):
            prefix = root / f"page_{page:03d}"
            _run(
                [
                    "pdftoppm",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-singlefile",
                    "-gray",
                    "-r",
                    "24",
                    str(path),
                    str(prefix),
                ],
                cwd=path.parent,
                check=True,
            )
            raster = prefix.with_suffix(".pgm")
            count = _pgm_nonwhite_pixels(raster)
            nonwhite[str(page)] = count
            if count < 20:
                blank.append(page)
    return {"passed": not blank, "blank_pages": blank, "nonwhite_pixels_24dpi": nonwhite}


def page_count_contract(page_count: int, *, main: bool) -> tuple[bool, str]:
    """Return the user-selected page-count gate and its audit label."""

    if main:
        return MAIN_PAGE_MIN <= page_count <= MAIN_PAGE_MAX, (
            f"{MAIN_PAGE_MIN}--{MAIN_PAGE_MAX} (detailed PRB long form)"
        )
    return page_count >= 1, ">=1"


def verify_pdf_structure(path: Path, *, main: bool) -> dict[str, Any]:
    try:
        info = _pdf_info(path)
        pages = int(info.get("Pages", "0"))
        page_range_ok, page_requirement = page_count_contract(pages, main=main)
        page_size = info.get("Page size", "")
        letter_size = "612 x 792 pts" in page_size
        fonts = _font_audit(path)
        blanks = _blank_page_audit(path, pages) if pages else {"passed": False, "blank_pages": []}
        mode_ok = _mode_is_0644(path)
        return {
            "passed": bool(
                path.read_bytes()[:4] == b"%PDF"
                and page_range_ok
                and letter_size
                and fonts["passed"]
                and blanks["passed"]
                and mode_ok
            ),
            "pages": pages,
            "page_requirement": page_requirement,
            "page_range_ok": page_range_ok,
            "letter_page_size": letter_size,
            "fonts": fonts,
            "blank_page_audit": blanks,
            "mode_0644": mode_ok,
            "sha256": sha256_file(path),
        }
    except Exception as exc:
        return {"passed": False, "error": str(exc)}


def _replace_directory_atomic(source: Path, destination: Path) -> None:
    backup = destination.with_name(f".{destination.name}.previous")
    if backup.exists():
        shutil.rmtree(backup)
    if destination.exists():
        os.replace(destination, backup)
    try:
        os.replace(source, destination)
    except BaseException:
        if backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def render_pdf_pages(
    repo_root: Path,
    documents: Mapping[str, Path],
) -> dict[str, Any]:
    """Render every page at 180 and 300 dpi and hash each preview."""

    output_root = repo_root / TASK_OUTPUT_RELATIVE
    details: dict[str, Any] = {}
    passed = True
    for dpi in (180, 300):
        dpi_records: dict[str, Any] = {}
        for name, pdf in documents.items():
            destination = output_root / f"render_{dpi}dpi" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(
                tempfile.mkdtemp(prefix=f".{name}_", dir=destination.parent)
            )
            try:
                prefix = temporary / "page"
                _run(
                    ["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(prefix)],
                    cwd=pdf.parent,
                    check=True,
                )
                pages = sorted(temporary.glob("page-*.png"))
                for page in pages:
                    os.chmod(page, 0o644)
                _replace_directory_atomic(temporary, destination)
                page_records = [
                    {
                        "page": index,
                        "path": str(page.relative_to(repo_root)),
                        "sha256": sha256_file(page),
                        "mode_0644": _mode_is_0644(page),
                    }
                    for index, page in enumerate(
                        sorted(destination.glob("page-*.png")), start=1
                    )
                ]
                record_passed = bool(page_records) and all(
                    item["mode_0644"] for item in page_records
                )
                dpi_records[name] = {
                    "passed": record_passed,
                    "page_count": len(page_records),
                    "pages": page_records,
                    "machine_visual_verdict": "rendered_nonblank_check_separate",
                }
                passed = passed and record_passed
            except Exception as exc:
                if temporary.exists():
                    shutil.rmtree(temporary)
                dpi_records[name] = {"passed": False, "error": str(exc)}
                passed = False
        details[str(dpi)] = dpi_records
    return {
        "passed": passed,
        "dpi": details,
        "human_visual_review": (
            "Required before submission; this audit records deterministic renders, "
            "font embedding, page geometry, and nonblank-page checks only."
        ),
    }


def _stable_audit_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "generated_utc"}


def write_audit_atomic(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Atomically write mode-0644 JSON and preserve an unchanged timestamp."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = _json_object(path)
    except RuntimeError:
        existing = None
    result = dict(payload)
    if (
        existing is not None
        and _stable_audit_payload(existing) == _stable_audit_payload(result)
        and isinstance(existing.get("generated_utc"), str)
    ):
        result["generated_utc"] = existing["generated_utc"]
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return result


def verify_delivery(
    repo_root: Path,
    *,
    compile_documents: bool = True,
    render_pages: bool = True,
    write: bool = True,
) -> dict[str, Any]:
    """Run the complete Paper-I delivery audit and return its JSON payload."""

    root = Path(repo_root).resolve()
    audit_path = root / AUDIT_RELATIVE
    previous_audit_error: str | None = None
    try:
        previous_audit = _json_object(audit_path)
    except RuntimeError as exc:
        previous_audit = None
        if audit_path.exists():
            previous_audit_error = str(exc)

    immutable = verify_immutable_v1_v12(root)
    registry_details, registry = verify_registry(root)
    figures = verify_figure_manifest(root)
    generated = verify_generated_assets(root, registry)
    claims = verify_claim_boundaries(root)
    citations = verify_citations(root)
    archive_preflight = verify_existing_archive(root, previous_audit)
    if previous_audit_error is not None:
        archive_preflight = {
            "passed": False,
            "error": previous_audit_error,
            "status": "existing_audit_is_unreadable",
        }

    if compile_documents:
        build, documents = build_documents(root)
    else:
        documents = {
            name: root / relative
            for name, relative in DELIVERY_PDFS.items()
            if (root / relative).is_file()
        }
        build = {
            "passed": False,
            "status": "diagnostic_only_existing_pdfs_not_a_clean_recompile",
            "existing_pdf_count": len(documents),
        }

    structures: dict[str, Any] = {}
    for name in ("main", "supplement"):
        if name in documents:
            structures[name] = verify_pdf_structure(
                documents[name], main=name == "main"
            )
        else:
            structures[name] = {"passed": False, "error": "compiled PDF unavailable"}
    pdf_structure_passed = all(record["passed"] for record in structures.values())

    if render_pages and len(documents) == 2:
        renders = render_pdf_pages(root, documents)
    elif render_pages:
        renders = {"passed": False, "error": "both PDFs required for rendering"}
    else:
        renders = {
            "passed": False,
            "status": "diagnostic_only_rendering_explicitly_skipped",
        }

    documents_payload: dict[str, Any] = {}
    for name, path in documents.items():
        documents_payload[name] = {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
            "mode_0644": _mode_is_0644(path),
            "structure": structures[name],
        }

    checks = {
        "immutable_v1_v12": immutable["passed"],
        "registry_and_required_sources": registry_details["passed"],
        "figure_manifest_and_seven_figures": figures["passed"],
        "generated_empirical_assets": generated["passed"],
        "claim_boundaries": claims["passed"],
        "citation_sources": citations["passed"],
        "existing_archive_not_corrupted": archive_preflight["passed"],
        "main_and_supplement_compile_cleanly": build["passed"],
        "pdf_structure_fonts_pages": pdf_structure_passed,
        "page_renders": renders["passed"],
    }
    payload: dict[str, Any] = {
        "version": VERSION,
        "schema": "paper1_prb_delivery_audit_v13",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "immutable_baseline": immutable,
        "registry": registry_details,
        "figures": figures,
        "generated_assets": generated,
        "claim_audit": claims,
        "citation_audit": citations,
        "archive_preflight": archive_preflight,
        "build": build,
        "documents": documents_payload,
        "renders": renders,
        "checks": checks,
        "passed": all(checks.values()),
    }
    if write:
        payload = write_audit_atomic(audit_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="audit existing delivery PDFs instead of running latexmk",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="skip 180/300-dpi delivery page rendering",
    )
    parser.add_argument("--no-write", action="store_true")
    arguments = parser.parse_args()
    result = verify_delivery(
        arguments.repo_root,
        compile_documents=not arguments.no_compile,
        render_pages=not arguments.no_render,
        write=not arguments.no_write,
    )
    summary = {
        "audit": str(AUDIT_RELATIVE),
        "checks": result["checks"],
        "passed": result["passed"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
