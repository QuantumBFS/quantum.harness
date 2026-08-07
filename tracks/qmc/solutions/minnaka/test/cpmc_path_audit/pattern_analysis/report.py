"""Evidence-gated Markdown report for the CPMC path-pattern audit."""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd


def write_pattern_report(
    *,
    selection_summary: pd.DataFrame,
    path_summaries: pd.DataFrame,
    predicted_masks: pd.DataFrame,
    slice_motifs: pd.DataFrame,
    counterfactual: pd.DataFrame,
    model_metrics: pd.DataFrame,
    output: pathlib.Path | str,
    command: str,
) -> pathlib.Path:
    destination = pathlib.Path(output)
    lines = [
        "# CPMC Important Under-Sampled Path Pattern Report",
        "",
        "## Exact selection",
        "",
        "| Trial | Worst 1% | D/⟨D⟩<0.5 | 0.5–1 | 1–2 | ≥2 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in selection_summary.itertuples():
        lines.append(
            f"| {row.trial} | {row.worst_count} | {row.below_half} | "
            f"{row.near_average} | {row.important} | "
            f"{row.strongly_important} |"
        )

    lines.extend(["", "## Stepwise mechanisms", ""])
    if len(path_summaries):
        mechanism = (
            path_summaries.groupby(["trial", "mechanism"])
            .size()
            .rename("count")
            .reset_index()
        )
        for trial, group in mechanism.groupby("trial"):
            total = int(group["count"].sum())
            leading = group.loc[group["count"].idxmax()]
            near = path_summaries.loc[
                path_summaries["trial"] == trial, "near_orthogonal"
            ].mean()
            trial_paths = path_summaries.loc[
                path_summaries["trial"] == trial
            ]
            lines.append(
                f"- {trial}: leading attribution "
                f"`{leading.mechanism}` ({leading['count']}/{total}); "
                f"{near:.3f} contain an event below the matched-control "
                f"1% subspace-overlap band. Median min-q event "
                f"{trial_paths.min_q_step.median():.0f}, median detrended "
                f"W minimum {trial_paths.detrended_min_step.median():.0f}, "
                f"median recovery {trial_paths.recovery_step.median():.0f}."
            )
            if "min_q_predicted_low_match" in trial_paths:
                lines.append(
                    f"  The minimum-q branch matches the one-body "
                    f"lower-overlap prediction in "
                    f"{trial_paths.min_q_predicted_low_match.mean():.3f}; "
                    f"median q={trial_paths.minimum_q_selected.median():.3g}, "
                    f"while the largest later W increment has median "
                    f"Δlog W="
                    f"{trial_paths.max_recovery_delta_log_w.median():.3g}."
                )
    else:
        lines.append("- No physically important case paths were selected.")

    if len(predicted_masks) and "onset_realized_rank" in predicted_masks:
        ranks = pd.to_numeric(
            predicted_masks["onset_realized_rank"], errors="coerce"
        )
        finite = ranks[np.isfinite(ranks)]
        if len(finite):
            lines.append(
                f"- Among the {len(finite)} paths that cross the "
                f"matched-control low-W band, the onset mask is the "
                f"one-body most-orthogonal prediction in "
                f"{float((finite == 1).mean()):.3f} of cases; median rank "
                f"{float(finite.median()):.2f}/16."
            )

    lines.extend(["", "## Auxiliary-field patterns", ""])
    candidates = slice_motifs.loc[
        (slice_motifs["comparison"] == "all_relevant")
        & (slice_motifs["case_count"] >= 10)
        & (slice_motifs["control_count"] >= 10)
        & (slice_motifs["q_value"] < 0.05)
        & np.isfinite(slice_motifs["odds_ratio"])
    ].copy()
    if len(candidates):
        for trial, group in candidates.groupby("trial", sort=False):
            enriched = group.loc[group["odds_ratio"] > 1.0].nlargest(
                1, "risk_difference"
            )
            depleted = group.loc[group["odds_ratio"] < 1.0].nsmallest(
                1, "risk_difference"
            )
            for direction, row in (
                ("enriched", enriched),
                ("depleted", depleted),
            ):
                if row.empty:
                    continue
                item = row.iloc[0]
                lines.append(
                    f"- {trial} {direction} `{item.mask_class}`: "
                    f"OR={item.odds_ratio:.3g}, support "
                    f"{item.case_support:.3f} vs "
                    f"{item.control_support:.3f}, BH q="
                    f"{item.q_value:.3g}."
                )
    else:
        lines.append("- No slice motif passed the minimum support filter.")

    lines.extend(["", "## M=4 proposal counterfactual", ""])
    for trial, group in counterfactual.groupby("trial"):
        if "relevant_worst_1pct" in group:
            group = group.loc[group["relevant_worst_1pct"]]
        if group.empty:
            lines.append(f"- {trial}: no relevant worst-tail paths.")
            continue
        lines.append(
            f"- {trial}, relevant worst-tail n={len(group)}: median score "
            f"reduction, reverse "
            f"{group.score_improvement_reverse.median():.3g}, "
            f"A-then-B {group.score_improvement_sublattice.median():.3g}, "
            f"joint-slice {group.score_improvement_joint.median():.3g}."
        )

    lines.extend(["", "## Held-out predictive checks", ""])
    if len(model_metrics):
        grouped = (
            model_metrics.groupby(["trial", "feature_set", "model"])[
                ["roc_auc", "pr_auc"]
            ]
            .mean()
            .reset_index()
        )
        for row in grouped.loc[
            grouped["feature_set"] == "field_only"
        ].itertuples():
            lines.append(
                f"- {row.trial} field-only {row.model}: "
                f"mean ROC-AUC={row.roc_auc:.3f}, "
                f"PR-AUC={row.pr_auc:.3f}."
            )
        lines.append(
            "- Dynamic Q/W/subspace features are retained as attribution "
            "diagnostics, not interpreted as field-only predictors because "
            "final log W is the target under-sampling quantity."
        )
    else:
        lines.append("- Dataset too small for a class-preserving held-out fold.")

    lines.extend(
        [
            "",
            "## Interpretation rule",
            "",
            "A field motif is called a mechanism only when matched enrichment, "
            "time-local Q/C/subspace evidence, symmetry replication, and the "
            "relevant M=4 counterfactual agree. The mechanism supported here "
            "is near-orthogonal recovery; the individual slice enrichments "
            "remain correlation patterns unless their time-local evidence is "
            "also established.",
            "",
            "## Reproduce",
            "",
            "```bash",
            command,
            "```",
            "",
            "Figures: [weight/efficiency](figures/weight_vs_efficiency.pdf), "
            "[trajectories](figures/matched_weight_trajectories.pdf), "
            "[event heatmap](figures/event_attribution_heatmap.pdf), "
            "[principal angles](figures/principal_angle_trajectories.pdf), "
            "[motifs](figures/motif_enrichment.pdf), "
            "[M=4 counterfactual](figures/m4_counterfactual.pdf).",
        ]
    )
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination
