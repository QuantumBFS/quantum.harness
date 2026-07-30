"""Exact score selection and deterministic physical-weight matching."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

import numpy as np
import pandas as pd

from .path_records import logsumexp_field, open_path_records


LN10 = math.log(10.0)
LOG_HALF = math.log(0.5)
LOG_TWO = math.log(2.0)


@dataclass(frozen=True)
class WorstSelection:
    indices: np.ndarray
    config_ids: np.ndarray
    scores: np.ndarray
    cutoff_score: float
    cutoff_tie_count: int


def exact_worst_fraction(
    records: np.ndarray, log_total_d: float, fraction: float
) -> WorstSelection:
    """Return the exact largest-score fraction with deterministic ties."""

    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must lie in (0,1]")
    score = (
        records["log_d"].astype(np.float64, copy=False)
        - log_total_d
        - records["log_q"].astype(np.float64, copy=False)
    ) / LN10
    valid = (
        records["alive"].astype(bool, copy=False)
        & np.isfinite(score)
        & np.isfinite(records["log_d"])
    )
    valid_indices = np.flatnonzero(valid)
    count = int(math.ceil(fraction * len(records)))
    if len(valid_indices) < count:
        raise ValueError("too few finite surviving records for exact fraction")
    valid_scores = score[valid_indices]
    cutoff_position = len(valid_scores) - count
    cutoff = float(np.partition(valid_scores, cutoff_position)[cutoff_position])
    above = valid_indices[valid_scores > cutoff]
    equal = valid_indices[valid_scores == cutoff]
    equal_order = np.argsort(records["config_id"][equal], kind="stable")
    required_equal = count - len(above)
    chosen = np.concatenate([above, equal[equal_order[:required_equal]]])
    order = np.lexsort(
        (records["config_id"][chosen], -score[chosen])
    )
    chosen = chosen[order]
    return WorstSelection(
        indices=chosen,
        config_ids=np.asarray(records["config_id"][chosen]),
        scores=np.asarray(score[chosen]),
        cutoff_score=cutoff,
        cutoff_tie_count=len(equal),
    )


def weight_bin(log_d_minus_log_mean: float) -> Optional[str]:
    """Return the mutually exclusive physical-weight matching layer."""

    if log_d_minus_log_mean < LOG_HALF:
        return None
    if log_d_minus_log_mean < 0.0:
        return "near_average"
    if log_d_minus_log_mean < LOG_TWO:
        return "important"
    return "strongly_important"


def nearest_unused_matches(
    case_log_d: np.ndarray,
    case_ids: np.ndarray,
    control_log_d: np.ndarray,
    control_ids: np.ndarray,
) -> np.ndarray:
    """Match each ordered case to the nearest unused control in log D."""

    case_log_d = np.asarray(case_log_d, dtype=np.float64)
    case_ids = np.asarray(case_ids, dtype=np.uint64)
    control_log_d = np.asarray(control_log_d, dtype=np.float64)
    control_ids = np.asarray(control_ids, dtype=np.uint64)
    if len(case_log_d) != len(case_ids):
        raise ValueError("case values and ids have different lengths")
    if len(control_log_d) != len(control_ids):
        raise ValueError("control values and ids have different lengths")
    if len(control_log_d) < len(case_log_d):
        raise ValueError("insufficient unique controls")
    if not (
        np.all(np.isfinite(case_log_d))
        and np.all(np.isfinite(control_log_d))
    ):
        raise ValueError("matching values must be finite")

    order = np.lexsort((control_ids, control_log_d))
    values = control_log_d[order]
    ids = control_ids[order]
    count = len(values)
    available = np.ones(count, dtype=bool)
    next_parent = np.arange(count + 1, dtype=np.int64)
    previous_parent = np.arange(count + 1, dtype=np.int64)

    def find(parent: np.ndarray, node: int) -> int:
        root = node
        while parent[root] != root:
            root = int(parent[root])
        while parent[node] != node:
            following = int(parent[node])
            parent[node] = root
            node = following
        return root

    def next_available(position: int) -> int:
        return find(next_parent, position)

    def previous_available(position: int) -> int:
        node = find(previous_parent, position + 1)
        return node - 1

    def best_in_equal_value_group(index: int) -> int:
        value = values[index]
        left = int(np.searchsorted(values, value, side="left"))
        right = int(np.searchsorted(values, value, side="right"))
        candidates = np.flatnonzero(available[left:right]) + left
        if len(candidates) == 0:
            raise RuntimeError("availability index is inconsistent")
        return int(candidates[np.argmin(ids[candidates])])

    def remove(index: int) -> None:
        available[index] = False
        next_parent[index] = find(next_parent, index + 1)
        previous_parent[index + 1] = find(previous_parent, index)

    matched = np.empty(len(case_log_d), dtype=np.uint64)
    for case_index, target in enumerate(case_log_d):
        insertion = int(np.searchsorted(values, target, side="left"))
        successor = next_available(insertion)
        predecessor = previous_available(insertion - 1)
        candidates = []
        if predecessor >= 0:
            candidates.append(best_in_equal_value_group(predecessor))
        if successor < count:
            candidates.append(best_in_equal_value_group(successor))
        candidates = sorted(set(candidates))
        if not candidates:
            raise RuntimeError("no unused control remains")
        selected = min(
            candidates,
            key=lambda index: (abs(values[index] - target), int(ids[index])),
        )
        matched[case_index] = ids[selected]
        remove(selected)
    return matched


def build_trial_selection(
    path: str, fraction: float = 0.01
) -> pd.DataFrame:
    """Build exact worst paths, D-matched controls, and low-D references."""

    header, records = open_path_records(path)
    if len(records) == 0:
        raise ValueError("cannot select from an empty path file")
    log_total = logsumexp_field(records, "log_d")
    log_mean = log_total - math.log(len(records))
    selected = exact_worst_fraction(records, log_total, fraction)
    all_scores = (
        records["log_d"].astype(np.float64, copy=False)
        - log_total
        - records["log_q"].astype(np.float64, copy=False)
    ) / LN10
    log_ratios = (
        records["log_d"].astype(np.float64, copy=False) - log_mean
    )
    bin_codes = np.full(len(records), -1, dtype=np.int8)
    bin_codes[(log_ratios >= LOG_HALF) & (log_ratios < 0.0)] = 0
    bin_codes[(log_ratios >= 0.0) & (log_ratios < LOG_TWO)] = 1
    bin_codes[log_ratios >= LOG_TWO] = 2
    bin_names = {
        -1: "below_half",
        0: "near_average",
        1: "important",
        2: "strongly_important",
    }
    selected_mask = np.zeros(len(records), dtype=bool)
    selected_mask[selected.indices] = True
    config_ids = np.asarray(records["config_id"], dtype=np.uint64)
    id_order = np.argsort(config_ids, kind="stable")
    sorted_ids = config_ids[id_order]
    if len(np.unique(sorted_ids)) != len(sorted_ids):
        raise ValueError("config_id values must be unique")

    def indices_for_ids(ids: np.ndarray) -> np.ndarray:
        positions = np.searchsorted(sorted_ids, ids)
        if np.any(positions >= len(sorted_ids)):
            raise ValueError("matched config_id is absent from path file")
        found = sorted_ids[positions]
        if not np.array_equal(found, ids):
            raise ValueError("matched config_id is absent from path file")
        return id_order[positions]

    def row(
        index: int,
        role: str,
        case_id: int,
        match_abs_dlog: float = math.nan,
    ) -> dict[str, object]:
        code = int(bin_codes[index])
        return {
            "trial": header.trial,
            "role": role,
            "case_id": int(case_id),
            "config_id": int(config_ids[index]),
            "score": float(all_scores[index]),
            "log_d": float(records["log_d"][index]),
            "log_d_over_mean": float(log_ratios[index]),
            "d_over_mean": math.exp(float(log_ratios[index])),
            "weight_bin": bin_names[code],
            "cutoff_score": selected.cutoff_score,
            "cutoff_tie_count": selected.cutoff_tie_count,
            "match_abs_dlog": match_abs_dlog,
        }

    rows = []
    case_indices = []
    low_indices = []
    for index in selected.indices:
        if bin_codes[index] < 0:
            rows.append(row(int(index), "worst_low", int(config_ids[index])))
            low_indices.append(int(index))
        else:
            rows.append(row(int(index), "case", int(config_ids[index])))
            case_indices.append(int(index))

    for code in (0, 1, 2):
        cases = np.asarray(
            [index for index in case_indices if bin_codes[index] == code],
            dtype=np.int64,
        )
        if len(cases) == 0:
            continue
        pool = np.flatnonzero((~selected_mask) & (bin_codes == code))
        if len(pool) < len(cases):
            raise ValueError(
                f"insufficient unique controls in {bin_names[code]}"
            )
        matched_ids = nearest_unused_matches(
            log_ratios[cases],
            config_ids[cases],
            log_ratios[pool],
            config_ids[pool],
        )
        matched_indices = indices_for_ids(matched_ids)
        for case_index, control_index in zip(cases, matched_indices):
            rows.append(
                row(
                    int(control_index),
                    "control",
                    int(config_ids[case_index]),
                    abs(
                        float(
                            records["log_d"][control_index]
                            - records["log_d"][case_index]
                        )
                    ),
                )
            )

    if case_indices:
        if len(low_indices) < len(case_indices):
            raise ValueError(
                "insufficient low-weight worst paths for score matching"
            )
        cases = np.asarray(case_indices, dtype=np.int64)
        low = np.asarray(low_indices, dtype=np.int64)
        reference_ids = nearest_unused_matches(
            all_scores[cases],
            config_ids[cases],
            all_scores[low],
            config_ids[low],
        )
        reference_indices = indices_for_ids(reference_ids)
        for case_index, reference_index in zip(cases, reference_indices):
            rows.append(
                row(
                    int(reference_index),
                    "low_weight_reference",
                    int(config_ids[case_index]),
                )
            )

    columns = [
        "trial",
        "role",
        "case_id",
        "config_id",
        "score",
        "log_d",
        "log_d_over_mean",
        "d_over_mean",
        "weight_bin",
        "cutoff_score",
        "cutoff_tie_count",
        "match_abs_dlog",
    ]
    return pd.DataFrame.from_records(rows, columns=columns)
