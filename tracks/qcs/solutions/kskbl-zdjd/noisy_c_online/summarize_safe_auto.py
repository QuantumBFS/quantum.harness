"""Summarize the conservative upper-bound automatic correlation diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--independent", action="append", type=Path, required=True)
    parser.add_argument("--correlated", action="append", type=Path, required=True)
    parser.add_argument("--point-summary", type=Path, required=True)
    parser.add_argument("--learned-network", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--output-figure", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_run(directory: Path) -> dict[str, Any]:
    path = directory / "run.json"
    run = json.loads(path.read_text(encoding="utf-8"))
    run["_path"] = path.as_posix()
    run["_sha256"] = sha256(path)
    return run


def signature(stage: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            (int(row["mask"]), int(row["coefficient"]))
            for row in stage["final_integer_coefficients"]
            if int(row["coefficient"]) != 0
        )
    )


def validate(
    independent: list[dict[str, Any]],
    correlated: list[dict[str, Any]],
    network: dict[str, Any],
) -> None:
    if len(independent) != 6 or len(correlated) != 6:
        raise ValueError("expected six runs per noise family")
    expected_signature = tuple(
        sorted(
            (int(row["mask"]), int(row["coefficient"]))
            for row in network["active_features"]
        )
    )
    for mode, runs in (
        ("independent", independent),
        ("common-xor", correlated),
    ):
        for run in runs:
            config = run["config"]
            if config["noise_mode"] != mode:
                raise ValueError("noise mode mismatch")
            if config["noise_confidence_unit"] != "auto":
                raise ValueError("run is not automatic")
            if config["auto_correlation_decision"] != "upper-bound":
                raise ValueError("run does not use the safe upper bound")
            if run["accepted_degree"] != 2:
                raise ValueError("a run did not accept degree two")
            if run["final_clean_metrics"]["word_accuracy"] != 1.0:
                raise ValueError("a run is not exact")
            if signature(run["stages"][-1]) != expected_signature:
                raise ValueError("a run recovered a different rule")
            for stage in run["stages"]:
                for check in stage["checks"]:
                    if check["noise_confidence_unit_selected"] != "word":
                        raise ValueError("safe rule unexpectedly switched to bit")
            verification = run["verification"]
            if verification["clean_labels_used_for_degree_selection"]:
                raise ValueError("clean labels leaked into selection")


def compact(run: dict[str, Any]) -> dict[str, Any]:
    accepted = run["stages"][-1]["checks"][-1]
    return {
        "path": run["_path"],
        "run_sha256": run["_sha256"],
        "base_seed": int(run["config"]["base_seed"]),
        "selected_unit_at_acceptance": accepted[
            "noise_confidence_unit_selected"
        ],
        "design_effect_point_at_acceptance": float(
            accepted["estimated_bitwise_design_effect"]
        ),
        "design_effect_upper_bound_at_acceptance": float(
            accepted["bitwise_design_effect_upper_bound"]
        ),
        "accept_step": int(accepted["stage_step"]),
        "training_examples": int(run["cumulative_training_examples"]),
        "holdout_words": int(run["cumulative_holdout_words"]),
        "total_noisy_oracle_words": int(
            run["cumulative_noisy_oracle_words"]
        ),
        "final_clean_word_accuracy": float(
            run["final_clean_metrics"]["word_accuracy"]
        ),
    }


def plot(
    independent: list[dict[str, Any]],
    correlated: list[dict[str, Any]],
    point_summary: dict[str, Any],
    threshold: float,
    output: Path,
) -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.7))
    for index, (label, rows, color) in enumerate(
        (
            ("independent", independent, "#075985"),
            ("correlated", correlated, "#c2415d"),
        )
    ):
        x = np.full(len(rows), index)
        points = [row["design_effect_point_at_acceptance"] for row in rows]
        uppers = [
            row["design_effect_upper_bound_at_acceptance"] for row in rows
        ]
        axes[0].scatter(x - 0.10, points, color=color, s=36, label=(
            "point estimate" if index == 0 else None
        ))
        axes[0].scatter(
            x + 0.10,
            uppers,
            facecolor="white",
            edgecolor=color,
            s=40,
            label="confidence upper bound" if index == 0 else None,
        )
        for point, upper in zip(points, uppers, strict=True):
            axes[0].plot(
                [index - 0.10, index + 0.10],
                [point, upper],
                color=color,
                alpha=0.35,
                linewidth=1,
            )
    axes[0].axhline(threshold, color="#666666", linestyle="--", linewidth=1)
    axes[0].set_xticks([0, 1], ["independent", "correlated"])
    axes[0].set_ylabel("12-bit design effect")
    axes[0].set_title("A valid upper bound is much more conservative")
    axes[0].grid(True, axis="y", alpha=0.2)
    axes[0].legend(frameon=False, fontsize=8)

    point_claims = point_summary["claims"]
    choice_data = np.array([[8, 0], [0, 8], [0, 6], [0, 6]])
    labels = [
        "point\nindependent",
        "point\ncorrelated",
        "upper\nindependent",
        "upper\ncorrelated",
    ]
    x = np.arange(4)
    axes[1].bar(
        x,
        choice_data[:, 0],
        color="#075985",
        label="choose bit",
    )
    axes[1].bar(
        x,
        choice_data[:, 1],
        bottom=choice_data[:, 0],
        color="#f1b24a",
        label="remain word-cluster",
    )
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("runs")
    axes[1].set_ylim(0, 9)
    axes[1].set_title("Safety removes the independent-noise switch")
    axes[1].grid(True, axis="y", alpha=0.2)
    axes[1].legend(frameon=False, fontsize=8)

    point_costs = [
        point_claims["independent_mean_total_noisy_words"],
        point_claims["correlated_mean_total_noisy_words"],
    ]
    safe_costs = [
        np.mean([row["total_noisy_oracle_words"] for row in independent]),
        np.mean([row["total_noisy_oracle_words"] for row in correlated]),
    ]
    x = np.arange(2)
    width = 0.36
    axes[2].bar(
        x - width / 2,
        point_costs,
        width,
        color="#08745a",
        label="point threshold",
    )
    axes[2].bar(
        x + width / 2,
        safe_costs,
        width,
        color="#7c3aed",
        label="upper-bound rule",
    )
    axes[2].set_xticks(x, ["independent", "correlated"])
    axes[2].set_ylabel("mean total noisy oracle words")
    axes[2].set_title("Formal caution has a measurable cost")
    axes[2].grid(True, axis="y", alpha=0.2)
    axes[2].legend(frameon=False, fontsize=8)

    fig.suptitle(
        "A confidence-safe switch is correct but currently too conservative",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    independent_runs = [load_run(path) for path in args.independent]
    correlated_runs = [load_run(path) for path in args.correlated]
    point_summary = json.loads(args.point_summary.read_text(encoding="utf-8"))
    network = json.loads(args.learned_network.read_text(encoding="utf-8"))
    validate(independent_runs, correlated_runs, network)
    independent = [compact(run) for run in independent_runs]
    correlated = [compact(run) for run in correlated_runs]
    threshold = float(
        independent_runs[0]["config"][
            "auto_correlation_design_effect_threshold"
        ]
    )
    independent_points = [
        row["design_effect_point_at_acceptance"] for row in independent
    ]
    independent_uppers = [
        row["design_effect_upper_bound_at_acceptance"]
        for row in independent
    ]
    correlated_points = [
        row["design_effect_point_at_acceptance"] for row in correlated
    ]
    correlated_uppers = [
        row["design_effect_upper_bound_at_acceptance"]
        for row in correlated
    ]
    point_independent_cost = float(
        point_summary["claims"]["independent_mean_total_noisy_words"]
    )
    safe_independent_cost = float(
        np.mean(
            [row["total_noisy_oracle_words"] for row in independent]
        )
    )
    summary = {
        "kind": "confidence-upper-bound-auto-correlation-guardrail",
        "protocol": {
            "design_effect_switch_threshold": threshold,
            "safe_switch_rule": (
                "use bitwise uncertainty only if a bounded empirical-"
                "Bernstein design-effect upper bound is below threshold"
            ),
            "clean_labels_used_for_updates_or_selection": False,
            "interpretation": (
                "negative efficiency result retained as a guardrail"
            ),
        },
        "claims": {
            "all_12_runs_remain_word_cluster": True,
            "all_12_runs_select_quadratic": True,
            "all_12_final_models_exact": True,
            "all_12_recover_verified_36_term_156_gate_rule": True,
            "independent_mean_point_design_effect": float(
                np.mean(independent_points)
            ),
            "independent_upper_bound_range": [
                float(np.min(independent_uppers)),
                float(np.max(independent_uppers)),
            ],
            "correlated_mean_point_design_effect": float(
                np.mean(correlated_points)
            ),
            "correlated_upper_bound_range": [
                float(np.min(correlated_uppers)),
                float(np.max(correlated_uppers)),
            ],
            "point_auto_independent_mean_total_noisy_words": (
                point_independent_cost
            ),
            "safe_auto_independent_mean_total_noisy_words": (
                safe_independent_cost
            ),
            "safe_auto_independent_cost_factor": (
                safe_independent_cost / point_independent_cost
            ),
            "safe_auto_correlated_mean_total_noisy_words": float(
                np.mean(
                    [
                        row["total_noisy_oracle_words"]
                        for row in correlated
                    ]
                )
            ),
        },
        "independent_runs": independent,
        "correlated_runs": correlated,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    plot(
        independent,
        correlated,
        point_summary,
        threshold,
        args.output_figure,
    )
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
