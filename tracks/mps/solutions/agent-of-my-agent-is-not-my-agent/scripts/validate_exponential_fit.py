#!/usr/bin/env python3
"""Fit and validate periodized exponential approximations."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lrtfim.couplings import periodic_couplings  # noqa: E402
from lrtfim.exponential_fit import (  # noqa: E402
    fit_power_law,
    periodized_exponential_couplings,
    power_law_values,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=64)
    parser.add_argument("--sigma", type=float, default=1.75)
    parser.add_argument("--r-fit", type=int, default=None)
    parser.add_argument("--min-rate-scale", type=float)
    parser.add_argument(
        "--k-values",
        type=int,
        nargs="+",
        default=[8, 12, 16, 20, 24],
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "results" / "phase2",
    )
    return parser.parse_args()


def error_metrics(approximate: np.ndarray, exact: np.ndarray) -> dict[str, float]:
    relative = np.abs(approximate - exact) / exact
    return {
        "max_relative_error": float(np.max(relative)),
        "rms_relative_error": float(np.sqrt(np.mean(relative**2))),
    }


def periodized_error_summary(
    approximate: np.ndarray,
    exact: np.ndarray,
    *,
    length: int,
) -> dict[str, object]:
    """Summarize global, short-distance, and central periodic residuals."""
    relative = np.abs(approximate - exact) / exact
    maximum_index = int(np.argmax(relative))
    center = length // 2
    short_slice = slice(0, 10)
    central_indices = np.arange(center - 2, center + 3, dtype=int) - 1

    def region(indices: slice | np.ndarray) -> dict[str, float]:
        values = relative[indices]
        return {
            "max_relative_error": float(np.max(values)),
            "rms_relative_error": float(np.sqrt(np.mean(values**2))),
        }

    summary: dict[str, object] = error_metrics(approximate, exact)
    summary["global_maximum"] = {
        "distance": maximum_index + 1,
        "relative_error": float(relative[maximum_index]),
        "exact_hurwitz": float(exact[maximum_index]),
        "periodized_fit": float(approximate[maximum_index]),
    }
    summary["short_distance"] = {
        "distance_min": 1,
        "distance_max": 10,
        **region(short_slice),
    }
    summary["central_region"] = {
        "distances": list(range(center - 2, center + 3)),
        **region(central_indices),
    }
    return summary


def write_profile(
    path: Path,
    fieldnames: list[str],
    columns: dict[str, np.ndarray],
) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in zip(*(columns[name] for name in fieldnames), strict=True):
            writer.writerow(dict(zip(fieldnames, row, strict=True)))


def main() -> int:
    args = parse_args()
    r_fit = 8 * args.length if args.r_fit is None else args.r_fit
    if args.length < 20 or args.length % 2:
        raise ValueError("length must be an even integer >= 20")
    if r_fit < 1:
        raise ValueError("r_fit must be positive")
    if any(k < 1 for k in args.k_values) or len(set(args.k_values)) != len(
        args.k_values
    ):
        raise ValueError("k-values must be distinct positive integers")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    kernel_r = np.arange(1, r_fit + 1, dtype=int)
    kernel_exact = power_law_values(kernel_r, sigma=args.sigma)
    periodic_r = np.arange(1, args.length, dtype=int)
    periodic_exact = periodic_couplings(args.length, args.sigma)
    summaries = []

    for k in args.k_values:
        fit = fit_power_law(
            sigma=args.sigma,
            num_exponentials=k,
            r_fit=r_fit,
            min_rate_scale=args.min_rate_scale,
        )
        rates = -np.log(fit.lambdas)
        kernel_fit = fit.evaluate(kernel_r)
        kernel_abs = np.abs(kernel_fit - kernel_exact)
        kernel_rel = kernel_abs / kernel_exact
        periodic_fit = periodized_exponential_couplings(args.length, fit)
        periodic_abs = np.abs(periodic_fit - periodic_exact)
        periodic_rel = periodic_abs / periodic_exact

        summary = {
            "K": k,
            "length": args.length,
            "sigma": args.sigma,
            "p": 1.0 + args.sigma,
            "r_fit": r_fit,
            "min_rate_scale": args.min_rate_scale,
            "lambdas": fit.lambdas.tolist(),
            "rates": rates.tolist(),
            "min_rate_times_r_fit": float(np.min(rates) * r_fit),
            "coefficients": fit.coefficients.tolist(),
            "infinite_kernel": error_metrics(kernel_fit, kernel_exact),
            "periodized_coupling": periodized_error_summary(
                periodic_fit,
                periodic_exact,
                length=args.length,
            ),
        }
        summaries.append(summary)
        (args.output_dir / f"summary_K{k}.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
        write_profile(
            args.output_dir / f"kernel_error_K{k}.csv",
            ["distance", "exact_power_law", "exponential_fit", "absolute_error",
             "relative_error"],
            {
                "distance": kernel_r,
                "exact_power_law": kernel_exact,
                "exponential_fit": kernel_fit,
                "absolute_error": kernel_abs,
                "relative_error": kernel_rel,
            },
        )
        write_profile(
            args.output_dir / f"periodic_error_K{k}.csv",
            ["distance", "exact_hurwitz", "periodized_fit", "absolute_error",
             "relative_error"],
            {
                "distance": periodic_r,
                "exact_hurwitz": periodic_exact,
                "periodized_fit": periodic_fit,
                "absolute_error": periodic_abs,
                "relative_error": periodic_rel,
            },
        )
        print(
            f"K={k}: kernel max={fit.max_relative_error:.6e}, "
            f"rms={fit.rms_relative_error:.6e}; "
            f"periodic max={summary['periodized_coupling']['max_relative_error']:.6e}, "
            f"rms={summary['periodized_coupling']['rms_relative_error']:.6e}",
            flush=True,
        )

    aggregate = {
        "length": args.length,
        "sigma": args.sigma,
        "p": 1.0 + args.sigma,
        "r_fit": r_fit,
        "min_rate_scale": args.min_rate_scale,
        "fits": summaries,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n"
    )
    print(f"Wrote profiles and summaries to {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
