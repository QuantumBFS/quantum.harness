"""Combine ED/NQS JSON files and fit the finite-size neutral gap."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _linear_fit(rows: list[dict], minimum_n: int) -> dict:
    selected = [row for row in rows if row["n_electrons"] >= minimum_n]
    if len(selected) < 3:
        raise ValueError("at least three ED sizes are required for a scaling fit")
    x = 1.0 / np.asarray([row["n_electrons"] for row in selected], dtype=float)
    y = np.asarray([row["ed_gap"] for row in selected], dtype=float)
    design = np.column_stack((np.ones_like(x), x))
    coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ coefficients
    residual_variance = float(residuals @ residuals / (len(y) - 2))
    covariance = residual_variance * np.linalg.inv(design.T @ design)
    return {
        "model": "Delta_N = Delta_infinity + slope/N",
        "minimum_n": minimum_n,
        "sizes": [row["n_electrons"] for row in selected],
        "delta_infinity": float(coefficients[0]),
        "delta_infinity_regression_error": float(np.sqrt(covariance[0, 0])),
        "slope": float(coefficients[1]),
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
    for n_electrons in sorted(ed_by_n):
        ed = ed_by_n[n_electrons]
        nqs = nqs_by_n.get(n_electrons)
        rows.append(
            {
                "n_electrons": n_electrons,
                "two_q": ed["two_q"],
                "ed_e_l0": ed["e_l0"],
                "ed_e_l2": ed["e_l2"],
                "ed_gap": ed["gap"],
                "ed_l2": ed["l2_excited"],
                "nqs_gap": "" if nqs is None else nqs["gap"],
                "nqs_gap_error": "" if nqs is None else abs(nqs["gap"] - ed["gap"]),
                "sampled_gap": "" if nqs is None else nqs["sampled_gap"],
                "sampled_gap_standard_error": (
                    "" if nqs is None else nqs["sampled_gap_error"]
                ),
            }
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "gap_table.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "energy_unit": "e^2/(epsilon*l_B)",
        "ed_sizes": sorted(ed_by_n),
        "nqs_sizes": sorted(nqs_by_n),
        "fit": _linear_fit(rows, args.minimum_n),
    }
    (output_dir / "scaling_fit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
