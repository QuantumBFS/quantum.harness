#!/usr/bin/env python3
"""Generate deterministic two-dimensional infrared-regime proxies."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


SCHEMA = "issue158.on_infrared_regimes.v1"
SIGMAS = (1.75, 2.0, 2.25)


def proxy_kernel(k: float, sigma: float) -> float:
    if not 0.0 < k <= 1.0:
        raise ValueError("k must lie in (0, 1]")
    if sigma < 2.0:
        return k**sigma
    if sigma == 2.0:
        return k**2 * math.log(math.e / k)
    return k**2


def infrared_integral(length: int, sigma: float) -> float:
    if length <= 2 * math.pi:
        raise ValueError("length must make 2*pi/L smaller than one")
    k_min = 2.0 * math.pi / length
    prefactor = 1.0 / (2.0 * math.pi)
    if sigma < 2.0:
        return prefactor * (
            1.0 - k_min ** (2.0 - sigma)
        ) / (2.0 - sigma)
    if sigma == 2.0:
        return prefactor * math.log(math.log(math.e / k_min))
    return prefactor * math.log(1.0 / k_min)


def build_payload() -> dict:
    lengths = [2**power for power in range(5, 21)]
    momenta = np.geomspace(1e-6, 1.0, 241)
    regimes = {}
    for sigma in SIGMAS:
        key = f"{sigma:.2f}"
        kernel_rows = [
            {"k": float(k), "E": proxy_kernel(float(k), sigma)}
            for k in momenta
        ]
        integral_rows = []
        for length in lengths:
            value = infrared_integral(length, sigma)
            k_min = 2.0 * math.pi / length
            if sigma < 2.0:
                scale = 1.0 / (2.0 * math.pi * (2.0 - sigma))
                diagnostic_name = "fraction_of_finite_limit"
                diagnostic = value / scale
            elif sigma == 2.0:
                scale = math.log(math.log(math.e / k_min))
                diagnostic_name = "coefficient_of_log_log"
                diagnostic = value / scale
            else:
                scale = math.log(1.0 / k_min)
                diagnostic_name = "coefficient_of_log"
                diagnostic = value / scale
            integral_rows.append(
                {
                    "L": length,
                    "k_min": k_min,
                    "I_L": value,
                    diagnostic_name: diagnostic,
                }
            )
        regimes[key] = {
            "sigma": sigma,
            "kernel_asymptotic": (
                "k^sigma"
                if sigma < 2.0
                else (
                    "k^2 log(e/k)" if sigma == 2.0 else "k^2"
                )
            ),
            "infrared_behavior": (
                "finite"
                if sigma < 2.0
                else ("log log L" if sigma == 2.0 else "log L")
            ),
            "kernel_rows": kernel_rows,
            "integral_rows": integral_rows,
        }
    return {
        "schema": SCHEMA,
        "dimension": 2,
        "radial_measure": "k dk / (2*pi)",
        "lengths": lengths,
        "regimes": regimes,
        "interpretation": (
            "deterministic continuum proxies for the infrared criterion; "
            "not Monte Carlo data and not a premise of the theorem"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/on_infrared_regimes.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
