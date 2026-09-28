#!/usr/bin/env python3
"""Run only the preregistered convergence gate from the data manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_research_datasets import validate_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=ROOT / "configs" / "burgers_decision_rules.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results_research_program" / "convergence" / "summary.json",
    )
    parser.add_argument("--require-accepted", action="store_true")
    args = parser.parse_args()

    validation = validate_manifest(
        args.manifest,
        include_blinded=False,
        rules_path=args.rules,
    )
    convergence = {
        "schema_version": 1,
        "manifest_path": validation["manifest_path"],
        **validation["convergence"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(convergence, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        json.dumps(
            {
                "accepted": convergence["accepted"],
                "condition_count": len(convergence["records"]),
                "statuses": [
                    record["status"] for record in convergence["records"]
                ],
            },
            ensure_ascii=False,
        )
    )
    if args.require_accepted and not convergence["accepted"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
