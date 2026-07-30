#!/usr/bin/env python3
"""Select a small, explicitly diagnostic Target-2 subset for overnight Clarabel runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from build_campaign import atomic_json, primary_cells


def presentation_cells() -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for source in primary_cells():
        if not (
            source["kind"] == "observable"
            and source["nmax"] == 1
            and source["L"] == 1
            and source["d"] == 2
            and source["encoding"] == "matrix"
            and source["basis_family"] == "complete"
            and source["symmetry"] == "U1_INVARIANT_KMS_STATES"
            and (
                source["point"] == "P2"
                or (source["point"] == "P4" and source["geometry"] == "83")
            )
        ):
            continue
        cell = dict(source)
        cell["source_cell_id"] = source["id"]
        cell["campaign"] = "presentation-clarabel"
        cell["id"] = "presentation-" + source["id"]
        cell["requested_walltime"] = "04:00:00"
        cell["diagnostic_only"] = True
        cell["precision_profile"] = "presentation-fast"
        selected.append(cell)
    selected.sort(key=lambda item: (str(item["point"]), str(item["geometry"]), float(item["gamma"])))
    if len(selected) != 12:
        raise RuntimeError(f"presentation subset regression: expected 12 cells, got {len(selected)}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",type=Path,default=Path("results/presentation_manifest.json"),
    )
    args = parser.parse_args()
    cells = presentation_cells()
    atomic_json(
        args.output,
        {
            "schema_version": 1,
            "generated_by": "scripts/build_presentation_manifest.py",
            "claim_scope": "LOW_PRECISION_CLARABEL_DIAGNOSTIC_ONLY",
            "solver_profile": {
                "name": "presentation-fast",
                "per_solve_time_limit_seconds": 600,
                "max_iterations": 60,
                "scientific_residual_threshold_unchanged": True,
            },
            "cell_count": len(cells),
            "observable_optimum_count": 6 * len(cells),
            "cells": cells,
        },
    )
    print(f"wrote {args.output}: {len(cells)} cells / {6*len(cells)} observable solves")


if __name__ == "__main__":
    main()
