#!/usr/bin/env python3
"""Audit a theory-only stochastic-trace variance-reduction pilot.

Two replicated finite-regulator groups must differ only in trace-probe
distribution.  The audit requires a smaller real-part variance and checks
that the two estimators have statistically compatible means.  It never reads
a wall trajectory or target transport coefficient.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def _value(payload: dict[str, object], scaled_wave: float, scaled_time: float) -> complex:
    waves = np.asarray(payload["scaled_waves_q_equals_k_over_h2"], dtype=float)
    times = np.asarray(payload["scaled_times_tau_equals_t_h3"], dtype=float)
    wave_index = int(np.argmin(np.abs(waves - scaled_wave)))
    time_index = int(np.argmin(np.abs(times - scaled_time)))
    if abs(waves[wave_index] - scaled_wave) > 1e-12:
        raise ValueError("requested scaled wave is absent")
    if abs(times[time_index] - scaled_time) > 1e-12:
        raise ValueError("requested scaled time is absent")
    return complex(
        *payload["structure_factors_over_chi_by_wave_then_time"][wave_index][time_index]
    )


def _group(paths: list[Path], scaled_wave: float, scaled_time: float) -> dict[str, object]:
    payloads = [json.loads(path.read_text()) for path in paths]
    if len(payloads) < 4:
        raise ValueError("at least four independent replicates are required")
    if any(item.get("uses_target_a_or_D") or item.get("uses_target_trajectory") for item in payloads):
        raise ValueError("target-dependent input is forbidden")
    if any(not item["iteration"]["converged"] for item in payloads):
        raise ValueError("unconverged fixed point")
    fields = {float(item["regulator"]["field"]) for item in payloads}
    distributions = {item["regulator"]["trace_distribution"] for item in payloads}
    seeds = [int(item["regulator"]["seed"]) for item in payloads]
    if len(fields) != 1 or len(distributions) != 1:
        raise ValueError("each group must have one field and one trace distribution")
    if len(set(seeds)) != len(seeds):
        raise ValueError("duplicate stochastic seed")
    values = np.asarray([_value(item, scaled_wave, scaled_time) for item in payloads])
    real_std = float(np.std(values.real, ddof=1))
    complex_std = float(np.sqrt(np.sum(np.abs(values - np.mean(values)) ** 2) / (values.size - 1)))
    return {
        "field": fields.pop(),
        "trace_distribution": distributions.pop(),
        "seeds": seeds,
        "values": values,
        "mean": complex(np.mean(values)),
        "real_standard_deviation": real_std,
        "complex_standard_deviation": complex_std,
        "complex_standard_error": complex_std / np.sqrt(values.size),
    }


def audit(
    ordinary_paths: list[Path],
    candidate_paths: list[Path],
    *,
    scaled_wave: float,
    scaled_time: float,
    maximum_variance_ratio: float = 0.75,
    maximum_mean_difference_sigma: float = 2.0,
) -> dict[str, object]:
    ordinary = _group(ordinary_paths, scaled_wave, scaled_time)
    candidate = _group(candidate_paths, scaled_wave, scaled_time)
    if ordinary["field"] != candidate["field"]:
        raise ValueError("pilot fields differ")
    if ordinary["trace_distribution"] == candidate["trace_distribution"]:
        raise ValueError("trace distributions must differ")
    variance_ratio = (
        candidate["real_standard_deviation"] ** 2
        / max(ordinary["real_standard_deviation"] ** 2, np.finfo(float).tiny)
    )
    pooled_sem = float(
        np.hypot(
            ordinary["complex_standard_error"],
            candidate["complex_standard_error"],
        )
    )
    mean_difference = abs(candidate["mean"] - ordinary["mean"])
    mean_difference_sigma = float(mean_difference / max(pooled_sem, np.finfo(float).tiny))
    accepted = bool(
        variance_ratio <= maximum_variance_ratio
        and mean_difference_sigma <= maximum_mean_difference_sigma
    )

    def encoded(group: dict[str, object]) -> dict[str, object]:
        return {
            "field": group["field"],
            "trace_distribution": group["trace_distribution"],
            "seeds": group["seeds"],
            "mean": [float(group["mean"].real), float(group["mean"].imag)],
            "real_standard_deviation": group["real_standard_deviation"],
            "complex_standard_deviation": group["complex_standard_deviation"],
            "complex_standard_error": group["complex_standard_error"],
        }

    return {
        "schema": 1,
        "method": "replicated_trace_variance_reduction_audit",
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "scaled_wave": scaled_wave,
        "scaled_time": scaled_time,
        "ordinary": encoded(ordinary),
        "candidate": encoded(candidate),
        "observed_real_variance_ratio": float(variance_ratio),
        "observed_complex_mean_difference": float(mean_difference),
        "pooled_complex_standard_error": pooled_sem,
        "observed_mean_difference_sigma": mean_difference_sigma,
        "maximum_variance_ratio": maximum_variance_ratio,
        "maximum_mean_difference_sigma": maximum_mean_difference_sigma,
        "accepted": accepted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinary", nargs="+", required=True, type=Path)
    parser.add_argument("--candidate", nargs="+", required=True, type=Path)
    parser.add_argument("--scaled-wave", type=float, default=0.4)
    parser.add_argument("--scaled-time", type=float, default=27 / (10 * np.pi))
    parser.add_argument("--maximum-variance-ratio", type=float, default=0.75)
    parser.add_argument("--maximum-mean-difference-sigma", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        args.ordinary,
        args.candidate,
        scaled_wave=args.scaled_wave,
        scaled_time=args.scaled_time,
        maximum_variance_ratio=args.maximum_variance_ratio,
        maximum_mean_difference_sigma=args.maximum_mean_difference_sigma,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
