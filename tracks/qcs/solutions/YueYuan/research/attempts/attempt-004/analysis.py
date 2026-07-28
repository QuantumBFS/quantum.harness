from __future__ import annotations

import json
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

import hessian


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def percentile(values: list[float | int], fraction: float):
    clean = sorted(value for value in values if value is not None)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    position = (len(clean) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return clean[lower]
    weight = position - lower
    return clean[lower] * (1.0 - weight) + clean[upper] * weight


def success_interval(success_count: int, n: int) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    rate = success_count / n
    radius = 1.96 * math.sqrt(max(0.0, rate * (1.0 - rate) / n))
    return (max(0.0, rate - radius), min(1.0, rate + radius))


def aggregate(results_dir: Path) -> dict:
    rows = read_jsonl(Path(results_dir) / "runs.jsonl")
    groups = defaultdict(list)
    for row in rows:
        key = (
            row["system"],
            row["method"],
            row["mismatch"],
            row["shots_per_query"],
            row["k"],
        )
        groups[key].append(row)
    summaries = []
    for (system, method, mismatch, shots, k), items in sorted(groups.items()):
        queries = [item["queries_to_target"] for item in items if item["queries_to_target"] is not None]
        shots_to_target = [
            item["total_shots_to_target"] for item in items if item["total_shots_to_target"] is not None
        ]
        success_count = sum(1 for item in items if item["success"])
        success_rate = success_count / len(items)
        success_low, success_high = success_interval(success_count, len(items))
        probe_queries = [
            item.get("device_probe_query_count")
            for item in items
            if item.get("device_probe_query_count") is not None
        ]
        probe_shots = [
            item.get("device_probe_shot_count")
            for item in items
            if item.get("device_probe_shot_count") is not None
        ]
        probe_selected = [
            item.get("device_probe_directions_selected")
            for item in items
            if item.get("device_probe_directions_selected") is not None
        ]
        summaries.append(
            {
                "system": system,
                "method": method,
                "mismatch": mismatch,
                "shots_per_query": shots,
                "k": k,
                "n": len(items),
                "n_success": success_count,
                "success_rate": success_rate,
                "success_ci95_low": success_low,
                "success_ci95_high": success_high,
                "median_queries_to_target": statistics.median(queries) if queries else None,
                "queries_to_target_q25": percentile(queries, 0.25),
                "queries_to_target_q75": percentile(queries, 0.75),
                "median_shots_to_target": statistics.median(shots_to_target) if shots_to_target else None,
                "shots_to_target_q25": percentile(shots_to_target, 0.25),
                "shots_to_target_q75": percentile(shots_to_target, 0.75),
                "median_final_infidelity": statistics.median(
                    [item["final_infidelity"] for item in items]
                ),
                "median_probe_query_count": statistics.median(probe_queries)
                if probe_queries
                else None,
                "median_probe_shot_count": statistics.median(probe_shots)
                if probe_shots
                else None,
                "median_probe_directions_selected": statistics.median(probe_selected)
                if probe_selected
                else None,
            }
        )
    return {"rows": len(rows), "groups": summaries}


def write_summary(results_dir: Path) -> dict:
    summary = aggregate(results_dir)
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    (Path(results_dir) / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary


GROUP_FIELDS = (
    "system",
    "method",
    "mismatch",
    "shots_per_query",
    "k",
    "n",
    "n_success",
    "success_rate",
    "success_ci95_low",
    "success_ci95_high",
    "median_queries_to_target",
    "queries_to_target_q25",
    "queries_to_target_q75",
    "median_shots_to_target",
    "shots_to_target_q25",
    "shots_to_target_q75",
    "median_final_infidelity",
)


def write_summary_tables(results_dir: Path, summary: dict | None = None) -> list[Path]:
    results_dir = Path(results_dir)
    summary = summary or aggregate(results_dir)
    tables = results_dir / "summary_tables"
    tables.mkdir(parents=True, exist_ok=True)
    group_path = tables / "group_summary.csv"
    _write_csv(group_path, summary["groups"], GROUP_FIELDS)

    headline = _headline_rows(summary["groups"])
    headline_path = tables / "headline_comparison.csv"
    _write_csv(headline_path, headline, GROUP_FIELDS)

    failure_rows = [
        {**row, "failure_rate": 1.0 - row["success_rate"]}
        for row in summary["groups"]
        if row["method"] == "hessian_subspace_nelder_mead" and row["success_rate"] < 0.5
    ]
    failure_path = tables / "failure_modes.csv"
    _write_csv(failure_path, failure_rows, GROUP_FIELDS + ("failure_rate",))

    recovery_path = tables / "recovery_study.csv"
    _write_csv(recovery_path, recovery_study_rows(summary["groups"]), RECOVERY_FIELDS)
    spectrum_path = tables / "spectrum_summary.csv"
    spectra_file = results_dir / "hessian_spectra.json"
    spectra = json.loads(spectra_file.read_text()) if spectra_file.exists() else []
    _write_csv(spectrum_path, spectrum_summary_rows(spectra), SPECTRUM_FIELDS)
    return [group_path, headline_path, failure_path, recovery_path, spectrum_path]


def _headline_rows(groups: list[dict]) -> list[dict]:
    benchmark_k = {"one_qubit_x": 3, "two_qubit_cz": 15}
    rows = []
    for row in groups:
        if row["method"] == "full_space_nelder_mead":
            rows.append(row)
        elif row["method"] in {
            "hessian_subspace_nelder_mead",
            "random_subspace_nelder_mead",
        } and row["k"] == benchmark_k.get(row["system"]):
            rows.append(row)
        elif row["method"] == "adaptive_hessian_subspace_nelder_mead":
            rows.append(row)
    return rows


RECOVERY_FIELDS = (
    "system",
    "mismatch",
    "shots_per_query",
    "benchmark_k",
    "benchmark_success_rate",
    "benchmark_median_queries_to_target",
    "best_k",
    "best_success_rate",
    "best_median_queries_to_target",
    "best_median_final_infidelity",
    "recovery_delta_success",
    "recovered_by_widening",
)

SPECTRUM_FIELDS = (
    "system",
    "mismatch",
    "shots_per_query",
    "seed",
    "effective_rank",
    "benchmark_rank",
    "total_absolute_curvature",
    "curvature_at_benchmark_k",
    "k_for_90pct_curvature",
    "k_for_95pct_curvature",
    "k_for_99pct_curvature",
)

DEVICE_INFORMED_FIELDS = GROUP_FIELDS + (
    "median_probe_query_count",
    "median_probe_shot_count",
    "median_probe_directions_selected",
)

DEVICE_INFORMED_RECOVERY_FIELDS = (
    "system",
    "mismatch",
    "shots_per_query",
    "fixed_hessian_success_rate",
    "widen_only_success_rate",
    "device_informed_success_rate",
    "device_informed_delta_vs_fixed",
    "device_informed_delta_vs_widen_only",
    "device_informed_median_final_infidelity",
    "device_informed_median_probe_query_count",
)

BENCHMARK_RANK = {"one_qubit_x": 3, "two_qubit_cz": 15}


def recovery_study_rows(groups: list[dict]) -> list[dict]:
    benchmark_k = {"one_qubit_x": 3, "two_qubit_cz": 15}
    rows = []
    for system in sorted({row["system"] for row in groups}):
        for mismatch in sorted({row["mismatch"] for row in groups if row["system"] == system}):
            shots_values = sorted(
                {
                    row["shots_per_query"]
                    for row in groups
                    if row["system"] == system and row["mismatch"] == mismatch
                }
            )
            for shots in shots_values:
                hessian = [
                    row
                    for row in groups
                    if row["system"] == system
                    and row["mismatch"] == mismatch
                    and row["shots_per_query"] == shots
                    and row["method"] == "hessian_subspace_nelder_mead"
                ]
                if not hessian:
                    continue
                benchmark = next(
                    (row for row in hessian if row["k"] == benchmark_k.get(system)),
                    None,
                )
                if benchmark is None:
                    continue
                best = sorted(
                    hessian,
                    key=lambda row: (
                        -row["success_rate"],
                        row["median_queries_to_target"]
                        if row["median_queries_to_target"] is not None
                        else 10**9,
                        row["median_final_infidelity"],
                    ),
                )[0]
                rows.append(
                    {
                        "system": system,
                        "mismatch": mismatch,
                        "shots_per_query": shots,
                        "benchmark_k": benchmark["k"],
                        "benchmark_success_rate": benchmark["success_rate"],
                        "benchmark_median_queries_to_target": benchmark[
                            "median_queries_to_target"
                        ],
                        "best_k": best["k"],
                        "best_success_rate": best["success_rate"],
                        "best_median_queries_to_target": best["median_queries_to_target"],
                        "best_median_final_infidelity": best["median_final_infidelity"],
                        "recovery_delta_success": best["success_rate"]
                        - benchmark["success_rate"],
                        "recovered_by_widening": best["k"] != benchmark["k"]
                        and best["success_rate"] > benchmark["success_rate"],
                    }
                )
    return rows


def spectrum_summary_rows(spectra: list[dict]) -> list[dict]:
    rows = []
    for spectrum in spectra:
        eigenvalues = spectrum.get("eigenvalues", [])
        benchmark_rank = int(
            spectrum.get(
                "benchmark_rank",
                BENCHMARK_RANK.get(spectrum.get("system"), 0),
            )
        )
        total_absolute_curvature = float(
            sum(abs(float(value)) for value in eigenvalues)
        )
        rows.append(
            {
                "system": spectrum.get("system"),
                "mismatch": spectrum.get("mismatch"),
                "shots_per_query": spectrum.get("shots_per_query"),
                "seed": spectrum.get("seed"),
                "effective_rank": spectrum.get(
                    "effective_rank",
                    hessian.effective_rank(eigenvalues),
                ),
                "benchmark_rank": benchmark_rank,
                "total_absolute_curvature": total_absolute_curvature,
                "curvature_at_benchmark_k": spectrum.get(
                    "curvature_at_benchmark_k",
                    hessian.curvature_fraction(eigenvalues, benchmark_rank),
                ),
                "k_for_90pct_curvature": spectrum.get(
                    "k_for_90pct_curvature",
                    hessian.min_k_for_curvature(eigenvalues, 0.90),
                ),
                "k_for_95pct_curvature": spectrum.get(
                    "k_for_95pct_curvature",
                    hessian.min_k_for_curvature(eigenvalues, 0.95),
                ),
                "k_for_99pct_curvature": spectrum.get(
                    "k_for_99pct_curvature",
                    hessian.min_k_for_curvature(eigenvalues, 0.99),
                ),
            }
        )
    return rows


def device_informed_summary_rows(groups: list[dict]) -> list[dict]:
    methods = {
        "full_space_nelder_mead",
        "random_subspace_nelder_mead",
        "hessian_subspace_nelder_mead",
        "adaptive_hessian_subspace_nelder_mead",
        "device_informed_adaptive_hessian_nelder_mead",
    }
    return [row for row in groups if row["method"] in methods]


def device_informed_recovery_rows(groups: list[dict]) -> list[dict]:
    rows = []
    for system in sorted({row["system"] for row in groups}):
        benchmark_k = BENCHMARK_RANK.get(system)
        for mismatch in sorted({row["mismatch"] for row in groups if row["system"] == system}):
            shots_values = sorted(
                {
                    row["shots_per_query"]
                    for row in groups
                    if row["system"] == system and row["mismatch"] == mismatch
                }
            )
            for shots in shots_values:
                fixed = _find_group(
                    groups,
                    system,
                    mismatch,
                    shots,
                    "hessian_subspace_nelder_mead",
                    benchmark_k,
                )
                widen = _find_group(
                    groups,
                    system,
                    mismatch,
                    shots,
                    "adaptive_hessian_subspace_nelder_mead",
                )
                informed = _find_group(
                    groups,
                    system,
                    mismatch,
                    shots,
                    "device_informed_adaptive_hessian_nelder_mead",
                )
                if fixed is None or widen is None or informed is None:
                    continue
                rows.append(
                    {
                        "system": system,
                        "mismatch": mismatch,
                        "shots_per_query": shots,
                        "fixed_hessian_success_rate": fixed["success_rate"],
                        "widen_only_success_rate": widen["success_rate"],
                        "device_informed_success_rate": informed["success_rate"],
                        "device_informed_delta_vs_fixed": informed["success_rate"]
                        - fixed["success_rate"],
                        "device_informed_delta_vs_widen_only": informed["success_rate"]
                        - widen["success_rate"],
                        "device_informed_median_final_infidelity": informed[
                            "median_final_infidelity"
                        ],
                        "device_informed_median_probe_query_count": informed[
                            "median_probe_query_count"
                        ],
                    }
                )
    return rows


def write_device_informed_tables(results_dir: Path, summary: dict | None = None) -> list[Path]:
    results_dir = Path(results_dir)
    summary = summary or aggregate(results_dir)
    tables = results_dir / "summary_tables"
    tables.mkdir(parents=True, exist_ok=True)
    summary_path = tables / "device_informed_summary.csv"
    recovery_path = tables / "device_informed_recovery.csv"
    _write_csv(summary_path, device_informed_summary_rows(summary["groups"]), DEVICE_INFORMED_FIELDS)
    _write_csv(
        recovery_path,
        device_informed_recovery_rows(summary["groups"]),
        DEVICE_INFORMED_RECOVERY_FIELDS,
    )
    return [summary_path, recovery_path]


def _find_group(groups, system, mismatch, shots, method, k=None):
    for row in groups:
        if row["system"] != system or row["mismatch"] != mismatch:
            continue
        if row["shots_per_query"] != shots or row["method"] != method:
            continue
        if k is not None and row["k"] != k:
            continue
        return row
    return None


def _write_csv(path: Path, rows: list[dict], fieldnames) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
