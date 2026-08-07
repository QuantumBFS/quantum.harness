"""Summarize automatic selection of bitwise versus word-cluster uncertainty."""

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
    if len(independent) != 8 or len(correlated) != 8:
        raise ValueError("expected eight runs per noise family")
    expected_signature = tuple(
        sorted(
            (int(row["mask"]), int(row["coefficient"]))
            for row in network["active_features"]
        )
    )
    for mode, expected_unit, runs in (
        ("independent", "bit", independent),
        ("common-xor", "word", correlated),
    ):
        for run in runs:
            config = run["config"]
            if config["noise_mode"] != mode:
                raise ValueError("noise mode mismatch")
            if config["noise_confidence_unit"] != "auto":
                raise ValueError("run is not in automatic mode")
            if run["accepted_degree"] != 2:
                raise ValueError("a run did not accept degree two")
            if run["final_clean_metrics"]["word_accuracy"] != 1.0:
                raise ValueError("a final model is not exact")
            if signature(run["stages"][-1]) != expected_signature:
                raise ValueError("a run recovered a different rule")
            for stage in run["stages"]:
                for check in stage["checks"]:
                    if (
                        check["noise_confidence_unit_selected"]
                        != expected_unit
                    ):
                        raise ValueError(
                            "automatic unit selection was inconsistent"
                        )
            verification = run["verification"]
            if verification["clean_labels_used_for_degree_selection"]:
                raise ValueError("clean labels leaked into selection")
            if verification["target_formula_seeded"]:
                raise ValueError("target formula was seeded")


def compact(run: dict[str, Any]) -> dict[str, Any]:
    accepted = run["stages"][-1]["checks"][-1]
    first = run["stages"][0]["checks"][0]
    return {
        "path": run["_path"],
        "run_sha256": run["_sha256"],
        "base_seed": int(run["config"]["base_seed"]),
        "selected_unit_at_first_recorded_check": first[
            "noise_confidence_unit_selected"
        ],
        "design_effect_at_first_recorded_check": float(
            first["estimated_bitwise_design_effect"]
        ),
        "selected_unit_at_acceptance": accepted[
            "noise_confidence_unit_selected"
        ],
        "design_effect_at_acceptance": float(
            accepted["estimated_bitwise_design_effect"]
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
    fig, axes = plt.subplots(1, 3, figsize=(13.3, 3.7))
    colors = {"independent": "#075985", "correlated": "#c2415d"}
    for label, rows in (
        ("independent", independent),
        ("correlated", correlated),
    ):
        axes[0].scatter(
            [row["design_effect_at_first_recorded_check"] for row in rows],
            [row["design_effect_at_acceptance"] for row in rows],
            s=48,
            color=colors[label],
            edgecolor="white",
            linewidth=0.7,
            label=label,
        )
    axes[0].axvline(threshold, color="#666666", linestyle="--", linewidth=1)
    axes[0].axhline(threshold, color="#666666", linestyle="--", linewidth=1)
    axes[0].set_xlabel("design effect at first degree check")
    axes[0].set_ylabel("design effect at acceptance")
    axes[0].set_title("Correlation is identified before selection")
    axes[0].grid(True, alpha=0.2)
    axes[0].legend(frameon=False)

    all_rows = independent + correlated
    x = np.arange(len(all_rows))
    effects = [row["design_effect_at_acceptance"] for row in all_rows]
    bar_colors = [
        colors["independent"] if index < len(independent)
        else colors["correlated"]
        for index in range(len(all_rows))
    ]
    axes[1].bar(x, effects, color=bar_colors)
    axes[1].axhline(
        threshold,
        color="#666666",
        linestyle="--",
        linewidth=1,
        label="automatic switch threshold",
    )
    axes[1].set_xticks(
        [3.5, 11.5],
        ["independent\n8 / 8 choose bit", "correlated\n8 / 8 choose word"],
    )
    axes[1].set_ylabel("estimated 12-bit design effect")
    axes[1].set_title("One threshold selects the uncertainty unit")
    axes[1].grid(True, axis="y", alpha=0.2)
    axes[1].legend(frameon=False, fontsize=8)

    independent_total = [
        row["total_noisy_oracle_words"] for row in independent
    ]
    correlated_total = [
        row["total_noisy_oracle_words"] for row in correlated
    ]
    axes[2].boxplot(
        [independent_total, correlated_total],
        tick_labels=["independent", "correlated"],
        patch_artist=True,
        boxprops={"facecolor": "#eaf6fb", "edgecolor": "#64748b"},
        medianprops={"color": "#075985", "linewidth": 2},
        whiskerprops={"color": "#64748b"},
        capprops={"color": "#64748b"},
    )
    axes[2].scatter(
        np.repeat(1, len(independent_total)),
        independent_total,
        color=colors["independent"],
        s=22,
        alpha=0.75,
    )
    axes[2].scatter(
        np.repeat(2, len(correlated_total)),
        correlated_total,
        color=colors["correlated"],
        s=22,
        alpha=0.75,
    )
    axes[2].set_ylabel("total noisy oracle words")
    axes[2].set_title("Automatic safety preserves the honest cost")
    axes[2].grid(True, axis="y", alpha=0.2)

    fig.suptitle(
        "The learner infers whether bitwise uncertainty is trustworthy",
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
    network = json.loads(args.learned_network.read_text(encoding="utf-8"))
    validate(independent_runs, correlated_runs, network)
    independent = [compact(run) for run in independent_runs]
    correlated = [compact(run) for run in correlated_runs]
    threshold = float(
        independent_runs[0]["config"][
            "auto_correlation_design_effect_threshold"
        ]
    )
    independent_effects = [
        row["design_effect_at_acceptance"] for row in independent
    ]
    correlated_effects = [
        row["design_effect_at_acceptance"] for row in correlated
    ]
    summary = {
        "kind": "automatic-correlation-aware-uncertainty-selection",
        "protocol": {
            "confidence_unit_at_start": (
                "word until at least 250 independent repeated-word pairs"
            ),
            "estimated_design_effect": (
                "12 times variance of word disagreement fraction divided "
                "by d(1-d)"
            ),
            "switch_to_bit_unit_below": threshold,
            "remain_word_cluster_above": threshold,
            "clean_labels_used_for_updates_or_selection": False,
            "target_noise_family_supplied_to_auto_selector": False,
        },
        "claims": {
            "all_16_runs_select_correct_uncertainty_unit_at_every_check": True,
            "all_16_runs_select_quadratic": True,
            "all_16_final_models_exact": True,
            "all_16_recover_verified_36_term_156_gate_rule": True,
            "independent_selected_bit_count": 8,
            "correlated_selected_word_count": 8,
            "independent_mean_design_effect": float(
                np.mean(independent_effects)
            ),
            "independent_design_effect_range": [
                float(np.min(independent_effects)),
                float(np.max(independent_effects)),
            ],
            "correlated_mean_design_effect": float(
                np.mean(correlated_effects)
            ),
            "correlated_design_effect_range": [
                float(np.min(correlated_effects)),
                float(np.max(correlated_effects)),
            ],
            "independent_mean_total_noisy_words": float(
                np.mean(
                    [
                        row["total_noisy_oracle_words"]
                        for row in independent
                    ]
                )
            ),
            "correlated_mean_total_noisy_words": float(
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
    plot(independent, correlated, threshold, args.output_figure)
    print(json.dumps(summary["claims"], indent=2))


if __name__ == "__main__":
    main()
