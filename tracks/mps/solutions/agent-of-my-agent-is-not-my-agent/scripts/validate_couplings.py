#!/usr/bin/env python3
"""Validate the exact finite-ring Hurwitz-zeta coupling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lrtfim.couplings import direct_image_sum, periodic_couplings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--sigma", type=float, required=True)
    parser.add_argument("--image-cutoff", type=int, default=1_000_000)
    parser.add_argument("--relative-tolerance", type=float, default=2e-10)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    couplings = periodic_couplings(args.length, args.sigma)
    symmetry_residual = float(np.max(np.abs(couplings - couplings[::-1])))

    sample_distances = sorted({1, args.length // 4, args.length // 2, args.length - 1})
    direct_errors = {}
    for distance in sample_distances:
        exact = float(couplings[distance - 1])
        truncated = direct_image_sum(
            distance,
            args.length,
            args.sigma,
            image_cutoff=args.image_cutoff,
        )
        direct_errors[str(distance)] = abs(exact - truncated) / exact

    result = {
        "length": args.length,
        "sigma": args.sigma,
        "image_cutoff": args.image_cutoff,
        "positive": bool(np.all(couplings > 0)),
        "symmetry_residual": symmetry_residual,
        "direct_relative_errors": direct_errors,
        "max_direct_relative_error": max(direct_errors.values()),
    }
    success = (
        result["positive"]
        and symmetry_residual < 1e-14
        and result["max_direct_relative_error"] < args.relative_tolerance
    )

    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"L={args.length} sigma={args.sigma}", flush=True)
        print(f"positive={result['positive']}", flush=True)
        print(f"symmetry residual={symmetry_residual:.3e}", flush=True)
        print(
            "max direct-image relative error="
            f"{result['max_direct_relative_error']:.3e}",
            flush=True,
        )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
