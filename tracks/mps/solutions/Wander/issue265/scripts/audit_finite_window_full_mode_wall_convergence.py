#!/usr/bin/env python3
"""Audit node and Fourier convergence of the self-consistent full-mode wall."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-record", action="append", required=True)
    parser.add_argument("--q8", type=Path, required=True)
    parser.add_argument("--q12", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = []
    for encoded in args.node_record:
        node_text, path_text = encoded.split("=", 1)
        payload = json.loads(Path(path_text).read_text(encoding="utf-8"))
        fit = payload["frozen_weak_projection"]
        rows.append(
            {
                "nodes_per_string": int(node_text),
                "a": float(fit["a"]),
                "D": float(fit["D"]),
            }
        )
    rows.sort(key=lambda row: row["nodes_per_string"])
    nodes = np.asarray([row["nodes_per_string"] for row in rows], dtype=float)
    values = {
        "a": np.asarray([row["a"] for row in rows]),
        "D": np.asarray([row["D"] for row in rows]),
    }
    extrapolations = []
    for start in range(max(1, len(rows) - 1)):
        if len(rows) - start < 2:
            continue
        for power in (2, 3, 4):
            design = np.column_stack((np.ones(nodes[start:].size), nodes[start:] ** -power))
            extrapolations.append(
                {
                    "first_node": int(nodes[start]),
                    "power": power,
                    **{
                        key: float(np.linalg.lstsq(design, value[start:], rcond=None)[0][0])
                        for key, value in values.items()
                    },
                }
            )
    q8 = json.loads(args.q8.read_text(encoding="utf-8"))["frozen_weak_projection"]
    q12 = json.loads(args.q12.read_text(encoding="utf-8"))["frozen_weak_projection"]
    result = {
        "schema": 1,
        "method": "target_free_full_mode_wall_regulator_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "node_rows": rows,
        "node_extrapolations": extrapolations,
        "node_extrapolation_envelope": {
            key + "_min": float(min(row[key] for row in extrapolations))
            for key in values
        }
        | {
            key + "_max": float(max(row[key] for row in extrapolations))
            for key in values
        },
        "q_cutoff_check_at_32_nodes": {
            "q8": {"a": float(q8["a"]), "D": float(q8["D"])},
            "q12": {"a": float(q12["a"]), "D": float(q12["D"])},
            "absolute_change": {
                "a": abs(float(q12["a"]) - float(q8["a"])),
                "D": abs(float(q12["D"]) - float(q8["D"])),
            },
        },
        "audit": {
            "q_cutoff_converged_at_1e_minus_3": bool(
                abs(float(q12["a"]) - float(q8["a"])) < 1.0e-3
                and abs(float(q12["D"]) - float(q8["D"])) < 1.0e-3
            ),
            "node_limit_unique_at_1_percent": False,
            "linear_full_mode_physical_pair_claimed": False,
            "remaining_requirement": (
                "UV-matched state-dependent velocity/diffusion/noise and observable vertices"
            ),
        },
    }
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
