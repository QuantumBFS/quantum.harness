#!/usr/bin/env python3
"""Independent, read-only audit of the immutable Attempt-49 result.

This script never imports the simulator and cannot open a truth instance.  It
reconstructs the frozen run grid, paired finite-shot seeds, truth-cell
aggregation, stratified bootstrap, resource gates, safety interval, source
seals, and generated-artifact hashes from the committed result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORE = HERE.parent
RESULT_PATH = (
    CORE / "results_summary" / "QL1F-attempt49-fresh-confirmation.json"
)
CONFIG_PATH = HERE / "attempt49_fresh_confirmation_config.json"
MANIFEST_PATH = HERE / "attempt49_preregistration_manifest.json"
DEFAULT_OUTPUT = (
    CORE / "results_summary" / "QL1F-attempt50-final-audit.json"
)

FAMILIES = ("control-map", "drift", "combined")
METHODS = (
    "model-informed-k15",
    "model-informed-k40",
    "raw-coordinate-global-40",
)
EXPECTED_METHOD_DIMENSIONS = {
    "model-informed-k15": 15,
    "model-informed-k40": 40,
    "raw-coordinate-global-40": 40,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def binary_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def finite_tree(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    if isinstance(value, dict):
        return all(finite_tree(item) for item in value.values())
    return False


def paired_noise_seed(
    np: Any,
    family: str,
    truth_seed: int,
    replicate: int,
) -> int:
    sequence = np.random.SeedSequence(
        [113, 49, FAMILIES.index(family), truth_seed, replicate]
    )
    return int(sequence.generate_state(1, dtype=np.uint64)[0])


def truth_rows(
    np: Any,
    runs: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[(run["method"], run["selected_cell"])].append(run)

    output: dict[str, list[dict[str, Any]]] = {
        method: [] for method in METHODS
    }
    for method in METHODS:
        cells = sorted(
            (
                (selected_cell, rows)
                for (candidate, selected_cell), rows in grouped.items()
                if candidate == method
            ),
            key=lambda item: (
                FAMILIES.index(item[1][0]["family"]),
                int(item[1][0]["truth_seed"]),
            ),
        )
        for selected_cell, rows in cells:
            rows = sorted(rows, key=lambda row: int(row["replicate"]))
            output[method].append(
                {
                    "selected_cell": selected_cell,
                    "family": rows[0]["family"],
                    "truth_seed": int(rows[0]["truth_seed"]),
                    "nested_replicates": len(rows),
                    "oracle_scored_success": float(
                        np.mean(
                            [
                                bool(row["scan"]["oracle_scored_success"])
                                for row in rows
                            ]
                        )
                    ),
                    "accepted_nonzero_steps": int(
                        sum(
                            int(row["scan"]["accepted_nonzero_steps"])
                            for row in rows
                        )
                    ),
                    "destructive_accepted_steps": int(
                        sum(
                            int(row["scan"]["destructive_accepted_steps"])
                            for row in rows
                        )
                    ),
                    "full_cap_queries": float(
                        np.mean(
                            [
                                int(row["charged_full_cap"]["queries"])
                                for row in rows
                            ]
                        )
                    ),
                    "full_cap_shots": float(
                        np.mean(
                            [
                                int(row["charged_full_cap"]["shots"])
                                for row in rows
                            ]
                        )
                    ),
                }
            )
    return output


def bootstrap_indices(
    np: Any,
    rows: list[dict[str, Any]],
    *,
    draws: int,
    seed: int,
) -> Any:
    rng = np.random.default_rng(seed)
    output = np.empty((draws, len(rows)), dtype=np.int64)
    offset = 0
    for family in FAMILIES:
        group = np.asarray(
            [
                index
                for index, row in enumerate(rows)
                if row["family"] == family
            ],
            dtype=np.int64,
        )
        if len(group) != 8:
            raise RuntimeError(
                f"expected eight {family} truth cells, found {len(group)}"
            )
        choices = rng.integers(0, len(group), size=(draws, len(group)))
        output[:, offset : offset + len(group)] = group[choices]
        offset += len(group)
    return output


def interval(np: Any, values: Any, indices: Any) -> dict[str, float]:
    draws = np.mean(values[indices], axis=1)
    return {
        "estimate": float(np.mean(values)),
        "lower_95": float(np.quantile(draws, 0.025)),
        "upper_95": float(np.quantile(draws, 0.975)),
    }


def same_interval(
    actual: dict[str, float],
    recorded: dict[str, Any],
    *,
    tolerance: float = 1e-12,
) -> bool:
    return all(
        math.isclose(
            float(actual[key]),
            float(recorded[key]),
            rel_tol=0.0,
            abs_tol=tolerance,
        )
        for key in ("estimate", "lower_95", "upper_95")
    )


def ledger_closes(run: dict[str, Any]) -> bool:
    if run["exception"] is not None:
        return False
    scan = run["scan"]
    closure = scan["query_ledger_closure"]
    dimension = int(run["search_dimension"])
    expected_queries = 4 * dimension + 6
    expected_shots = (4 * dimension + 4) * 32768 + 2 * 1024
    return (
        int(scan["service_query_count"])
        == int(closure["row_count"])
        == int(scan["query_cap"])
        == int(run["charged_full_cap"]["queries"])
        == expected_queries
        and int(scan["service_total_shots"])
        == int(closure["total_shots"])
        == int(scan["shot_cap"])
        == int(run["charged_full_cap"]["shots"])
        == expected_shots
        and sum(int(value) for value in closure["purpose_counts"].values())
        == expected_queries
        and sum(int(value) for value in closure["purpose_shots"].values())
        == expected_shots
        and closure["full_rows_retained"] is False
    )


def audit() -> dict[str, Any]:
    import numpy as np
    from scipy.stats import beta

    result = load_json(RESULT_PATH)
    config = load_json(CONFIG_PATH)
    manifest = load_json(MANIFEST_PATH)
    runs = result["runs"]

    expected_cells = {
        (
            family,
            int(seed),
            float(config["benchmark"]["fixed_epsilon_by_family"][family]),
        )
        for family in FAMILIES
        for seed in config["benchmark"]["fresh_truth_seeds"]
    }
    expected_grid = {
        (family, seed, epsilon, replicate, method)
        for family, seed, epsilon in expected_cells
        for replicate in range(4)
        for method in METHODS
    }
    actual_grid = [
        (
            run["family"],
            int(run["truth_seed"]),
            float(run["epsilon"]),
            int(run["replicate"]),
            run["method"],
        )
        for run in runs
    ]

    grouped_pairing: dict[tuple[str, int, int], list[dict[str, Any]]] = (
        defaultdict(list)
    )
    for run in runs:
        grouped_pairing[
            (
                run["family"],
                int(run["truth_seed"]),
                int(run["replicate"]),
            )
        ].append(run)

    rows = truth_rows(np, runs)
    indices = bootstrap_indices(
        np,
        rows[METHODS[0]],
        draws=int(config["bootstrap"]["draws"]),
        seed=int(config["bootstrap"]["seed"]),
    )
    method_intervals: dict[str, dict[str, float]] = {}
    for method in METHODS:
        values = np.asarray(
            [row["oracle_scored_success"] for row in rows[method]],
            dtype=float,
        )
        method_intervals[method] = interval(np, values, indices)

    paired_intervals: dict[str, dict[str, float]] = {}
    reference_rows = {
        method: {
            row["selected_cell"]: row["oracle_scored_success"]
            for row in rows[method]
        }
        for method in METHODS
    }
    for reference in METHODS[1:]:
        difference = np.asarray(
            [
                reference_rows[METHODS[0]][row["selected_cell"]]
                - reference_rows[reference][row["selected_cell"]]
                for row in rows[METHODS[0]]
            ],
            dtype=float,
        )
        paired_intervals[reference] = interval(np, difference, indices)

    accepted = sum(
        int(run["scan"]["accepted_nonzero_steps"])
        for run in runs
        if run["method"] == METHODS[0]
    )
    destructive = sum(
        int(run["scan"]["destructive_accepted_steps"])
        for run in runs
        if run["method"] == METHODS[0]
    )
    destructive_upper = (
        1.0
        if accepted == 0 or destructive == accepted
        else float(beta.ppf(0.95, destructive + 1, accepted - destructive))
    )

    source_seal_matches = {
        relative: (
            (CORE / relative).is_file()
            and canonical_sha256(CORE / relative) == expected
        )
        for relative, expected in manifest["sealed_files"].items()
    }
    result_source_matches = {
        relative: (
            relative in manifest["sealed_files"]
            and actual == manifest["sealed_files"][relative]
        )
        for relative, actual in result["source_hashes"].items()
    }

    artifact_matches: dict[str, bool] = {}
    for name, record in result["artifacts"].items():
        path = CORE / record["path"]
        if "binary_sha256" in record:
            actual = binary_sha256(path)
            expected = record["binary_sha256"]
        else:
            actual = canonical_sha256(path)
            expected = record["canonical_sha256"]
        artifact_matches[name] = path.is_file() and actual == expected

    recorded_methods = result["summary"]["methods"]
    recorded_paired = result["summary"]["paired_success_differences"]
    recorded_safety = result["summary"][
        "k15_destructive_accepted_step_rate"
    ]
    recorded_cost = result["summary"]["cost_ratios"]

    query_ratio = 66 / 166
    shot_ratio = 2_099_200 / 5_376_000
    recomputed_gates = {
        "k15_success_lcb95_at_least_0_75": (
            method_intervals[METHODS[0]]["lower_95"] >= 0.75
        ),
        "k15_minus_k40_lcb95_above_minus_0_10": (
            paired_intervals[METHODS[1]]["lower_95"] > -0.10
        ),
        "k15_minus_raw40_lcb95_above_zero": (
            paired_intervals[METHODS[2]]["lower_95"] > 0.0
        ),
        "full_cap_query_ratios_below_0_60": query_ratio < 0.60,
        "full_cap_shot_ratios_below_0_60": shot_ratio < 0.60,
        "destructive_rate_ucb95_at_most_0_05": (
            destructive_upper <= 0.05
        ),
    }

    metadata_drift_rows = [
        run
        for run in runs
        if run["family"] == "drift"
        and float(
            run["truth_metadata"][
                "control_map_minus_identity_spectral_norm"
            ]
        )
        > 0.0
    ]

    checks = {
        "result_schema_and_status_exact": (
            result["schema"] == "QL1F-attempt49-fresh-confirmation-v1"
            and result["status"] == "complete"
            and result["confirmation_decision"] == "pass"
        ),
        "exact_unique_288_run_grid": (
            len(actual_grid) == 288
            and len(set(actual_grid)) == 288
            and set(actual_grid) == expected_grid
        ),
        "exact_24_truth_cells_and_four_nested_replicates": (
            all(len(method_rows) == 24 for method_rows in rows.values())
            and all(
                row["nested_replicates"] == 4
                for method_rows in rows.values()
                for row in method_rows
            )
        ),
        "method_dimensions_exact": all(
            int(run["search_dimension"])
            == EXPECTED_METHOD_DIMENSIONS[run["method"]]
            for run in runs
        ),
        "paired_noise_seed_formula_exact": all(
            int(run["noise_seed"])
            == paired_noise_seed(
                np,
                run["family"],
                int(run["truth_seed"]),
                int(run["replicate"]),
            )
            for run in runs
        ),
        "paired_noise_seed_shared_across_methods": (
            len(grouped_pairing) == 96
            and all(
                Counter(run["method"] for run in group)
                == Counter({method: 1 for method in METHODS})
                and len({int(run["noise_seed"]) for run in group}) == 1
                for group in grouped_pairing.values()
            )
        ),
        "all_runs_exception_free_and_finite": (
            all(run["exception"] is None for run in runs)
            and finite_tree(runs)
        ),
        "posthoc_boundary_closed": all(
            run["black_box_boundary"]["posthoc_started_after_client_end"]
            and not run["black_box_boundary"][
                "posthoc_values_used_in_decisions"
            ]
            and not run["scan"]["posthoc_values_used_in_calibration"]
            for run in runs
        ),
        "aggregate_ledgers_and_frozen_cost_formula_close": all(
            ledger_closes(run) for run in runs
        ),
        "method_bootstrap_intervals_reproduced": all(
            same_interval(
                method_intervals[method],
                recorded_methods[method]["success"],
            )
            for method in METHODS
        ),
        "paired_bootstrap_intervals_reproduced": all(
            same_interval(
                paired_intervals[method],
                recorded_paired[method],
            )
            for method in METHODS[1:]
        ),
        "safety_interval_reproduced": (
            accepted
            == int(recorded_safety["accepted_nonzero_steps"])
            and destructive
            == int(recorded_safety["destructive_accepted_steps"])
            and math.isclose(
                destructive_upper,
                float(recorded_safety["upper_95"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ),
        "cost_ratios_reproduced": all(
            math.isclose(
                float(recorded_cost[method]["query_ratio"]),
                query_ratio,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and math.isclose(
                float(recorded_cost[method]["shot_ratio"]),
                shot_ratio,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            for method in METHODS[1:]
        ),
        "all_six_gates_reproduced_and_pass": (
            recomputed_gates == result["summary"]["gate_checks"]
            and all(recomputed_gates.values())
        ),
        "source_manifest_seals_match": (
            bool(source_seal_matches)
            and all(source_seal_matches.values())
            and all(result_source_matches.values())
        ),
        "generated_artifact_hashes_match": (
            bool(artifact_matches) and all(artifact_matches.values())
        ),
        "preregistration_commit_and_revalidation_recorded": (
            result["preregistration"]["before_truth"]["status"] == "pass"
            and result["preregistration"]["after_runs"]["status"] == "pass"
            and result["preregistration"]["before_truth"]["git"]["head"]
            == result["preregistration"]["after_runs"]["git"]["head"]
            and result["checks"][
                "postrun_source_and_commit_revalidation_passed"
            ]
        ),
        "claim_boundary_is_synthetic_not_hardware": (
            result["claim_boundary"]["synthetic_cnot"] is True
            and result["claim_boundary"]["real_hardware"] is False
            and result["claim_boundary"]["cesium_specific"] is False
            and result["claim_boundary"]["online_target_certificate"] is False
        ),
    }

    return {
        "schema": "QL1F-attempt50-final-audit-v1",
        "attempt": 50,
        "status": "pass" if all(checks.values()) else "fail",
        "audited_result": RESULT_PATH.relative_to(CORE).as_posix(),
        "audited_result_binary_sha256": binary_sha256(RESULT_PATH),
        "checks": checks,
        "recomputed": {
            "method_success": method_intervals,
            "paired_success_differences": paired_intervals,
            "cost_ratios": {
                "query": query_ratio,
                "shots": shot_ratio,
            },
            "safety": {
                "accepted_nonzero_steps": accepted,
                "destructive_accepted_steps": destructive,
                "one_sided_95pct_clopper_pearson_upper": (
                    destructive_upper
                ),
            },
            "gates": recomputed_gates,
        },
        "source_seal_matches": source_seal_matches,
        "result_source_matches": result_source_matches,
        "artifact_matches": artifact_matches,
        "known_evidence_boundaries": {
            "aggregate_ledger_only": {
                "severity": "P1-auditability-not-performance",
                "description": (
                    "The immutable formal result stores aggregate ledger "
                    "closure, purpose totals, and a canonical ledger hash, "
                    "but not every query row. Aggregate costs are independently "
                    "reproducible; the stored row hash cannot be reconstructed "
                    "from the compact result alone."
                ),
                "mitigation": (
                    "Attempt-50 MWE retains complete query-ledger rows."
                ),
            },
            "drift_control_map_metadata": {
                "severity": "P2-label-semantics",
                "affected_run_count": len(metadata_drift_rows),
                "description": (
                    "For drift-only truths, the metadata field named "
                    "control_map_minus_identity_spectral_norm describes a "
                    "sampled candidate map that was not applied. The actual "
                    "applied control-map perturbation is zero. This field does "
                    "not enter simulation, success, bootstrap, or any gate."
                ),
            },
            "statistical_unit": (
                "Twenty-four truth cells; four finite-shot replicates are "
                "nested within each cell and are never treated as 96 "
                "independent samples."
            ),
        },
        "decision": (
            "Attempt-49 PASS independently reproduced"
            if all(checks.values())
            else "Attempt-49 audit failed"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="audit JSON destination",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="run checks without writing an audit artifact",
    )
    args = parser.parse_args()
    result = audit()
    if not args.verify_only:
        atomic_write_json(args.output.resolve(), result)
    print(
        f"attempt50 final audit {result['status']}; "
        f"checks={sum(result['checks'].values())}/{len(result['checks'])}"
    )
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
