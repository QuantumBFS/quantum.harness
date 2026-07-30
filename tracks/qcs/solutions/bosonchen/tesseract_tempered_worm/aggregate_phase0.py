#!/usr/bin/env python3
"""Aggregate the three phase-0 tempered-worm diagnostics."""

import argparse
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    reports = []
    for path in sorted(args.run_directory.glob("*.json")):
        report = json.loads(path.read_text())
        if report.get("status") != "phase0_mixing_diagnostic":
            continue
        reports.append((path.stem, report))
    if not reports:
        raise RuntimeError(f"No phase-0 reports found in {args.run_directory}")

    cases = []
    for name, report in reports:
        shots = report["shot_results"]
        summary = report["summary"]
        cases.append(
            {
                "case": name,
                "shots": report["shots"],
                "num_errors": report["model"]["num_errors"],
                "num_detectors": report["model"]["num_detectors"],
                "kernel_moves": report["cycle_library"]["moves"],
                "logical_sector_moves": report["cycle_library"][
                    "logical_sector_moves"
                ],
                "logical_sector_rank": report["cycle_library"][
                    "logical_mask_rank"
                ],
                "preprocessing_seconds": report["cycle_library"][
                    "preprocessing_seconds"
                ],
                "random_worm_closure_rate": (
                    report["cycle_library"]["random_closed_moves"]
                    / max(
                        1,
                        report["cycle_library"]["random_closed_moves"]
                        + report["cycle_library"]["random_failed_attempts"],
                    )
                ),
                "baseline_errors": summary["baseline_errors"],
                "mc_errors": summary["mc_errors"],
                "bar_errors": summary["bar_errors"],
                "prediction_mismatches": summary[
                    "mc_baseline_prediction_mismatches"
                ],
                "bar_prediction_mismatches": summary[
                    "bar_baseline_prediction_mismatches"
                ],
                "baseline_seconds": summary["baseline_seconds"],
                "seed_seconds": summary["seed_seconds"],
                "bar_seconds": summary["bar_seconds"],
                "candidate_seconds": summary["candidate_seconds"],
                "baseline_seconds_per_shot": (
                    summary["baseline_seconds"] / report["shots"]
                ),
                "candidate_seconds_per_shot": (
                    summary["candidate_seconds"] / report["shots"]
                ),
                "candidate_seconds_per_shot_with_preprocessing": (
                    (
                        summary["candidate_seconds"]
                        + report["cycle_library"]["preprocessing_seconds"]
                    )
                    / report["shots"]
                ),
                "exploratory_speedup_with_preprocessing": (
                    summary["baseline_seconds"]
                    / (
                        summary["candidate_seconds"]
                        + report["cycle_library"]["preprocessing_seconds"]
                    )
                ),
                "seed_retries": summary.get("seed_retries", 0),
                "seed_fallbacks": summary.get("seed_fallbacks", 0),
                "exploratory_speedup": summary["exploratory_speedup"],
                "median_distinct_sectors": statistics.median(
                    shot["distinct_logical_sectors"] for shot in shots
                ),
                "median_margin": statistics.median(
                    shot["top_two_margin"] for shot in shots
                ),
                "median_ess": statistics.median(
                    shot["effective_sample_size"] for shot in shots
                ),
                "logical_move_acceptance": (
                    sum(shot["logical_move_accepts"] for shot in shots)
                    / max(
                        1,
                        sum(shot["logical_move_attempts"] for shot in shots),
                    )
                ),
                "total_target_logical_transitions": sum(
                    shot["target_logical_transitions"] for shot in shots
                ),
                "median_bar_candidate_sectors": statistics.median(
                    shot["bar_candidate_sectors"] for shot in shots
                ),
                "median_bar_reachable_sectors": statistics.median(
                    shot["bar_reachable_sectors"] for shot in shots
                ),
                "median_best_bar_overlap": statistics.median(
                    max(
                        (
                            comparison["overlap_score"]
                            for comparison in shot["bar_comparisons"]
                        ),
                        default=0,
                    )
                    for shot in shots
                ),
                "total_reliable_bar_comparisons": sum(
                    shot["bar_reliable_comparisons"] for shot in shots
                ),
                "bar_triggered_shots": sum(
                    shot["bar_triggered"] for shot in shots
                ),
                "total_round_trips": sum(
                    shot["temperature_round_trips"] for shot in shots
                ),
            }
        )

    all_shots = sum(case["shots"] for case in cases)
    output = {
        "schema_version": 1,
        "status": "phase0_aggregate",
        "timing_warning": (
            "Exploratory only: one-time preprocessing is excluded; BAR burn-in "
            "is included when BAR is triggered; direct replica exchange is a "
            "diagnostic and is excluded from candidate timing."
        ),
        "cases": cases,
        "totals": {
            "cases": len(cases),
            "shots": all_shots,
            "baseline_errors": sum(case["baseline_errors"] for case in cases),
            "mc_errors": sum(case["mc_errors"] for case in cases),
            "bar_errors": sum(case["bar_errors"] for case in cases),
            "prediction_mismatches": sum(
                case["prediction_mismatches"] for case in cases
            ),
            "bar_prediction_mismatches": sum(
                case["bar_prediction_mismatches"] for case in cases
            ),
            "cases_with_sector_moves": sum(
                case["logical_sector_moves"] > 0 for case in cases
            ),
            "cases_with_multiple_sampled_sectors": sum(
                case["median_distinct_sectors"] > 1 for case in cases
            ),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
