#!/usr/bin/env python3
"""Regenerate the locked exponential-fit validation grid for one sigma."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from lrtfim.fit_protocol import (
    regenerate_primary_sigma_fit,
    regenerate_sigma_fits,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sigma", type=float, required=True)
    parser.add_argument("--lengths", nargs="+", type=int, default=[32, 64, 128, 256])
    parser.add_argument("--l-max", type=int, default=256)
    parser.add_argument("--primary-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"regenerate sigma={args.sigma:g}, L_max={args.l_max}",
        flush=True,
    )
    regenerate = (
        regenerate_primary_sigma_fit
        if args.primary_only
        else regenerate_sigma_fits
    )
    result = regenerate(
        sigma=args.sigma,
        lengths=args.lengths,
        l_max=args.l_max,
    )
    for record in result["fits"]:
        for length, rows in record["coupling_profiles"].items():
            name = (
                f"couplings_K{record['num_exponentials']}"
                f"_alpha{record['alpha']:g}_rfit{record['r_fit']}_L{length}.csv"
            )
            with (args.output_dir / name).open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0])
                writer.writeheader()
                writer.writerows(rows)
    (args.output_dir / "fit-summary.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(f"wrote {len(result['fits'])} fit cells", flush=True)


if __name__ == "__main__":
    main()
