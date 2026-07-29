"""Combine ED/NQS JSON files and fit the finite-size neutral gap."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fit(rows: list[dict], minimum_n: int, powers: tuple[int, ...], parity: int | None) -> dict:
    selected = [
        row
        for row in rows
        if row["n_electrons"] >= minimum_n
        and (parity is None or row["n_electrons"] % 2 == parity)
    ]
    if len(selected) <= len(powers):
        raise ValueError("not enough sizes for the requested scaling fit")
    x = 1.0 / np.asarray([row["n_electrons"] for row in selected], dtype=float)
    y = np.asarray([row["best_gap"] for row in selected], dtype=float)
    design = np.column_stack([np.ones_like(x), *(x**power for power in powers)])
    coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ coefficients
    residual_variance = float(residuals @ residuals / (len(y) - design.shape[1]))
    covariance = residual_variance * np.linalg.inv(design.T @ design)
    return {
        "model": "Delta_N = Delta_infinity + " + " + ".join(
            f"a{power}/N^{power}" for power in powers
        ),
        "minimum_n": minimum_n,
        "parity": "all" if parity is None else ("even" if parity == 0 else "odd"),
        "sizes": [row["n_electrons"] for row in selected],
        "delta_infinity": float(coefficients[0]),
        "delta_infinity_regression_error": float(np.sqrt(covariance[0, 0])),
        "coefficients": {
            f"inverse_n_power_{power}": float(value)
            for power, value in zip(powers, coefficients[1:])
        },
        "residual_rms": float(np.sqrt(np.mean(residuals**2))),
        "caveat": "regression error excludes finite-size-model systematics",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ed", nargs="+", required=True)
    parser.add_argument("--nqs", nargs="*", default=[])
    parser.add_argument("--minimum-n", type=int, default=4)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    ed_by_n = {int(item["n_electrons"]): item for item in map(_load, args.ed)}
    nqs_by_n = {int(item["n_electrons"]): item for item in map(_load, args.nqs)}
    rows: list[dict] = []
    for n_electrons in sorted(ed_by_n.keys() | nqs_by_n.keys()):
        ed = ed_by_n.get(n_electrons)
        nqs = nqs_by_n.get(n_electrons)
        if ed is None and nqs is None:
            continue
        reference = ed if ed is not None else nqs
        best_gap = ed["gap"] if ed is not None else nqs["gap"]
        rows.append(
            {
                "n_electrons": n_electrons,
                "two_q": reference["two_q"],
                "ed_e_l0": "" if ed is None else ed["e_l0"],
                "ed_e_l2": "" if ed is None else ed["e_l2"],
                "ed_gap": "" if ed is None else ed["gap"],
                "ed_l2": "" if ed is None else ed["l2_excited"],
                "nqs_gap": "" if nqs is None else nqs["gap"],
                "nqs_gap_error": (
                    "" if nqs is None or ed is None else abs(nqs["gap"] - ed["gap"])
                ),
                "sampled_gap": "" if nqs is None else nqs["sampled_gap"],
                "sampled_gap_standard_error": (
                    "" if nqs is None else nqs["sampled_gap_error"]
                ),
                "best_gap": best_gap,
                "best_gap_source": "ed" if ed is not None else "nqs",
            }
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "gap_table.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    fits = {
        "linear_all": _fit(rows, args.minimum_n, (1,), None),
        "linear_even": _fit(rows, args.minimum_n, (1,), 0),
        "linear_odd": _fit(rows, args.minimum_n, (1,), 1),
        "quadratic_all": _fit(rows, args.minimum_n, (1, 2), None),
    }
    intercepts = [fit["delta_infinity"] for fit in fits.values()]
    central = fits["linear_all"]["delta_infinity"]
    summary = {
        "energy_unit": "e^2/(epsilon*l_B)",
        "ed_sizes": sorted(ed_by_n),
        "nqs_sizes": sorted(nqs_by_n),
        "fits": fits,
        "recommended": {
            "delta_infinity": central,
            "regression_error": fits["linear_all"]["delta_infinity_regression_error"],
            "fit_model_systematic_envelope": max(abs(value - central) for value in intercepts),
            "caveat": "small-size envelope, not a controlled thermodynamic error bar",
        },
    }
    (output_dir / "scaling_fit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
