#!/usr/bin/env python3
"""Generate the approved small-time-step and field-bracketing scan."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any

from generate_challenge_scan_specs import SETTINGS


SIZES = {
    "triangular": [32, 40, 48],
    "honeycomb": [24, 28, 32],
}
WINDOWS = {
    "triangular": {
        0.010: [4.7705, 4.7710, 4.7715, 4.7720, 4.7725],
        0.013: [4.7728, 4.7733, 4.7738, 4.7743, 4.7748],
        0.016: [4.7743, 4.7748, 4.7753, 4.7758, 4.7763],
    },
    "honeycomb": {
        0.010: [2.1318, 2.1323, 2.1328, 2.1333, 2.1338],
        0.016: [2.1340, 2.1345],
    },
}
EXPECTED_COUNTS = {"triangular": 45, "honeycomb": 21}
BUNDLE_COUNTS = {"triangular": 12, "honeycomb": 8}


def cost_proxy(params: dict[str, Any]) -> float:
    """Order the approximate L-cubed, inverse-time-step work longest first."""
    return int(params["L"]) ** 3 / float(params["FixedDltau"])


def scan_points(lattice: str) -> list[dict[str, Any]]:
    if lattice not in SIZES:
        raise ValueError(f"unsupported lattice {lattice!r}")
    points = [
        {
            "lattice": lattice,
            "L": size,
            "hTrfd": field,
            "FixedDltau": requested_step,
            "scan_kind": "dtau",
        }
        for requested_step, fields in WINDOWS[lattice].items()
        for size, field in itertools.product(SIZES[lattice], fields)
    ]
    return sorted(points, key=cost_proxy, reverse=True)


def balanced_bundles(
    cells: list[dict[str, Any]],
    bundle_count: int,
) -> list[dict[str, Any]]:
    bundles: list[list[int]] = [[] for _ in range(bundle_count)]
    loads = [0.0] * bundle_count
    for cell_index, cell in enumerate(cells, start=1):
        bundle_index = min(
            range(bundle_count),
            key=lambda index: (loads[index], index),
        )
        bundles[bundle_index].append(cell_index)
        loads[bundle_index] += cost_proxy(cell["params"])
    return [
        {
            "bundle_id": bundle_index + 1,
            "cell_indices": indices,
            "cost_proxy_sum": loads[bundle_index],
        }
        for bundle_index, indices in enumerate(bundles)
    ]


def build_spec(lattice: str) -> dict[str, Any]:
    points = scan_points(lattice)
    if len(points) != EXPECTED_COUNTS[lattice]:
        raise RuntimeError(f"unexpected {lattice} cell count")
    keys = {
        (
            point["lattice"],
            point["L"],
            point["hTrfd"],
            point["FixedDltau"],
        )
        for point in points
    }
    if len(keys) != len(points):
        raise RuntimeError(f"duplicate {lattice} scan cell")
    offset = 3000 if lattice == "triangular" else 4000
    cells = []
    for index, point in enumerate(points, start=1):
        params = dict(point)
        params["seed"] = int(SETTINGS["base_seed"]) + offset + index
        cells.append({"cell_id": f"cell-{index:04d}", "params": params})
    run_id = f"challenge-precision-recovery-{lattice}-20260729"
    return {
        "run_id": run_id,
        "run_dir": f"tracks/qmc/results/Only-team/{run_id}",
        "settings": dict(SETTINGS),
        "provenance": {
            "design": (
                "tracks/qmc/solutions/Only-team/"
                "PRECISION_RECOVERY_PLAN.md"
            ),
            "parent_analysis": "challenge-analysis-20260729",
            "ordering": "descending L^3/FixedDltau cost proxy",
        },
        "execution": {
            "strategy": "balanced_sequential_bundles",
            "bundle_count": BUNDLE_COUNTS[lattice],
            "bundles": balanced_bundles(
                cells,
                BUNDLE_COUNTS[lattice],
            ),
        },
        "cells": cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    allowed = (
        repo_root / "tracks" / "qmc" / "results" / "Only-team"
    ).resolve()
    for lattice in ("triangular", "honeycomb"):
        spec = build_spec(lattice)
        run_dir = (repo_root / spec["run_dir"]).resolve()
        run_dir.relative_to(allowed)
        run_dir.mkdir(parents=True, exist_ok=False)
        destination = run_dir / "run_spec.json"
        destination.write_text(
            json.dumps(spec, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"{lattice}: {len(spec['cells'])} cells -> {destination}",
            flush=True,
        )


if __name__ == "__main__":
    main()
