#!/usr/bin/env python3
"""Prepare only the K=24 and K=32 fits needed by the local comparison."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from lrtfim.couplings import periodic_couplings
from lrtfim.exponential_fit import (
    ExponentialFit,
    fit_power_law,
    periodized_exponential_couplings,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k24-summary", type=Path, required=True)
    parser.add_argument("--sigma", type=float, required=True)
    parser.add_argument("--lengths", nargs="+", type=int, required=True)
    parser.add_argument("--l-max", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _coefficient_hash(values) -> str:
    return hashlib.sha256(
        np.asarray(values, dtype="<f8").tobytes()
    ).hexdigest()


def _metrics(approximate: np.ndarray, exact: np.ndarray) -> dict:
    relative = np.abs(approximate - exact) / exact
    maximum = int(np.argmax(relative))
    return {
        "max_relative_error": float(np.max(relative)),
        "rms_relative_error": float(np.sqrt(np.mean(relative**2))),
        "maximum_distance": maximum + 1,
        "central_relative_error": float(relative[len(relative) // 2]),
    }


def _fit_record(
    *,
    fit: ExponentialFit,
    num_exponentials: int,
    alpha: float,
    source_sha256: str | None = None,
) -> dict:
    record = {
        "num_exponentials": num_exponentials,
        "alpha": alpha,
        "r_fit": fit.r_fit,
        "lambdas": fit.lambdas.tolist(),
        "coefficients": fit.coefficients.tolist(),
        "coefficient_hash": _coefficient_hash(fit.coefficients),
        "kernel_max_relative_error": fit.max_relative_error,
        "kernel_rms_relative_error": fit.rms_relative_error,
    }
    if source_sha256 is not None:
        record["source_sha256"] = source_sha256
    return record


def main() -> None:
    args = parse_args()
    if sorted(set(args.lengths)) != sorted(args.lengths):
        raise ValueError("lengths must be unique")
    r_fit = 8 * args.l_max
    source_bytes = args.k24_summary.read_bytes()
    source = json.loads(source_bytes)
    if (
        int(source["K"]) != 24
        or float(source["min_rate_scale"]) != 0.5
        or int(source["r_fit"]) != r_fit
        or float(source["p"]) - 1.0 != args.sigma
    ):
        raise ValueError("K=24 source does not match the locked fit tuple")

    fit24 = ExponentialFit(
        sigma=args.sigma,
        r_fit=r_fit,
        lambdas=np.asarray(source["lambdas"], dtype=float),
        coefficients=np.asarray(source["coefficients"], dtype=float),
        max_relative_error=float(
            source.get("infinite_kernel", {}).get("max_relative_error", np.nan)
        ),
        rms_relative_error=float(
            source.get("infinite_kernel", {}).get("rms_relative_error", np.nan)
        ),
    )
    print("fitting K=32, alpha=0.5", flush=True)
    fit32 = fit_power_law(
        sigma=args.sigma,
        num_exponentials=32,
        r_fit=r_fit,
        min_rate_scale=0.5,
    )
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    record24 = _fit_record(
        fit=fit24,
        num_exponentials=24,
        alpha=0.5,
        source_sha256=source_hash,
    )
    record32 = _fit_record(
        fit=fit32,
        num_exponentials=32,
        alpha=0.5,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    comparisons = {}
    for length in args.lengths:
        exact = periodic_couplings(length, args.sigma)
        approximate = {
            24: periodized_exponential_couplings(length, fit24),
            32: periodized_exponential_couplings(length, fit32),
        }
        comparisons[str(length)] = {
            "K24": _metrics(approximate[24], exact),
            "K32": _metrics(approximate[32], exact),
            "max_absolute_K_shift": float(
                np.max(np.abs(approximate[32] - approximate[24]))
            ),
        }
        for k in (24, 32):
            path = args.output_dir / f"couplings_K{k}_L{length}.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=(
                        "distance",
                        "exact_hurwitz",
                        "periodized_fit",
                        "absolute_error",
                        "relative_error",
                    ),
                )
                writer.writeheader()
                for distance, (exact_value, fit_value) in enumerate(
                    zip(exact, approximate[k], strict=True),
                    start=1,
                ):
                    writer.writerow(
                        {
                            "distance": distance,
                            "exact_hurwitz": exact_value,
                            "periodized_fit": fit_value,
                            "absolute_error": abs(fit_value - exact_value),
                            "relative_error": abs(fit_value - exact_value)
                            / exact_value,
                        }
                    )

    result = {
        "sigma": args.sigma,
        "lengths": args.lengths,
        "l_max": args.l_max,
        "primary": {
            "num_exponentials": 24,
            "alpha": 0.5,
            "r_fit": r_fit,
        },
        "fits": [record24, record32],
        "K24": record24,
        "K32": record32,
        "coupling_comparison": comparisons,
    }
    (args.output_dir / "fit-summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {args.output_dir / 'fit-summary.json'}", flush=True)


if __name__ == "__main__":
    main()
