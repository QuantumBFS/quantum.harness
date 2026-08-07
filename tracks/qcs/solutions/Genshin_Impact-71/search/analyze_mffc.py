#!/usr/bin/env python3
"""Read-only MFFC inventory using the strict parser in divisor_resynth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from divisor_resynth import fanout_counts, mffc, parse_circuit, prune_and_compact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    circuit = prune_and_compact(parse_circuit(args.input))
    counts = fanout_counts(circuit)
    roots = []
    for root in range(1, len(circuit.gates) + 1):
        removed = mffc(circuit, root, counts)
        if len(removed) > 1:
            roots.append(
                {
                    "root": root,
                    "mffc_size": len(removed),
                    "max_useful_cost": min(3, len(removed) - 1),
                    "excluded_prior_wires": sorted(
                        wire for wire in removed if wire < root
                    ),
                }
            )
    print(
        json.dumps(
            {
                "gates": len(circuit.gates),
                "roots_with_mffc_gt_1": roots,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
