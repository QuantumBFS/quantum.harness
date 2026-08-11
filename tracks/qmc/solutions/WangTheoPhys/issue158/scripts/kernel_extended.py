#!/usr/bin/env python3
"""High-precision lattice-kernel audit for Issue #158.

For sigma=2 and axial momentum, the infinite square-lattice sum is reduced to
one dimension.  The algebraic tail is evaluated with a trilogarithm, leaving
only an exponentially convergent correction.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import mpmath as mp
import numpy as np


CATALAN = mp.mpf("0.915965594177219015054603514932384110774")


def c_infinity() -> mp.mpf:
    return 6 / (mp.pi**2 * CATALAN)


def infinite_axial_sigma2(k: float, dps: int = 60) -> float:
    """Evaluate sum_R c_inf |R|^-4 [1-cos(k R_x)] exactly enough.

    For integer x != 0,

      sum_y (x^2+y^2)^-2
        = pi*coth(pi*x)/(2*x^3)
          + pi^2*csch(pi*x)^2/(2*x^2).

    The pi/(2*x^3) tail is summed with Li_3(exp(i*k)); the remaining
    correction decays exponentially in x.
    """
    mp.mp.dps = dps
    kval = mp.mpf(str(k))
    c = c_infinity()
    main_series = mp.zeta(3) - mp.re(mp.polylog(3, mp.e ** (1j * kval)))
    main = c * mp.pi * main_series
    correction = mp.mpf("0")
    for x in range(1, 80):
        xm = mp.mpf(x)
        exact_y_sum = (
            mp.pi * mp.coth(mp.pi * xm) / (2 * xm**3)
            + mp.pi**2 * mp.csch(mp.pi * xm) ** 2 / (2 * xm**2)
        )
        delta = exact_y_sum - mp.pi / (2 * xm**3)
        correction += 2 * c * (1 - mp.cos(kval * xm)) * delta
    return float(main + correction)


def minimum_image_kernel(
    L: int, sigma: float, normalize_to_four: bool = True
) -> tuple[float, float, float]:
    """Return normalized E(kmin), c_L, and raw coupling sum.

    The displacement representatives are [-L/2,L/2)^2 for even L, matching
    the convention used in the earlier audit.
    """
    coords = np.arange(-L // 2, L // 2, dtype=np.float64)
    k = 2 * np.pi / L
    raw_sum = 0.0
    weighted = 0.0
    power = (2.0 + sigma) / 2.0
    y2 = coords * coords
    for x in coords:
        r2 = x * x + y2
        if x == 0:
            mask = r2 > 0
            row = np.sum(r2[mask] ** (-power))
        else:
            row = np.sum(r2 ** (-power))
        raw_sum += float(row)
        weighted += float((1 - math.cos(k * x)) * row)
    c_L = 4.0 / raw_sum if normalize_to_four else 1.0
    return c_L * weighted, c_L, raw_sum


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-mi-power", type=int, default=12)
    parser.add_argument("--max-infinite-power", type=int, default=16)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    c_inf = float(c_infinity())
    predicted = math.pi * c_inf / 2
    infinite_rows: list[dict] = []
    for power in range(5, args.max_infinite_power + 1):
        L = 2**power
        k = 2 * math.pi / L
        energy = infinite_axial_sigma2(k)
        infinite_rows.append(
            {
                "L": L,
                "k": k,
                "E_infinite_PI": energy,
                "E_over_k2": energy / k**2,
                "ratio_to_leading": energy
                / (predicted * k**2 * math.log(1 / k)),
            }
        )
    for previous, current in zip(infinite_rows, infinite_rows[1:]):
        dx = math.log(1 / current["k"]) - math.log(1 / previous["k"])
        current["local_log_slope"] = (
            current["E_over_k2"] - previous["E_over_k2"]
        ) / dx
    infinite_rows[0]["local_log_slope"] = None

    xfit = np.asarray(
        [math.log(1 / row["k"]) for row in infinite_rows[-6:]]
    )
    yfit = np.asarray([row["E_over_k2"] for row in infinite_rows[-6:]])
    fitted_slope, fitted_intercept = np.polyfit(xfit, yfit, 1)

    mi_rows: list[dict] = []
    for sigma in [1.875, 2.0, 2.125]:
        sigma_rows: list[dict] = []
        for power in range(5, args.max_mi_power + 1):
            L = 2**power
            energy, c_L, raw_sum = minimum_image_kernel(L, sigma, True)
            row = {
                "sigma": sigma,
                "L": L,
                "k": 2 * math.pi / L,
                "E_MI_normalized": energy,
                "c_L": c_L,
                "raw_sum": raw_sum,
            }
            if sigma == 2.0:
                e_inf = infinite_axial_sigma2(row["k"])
                relative = (energy - e_inf) / e_inf
                row.update(
                    {
                        "E_infinite_PI": e_inf,
                        "MI_minus_PI_relative": relative,
                        "relative_times_logL": relative * math.log(L),
                        "cL_minus_cinf_times_L2": (
                            c_L - c_inf
                        )
                        * L**2,
                        "MI_leading_ratio": energy
                        / (
                            predicted
                            * row["k"] ** 2
                            * math.log(1 / row["k"])
                        ),
                    }
                )
            sigma_rows.append(row)
        for previous, current in zip(sigma_rows, sigma_rows[1:]):
            current["effective_power"] = -math.log(
                current["E_MI_normalized"]
                / previous["E_MI_normalized"]
            ) / math.log(current["L"] / previous["L"])
        sigma_rows[0]["effective_power"] = None
        mi_rows.extend(sigma_rows)

    result = {
        "c_infinity": c_inf,
        "predicted_log_slope": predicted,
        "fitted_log_slope_last_six": float(fitted_slope),
        "fitted_intercept_last_six": float(fitted_intercept),
        "relative_slope_error": float((fitted_slope - predicted) / predicted),
        "infinite_PI_rows": infinite_rows,
        "minimum_image_rows": mi_rows,
        "method": (
            "Exact axial y-sum plus Li_3 algebraic-tail summation at sigma=2; "
            "direct minimum-image row sums for finite tori."
        ),
    }
    (args.out_dir / "kernel_extended_results.json").write_text(
        json.dumps(result, indent=2)
    )

    fields = [
        "sigma",
        "L",
        "k",
        "E_MI_normalized",
        "effective_power",
        "c_L",
        "E_infinite_PI",
        "MI_minus_PI_relative",
        "relative_times_logL",
        "cL_minus_cinf_times_L2",
        "MI_leading_ratio",
    ]
    with (args.out_dir / "kernel_scaling.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in mi_rows:
            writer.writerow({field: row.get(field) for field in fields})

    infinite_fields = [
        "L",
        "k",
        "E_infinite_PI",
        "E_over_k2",
        "local_log_slope",
        "ratio_to_leading",
    ]
    with (args.out_dir / "kernel_infinite_PI.csv").open(
        "w", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=infinite_fields)
        writer.writeheader()
        for row in infinite_rows:
            writer.writerow(row)


if __name__ == "__main__":
    main()
