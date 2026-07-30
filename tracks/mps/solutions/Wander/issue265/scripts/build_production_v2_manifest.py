#!/usr/bin/env python3
"""Build the approved production-v2 manifest; this command never submits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.production_v2_manifest import build_production_manifest_v2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-matrix",
        type=Path,
        default=ROOT / "configs" / "burgers_research_matrix.json",
    )
    parser.add_argument(
        "--base-manifest",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    parser.add_argument(
        "--amendment",
        type=Path,
        default=ROOT / "configs" / "two_mode_fcs_amendment_20260730.json",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "research",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results_research_program" / "production_manifest_v2.json",
    )
    args = parser.parse_args()
    payload = build_production_manifest_v2(
        base_matrix_path=args.base_matrix,
        base_manifest_path=args.base_manifest,
        amendment_path=args.amendment,
        data_root=args.data_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(args.output)
    print(json.dumps(payload["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
