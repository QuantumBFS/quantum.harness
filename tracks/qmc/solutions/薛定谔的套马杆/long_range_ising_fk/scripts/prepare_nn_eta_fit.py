#!/usr/bin/env python3
"""Prepare the three-size nearest-neighbor susceptibility scaling table."""

import argparse
import csv
import math
from pathlib import Path


def read_size(root, wanted_L):
    values = []
    cells = 0
    for block_path in sorted((root / "cells").glob("*/blocks.csv")):
        summary_path = block_path.with_name("summary.csv")
        if not summary_path.exists():
            continue
        with summary_path.open(newline="") as handle:
            summary = next(csv.DictReader(handle))
        L = int(summary["L"])
        if L != wanted_L:
            continue
        cells += 1
        with block_path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                values.append(L * L * float(row["m2"]))
    if not values:
        raise SystemExit(f"blocked: no L={wanted_L} blocks under {root}")
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, math.sqrt(variance / len(values)), len(values), cells


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("nn_v3", type=Path)
    parser.add_argument("nn_large", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    sources = {
        64: args.nn_v3,
        128: args.nn_v3,
        256: args.nn_large,
        512: args.nn_large,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("L", "chi", "err", "blocks", "cells", "source"))
        for L, root in sources.items():
            chi, err, blocks, cells = read_size(root, L)
            writer.writerow((L, chi, err, blocks, cells, root.name))
            print(
                f"L={L} chi={chi:.10g} err={err:.4g} "
                f"blocks={blocks} cells={cells} source={root.name}",
                flush=True,
            )


if __name__ == "__main__":
    main()
