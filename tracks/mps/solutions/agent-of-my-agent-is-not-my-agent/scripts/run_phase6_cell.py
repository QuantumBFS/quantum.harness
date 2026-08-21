#!/usr/bin/env python3
"""Run or resume one raw-observable Phase 6 ground-state cell."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from lrtfim.correlation_ratio import (
    physical_correlations_rotated,
    second_moment_ratio,
)
from lrtfim.dmrg_workflow import build_mpo_model, default_dmrg_options
from lrtfim.exponential_fit import ExponentialFit
from lrtfim.mpo import build_rotated_periodized_mpo
from lrtfim.parity_dmrg import run_parity_ground


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-summary", type=Path, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--gamma", type=float, required=True)
    parser.add_argument("--chi", type=int, default=128)
    parser.add_argument("--max-sweeps", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _primary_fit(summary: dict) -> dict:
    primary = summary["primary"]
    return next(
        record
        for record in summary["fits"]
        if record["num_exponentials"] == primary["num_exponentials"]
        and record["alpha"] == primary["alpha"]
        and record["r_fit"] == primary["r_fit"]
    )


def _normalize_fit_summary(summary: dict) -> dict:
    """Normalize either a Phase 6 grid or validated Phase 2 single-fit file."""
    if "primary" in summary and "fits" in summary:
        return summary
    required = {
        "K",
        "p",
        "r_fit",
        "min_rate_scale",
        "lambdas",
        "coefficients",
        "infinite_kernel",
    }
    missing = required.difference(summary)
    if missing:
        raise ValueError(f"fit summary is missing fields: {sorted(missing)}")
    primary = {
        "num_exponentials": int(summary["K"]),
        "alpha": float(summary["min_rate_scale"]),
        "r_fit": int(summary["r_fit"]),
    }
    fit = {
        **primary,
        "lambdas": summary["lambdas"],
        "coefficients": summary["coefficients"],
        "kernel_max_relative_error": summary["infinite_kernel"][
            "max_relative_error"
        ],
        "kernel_rms_relative_error": summary["infinite_kernel"][
            "rms_relative_error"
        ],
    }
    return {
        "sigma": float(summary["p"]) - 1.0,
        "primary": primary,
        "fits": [fit],
    }


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fit_bytes = args.fit_summary.read_bytes()
    fit_id = hashlib.sha256(fit_bytes).hexdigest()
    summary = _normalize_fit_summary(json.loads(fit_bytes))
    primary = _primary_fit(summary)
    settings = {
        "sigma": summary["sigma"],
        "length": args.length,
        "gamma": args.gamma,
        "chi": args.chi,
        "max_sweeps": args.max_sweeps,
        "fit_id": fit_id,
        "num_exponentials": primary["num_exponentials"],
        "alpha": primary["alpha"],
        "r_fit": primary["r_fit"],
        "sector": "even",
    }
    manifest_path = args.output_dir / "manifest.json"
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text())
        if existing.get("status") == "success" and existing.get("settings") == settings:
            print("reusing successful cell", flush=True)
            return

    fit = ExponentialFit(
        sigma=summary["sigma"],
        r_fit=primary["r_fit"],
        lambdas=np.asarray(primary["lambdas"]),
        coefficients=np.asarray(primary["coefficients"]),
        max_relative_error=primary["kernel_max_relative_error"],
        rms_relative_error=primary["kernel_rms_relative_error"],
    )
    mpo = build_rotated_periodized_mpo(
        args.length,
        fit.lambdas,
        fit.coefficients,
        args.gamma,
    )
    options = default_dmrg_options(args.chi)
    options["max_sweeps"] = args.max_sweeps
    state = run_parity_ground(build_mpo_model(mpo), options)
    correlations = physical_correlations_rotated(state.psi)
    ratio = second_moment_ratio(correlations)
    raw = {
        "energy": state.energy,
        "variance": state.variance,
        "discarded_weight": state.max_discarded_weight,
        "max_chi": state.max_chi,
        "correlations": correlations.tolist(),
        "s_zero": ratio.s_zero,
        "s_k_min": ratio.s_k_min,
        "k_min": ratio.k_min,
        "xi": ratio.xi,
        "r_xi": ratio.r_xi,
        "sweep_statistics": _json_safe(state.sweep_statistics),
    }
    with (args.output_dir / "correlations.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["distance", "correlation"])
        writer.writeheader()
        writer.writerows(
            {
                "distance": distance,
                "correlation": correlation,
            }
            for distance, correlation in enumerate(correlations)
        )
    manifest = {
        "status": "success",
        "settings": settings,
        "raw_observables": raw,
    }
    temporary = args.output_dir / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(manifest_path)
    print(
        f"L={args.length}, Gamma={args.gamma:g}, R_xi={ratio.r_xi:.12g}",
        flush=True,
    )


if __name__ == "__main__":
    main()
