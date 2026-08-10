#!/usr/bin/env python3
"""Generate the approved intermediate-size and time-step scan specifications."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any


MAIN_FIELDS = {
    "triangular": [
        4.76511,
        4.76611,
        4.76711,
        4.76811,
        4.76911,
        4.77011,
        4.77111,
    ],
    "honeycomb": [
        2.1295,
        2.1305,
        2.1315,
        2.1325,
        2.1335,
        2.1345,
        2.1355,
    ],
}
MAIN_SIZES = {
    "triangular": [12, 16, 20, 24, 32, 40],
    "honeycomb": [12, 16, 20, 24, 28],
}
DTAU_SIZES = {
    "triangular": [32, 40, 48],
    "honeycomb": [24, 28, 32],
}
DTAU_FIELDS = {
    "triangular": [4.76711, 4.76761, 4.76811, 4.76861, 4.76911],
    "honeycomb": [2.1315, 2.132, 2.1325, 2.133, 2.1335],
}
HALF_STEP_FIELDS = {
    "triangular": [4.76761, 4.76861],
    "honeycomb": [2.132, 2.133],
}
EXPECTED_COUNTS = {"triangular": 78, "honeycomb": 71}

SETTINGS = {
    "Hamiltonian": (
        "H = J1 sum_<i,j> sigma_z_i sigma_z_j"
        " - hTrfd sum_i sigma_x_i"
    ),
    "J1": -1.0,
    "J2": 0.0,
    "boundary": "periodic",
    "BetaT_rule": "L/hTrfd",
    "IfSetDltau": True,
    "FixedDltau": 0.013,
    "nLocal": 1,
    "nWolff": 5,
    "nWarm": 10000,
    "NmBin": 32,
    "NSwep": 2000,
    "NmMeaConfg": 10,
    "discard_initial_bins": 1,
    "trim_extrema": True,
    "statistics_mode": "bin_sem",
    "base_seed": 20260729,
    "initial_state": "random",
    "nprocs": 32,
}


def scan_points(lattice: str) -> list[dict[str, Any]]:
    points = [
        {
            "lattice": lattice,
            "L": size,
            "hTrfd": field,
            "FixedDltau": 0.013,
            "scan_kind": "main",
        }
        for size, field in itertools.product(
            MAIN_SIZES[lattice],
            MAIN_FIELDS[lattice],
        )
    ]
    points.extend(
        {
            "lattice": lattice,
            "L": size,
            "hTrfd": field,
            "FixedDltau": 0.013,
            "scan_kind": "dtau",
        }
        for size, field in itertools.product(
            DTAU_SIZES[lattice],
            HALF_STEP_FIELDS[lattice],
        )
    )
    points.extend(
        {
            "lattice": lattice,
            "L": size,
            "hTrfd": field,
            "FixedDltau": requested_step,
            "scan_kind": "dtau",
        }
        for requested_step, size, field in itertools.product(
            [0.016, 0.02],
            DTAU_SIZES[lattice],
            DTAU_FIELDS[lattice],
        )
    )
    return points


def build_spec(lattice: str) -> dict[str, Any]:
    run_id = f"challenge-production-{lattice}-20260729"
    offset = 1000 if lattice == "triangular" else 2000
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
    cells = []
    for index, point in enumerate(points, start=1):
        params = dict(point)
        params["seed"] = SETTINGS["base_seed"] + offset + index
        cells.append({"cell_id": f"cell-{index:04d}", "params": params})
    return {
        "run_id": run_id,
        "run_dir": f"tracks/qmc/results/Only-team/{run_id}",
        "settings": SETTINGS,
        "provenance": {
            "design": (
                "tracks/qmc/solutions/Only-team/"
                "CHALLENGE_RUN_DESIGN.md"
            ),
            "reused_runs": [
                "challenge-extremes-max-20260729",
                "challenge-extremes-min-20260729",
            ],
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
        print(f"{lattice}: {len(spec['cells'])} cells -> {destination}", flush=True)


if __name__ == "__main__":
    main()
