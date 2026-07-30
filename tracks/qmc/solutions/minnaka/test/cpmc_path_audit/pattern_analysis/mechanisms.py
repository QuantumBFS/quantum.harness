"""Attribute CPMC sampling failures to time-local proposal mechanisms."""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np
import pandas as pd

from .patterns import canonical_mask, site_permutations_2x2


BASELINE_COLUMNS = [
    "cumulative_log_q",
    "cumulative_log_w",
    "log_normalized_overlap",
    "sigma_min",
    "overlap_after",
    "q_selected",
    "c_factor",
]


def summarize_recovery(delta_log_weight: np.ndarray) -> dict[str, float]:
    """Measure whether positive/negative changes concentrate in one event."""

    delta = np.asarray(delta_log_weight, dtype=np.float64)
    finite = delta[np.isfinite(delta)]
    positive = finite[finite > 0.0]
    negative = -finite[finite < 0.0]
    positive_total = float(positive.sum())
    negative_total = float(negative.sum())
    return {
        "positive_total": positive_total,
        "negative_total": negative_total,
        "recovery_concentration": (
            float(positive.max()) / positive_total
            if positive_total > 0.0
            else 0.0
        ),
        "penalty_concentration": (
            float(negative.max()) / negative_total
            if negative_total > 0.0
            else 0.0
        ),
    }


def classify_overlap(
    *,
    min_sigma: float,
    log_scale: float,
    sigma_threshold: float = 1.0e-6,
    scale_threshold: float = -10.0,
) -> str:
    """Absolute classification used for synthetic checks and trace display."""

    if min_sigma < sigma_threshold:
        return "near_orthogonal"
    if log_scale < scale_threshold:
        return "orbital_scale"
    return "regular"


def _control_baselines(events: pd.DataFrame) -> pd.DataFrame:
    controls = events.loc[events["role"] == "control"]
    if controls.empty:
        raise ValueError("event attribution requires matched controls")
    rows = []
    keys = ["trial", "weight_bin", "event_index"]
    for key, group in controls.groupby(keys, sort=True):
        row = dict(zip(keys, key))
        for column in BASELINE_COLUMNS:
            values = group[column].to_numpy(dtype=np.float64)
            finite = values[np.isfinite(values)]
            if len(finite) == 0:
                for suffix in ("q01", "q05", "median", "q95", "mad"):
                    row[f"{column}_{suffix}"] = math.nan
                continue
            median = float(np.median(finite))
            row[f"{column}_q01"] = float(np.quantile(finite, 0.01))
            row[f"{column}_q05"] = float(np.quantile(finite, 0.05))
            row[f"{column}_median"] = median
            row[f"{column}_q95"] = float(np.quantile(finite, 0.95))
            row[f"{column}_mad"] = float(
                np.median(np.abs(finite - median))
            )
        rows.append(row)
    return pd.DataFrame.from_records(rows)


def _first_event(group: pd.DataFrame, condition: np.ndarray) -> int:
    matches = np.flatnonzero(np.asarray(condition, dtype=bool))
    if len(matches) == 0:
        return -1
    return int(group.iloc[int(matches[0])]["event_index"])


def _event_slice(group: pd.DataFrame, event_index: int) -> int:
    if event_index < 0:
        return -1
    row = group.loc[group["event_index"] == event_index]
    if row.empty:
        return -1
    return int(row.iloc[0]["slice"])


def classify_mechanism(summary: Mapping[str, object]) -> str:
    """Apply a deterministic hierarchy to measured path diagnostics."""

    if bool(summary.get("near_orthogonal", False)) and int(
        summary.get("recovery_step", -1)
    ) >= 0:
        return "near_orthogonal_recovery"
    if bool(summary.get("scale_only", False)):
        return "orbital_scale"
    if bool(summary.get("small_q_event", False)) and not bool(
        summary.get("small_c_event", False)
    ):
        return "rare_selected_branch"
    if bool(summary.get("small_c_event", False)):
        return "low_branching_factor"
    if bool(summary.get("half_k_contraction", False)):
        return "half_kinetic_contraction"
    if float(summary.get("recovery_concentration", 0.0)) >= 0.5:
        return "single_event_compensation"
    return "repeated_moderate"


def attribute_events(
    selection: pd.DataFrame, steps: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach control bands and summarize each physically important case."""

    required_metadata = [
        "path_id",
        "trial",
        "role",
        "case_id",
        "weight_bin",
    ]
    missing = [
        column for column in required_metadata if column not in selection
    ]
    if missing:
        raise ValueError(f"selection misses columns: {missing}")
    metadata = selection[required_metadata].drop_duplicates("path_id")
    if len(metadata) != selection["path_id"].nunique():
        raise ValueError("selection path metadata is not unique")
    event_columns = steps.drop(
        columns=[
            column
            for column in ("trial", "role", "case_id", "weight_bin")
            if column in steps
        ]
    )
    events = event_columns.merge(
        metadata, on="path_id", how="left", validate="many_to_one"
    )
    if events["role"].isna().any():
        raise ValueError("step table contains unknown path_id")
    events["sigma_min"] = np.minimum(
        events["sigma_min_up"], events["sigma_min_down"]
    )
    baselines = _control_baselines(events)
    events = events.merge(
        baselines,
        on=["trial", "weight_bin", "event_index"],
        how="left",
        validate="many_to_one",
    )

    paired_columns = [
        "trial",
        "weight_bin",
        "case_id",
        "event_index",
        "cumulative_log_q",
        "cumulative_log_w",
        "sigma_min",
        "log_normalized_overlap",
    ]
    paired = events.loc[
        events["role"] == "control", paired_columns
    ].rename(
        columns={
            "cumulative_log_q": "paired_control_log_q",
            "cumulative_log_w": "paired_control_log_w",
            "sigma_min": "paired_control_sigma_min",
            "log_normalized_overlap": "paired_control_log_overlap",
        }
    )
    if paired.duplicated(
        ["trial", "weight_bin", "case_id", "event_index"]
    ).any():
        raise ValueError("a case has multiple matched control events")
    events = events.merge(
        paired,
        on=["trial", "weight_bin", "case_id", "event_index"],
        how="left",
        validate="many_to_one",
    )
    events["paired_delta_log_q"] = (
        events["cumulative_log_q"] - events["paired_control_log_q"]
    )
    events["paired_delta_log_w"] = (
        events["cumulative_log_w"] - events["paired_control_log_w"]
    )
    events["paired_delta_sigma_min"] = (
        events["sigma_min"] - events["paired_control_sigma_min"]
    )

    summaries = []
    for path_id, group in events.loc[
        events["role"] == "case"
    ].groupby("path_id", sort=True):
        group = group.sort_values("event_index").reset_index(drop=True)
        first_low_q = _first_event(
            group,
            group["cumulative_log_q"].to_numpy()
            < group["cumulative_log_q_q05"].to_numpy(),
        )
        first_low_w = _first_event(
            group,
            group["cumulative_log_w"].to_numpy()
            < group["cumulative_log_w_q05"].to_numpy(),
        )
        site_events = group.loc[group["kind"] == "site"]
        if site_events.empty:
            raise ValueError("site-proposal path contains no site events")
        q_index = int(site_events["q_selected"].astype(float).idxmin())
        c_index = int(site_events["c_factor"].astype(float).idxmin())
        min_q_step = int(group.loc[q_index, "event_index"])
        min_c_step = int(group.loc[c_index, "event_index"])

        cumulative_w = group["cumulative_log_w"].to_numpy(dtype=float)
        fractions = np.arange(1, len(group) + 1, dtype=float) / len(group)
        detrended = cumulative_w - fractions * cumulative_w[-1]
        detrended_position = int(np.nanargmin(detrended))
        detrended_min_step = int(
            group.iloc[detrended_position]["event_index"]
        )
        recovery_positions = np.flatnonzero(
            (np.arange(len(group)) > detrended_position)
            & (detrended >= 0.0)
        )
        recovery_step = (
            int(group.iloc[int(recovery_positions[0])]["event_index"])
            if len(recovery_positions)
            else -1
        )
        after_minimum = group.iloc[detrended_position + 1 :]
        if after_minimum.empty:
            max_recovery_step = -1
        else:
            max_recovery_step = int(
                after_minimum.loc[
                    after_minimum["delta_log_w"].idxmax(),
                    "event_index",
                ]
            )
        recovery = summarize_recovery(
            after_minimum["delta_log_w"].to_numpy(dtype=float)
        )
        penalty = summarize_recovery(
            group.iloc[: detrended_position + 1][
                "delta_log_w"
            ].to_numpy(dtype=float)
        )

        min_sigma_position = int(
            np.nanargmin(group["sigma_min"].to_numpy(dtype=float))
        )
        min_sigma_row = group.iloc[min_sigma_position]
        min_sigma_step = int(min_sigma_row["event_index"])
        min_sigma_spin = (
            "up"
            if min_sigma_row["sigma_min_up"]
            <= min_sigma_row["sigma_min_down"]
            else "down"
        )
        near_event = (
            group["sigma_min"].to_numpy(dtype=float)
            < group["sigma_min_q01"].to_numpy(dtype=float)
        )
        raw_low = (
            group["overlap_after"].abs().to_numpy(dtype=float)
            < np.abs(
                group["overlap_after_q01"].to_numpy(dtype=float)
            )
        )
        orientation_normal = (
            group["sigma_min"].to_numpy(dtype=float)
            >= group["sigma_min_q05"].to_numpy(dtype=float)
        )
        normalized = group["log_normalized_overlap"].to_numpy(dtype=float)
        normalized_normal = (
            normalized
            >= group["log_normalized_overlap_q05"].to_numpy(dtype=float)
        ) & (
            normalized
            <= group["log_normalized_overlap_q95"].to_numpy(dtype=float)
        )
        site_mask = group["kind"].to_numpy() == "site"
        small_q_event = bool(
            np.any(
                site_mask
                & (
                    group["q_selected"].to_numpy(dtype=float)
                    < group["q_selected_q01"].to_numpy(dtype=float)
                )
            )
        )
        small_c_event = bool(
            np.any(
                site_mask
                & (
                    group["c_factor"].to_numpy(dtype=float)
                    < group["c_factor_q01"].to_numpy(dtype=float)
                )
            )
        )
        most_negative_position = int(
            np.nanargmin(group["delta_log_w"].to_numpy(dtype=float))
        )
        most_positive_position = int(
            np.nanargmax(group["delta_log_w"].to_numpy(dtype=float))
        )
        max_recovery_row = (
            group.loc[group["event_index"] == max_recovery_step].iloc[0]
            if max_recovery_step >= 0
            else None
        )
        half_k_contraction = (
            group.iloc[most_negative_position]["kind"] == "half_k"
        )
        summary = {
            "path_id": path_id,
            "trial": group.iloc[0]["trial"],
            "case_id": int(group.iloc[0]["case_id"]),
            "weight_bin": group.iloc[0]["weight_bin"],
            "event_count": len(group),
            "first_low_q_step": first_low_q,
            "first_low_w_step": first_low_w,
            "min_q_step": min_q_step,
            "min_c_step": min_c_step,
            "minimum_q_selected": float(group.loc[q_index, "q_selected"]),
            "minimum_c_factor": float(group.loc[c_index, "c_factor"]),
            "min_q_predicted_low_match": bool(
                group.loc[q_index, "kind"] == "site"
                and group.loc[q_index, "field"]
                == group.loc[q_index, "predicted_low_field"]
            ),
            "min_sigma_predicted_low_match": bool(
                min_sigma_row["kind"] == "site"
                and min_sigma_row["field"]
                == min_sigma_row["predicted_low_field"]
            ),
            "min_q_delta_log_w": float(
                group.loc[q_index, "delta_log_w"]
            ),
            "min_sigma_q_selected": (
                float(min_sigma_row["q_selected"])
                if min_sigma_row["kind"] == "site"
                else math.nan
            ),
            "max_recovery_q_selected": (
                float(max_recovery_row["q_selected"])
                if max_recovery_row is not None
                and max_recovery_row["kind"] == "site"
                else math.nan
            ),
            "max_recovery_delta_log_w": (
                float(max_recovery_row["delta_log_w"])
                if max_recovery_row is not None
                else math.nan
            ),
            "max_positive_weight_step": int(
                group.iloc[most_positive_position]["event_index"]
            ),
            "max_negative_weight_step": int(
                group.iloc[most_negative_position]["event_index"]
            ),
            "max_positive_delta_log_w": float(
                group.iloc[most_positive_position]["delta_log_w"]
            ),
            "max_negative_delta_log_w": float(
                group.iloc[most_negative_position]["delta_log_w"]
            ),
            "minimum_cumulative_log_w": float(np.nanmin(cumulative_w)),
            "final_cumulative_log_w": float(cumulative_w[-1]),
            "detrended_min_step": detrended_min_step,
            "recovery_step": recovery_step,
            "max_recovery_step": max_recovery_step,
            "recovery_concentration": recovery[
                "recovery_concentration"
            ],
            "penalty_concentration": penalty["penalty_concentration"],
            "min_sigma_step": min_sigma_step,
            "min_sigma_spin": min_sigma_spin,
            "minimum_sigma": float(min_sigma_row["sigma_min"]),
            "near_orthogonal": bool(np.any(near_event)),
            "scale_only": bool(
                np.any(raw_low & orientation_normal & normalized_normal)
            ),
            "small_q_event": small_q_event,
            "small_c_event": small_c_event,
            "half_k_contraction": half_k_contraction,
            "max_ratio_residual": float(
                group["ratio_residual"].max()
            ),
            "first_low_w_slice": _event_slice(group, first_low_w),
            "min_sigma_slice": _event_slice(group, min_sigma_step),
            "recovery_slice": _event_slice(group, recovery_step),
        }
        summary["mechanism"] = classify_mechanism(summary)
        summaries.append(summary)
    return pd.DataFrame.from_records(summaries), events


def join_critical_mask_predictions(
    summaries: pd.DataFrame, masks: pd.DataFrame
) -> pd.DataFrame:
    """Attach mask ranks at onset, minimum sigma, and recovery slices."""

    mask_columns = [
        column for column in masks.columns if column not in ("path_id", "slice")
    ]
    rows = []
    transforms = site_permutations_2x2()
    for _, summary in summaries.iterrows():
        row = summary.to_dict()
        critical = {
            "onset": int(summary["first_low_w_slice"]),
            "min_sigma": int(summary["min_sigma_slice"]),
            "recovery": int(summary["recovery_slice"]),
        }
        path_masks = masks.loc[masks["path_id"] == summary["path_id"]]
        for label, slice_index in critical.items():
            match = path_masks.loc[path_masks["slice"] == slice_index]
            for column in mask_columns:
                row[f"{label}_{column}"] = (
                    match.iloc[0][column] if len(match) else math.nan
                )
            if len(match) and {
                "realized_mask",
                "best_mask",
            } <= set(match.columns):
                realized = int(match.iloc[0]["realized_mask"])
                best = int(match.iloc[0]["best_mask"])
                row[f"{label}_same_spatial_orbit"] = (
                    canonical_mask(realized, transforms)
                    == canonical_mask(best, transforms)
                )
            else:
                row[f"{label}_same_spatial_orbit"] = False
        rows.append(row)
    return pd.DataFrame.from_records(rows)
