#!/usr/bin/env python3
"""Build the Challenge-113 queries-to-target deliverable from sealed results.

No simulator is imported and no scientific query is made.  The development
panel reads the Attempt-44 truth-cell summaries.  The confirmation panel
reconstructs a restricted-mean, post-hoc oracle-scored query count from the
immutable Attempt-49 runs: successful replicates are charged at the first
accepted pulse whose exact post-hoc score reaches the target, while failures
are charged the complete frozen query cap.

This quantity answers the challenge's benchmark question, but it is not a
deployable online stopping rule.  Attempt 43's failed online certificate
remains a retained negative result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORE = HERE.parent
DEVELOPMENT_PATH = (
    CORE / "results_summary" / "QL1F-attempt44-dimension-cost.json"
)
CONFIRMATION_PATH = (
    CORE / "results_summary" / "QL1F-attempt49-fresh-confirmation.json"
)
CONFIG_PATH = HERE / "attempt49_fresh_confirmation_config.json"
OUTPUT_PATH = (
    CORE / "results_summary" / "QL1F-attempt51-queries-to-target.json"
)
PLOT_PNG = CORE / "plots" / "attempt51-queries-to-target.png"
PLOT_SVG = CORE / "plots" / "attempt51-queries-to-target.svg"
REPORT_PATH = CORE / "docs" / "ATTEMPT51_DELIVERABLE_REPORT.md"

FAMILIES = ("control-map", "drift", "combined")
DEVELOPMENT_METHODS = (
    "model-informed-k5",
    "model-informed-k10",
    "model-informed-k15",
    "model-informed-k20",
    "model-informed-k40",
)
CONFIRMATION_METHODS = (
    "model-informed-k15",
    "model-informed-k40",
    "raw-coordinate-global-40",
)


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


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        text.rstrip() + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def normalize_generated_svg(path: Path) -> None:
    """Remove Matplotlib's path-line trailing spaces deterministically."""
    text = path.read_text(encoding="utf-8")
    normalized = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    path.write_text(normalized, encoding="utf-8", newline="\n")


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
                f"expected eight {family} confirmation cells, found "
                f"{len(group)}"
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


def confirmation_truth_rows(
    np: Any,
    runs: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[(run["method"], run["selected_cell"])].append(run)

    output: dict[str, list[dict[str, Any]]] = {
        method: [] for method in CONFIRMATION_METHODS
    }
    for method in CONFIRMATION_METHODS:
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
            restricted_queries: list[int] = []
            restricted_shots: list[int] = []
            successes: list[bool] = []
            for run in rows:
                scan = run["scan"]
                success = bool(scan["oracle_scored_success"])
                first = scan["oracle_scored_first_accepted_to_target"]
                if success:
                    if first is None:
                        raise RuntimeError(
                            "successful run is missing its oracle first hit"
                        )
                    queries = int(first["queries"])
                    shots = int(first["shots"])
                else:
                    if first is not None:
                        raise RuntimeError(
                            "failed run unexpectedly has an oracle first hit"
                        )
                    queries = int(scan["query_cap"])
                    shots = int(scan["shot_cap"])
                if queries > int(scan["query_cap"]):
                    raise RuntimeError("first-hit query exceeds frozen cap")
                if shots > int(scan["shot_cap"]):
                    raise RuntimeError("first-hit shots exceed frozen cap")
                restricted_queries.append(queries)
                restricted_shots.append(shots)
                successes.append(success)

            output[method].append(
                {
                    "selected_cell": selected_cell,
                    "family": rows[0]["family"],
                    "truth_seed": int(rows[0]["truth_seed"]),
                    "nested_replicates": len(rows),
                    "oracle_scored_success": float(np.mean(successes)),
                    "restricted_mean_queries_to_target": float(
                        np.mean(restricted_queries)
                    ),
                    "restricted_mean_shots_to_target": float(
                        np.mean(restricted_shots)
                    ),
                }
            )
    return output


def development_summary(
    development: dict[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for method in DEVELOPMENT_METHODS:
        record = development["summary"]["methods"][method]
        metrics = record["metrics"]
        rows = record["truth_level_rows"]
        query_values = [
            float(row["oracle_first_hit_queries"]) for row in rows
        ]
        shot_values = [
            float(row["oracle_first_hit_shots"]) for row in rows
        ]
        success_values = [
            float(row["oracle_scored_success"]) for row in rows
        ]
        for values, metric_name in (
            (query_values, "oracle_first_hit_queries"),
            (shot_values, "oracle_first_hit_shots"),
            (success_values, "oracle_scored_success"),
        ):
            if not math.isclose(
                sum(values) / len(values),
                float(metrics[metric_name]["estimate"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise RuntimeError(
                    f"Attempt-44 {method} {metric_name} mean mismatch"
                )
        output.append(
            {
                "method": method,
                "search_dimension": int(record["search_dimension"]),
                "independent_truth_cells": len(rows),
                "queries_to_target": metrics["oracle_first_hit_queries"],
                "shots_to_target": metrics["oracle_first_hit_shots"],
                "oracle_scored_success": metrics[
                    "oracle_scored_success"
                ],
                "semantics": (
                    "development; post-hoc oracle first accepted hit; "
                    "failures charged full cap"
                ),
            }
        )
    return output


def confirmation_summary(
    np: Any,
    confirmation: dict[str, Any],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    runs = confirmation["runs"]
    rows = confirmation_truth_rows(np, runs)
    indices = bootstrap_indices(
        np,
        rows[CONFIRMATION_METHODS[0]],
        draws=int(config["bootstrap"]["draws"]),
        seed=int(config["bootstrap"]["seed"]),
    )
    output: list[dict[str, Any]] = []
    success_matches: dict[str, bool] = {}
    for method in CONFIRMATION_METHODS:
        query_values = np.asarray(
            [
                row["restricted_mean_queries_to_target"]
                for row in rows[method]
            ],
            dtype=float,
        )
        shot_values = np.asarray(
            [
                row["restricted_mean_shots_to_target"]
                for row in rows[method]
            ],
            dtype=float,
        )
        success_values = np.asarray(
            [row["oracle_scored_success"] for row in rows[method]],
            dtype=float,
        )
        success = interval(np, success_values, indices)
        recorded_success = confirmation["summary"]["methods"][method][
            "success"
        ]
        success_matches[method] = same_interval(
            success, recorded_success
        )
        output.append(
            {
                "method": method,
                "search_dimension": int(
                    next(
                        run["search_dimension"]
                        for run in runs
                        if run["method"] == method
                    )
                ),
                "independent_truth_cells": len(rows[method]),
                "nested_replicates_per_cell": 4,
                "queries_to_target": interval(
                    np, query_values, indices
                ),
                "shots_to_target": interval(np, shot_values, indices),
                "oracle_scored_success": success,
                "truth_level_rows": rows[method],
                "semantics": (
                    "fresh confirmation; post-hoc oracle first accepted hit; "
                    "failures charged full cap"
                ),
            }
        )
    return output, success_matches


def make_plot(
    plt: Any,
    np: Any,
    development: list[dict[str, Any]],
    confirmation: list[dict[str, Any]],
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.4, 4.9))
    green = "#00796B"
    gray = "#6B7280"
    orange = "#B45F06"
    red = "#A51C30"

    dev_x = np.asarray(
        [row["search_dimension"] for row in development], dtype=float
    )
    dev_y = np.asarray(
        [row["queries_to_target"]["estimate"] for row in development],
        dtype=float,
    )
    dev_low = np.asarray(
        [row["queries_to_target"]["lower_95"] for row in development],
        dtype=float,
    )
    dev_high = np.asarray(
        [row["queries_to_target"]["upper_95"] for row in development],
        dtype=float,
    )
    colors = [green if int(value) == 15 else gray for value in dev_x]
    axes[0].plot(dev_x, dev_y, color=gray, linewidth=1.4, alpha=0.75)
    axes[0].errorbar(
        dev_x,
        dev_y,
        yerr=np.vstack((dev_y - dev_low, dev_high - dev_y)),
        fmt="none",
        ecolor=gray,
        elinewidth=1.3,
        capsize=3,
    )
    axes[0].scatter(dev_x, dev_y, c=colors, s=62, zorder=3)
    for row, x, y in zip(development, dev_x, dev_y):
        success = 100.0 * float(
            row["oracle_scored_success"]["estimate"]
        )
        axes[0].annotate(
            f"{success:.0f}%",
            (x, y),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8.5,
        )
    axes[0].axvline(15, color=green, linestyle="--", linewidth=1.0)
    axes[0].set_xlabel("Model-informed search dimension k")
    axes[0].set_ylabel("Restricted-mean queries to target")
    axes[0].set_title("Development dimension sweep")
    axes[0].grid(alpha=0.22)

    labels = ["model k=15", "completed k=40", "raw k=40"]
    x = np.asarray([0.0, 1.0, 2.0])
    y = np.asarray(
        [row["queries_to_target"]["estimate"] for row in confirmation],
        dtype=float,
    )
    low = np.asarray(
        [row["queries_to_target"]["lower_95"] for row in confirmation],
        dtype=float,
    )
    high = np.asarray(
        [row["queries_to_target"]["upper_95"] for row in confirmation],
        dtype=float,
    )
    bar_colors = [green, gray, orange]
    axes[1].bar(x, y, color=bar_colors, width=0.68)
    axes[1].errorbar(
        x,
        y,
        yerr=np.vstack((y - low, high - y)),
        fmt="none",
        ecolor="#222222",
        elinewidth=1.3,
        capsize=4,
    )
    for row, xpos, value in zip(confirmation, x, y):
        success = 100.0 * float(
            row["oracle_scored_success"]["estimate"]
        )
        axes[1].annotate(
            f"{success:.1f}% success",
            (xpos, value),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8.5,
        )
    axes[1].set_xticks(x, labels, rotation=12, ha="right")
    axes[1].set_ylabel("Restricted-mean queries to target")
    axes[1].set_title("Preregistered fresh confirmation")
    axes[1].grid(axis="y", alpha=0.22)

    figure.suptitle(
        "Queries to 1 − F ≤ 10⁻³ versus search dimension",
        fontsize=13,
    )
    figure.text(
        0.5,
        -0.015,
        (
            "Post-hoc exact scoring; failures charged the frozen full cap. "
            "This is a benchmark metric, not an online stopping certificate."
        ),
        ha="center",
        color=red,
        fontsize=9,
    )
    figure.tight_layout()
    PLOT_PNG.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(PLOT_PNG, dpi=190, bbox_inches="tight")
    figure.savefig(PLOT_SVG, bbox_inches="tight")
    plt.close(figure)
    normalize_generated_svg(PLOT_SVG)


def build_report(payload: dict[str, Any]) -> str:
    formal = {
        row["method"]: row for row in payload["confirmation"]
    }
    return f"""# Attempt 51 — queries-to-target deliverable

## Purpose

Challenge 113 explicitly requests queries-to-target versus search dimension.
This deliverable derives that figure from sealed Attempt-44 development and
Attempt-49 confirmation evidence. It makes no new simulator or device query,
does not tune a method, and does not alter either archived result.

## Metric

For each finite-shot run:

- if an accepted pulse first reaches exact post-hoc infidelity `<= 1e-3`, use
  the number of black-box queries and shots consumed at that accepted step;
- otherwise charge the complete frozen query and shot cap;
- average four nested shot-noise replicates within each truth cell; and
- compute a family-stratified truth-cell bootstrap interval.

This is a restricted-mean, post-hoc oracle-scored benchmark metric. It is not
available to the optimizer online. Attempt 43's online stopping certificate
failed and remains a negative result.

## Fresh confirmation values

| Method | Search dimension | Queries to target (95% CI) | Shots to target | Success |
|---|---:|---:|---:|---:|
| model-informed `k=15` | 15 | {formal["model-informed-k15"]["queries_to_target"]["estimate"]:.2f} [{formal["model-informed-k15"]["queries_to_target"]["lower_95"]:.2f}, {formal["model-informed-k15"]["queries_to_target"]["upper_95"]:.2f}] | {formal["model-informed-k15"]["shots_to_target"]["estimate"]:,.0f} | {100.0 * formal["model-informed-k15"]["oracle_scored_success"]["estimate"]:.3f}% |
| completed model-informed `k=40` | 40 | {formal["model-informed-k40"]["queries_to_target"]["estimate"]:.2f} [{formal["model-informed-k40"]["queries_to_target"]["lower_95"]:.2f}, {formal["model-informed-k40"]["queries_to_target"]["upper_95"]:.2f}] | {formal["model-informed-k40"]["shots_to_target"]["estimate"]:,.0f} | {100.0 * formal["model-informed-k40"]["oracle_scored_success"]["estimate"]:.3f}% |
| raw-coordinate `k=40` | 40 | {formal["raw-coordinate-global-40"]["queries_to_target"]["estimate"]:.2f} [{formal["raw-coordinate-global-40"]["queries_to_target"]["lower_95"]:.2f}, {formal["raw-coordinate-global-40"]["queries_to_target"]["upper_95"]:.2f}] | {formal["raw-coordinate-global-40"]["shots_to_target"]["estimate"]:,.0f} | {100.0 * formal["raw-coordinate-global-40"]["oracle_scored_success"]["estimate"]:.3f}% |

The development panel supplies the requested dimension sweep over
`k = 5, 10, 15, 20, 40`; the confirmation panel tests the selected `k=15`
method against the two frozen `k=40` comparators on fresh truths.

## Claim boundary

- Development selects the dimension; it is not confirmation evidence.
- Confirmation uses 24 independent truth cells with four nested replicates.
- Hidden exact values are attached only after each calibration client closes.
- The online stopping rule did not pass and is not revived by this plot.
- Failures remain in the metric at their complete frozen cap.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="recompute checks and statistics without writing artifacts",
    )
    args = parser.parse_args()

    import matplotlib
    import numpy as np

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    development_result = load_json(DEVELOPMENT_PATH)
    confirmation_result = load_json(CONFIRMATION_PATH)
    config = load_json(CONFIG_PATH)

    development = development_summary(development_result)
    confirmation, success_matches = confirmation_summary(
        np, confirmation_result, config
    )
    runs = confirmation_result["runs"]
    checks = {
        "development_status_complete": (
            development_result.get("status") == "complete"
        ),
        "development_dimensions_exact": (
            [row["search_dimension"] for row in development]
            == [5, 10, 15, 20, 40]
        ),
        "development_has_21_truth_cells_each": all(
            row["independent_truth_cells"] == 21 for row in development
        ),
        "confirmation_status_complete": (
            confirmation_result.get("status") == "complete"
            and confirmation_result.get("confirmation_decision") == "pass"
        ),
        "confirmation_grid_288_without_exception": (
            len(runs) == 288
            and all(run["exception"] is None for run in runs)
        ),
        "confirmation_has_24_truth_cells_each": all(
            row["independent_truth_cells"] == 24 for row in confirmation
        ),
        "confirmation_four_nested_replicates": all(
            all(
                truth["nested_replicates"] == 4
                for truth in row["truth_level_rows"]
            )
            for row in confirmation
        ),
        "first_hit_present_if_and_only_if_success": all(
            bool(run["scan"]["oracle_scored_success"])
            == (
                run["scan"][
                    "oracle_scored_first_accepted_to_target"
                ]
                is not None
            )
            for run in runs
        ),
        "recomputed_success_intervals_match_formal_summary": all(
            success_matches.values()
        ),
        "all_statistics_finite": finite_tree(
            {"development": development, "confirmation": confirmation}
        ),
        "online_certificate_not_relabelled": (
            development_result["summary"]["cost_semantics"]["headline"]
            == "full-cap-online"
            and "not deployable"
            in development_result["summary"]["cost_semantics"][
                "oracle_scored_first_hit"
            ]
            and "post-hoc"
            in confirmation_result["summary"]["success_scoring"]
            and confirmation_result["summary"]["cost_semantics"]
            == "deterministic full-cap online"
        ),
    }
    payload: dict[str, Any] = {
        "schema": "challenge113-queries-to-target-v1",
        "status": "pass" if all(checks.values()) else "fail",
        "title": "Queries to target versus search dimension",
        "target_infidelity": 1e-3,
        "metric": {
            "name": (
                "restricted-mean post-hoc oracle-scored first accepted hit"
            ),
            "failure_charge": "complete frozen query and shot cap",
            "independent_unit": "truth cell",
            "nested_replicates": 4,
            "bootstrap": config["bootstrap"],
            "online_stopping_rule": False,
        },
        "development": development,
        "confirmation": confirmation,
        "checks": checks,
        "inputs": {
            "development_result": {
                "path": DEVELOPMENT_PATH.relative_to(CORE).as_posix(),
                "canonical_sha256": canonical_sha256(DEVELOPMENT_PATH),
            },
            "confirmation_result": {
                "path": CONFIRMATION_PATH.relative_to(CORE).as_posix(),
                "binary_sha256": binary_sha256(CONFIRMATION_PATH),
            },
            "confirmation_config": {
                "path": CONFIG_PATH.relative_to(CORE).as_posix(),
                "canonical_sha256": canonical_sha256(CONFIG_PATH),
            },
        },
        "claim_boundary": [
            "The development dimension sweep is not confirmation evidence.",
            "The confirmation truths are now public.",
            "Exact scores are post-hoc and never enter calibration.",
            "This metric is not a deployable online stopping rule.",
            "Attempt 43's failed online certificate remains negative.",
        ],
    }
    if not args.verify_only:
        make_plot(plt, np, development, confirmation)
        payload["artifacts"] = {
            "plot_png": {
                "path": PLOT_PNG.relative_to(CORE).as_posix(),
                "binary_sha256": binary_sha256(PLOT_PNG),
            },
            "plot_svg": {
                "path": PLOT_SVG.relative_to(CORE).as_posix(),
                "canonical_sha256": canonical_sha256(PLOT_SVG),
            },
            "report": {
                "path": REPORT_PATH.relative_to(CORE).as_posix(),
            },
        }
        atomic_write_text(REPORT_PATH, build_report(payload))
        payload["artifacts"]["report"]["canonical_sha256"] = (
            canonical_sha256(REPORT_PATH)
        )
        atomic_write_json(OUTPUT_PATH, payload)

    print(
        f"attempt51 queries-to-target {payload['status']}; "
        f"checks={sum(checks.values())}/{len(checks)}"
    )
    if payload["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
