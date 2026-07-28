# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Compare registered c_tau=1 and c_tau=2 Challenge 148 runs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import analyze_stage4 as analysis


def compare_points(first, second):
    rows = []
    failures = []
    common = sorted(set(first) & set(second))
    if not common:
        raise ValueError("the c_tau runs have no common (L,h) points")
    for key in common:
        for observable, error_name in (("Q", "Q_err"), ("xi", "xi_err")):
            left = first[key][observable]
            right = second[key][observable]
            combined_error = float(np.hypot(
                first[key][error_name], second[key][error_name]
            ))
            shift = right - left
            shift_z = abs(shift) / combined_error if combined_error > 0.0 else np.inf
            passed = np.isfinite(shift_z) and shift_z <= analysis.SAMPLING_Z_MAX
            rows.append((
                key[0], key[1], observable, left, first[key][error_name], right,
                second[key][error_name], shift, combined_error, shift_z, int(passed),
            ))
            if not passed:
                failures.append(
                    f"L={key[0]} h={key[1]} observable={observable}: "
                    f"c_tau shift_z={shift_z:.3g}"
                )
    return rows, failures


def compare_fits(first, second, shift_budget):
    if not np.isfinite(shift_budget) or shift_budget <= 0.0:
        raise ValueError("the critical-field shift budget must be positive")
    rows = []
    failures = []
    for observable in ("Q", "xi"):
        left = first[observable]
        right = second[observable]
        shift = right["hc"] - left["hc"]
        combined_error = float(np.hypot(left["error"], right["error"]))
        shift_z = abs(shift) / combined_error if combined_error > 0.0 else np.inf
        upper_95 = abs(shift) + 1.96 * combined_error
        consistent = np.isfinite(shift_z) and shift_z <= analysis.SAMPLING_Z_MAX
        resolved = np.isfinite(upper_95) and upper_95 <= shift_budget
        passed = consistent and resolved
        rows.append((
            observable, left["hc"], left["error"], right["hc"], right["error"],
            shift, combined_error, shift_z, upper_95, shift_budget, int(consistent),
            int(resolved), int(passed),
        ))
        if not passed:
            failures.append(
                f"observable={observable}: shift_z={shift_z:.3g} "
                f"upper_95={upper_95:.6g} budget={shift_budget:.6g}"
            )
    return rows, failures


def write_outputs(prefix: Path, point_rows, fit_rows, gate):
    prefix.parent.mkdir(parents=True, exist_ok=True)
    point_path = prefix.with_name(prefix.name + "_ctau_points.csv")
    with point_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "L", "h", "observable", "c_tau_1", "c_tau_1_err", "c_tau_2",
            "c_tau_2_err", "shift", "combined_error", "shift_z", "passed",
        ])
        writer.writerows(point_rows)
    fit_path = prefix.with_name(prefix.name + "_ctau_fits.csv")
    with fit_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "observable", "c_tau_1_hc", "c_tau_1_hc_err", "c_tau_2_hc",
            "c_tau_2_hc_err", "hc_shift", "combined_error", "shift_z",
            "shift_upper_95", "shift_budget", "consistent", "resolved",
            "passed",
        ])
        writer.writerows(fit_rows)
    gate_path = prefix.with_name(prefix.name + "_ctau_gate.json")
    gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n")

    figure, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for axis, observable in zip(axes, ("Q", "xi")):
        selected = [row for row in point_rows if row[2] == observable]
        x = np.arange(len(selected))
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.errorbar(
            x,
            [row[7] for row in selected],
            yerr=[row[8] for row in selected],
            fmt="o",
            markersize=3,
        )
        axis.set(
            xlabel="common (L, h) point",
            ylabel=r"$c_\tau=2$ minus $c_\tau=1$",
            title="Binder ratio" if observable == "Q" else "Correlation length",
        )
    figure.savefig(prefix.with_name(prefix.name + "_ctau_shifts.png"), dpi=180)
    plt.close(figure)
    return point_path, fit_path, gate_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("c_tau_1", type=Path)
    parser.add_argument("c_tau_2", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--hc-shift-budget", type=float, required=True)
    parser.add_argument("--bootstrap", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--protocol-window", choices=("broad", "narrow"), required=True)
    parser.add_argument("--l-min", type=int, required=True)
    parser.add_argument("--omega", type=float, default=analysis.OMEGA)
    parser.add_argument("--omit-mixed", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()
    if args.bootstrap < 2:
        parser.error("--bootstrap must be at least 2")

    first_chains, first_metadata = analysis.load_bins(args.c_tau_1)
    second_chains, second_metadata = analysis.load_bins(args.c_tau_2)
    first_identity = next(iter(first_metadata.values()))
    second_identity = next(iter(second_metadata.values()))
    if first_identity["lattice"] != second_identity["lattice"]:
        raise ValueError("c_tau runs use different lattices")
    if not np.isclose(first_identity["c_tau"], 1.0):
        raise ValueError("the first input is not c_tau=1")
    if not np.isclose(second_identity["c_tau"], 2.0):
        raise ValueError("the second input is not c_tau=2")

    first_cells = analysis.grouped_cells(first_chains)
    second_cells = analysis.grouped_cells(second_chains)
    common = sorted(set(first_cells) & set(second_cells))
    first_cells = {key: first_cells[key] for key in common}
    second_cells = {key: second_cells[key] for key in common}
    first_metadata = {key: first_metadata[key] for key in common}
    second_metadata = {key: second_metadata[key] for key in common}
    first_points, _ = analysis.point_estimates(
        first_cells, first_metadata, args.bootstrap, np.random.default_rng(args.seed)
    )
    second_points, _ = analysis.point_estimates(
        second_cells,
        second_metadata,
        args.bootstrap,
        np.random.default_rng(args.seed + 1),
    )
    point_rows, point_failures = compare_points(first_points, second_points)

    protocol = analysis.PROTOCOL_WINDOWS[first_identity["lattice"]]
    h_min, h_max = protocol[args.protocol_window]
    keys = analysis.select_keys(first_points, h_min, h_max, args.l_min)
    analysis.validate_protocol_selection(
        first_metadata, first_points, args.protocol_window, args.l_min, args.omega
    )
    analysis.validate_protocol_selection(
        second_metadata, second_points, args.protocol_window, args.l_min, args.omega
    )
    include_mixed = not args.omit_mixed
    first_fits = analysis.fit_observables(
        keys, first_points, first_cells, first_metadata, args.bootstrap, args.seed,
        args.omega, include_mixed,
    )
    second_fits = analysis.fit_observables(
        keys, second_points, second_cells, second_metadata, args.bootstrap,
        args.seed + 10, args.omega, include_mixed,
    )
    fit_rows, fit_failures = compare_fits(
        first_fits, second_fits, args.hc_shift_budget
    )
    failures = point_failures + fit_failures
    gate = {
        "schema_version": "challenge148-ctau-gate-v1",
        "lattice": first_identity["lattice"],
        "c_tau_values": [1.0, 2.0],
        "common_points": len(common),
        "hc_shift_budget": args.hc_shift_budget,
        "passed": not failures,
        "failures": failures,
    }
    paths = write_outputs(args.output_prefix, point_rows, fit_rows, gate)
    print(
        f"lattice={gate['lattice']} common_points={len(common)} "
        f"c_tau_gate={'pass' if gate['passed'] else 'fail'}"
    )
    print("outputs=" + ",".join(str(path) for path in paths))
    if args.enforce and failures:
        raise ValueError("c_tau comparison failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
