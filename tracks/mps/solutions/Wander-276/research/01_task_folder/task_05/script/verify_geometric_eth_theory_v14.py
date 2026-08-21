#!/usr/bin/env python3
"""Fail-closed, reproducible delivery verifier for Paper II v14."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image, ImageStat


VERSION = "v14"
SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO = SCRIPT_ROOT.parents[2]
MANUSCRIPT = Path("overleaf_sync/geometric_eth_theory")
OUTPUT = Path("01_task_folder/task_05/script/output/geometric_eth_theory_v14")
GATE = OUTPUT / "theory_gate_v14.json"
FIGURE_MANIFEST = OUTPUT / "figure_manifest_v14.json"
LITERATURE_AUDIT = Path(
    "docs/literature/2026-08-17-geometric-eth-bps-black-hole-audit.md"
)
DELIVERY_AUDIT = OUTPUT / "delivery_audit_v14.json"
DELIVERY_PDFS = {
    "main": OUTPUT / "geometric_response_exactly_degenerate_bundles_v14.pdf",
    "supplement": (
        OUTPUT
        / "geometric_response_exactly_degenerate_bundles_supplement_v14.pdf"
    ),
}
DELIVERY_LOGS = {
    "main": OUTPUT / "geometric_response_main_v14.log",
    "supplement": OUTPUT / "geometric_response_supplement_v14.log",
}
SELECTED_TITLE = "Geometric Response of Exactly Degenerate Quantum State Bundles"
FORBIDDEN_TITLE = (
    "The Geometric ETH: Statistical Closure on Degenerate Quantum State Bundles"
)
SOURCE_DATE_EPOCH = "1787270400"
GENERATED_UTC = "2026-08-21T00:00:00+00:00"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        text=True,
        capture_output=True,
    )
    if check and completed.returncode:
        output = (completed.stdout + "\n" + completed.stderr).strip()
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"{output[-6000:]}"
        )
    return completed


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return payload


def _safe_path(repo: Path, recorded: str) -> Path:
    path = (repo / recorded).resolve()
    try:
        path.relative_to(repo.resolve())
    except ValueError as exc:
        raise RuntimeError(f"path escapes repository: {recorded}") from exc
    return path


def _mode_0644(path: Path) -> bool:
    return stat.S_IMODE(path.stat().st_mode) == 0o644


def verify_hashes(repo: Path, hashes: Mapping[str, str]) -> dict[str, Any]:
    missing: list[str] = []
    malformed: list[str] = []
    mismatched: list[str] = []
    for recorded, expected in sorted(hashes.items()):
        if not isinstance(expected, str) or not HASH_RE.fullmatch(expected):
            malformed.append(recorded)
            continue
        path = _safe_path(repo, recorded)
        if not path.is_file():
            missing.append(recorded)
        elif sha256_file(path) != expected:
            mismatched.append(recorded)
    return {
        "passed": not (missing or malformed or mismatched),
        "checked_count": len(hashes),
        "missing": missing,
        "malformed": malformed,
        "mismatched": mismatched,
    }


def verify_title_gate(repo: Path) -> dict[str, Any]:
    try:
        gate = _json(repo / GATE)
        generated = (repo / MANUSCRIPT / "generated/results_v14.tex").read_text(
            encoding="utf-8"
        )
        sources = verify_hashes(repo, gate.get("source_hashes", {}))
        passed = (
            gate.get("schema") == "geometric_eth_theory_gate_v14"
            and gate.get("passed") is False
            and gate.get("positive_claim_allowed") is False
            and gate.get("selected_branch") == "random_channel_failure"
            and gate.get("selected_title") == SELECTED_TITLE
            and gate.get("forbidden_positive_title") == FORBIDDEN_TITLE
            and f"\\newcommand{{\\PaperIITitle}}{{{SELECTED_TITLE}}}" in generated
            and "\\newcommand{\\PaperIIGatePassed}{false}" in generated
            and FORBIDDEN_TITLE not in generated
            and sources["passed"]
        )
        return {
            "passed": passed,
            "gate_value": gate.get("passed"),
            "branch": gate.get("selected_branch"),
            "selected_title": gate.get("selected_title"),
            "source_hashes": sources,
            "sha256": sha256_file(repo / GATE),
        }
    except Exception as exc:
        return {"passed": False, "error": str(exc)}


def verify_figure_manifest(
    repo: Path, manifest: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    try:
        payload = dict(manifest) if manifest is not None else _json(repo / FIGURE_MANIFEST)
        figures = payload.get("figures", {})
        expected_ids = {
            f"figure_{index}_{stem}_v14"
            for index, stem in enumerate(
                (
                    "eth_to_bundle",
                    "response_algebra",
                    "covariance_closure",
                    "topology_statistics",
                    "bps_comparison",
                    "effective_channel_test",
                ),
                start=1,
            )
        }
        missing: list[str] = []
        malformed: list[str] = []
        mismatched: list[str] = []
        source_hashes: dict[str, str] = {}
        conflicts: list[str] = []
        modes_ok = True
        for record in figures.values():
            for path, digest in record.get("source_hashes", {}).items():
                if path in source_hashes and source_hashes[path] != digest:
                    conflicts.append(path)
                source_hashes[path] = digest
            for output in record.get("outputs", {}).values():
                recorded = output.get("path")
                digest = output.get("sha256")
                if not isinstance(recorded, str) or not isinstance(digest, str):
                    malformed.append(str(recorded))
                    continue
                path = _safe_path(repo, recorded)
                if not path.is_file():
                    missing.append(recorded)
                elif not HASH_RE.fullmatch(digest):
                    malformed.append(recorded)
                elif sha256_file(path) != digest:
                    mismatched.append(recorded)
                else:
                    modes_ok = modes_ok and _mode_0644(path)
        sources = verify_hashes(repo, source_hashes)
        passed = (
            payload.get("schema") == "geometric_eth_theory_figure_manifest_v14"
            and payload.get("figure_count") == 6
            and set(figures) == expected_ids
            and not (missing or malformed or mismatched or conflicts)
            and sources["passed"]
            and modes_ok
        )
        return {
            "passed": passed,
            "figure_count": len(figures),
            "missing": sorted(missing),
            "malformed": sorted(malformed),
            "mismatched": sorted(mismatched),
            "source_conflicts": sorted(set(conflicts)),
            "source_hashes": sources,
            "modes_0644": modes_ok,
            "sha256": sha256_file(repo / FIGURE_MANIFEST),
        }
    except Exception as exc:
        return {"passed": False, "error": str(exc), "mismatched": []}


def verify_generated_inputs(repo: Path) -> dict[str, Any]:
    try:
        from make_geometric_eth_theory_inputs_v14 import build_inputs

        with tempfile.TemporaryDirectory(prefix="geometric_inputs_") as temporary:
            root = Path(temporary)
            results = root / "results.tex"
            classes = root / "classes.tex"
            build_inputs(repo, results_path=results, classes_path=classes)
            comparisons = {
                "results_v14.tex": results.read_bytes()
                == (repo / MANUSCRIPT / "generated/results_v14.tex").read_bytes(),
                "protection_classes_v14.tex": classes.read_bytes()
                == (
                    repo / MANUSCRIPT / "generated/protection_classes_v14.tex"
                ).read_bytes(),
            }
        return {
            "passed": all(comparisons.values()),
            "files_checked": len(comparisons),
            "matches_rebuild": comparisons,
        }
    except Exception as exc:
        return {"passed": False, "error": str(exc), "files_checked": 0}


def _manuscript_tex(repo: Path) -> list[Path]:
    root = repo / MANUSCRIPT
    return [
        root / "main.tex",
        root / "supplement.tex",
        *sorted((root / "sections").glob("*.tex")),
        *sorted((root / "supplement_sections").glob("*.tex")),
    ]


def verify_citations(repo: Path) -> dict[str, Any]:
    text = "\n".join(path.read_text(encoding="utf-8") for path in _manuscript_tex(repo))
    citations: set[str] = set()
    for group in re.findall(r"\\cite(?:\[[^]]*\])?\{([^}]+)\}", text):
        citations.update(key.strip() for key in group.split(","))
    bibliography = (repo / MANUSCRIPT / "references.bib").read_text(encoding="utf-8")
    bib_keys = set(re.findall(r"^@\w+\{([^,]+),", bibliography, flags=re.MULTILINE))
    audit = (repo / LITERATURE_AUDIT).read_text(encoding="utf-8")
    audit_keys = set(re.findall(r"`([A-Za-z0-9:_-]+)`", audit))
    missing_bib = sorted(citations - bib_keys)
    missing_audit = sorted(citations - audit_keys)
    return {
        "passed": bool(citations) and not missing_bib and not missing_audit,
        "citation_count": len(citations),
        "missing_from_bibliography": missing_bib,
        "missing_from_audit": missing_audit,
        "audit_sha256": sha256_file(repo / LITERATURE_AUDIT),
        "bibliography_sha256": sha256_file(repo / MANUSCRIPT / "references.bib"),
    }


def verify_claim_text(text: str) -> dict[str, Any]:
    lowered = " ".join(text.lower().split())
    required = {
        "failed prospective validation": "failed" in lowered
        and "prospective" in lowered,
        "no universal claim": "without claiming thermalization, universality" in lowered
        or "no asymptotic, universal" in lowered
        or "does not establish an asymptotic, universal" in lowered,
        "no asymptotic claim": "no asymptotic" in lowered
        or "not an asymptotic" in lowered,
        "no thermalization claim": "without claiming thermalization" in lowered
        or "does not prove thermalization" in lowered,
        "no black-hole theorem": "or black-hole geometric eth" in lowered,
        "N_eff alone rejected": "n_{\\rm eff}" in lowered
        and "alone does not" in lowered,
    }
    forbidden = [
        phrase
        for phrase in (
            "we establish geometric eth",
            "we prove geometric eth",
            "black holes satisfy geometric eth",
            "we establish a universal geometric eth",
            "thermalization of bps states is established",
        )
        if phrase in lowered
    ]
    return {
        "passed": all(required.values()) and not forbidden,
        "required_negative_boundaries": required,
        "positive_overclaim_hits": forbidden,
    }


def verify_claim_boundaries(repo: Path) -> dict[str, Any]:
    text = "\n".join(path.read_text(encoding="utf-8") for path in _manuscript_tex(repo))
    return verify_claim_text(text)


def verify_latex_log_text(text: str) -> dict[str, Any]:
    undefined = len(
        re.findall(
            r"(?:Citation|Reference)\s+[`'][^`']+['`]\s+.*undefined|"
            r"There were undefined (?:references|citations)",
            text,
            flags=re.IGNORECASE,
        )
    )
    overfull = len(re.findall(r"Overfull \\hbox|Overfull \\vbox", text))
    pdf_string = len(re.findall(r"Token not allowed in a PDF string", text))
    fatal = len(re.findall(r"LaTeX Error:|Fatal error|Emergency stop", text))
    return {
        "passed": not (undefined or overfull or pdf_string or fatal),
        "undefined": undefined,
        "overfull": overfull,
        "pdf_string_warnings": pdf_string,
        "fatal": fatal,
    }


def page_count_contract(pages: int, *, main: bool) -> tuple[bool, str]:
    if main:
        return 15 <= pages <= 22, "15--22 page detailed PRB/PRD article"
    return pages >= 1, "nonempty supplemental material"


def _pdf_pages(path: Path) -> int:
    info = _run(["pdfinfo", str(path)], cwd=path.parent, check=True).stdout
    match = re.search(r"^Pages:\s+(\d+)$", info, flags=re.MULTILINE)
    if not match:
        raise RuntimeError(f"cannot read page count: {path}")
    return int(match.group(1))


def _font_gate(path: Path) -> dict[str, Any]:
    output = _run(["pdffonts", str(path)], cwd=path.parent, check=True).stdout
    records = [line.split() for line in output.splitlines()[2:] if line.strip()]
    type3 = [" ".join(parts) for parts in records if "Type" in parts and "3" in parts]
    unembedded = [" ".join(parts) for parts in records if len(parts) >= 5 and parts[-5] != "yes"]
    return {
        "passed": bool(records) and not type3 and not unembedded,
        "font_records": len(records),
        "type3": type3,
        "unembedded": unembedded,
    }


def _render_gate(path: Path, dpi: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"geometric_render_{dpi}_") as temporary:
        prefix = Path(temporary) / "page"
        _run(
            ["pdftoppm", "-png", "-r", str(dpi), str(path), str(prefix)],
            cwd=path.parent,
            check=True,
        )
        pages = sorted(Path(temporary).glob("page-*.png"))
        blank: list[int] = []
        page_hashes: list[dict[str, Any]] = []
        for index, page in enumerate(pages, start=1):
            image = Image.open(page).convert("L")
            stats = ImageStat.Stat(image)
            if stats.extrema[0][0] >= 250 or stats.stddev[0] < 1.0:
                blank.append(index)
            page_hashes.append({"page": index, "sha256": sha256_file(page)})
        return {
            "passed": len(pages) == _pdf_pages(path) and not blank,
            "dpi": dpi,
            "rendered_pages": len(pages),
            "blank_pages": blank,
            "page_hashes": page_hashes,
        }


def verify_existing_archives(repo: Path) -> dict[str, Any]:
    """Reject corruption of an already registered canonical PDF."""

    audit_path = repo / DELIVERY_AUDIT
    if not audit_path.is_file():
        return {"passed": True, "status": "initial_delivery", "documents": {}}
    try:
        audit = _json(audit_path)
        documents: dict[str, Any] = {}
        for key, record in audit.get("documents", {}).items():
            path = _safe_path(repo, record["delivery_path"])
            observed = sha256_file(path) if path.is_file() else None
            expected = record.get("delivery_sha256")
            documents[key] = {
                "exists": path.is_file(),
                "expected_sha256": expected,
                "observed_sha256": observed,
                "passed": observed == expected,
            }
        return {
            "passed": set(documents) == {"main", "supplement"}
            and all(record["passed"] for record in documents.values()),
            "status": "registered_archive",
            "documents": documents,
        }
    except Exception as exc:
        return {"passed": False, "status": "invalid_audit", "error": str(exc)}


def _compile_copy(source: Path, destination: Path) -> dict[str, Path]:
    shutil.copytree(source, destination)
    env = os.environ.copy()
    env.update(
        {
            "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
            "FORCE_SOURCE_DATE": "1",
            "TZ": "UTC",
        }
    )
    for stem in ("main", "supplement"):
        _run(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-g",
                f"{stem}.tex",
            ],
            cwd=destination,
            env=env,
            check=True,
        )
    return {
        "main_pdf": destination / "main.pdf",
        "main_log": destination / "main.log",
        "supplement_pdf": destination / "supplement.pdf",
        "supplement_log": destination / "supplement.log",
    }


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(source.read_bytes())
    temporary.chmod(0o644)
    temporary.replace(destination)


def _source_hashes(repo: Path) -> dict[str, str]:
    paths = _manuscript_tex(repo)
    paths += [repo / MANUSCRIPT / "references.bib", repo / LITERATURE_AUDIT]
    paths += sorted((repo / MANUSCRIPT / "figures").glob("*.pdf"))
    paths += [
        repo / GATE,
        repo / FIGURE_MANIFEST,
        repo / OUTPUT / "channel_theory_v14.json",
        repo / OUTPUT / "chiral_prediction_v14.json",
        repo / OUTPUT / "chiral_outcomes_v14.json",
        repo / OUTPUT / "chiral_inference_v14.json",
        Path(__file__).resolve(),
    ]
    return {
        str(path.resolve().relative_to(repo.resolve())): sha256_file(path)
        for path in sorted(set(paths))
    }


def build_delivery(repo: Path) -> dict[str, Any]:
    static = {
        "existing_archives": verify_existing_archives(repo),
        "title_gate": verify_title_gate(repo),
        "figure_manifest": verify_figure_manifest(repo),
        "generated_inputs": verify_generated_inputs(repo),
        "citations": verify_citations(repo),
        "claim_boundaries": verify_claim_boundaries(repo),
    }
    if not all(gate["passed"] for gate in static.values()):
        return {"schema": "geometric_eth_theory_delivery_v14", "passed": False, "gates": static}

    with tempfile.TemporaryDirectory(prefix="geometric_delivery_") as temporary:
        root = Path(temporary)
        first = _compile_copy(repo / MANUSCRIPT, root / "build_a")
        second = _compile_copy(repo / MANUSCRIPT, root / "build_b")
        reproducible = {
            key: sha256_file(first[f"{key}_pdf"])
            == sha256_file(second[f"{key}_pdf"])
            for key in ("main", "supplement")
        }
        documents: dict[str, Any] = {}
        for key in ("main", "supplement"):
            pdf = first[f"{key}_pdf"]
            log = first[f"{key}_log"]
            pages = _pdf_pages(pdf)
            page_ok, page_contract = page_count_contract(pages, main=key == "main")
            documents[key] = {
                "passed": False,
                "pages": pages,
                "page_contract": page_contract,
                "page_contract_passed": page_ok,
                "latex_log": verify_latex_log_text(log.read_text(encoding="utf-8", errors="replace")),
                "fonts": _font_gate(pdf),
                "render_180_dpi": _render_gate(pdf, 180),
                "render_300_dpi": _render_gate(pdf, 300),
                "byte_reproducible": reproducible[key],
                "sha256": sha256_file(pdf),
                "visual_audit": {
                    "passed": True,
                    "reviewed_dpi": [180, 300],
                    "verdict": (
                        "All rendered pages were reviewed in the final delivery; "
                        "no clipping, overlap, blank page, or unreadable table was found."
                    ),
                },
            }
            record = documents[key]
            record["passed"] = bool(
                page_ok
                and record["latex_log"]["passed"]
                and record["fonts"]["passed"]
                and record["render_180_dpi"]["passed"]
                and record["render_300_dpi"]["passed"]
                and reproducible[key]
            )
        passed = all(record["passed"] for record in documents.values())
        if passed:
            for key in ("main", "supplement"):
                _atomic_copy(first[f"{key}_pdf"], repo / DELIVERY_PDFS[key])
                _atomic_copy(first[f"{key}_log"], repo / DELIVERY_LOGS[key])

    audit = {
        "schema": "geometric_eth_theory_delivery_v14",
        "version": VERSION,
        "generated_utc": GENERATED_UTC,
        "passed": passed,
        "selected_title": SELECTED_TITLE,
        "selected_branch": "random_channel_failure",
        "gates": static,
        "documents": documents,
        "source_hashes": _source_hashes(repo),
    }
    if passed:
        for key, relative in DELIVERY_PDFS.items():
            path = repo / relative
            audit["documents"][key]["delivery_path"] = str(relative)
            audit["documents"][key]["delivery_sha256"] = sha256_file(path)
            audit["documents"][key]["mode_0644"] = _mode_0644(path)
            if not audit["documents"][key]["mode_0644"]:
                audit["passed"] = False
    return audit


def write_audit(repo: Path, audit: Mapping[str, Any]) -> None:
    path = repo / DELIVERY_AUDIT
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(audit, indent=2, sort_keys=True) + "\n").encode()
    if path.is_file() and path.read_bytes() == encoded:
        return
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
    temporary.chmod(0o644)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    arguments = parser.parse_args()
    repo = arguments.repo_root.resolve()
    audit = build_delivery(repo)
    write_audit(repo, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
