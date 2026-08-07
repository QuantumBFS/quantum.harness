#!/usr/bin/env python3
"""Build the frozen simulation manifest for the Burgers research program."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research_dataset import build_simulation_manifest
from src.research_protocol import load_research_matrix


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix",
        type=Path,
        default=ROOT / "configs" / "burgers_research_matrix.json",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "research",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results_research_program" / "manifest.json",
    )
    args = parser.parse_args()

    matrix = load_research_matrix(args.matrix)
    manifest = build_simulation_manifest(
        matrix,
        matrix_path=args.matrix,
        output_root=args.data_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )

    counts: dict[str, int] = {}
    for job in manifest["jobs"]:
        stage = str(job["stage"])
        counts[stage] = counts.get(stage, 0) + 1
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "job_count": manifest["job_count"],
                "counts": counts,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
