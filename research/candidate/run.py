#!/usr/bin/env python3
"""Candidate CLI: reduce every NPZ instance and emit one JSON artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from reducer import reduce_invariant_hermitian


def _complex_matrix(value: np.ndarray) -> list:
    return [[[float(z.real), float(z.imag)] for z in row] for row in value]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    results = []
    for path in sorted(Path(args.input_dir).glob("*.npz")):
        with np.load(path) as data:
            reduction = reduce_invariant_hermitian(data["matrix"], data["generators"], data["moduli"])
        results.append(
            {
                "id": path.stem,
                "method": "character_projectors",
                "dimension": reduction["dimension"],
                "moduli": reduction["moduli"],
                "sectors": [
                    {
                        "character": sector["character"],
                        "basis": _complex_matrix(sector["basis"]),
                        "block": _complex_matrix(sector["block"]),
                        "eigenvalues": [float(x) for x in sector["eigenvalues"]],
                    }
                    for sector in reduction["sectors"]
                ],
            }
        )
    Path(args.output).write_text(json.dumps({"schema_version": 1, "instances": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
