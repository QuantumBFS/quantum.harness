#!/usr/bin/env python3
"""Audit the compiled v12 cross-mechanism manuscript and supplement."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from make_cross_mechanism_manuscript_assets_v12 import (
    FIGURE_TARGET,
    MANIFEST_JSON as ASSET_MANIFEST_JSON,
    MANUSCRIPT_ROOT,
    RESULTS_TEX,
    TABLE_TEX,
    sha256,
)


SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"
MAIN_TEX = MANUSCRIPT_ROOT / "main.tex"
MAIN_PDF = MANUSCRIPT_ROOT / "main.pdf"
MAIN_LOG = MANUSCRIPT_ROOT / "main.log"
SUPPLEMENT_TEX = MANUSCRIPT_ROOT / "supplement.tex"
SUPPLEMENT_PDF = MANUSCRIPT_ROOT / "supplement.pdf"
SUPPLEMENT_LOG = MANUSCRIPT_ROOT / "supplement.log"
ARCHIVE_PDF = OUTPUT_ROOT / "mechanism_dependent_geometric_eth_v12.pdf"
ARCHIVE_SUPPLEMENT_PDF = (
    OUTPUT_ROOT / "mechanism_dependent_geometric_eth_supplement_v12.pdf"
)
OUTPUT_JSON = OUTPUT_ROOT / "cross_mechanism_manuscript_audit_v12.json"


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
    return len(data) > 10_000 and data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]


def _same_file(first: Path, second: Path) -> bool:
    try:
        return sha256(first) == sha256(second)
    except (FileNotFoundError, OSError):
        return False


def _clean_log(path: Path) -> bool:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace").lower()
    except (FileNotFoundError, OSError):
        return False
    forbidden = (
        "undefined citation",
        "undefined references",
        "citation `",
        "reference `",
        "overfull \\hbox",
        "overfull \\vbox",
        "emergency stop",
        "fatal error",
    )
    return bool(text) and not any(token in text for token in forbidden)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def verify_manuscript(
    *,
    asset_manifest_json: Path = ASSET_MANIFEST_JSON,
    main_tex: Path = MAIN_TEX,
    supplement_tex: Path = SUPPLEMENT_TEX,
    results_tex: Path = RESULTS_TEX,
    table_tex: Path = TABLE_TEX,
    figure_pdf: Path = FIGURE_TARGET,
    main_pdf: Path = MAIN_PDF,
    supplement_pdf: Path = SUPPLEMENT_PDF,
    archive_pdf: Path = ARCHIVE_PDF,
    archive_supplement_pdf: Path = ARCHIVE_SUPPLEMENT_PDF,
    main_log: Path = MAIN_LOG,
    supplement_log: Path = SUPPLEMENT_LOG,
    output_json: Path = OUTPUT_JSON,
) -> dict[str, Any]:
    """Return a fail-closed manuscript audit."""

    manifest = _load(asset_manifest_json)
    try:
        main_source = Path(main_tex).read_text(encoding="utf-8")
        supplement_source = Path(supplement_tex).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        main_source = ""
        supplement_source = ""
    outputs = manifest.get("outputs", {}) if manifest else {}
    checks = {
        "asset_manifest_passed": bool(
            manifest
            and manifest.get("version") == "v12"
            and manifest.get("passed") is True
            and manifest.get("selected_branch") == "domain_limited_geometric_eth"
            and all(manifest.get("checks", {}).values())
        ),
        "generated_results_hash": bool(manifest)
        and outputs.get(Path(results_tex).name) == sha256(results_tex),
        "generated_table_hash": bool(manifest)
        and outputs.get(Path(table_tex).name) == sha256(table_tex),
        "figure_hash": bool(manifest)
        and outputs.get(Path(figure_pdf).name) == sha256(figure_pdf),
        "main_uses_generated_results": r"\input{generated/results_v12.tex}" in main_source,
        "supplement_uses_generated_table": r"\input{generated/mechanism_table_v12.tex}"
        in supplement_source,
        "supplement_uses_generated_results": r"\input{generated/results_v12.tex}" in supplement_source,
        "claim_boundary_present": "neither an asymptotic law nor cross-mechanism universality" in main_source
        and "do not establish asymptotic Geometric ETH" in supplement_source,
        "compiled_main_pdf": _valid_pdf(main_pdf),
        "compiled_supplement_pdf": _valid_pdf(supplement_pdf),
        "archived_main_exact": _valid_pdf(archive_pdf) and _same_file(main_pdf, archive_pdf),
        "archived_supplement_exact": _valid_pdf(archive_supplement_pdf)
        and _same_file(supplement_pdf, archive_supplement_pdf),
        "clean_main_log": _clean_log(main_log),
        "clean_supplement_log": _clean_log(supplement_log),
    }
    artifacts = (
        asset_manifest_json,
        main_tex,
        supplement_tex,
        results_tex,
        table_tex,
        figure_pdf,
        main_pdf,
        supplement_pdf,
        archive_pdf,
        archive_supplement_pdf,
        main_log,
        supplement_log,
    )
    payload = {
        "version": "v12",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "selected_branch": manifest.get("selected_branch") if manifest else None,
        "artifact_hashes": {
            Path(path).name: sha256(path) for path in artifacts if Path(path).is_file()
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    existing = _load(output_json)
    if existing is not None:
        existing_stable = {
            key: value for key, value in existing.items() if key != "generated_utc"
        }
        payload_stable = {
            key: value for key, value in payload.items() if key != "generated_utc"
        }
        if existing_stable == payload_stable and isinstance(
            existing.get("generated_utc"), str
        ):
            payload["generated_utc"] = existing["generated_utc"]
    _atomic_json(output_json, payload)
    return payload


def main() -> None:
    payload = verify_manuscript()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
