#!/usr/bin/env python3
"""Fail-closed verification of the cross-mechanism v12 delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "v12"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_delivery(
    root: Path = OUTPUT_ROOT,
    *,
    write: bool = True,
) -> dict[str, Any]:
    root = Path(root)
    inference_path = root / f"cross_mechanism_geometric_eth_{VERSION}.json"
    assets_path = root / f"cross_mechanism_assets_{VERSION}.json"
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    assets = json.loads(assets_path.read_text(encoding="utf-8"))
    pdf = root / assets["figure_pdf"]
    png = root / assets["figure_png"]
    checks = {
        "inference_passed": inference.get("all_checks_pass") is True,
        "registered_branch": inference.get("selected_branch")
        in inference.get("registered_branches", ()),
        "claim_is_provisional": inference.get("claim_status")
        == "provisional_opened_cross_mechanism_result",
        "missing_gates_disclosed": bool(inference.get("production_missing"))
        and bool(inference.get("complete_covariance_missing")),
        "asset_checks_passed": all(assets.get("checks", {}).values()),
        "asset_hashes_match": pdf.is_file()
        and png.is_file()
        and _sha256(pdf) == assets.get("figure_pdf_sha256")
        and _sha256(png) == assets.get("figure_png_sha256"),
        "figure_formats": pdf.is_file()
        and png.is_file()
        and pdf.read_bytes().startswith(b"%PDF")
        and png.read_bytes().startswith(b"\x89PNG"),
    }
    result = {
        "version": VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "selected_branch": inference.get("selected_branch"),
        "checks": checks,
        "passed": all(checks.values()),
    }
    if write:
        path = root / f"cross_mechanism_delivery_audit_{VERSION}.json"
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            existing = None
        if isinstance(existing, dict):
            existing_stable = {
                key: value
                for key, value in existing.items()
                if key != "generated_utc"
            }
            result_stable = {
                key: value
                for key, value in result.items()
                if key != "generated_utc"
            }
            if existing_stable == result_stable and isinstance(
                existing.get("generated_utc"), str
            ):
                result["generated_utc"] = existing["generated_utc"]
        path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=OUTPUT_ROOT)
    arguments = parser.parse_args()
    result = verify_delivery(arguments.root)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
