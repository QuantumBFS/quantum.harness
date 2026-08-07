#!/usr/bin/env python3
"""Verify the result-bearing v7 manuscript after compilation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from make_susy_hodge_manuscript_assets_v7 import (
    FIGURE_TARGET,
    MANIFEST_JSON as ASSET_MANIFEST_JSON,
    MANUSCRIPT_ROOT,
    RESULTS_TEX,
)
from run_susy_hodge_geometric_eth_v7 import _atomic_json, sha256


SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_JSON = SCRIPT_ROOT / "output" / "susy_hodge_manuscript_audit_v7.json"
ARCHIVE_PDF = SCRIPT_ROOT / "output" / "response_complex_memory_v7.pdf"
SUPPLEMENT_TEX = MANUSCRIPT_ROOT / "supplement.tex"
SUPPLEMENT_PDF = MANUSCRIPT_ROOT / "supplement.pdf"
SUPPLEMENT_LOG = MANUSCRIPT_ROOT / "supplement.log"
SUPPLEMENT_ARCHIVE_PDF = (
    SCRIPT_ROOT / "output" / "response_complex_memory_supplement_v7.pdf"
)
MAIN_TEX = MANUSCRIPT_ROOT / "main.tex"
MAIN_PDF = MANUSCRIPT_ROOT / "main.pdf"
MAIN_LOG = MANUSCRIPT_ROOT / "main.log"


def _load(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _valid_pdf(path: Path) -> bool:
    try:
        data = Path(path).read_bytes()
    except (FileNotFoundError, OSError):
        return False
    return (
        len(data) > 1024
        and data.startswith(b"%PDF-")
        and b"%%EOF" in data[-1024:]
    )


def _matches_hash(path: Path, expected: object) -> bool:
    try:
        return isinstance(expected, str) and sha256(path) == expected
    except (FileNotFoundError, OSError):
        return False


def _same_hash(first: Path, second: Path) -> bool:
    try:
        return sha256(first) == sha256(second)
    except (FileNotFoundError, OSError):
        return False


def verify_manuscript(
    *,
    asset_manifest_json: Path = ASSET_MANIFEST_JSON,
    main_tex: Path = MAIN_TEX,
    results_tex: Path = RESULTS_TEX,
    figure_pdf: Path = FIGURE_TARGET,
    main_pdf: Path = MAIN_PDF,
    archive_pdf: Path = ARCHIVE_PDF,
    main_log: Path = MAIN_LOG,
    supplement_tex: Path = SUPPLEMENT_TEX,
    supplement_pdf: Path = SUPPLEMENT_PDF,
    supplement_archive_pdf: Path = SUPPLEMENT_ARCHIVE_PDF,
    supplement_log: Path = SUPPLEMENT_LOG,
    output_json: Path = OUTPUT_JSON,
) -> dict[str, Any]:
    """Audit source activation, copied assets, compilation, and claim branch."""

    manifest = _load(asset_manifest_json)
    try:
        main_source = Path(main_tex).read_text(encoding="utf-8")
        supplement_source = Path(supplement_tex).read_text(encoding="utf-8")
        result_source = Path(results_tex).read_text(encoding="utf-8")
        log_text = Path(main_log).read_text(encoding="utf-8").lower()
        supplement_log_text = Path(supplement_log).read_text(
            encoding="utf-8"
        ).lower()
    except (FileNotFoundError, OSError):
        main_source = ""
        supplement_source = ""
        result_source = ""
        log_text = ""
        supplement_log_text = ""
    outputs = manifest.get("outputs", {}) if manifest else {}
    branch = str(manifest.get("selected_branch", "")) if manifest else ""
    checks = {
        "asset_manifest_passed": bool(
            manifest
            and manifest.get("version") == "v7"
            and manifest.get("passed")
            and all(manifest.get("checks", {}).values())
        ),
        "result_source_hash": bool(manifest)
        and _matches_hash(
            Path(results_tex), outputs.get(Path(results_tex).name)
        ),
        "figure_source_hash": bool(manifest)
        and _matches_hash(
            Path(figure_pdf), outputs.get(Path(figure_pdf).name)
        ),
        "main_uses_generated_results": r"\input{generated/results_v7.tex}"
        in main_source,
        "supplement_uses_generated_results": r"\input{generated/results_v7.tex}"
        in supplement_source,
        "heldout_result_enabled": r"\heldoutcompletetrue" in result_source
        and r"\heldoutcompletefalse" not in result_source,
        "selected_branch_in_source": bool(branch)
        and branch.replace("_", r"\_") in result_source,
        "compiled_pdf_structure": _valid_pdf(main_pdf),
        "archived_pdf_exact": _valid_pdf(archive_pdf)
        and _same_hash(Path(archive_pdf), Path(main_pdf)),
        "compiled_supplement_structure": _valid_pdf(supplement_pdf),
        "archived_supplement_exact": _valid_pdf(supplement_archive_pdf)
        and _same_hash(Path(supplement_archive_pdf), Path(supplement_pdf)),
        "clean_latex_log": bool(log_text)
        and not any(
            token in log_text
            for token in (
                "undefined citation",
                "undefined references",
                "overfull \\hbox",
                "overfull \\vbox",
                "underfull \\hbox",
                "emergency stop",
                "fatal error",
            )
        ),
        "clean_supplement_log": bool(supplement_log_text)
        and not any(
            token in supplement_log_text
            for token in (
                "undefined citation",
                "undefined references",
                "overfull \\hbox",
                "overfull \\vbox",
                "underfull \\hbox",
                "emergency stop",
                "fatal error",
            )
        ),
    }
    payload = {
        "version": "v7",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "selected_branch": branch or None,
        "prediction_sha256": (
            manifest.get("prediction_sha256") if manifest else None
        ),
        "artifact_hashes": {
            path.name: sha256(path)
            for path in (
                Path(asset_manifest_json),
                Path(main_tex),
                Path(results_tex),
                Path(figure_pdf),
                Path(main_pdf),
                Path(archive_pdf),
                Path(main_log),
                Path(supplement_tex),
                Path(supplement_pdf),
                Path(supplement_archive_pdf),
                Path(supplement_log),
            )
            if path.is_file()
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    _atomic_json(output_json, payload)
    return payload


def main() -> None:
    payload = verify_manuscript()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
