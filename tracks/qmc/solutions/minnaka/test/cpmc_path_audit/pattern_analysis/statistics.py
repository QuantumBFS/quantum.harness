"""Effect sizes and exhaustive motif statistics for auxiliary fields."""

from __future__ import annotations

from itertools import combinations
import math

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact


def contingency_statistics(
    case_positive: int,
    case_negative: int,
    control_positive: int,
    control_negative: int,
) -> dict[str, float]:
    """Return corrected odds, risk difference, MI, and Fisher probability."""

    values = np.array(
        [
            [case_positive, case_negative],
            [control_positive, control_negative],
        ],
        dtype=np.float64,
    )
    corrected = values + 0.5
    odds_ratio = (
        corrected[0, 0] * corrected[1, 1]
        / (corrected[0, 1] * corrected[1, 0])
    )
    case_total = case_positive + case_negative
    control_total = control_positive + control_negative
    case_risk = (
        case_positive / case_total if case_total else math.nan
    )
    control_risk = (
        control_positive / control_total if control_total else math.nan
    )
    total = float(values.sum())
    mutual_information = 0.0
    if total > 0.0:
        probabilities = values / total
        row_probability = probabilities.sum(axis=1)
        column_probability = probabilities.sum(axis=0)
        for row in range(2):
            for column in range(2):
                probability = probabilities[row, column]
                if probability > 0.0:
                    mutual_information += probability * math.log(
                        probability
                        / (
                            row_probability[row]
                            * column_probability[column]
                        )
                    )
    probability = float(
        fisher_exact(
            [
                [case_positive, case_negative],
                [control_positive, control_negative],
            ],
            alternative="two-sided",
        ).pvalue
    )
    return {
        "odds_ratio": float(odds_ratio),
        "risk_difference": float(case_risk - control_risk),
        "mutual_information": float(mutual_information),
        "p_value": probability,
    }


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    values = np.asarray(p_values, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("p-values must be one dimensional")
    if np.any((values < 0.0) | (values > 1.0) | ~np.isfinite(values)):
        raise ValueError("p-values must be finite and lie in [0,1]")
    if len(values) == 0:
        return values.copy()
    order = np.argsort(values, kind="stable")
    ranked = values[order] * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.minimum(adjusted, 1.0)
    return result


def _attach_statistics(
    rows: list[dict[str, int]], case_total: int, control_total: int
) -> pd.DataFrame:
    result = []
    for row in rows:
        case_count = int(row["case_count"])
        control_count = int(row["control_count"])
        result.append(
            {
                **row,
                "case_support": (
                    case_count / case_total if case_total else math.nan
                ),
                "control_support": (
                    control_count / control_total if control_total else math.nan
                ),
                **contingency_statistics(
                    case_count,
                    case_total - case_count,
                    control_count,
                    control_total - control_count,
                ),
            }
        )
    frame = pd.DataFrame.from_records(result)
    if len(frame):
        frame["q_value"] = benjamini_hochberg(
            frame["p_value"].to_numpy()
        )
    return frame


def count_adjacent_pairs(
    cases: np.ndarray, controls: np.ndarray
) -> pd.DataFrame:
    case_masks = np.asarray(cases, dtype=np.uint8)
    control_masks = np.asarray(controls, dtype=np.uint8)
    if (
        case_masks.ndim != 2
        or control_masks.ndim != 2
        or case_masks.shape[1] != control_masks.shape[1]
        or case_masks.shape[1] < 2
    ):
        raise ValueError("case/control masks need equal slice counts >=2")
    case_codes = (
        case_masks[:, :-1].astype(np.int64) * 16
        + case_masks[:, 1:].astype(np.int64)
    ).ravel()
    control_codes = (
        control_masks[:, :-1].astype(np.int64) * 16
        + control_masks[:, 1:].astype(np.int64)
    ).ravel()
    case_counts = np.bincount(case_codes, minlength=256)
    control_counts = np.bincount(control_codes, minlength=256)
    rows = [
        {
            "mask_a": code // 16,
            "mask_b": code % 16,
            "case_count": int(case_counts[code]),
            "control_count": int(control_counts[code]),
        }
        for code in range(256)
    ]
    return _attach_statistics(rows, len(case_codes), len(control_codes))


def _count_slice_masks(
    cases: np.ndarray, controls: np.ndarray
) -> pd.DataFrame:
    case_values = np.asarray(cases, dtype=np.uint8).ravel()
    control_values = np.asarray(controls, dtype=np.uint8).ravel()
    case_counts = np.bincount(case_values, minlength=16)
    control_counts = np.bincount(control_values, minlength=16)
    rows = [
        {
            "mask": mask,
            "case_count": int(case_counts[mask]),
            "control_count": int(control_counts[mask]),
        }
        for mask in range(16)
    ]
    return _attach_statistics(rows, len(case_values), len(control_values))


def _count_slice_triples(
    cases: np.ndarray, controls: np.ndarray
) -> pd.DataFrame:
    case_masks = np.asarray(cases, dtype=np.uint8)
    control_masks = np.asarray(controls, dtype=np.uint8)
    if case_masks.shape[1] < 3 or control_masks.shape[1] < 3:
        raise ValueError("triple motifs require at least three slices")
    case_codes = (
        case_masks[:, :-2].astype(np.int64) * 256
        + case_masks[:, 1:-1].astype(np.int64) * 16
        + case_masks[:, 2:].astype(np.int64)
    ).ravel()
    control_codes = (
        control_masks[:, :-2].astype(np.int64) * 256
        + control_masks[:, 1:-1].astype(np.int64) * 16
        + control_masks[:, 2:].astype(np.int64)
    ).ravel()
    case_counts = np.bincount(case_codes, minlength=4096)
    control_counts = np.bincount(control_codes, minlength=4096)
    rows = [
        {
            "mask_a": code // 256,
            "mask_b": (code // 16) % 16,
            "mask_c": code % 16,
            "case_count": int(case_counts[code]),
            "control_count": int(control_counts[code]),
        }
        for code in range(4096)
    ]
    return _attach_statistics(rows, len(case_codes), len(control_codes))


def motif_tables(
    cases: np.ndarray, controls: np.ndarray
) -> dict[str, pd.DataFrame]:
    """Return exhaustive one-, two-, and three-slice motif tables."""

    case_masks = np.asarray(cases, dtype=np.uint8)
    control_masks = np.asarray(controls, dtype=np.uint8)
    if (
        case_masks.ndim != 2
        or control_masks.ndim != 2
        or case_masks.shape[1] != control_masks.shape[1]
    ):
        raise ValueError("case/control masks need equal slice counts")
    return {
        "slice": _count_slice_masks(case_masks, control_masks),
        "pair": count_adjacent_pairs(case_masks, control_masks),
        "triple": _count_slice_triples(case_masks, control_masks),
    }


def bit_itemset_table(
    cases: np.ndarray,
    controls: np.ndarray,
    bits: int = 24,
    max_order: int = 3,
) -> pd.DataFrame:
    """Count all-positive bit itemsets through the requested order."""

    if bits <= 0 or bits > 64 or max_order <= 0 or max_order > bits:
        raise ValueError("invalid bit width or itemset order")
    case_ids = np.asarray(cases, dtype=np.uint64)
    control_ids = np.asarray(controls, dtype=np.uint64)
    if bits < 64:
        limit = np.uint64(1 << bits)
        if np.any(case_ids >= limit) or np.any(control_ids >= limit):
            raise ValueError("config id exceeds requested bit width")
    rows = []
    for order in range(1, max_order + 1):
        for chronological in combinations(range(bits), order):
            subset = sum(1 << (bits - 1 - position) for position in chronological)
            case_count = int(np.count_nonzero((case_ids & subset) == subset))
            control_count = int(
                np.count_nonzero((control_ids & subset) == subset)
            )
            rows.append(
                {
                    "order": order,
                    "subset_mask": subset,
                    "chronological_positions": ",".join(
                        map(str, chronological)
                    ),
                    "case_count": case_count,
                    "control_count": control_count,
                }
            )
    return _attach_statistics(rows, len(case_ids), len(control_ids))


def connected_itemset_table(
    cases: np.ndarray,
    controls: np.ndarray,
    *,
    slices: int,
    sites: int,
    lx: int,
    ly: int,
    max_size: int = 6,
    min_support: float = 0.001,
) -> pd.DataFrame:
    """Grow supported itemsets connected by spatial or temporal edges."""

    if sites != lx * ly or slices <= 0 or slices * sites > 64:
        raise ValueError("invalid space-time lattice shape")
    if max_size < 2 or max_size > slices * sites:
        raise ValueError("max_size must lie between 2 and field count")
    if min_support < 0.0 or min_support > 1.0:
        raise ValueError("min_support must lie in [0,1]")
    case_ids = np.asarray(cases, dtype=np.uint64)
    control_ids = np.asarray(controls, dtype=np.uint64)
    total_bits = slices * sites
    adjacency = [set() for _ in range(total_bits)]
    for slice_index in range(slices):
        for site in range(sites):
            node = slice_index * sites + site
            x = site % lx
            y = site // lx
            neighbor_sites = {
                y * lx + (x + 1) % lx,
                y * lx + (x + lx - 1) % lx,
                ((y + 1) % ly) * lx + x,
                ((y + ly - 1) % ly) * lx + x,
            }
            for neighbor_site in neighbor_sites:
                if neighbor_site != site:
                    adjacency[node].add(
                        slice_index * sites + neighbor_site
                    )
            for neighbor_slice in (slice_index - 1, slice_index + 1):
                if 0 <= neighbor_slice < slices:
                    adjacency[node].add(neighbor_slice * sites + site)

    def raw_mask(nodes: frozenset[int]) -> int:
        return sum(1 << (total_bits - 1 - node) for node in nodes)

    def counts(nodes: frozenset[int]) -> tuple[int, int]:
        subset = raw_mask(nodes)
        return (
            int(np.count_nonzero((case_ids & subset) == subset)),
            int(np.count_nonzero((control_ids & subset) == subset)),
        )

    case_threshold = math.ceil(min_support * len(case_ids))
    control_threshold = math.ceil(min_support * len(control_ids))
    active = {frozenset([node]) for node in range(total_bits)}
    rows = []
    for size in range(2, max_size + 1):
        candidates = set()
        for nodes in active:
            boundary = set().union(*(adjacency[node] for node in nodes))
            for node in boundary.difference(nodes):
                grown = frozenset((*nodes, node))
                if len(grown) == size:
                    candidates.add(grown)
        next_active = set()
        for nodes in sorted(candidates, key=lambda item: tuple(sorted(item))):
            case_count, control_count = counts(nodes)
            if (
                case_count < case_threshold
                and control_count < control_threshold
            ):
                continue
            next_active.add(nodes)
            positions = tuple(sorted(nodes))
            rows.append(
                {
                    "order": size,
                    "subset_mask": raw_mask(nodes),
                    "chronological_positions": ",".join(
                        map(str, positions)
                    ),
                    "case_count": case_count,
                    "control_count": control_count,
                    "min_support_threshold": min_support,
                }
            )
        active = next_active
        if not active:
            break
    return _attach_statistics(rows, len(case_ids), len(control_ids))


def _walsh_hadamard_counts(ids: np.ndarray, bits: int) -> np.ndarray:
    size = 1 << bits
    values = np.asarray(ids, dtype=np.uint64)
    if np.any(values >= size):
        raise ValueError("config id exceeds requested bit width")
    transformed = np.bincount(
        values.astype(np.int64), minlength=size
    ).astype(np.float64)
    width = 1
    while width < size:
        block = transformed.reshape(-1, 2 * width)
        left = block[:, :width].copy()
        right = block[:, width:].copy()
        block[:, :width] = left + right
        block[:, width:] = left - right
        width *= 2
    return transformed


def fourth_order_parity_table(
    cases: np.ndarray, controls: np.ndarray, bits: int = 24
) -> pd.DataFrame:
    """Count positive fourth-order parity for every bit quadruple."""

    if bits < 4 or bits > 24:
        raise ValueError("bits must lie in [4,24]")
    case_transform = _walsh_hadamard_counts(cases, bits)
    control_transform = _walsh_hadamard_counts(controls, bits)
    case_total = len(cases)
    control_total = len(controls)
    rows = []
    for positions in combinations(range(bits), 4):
        subset = sum(1 << position for position in positions)
        case_positive = int(
            round((case_total + case_transform[subset]) / 2.0)
        )
        control_positive = int(
            round((control_total + control_transform[subset]) / 2.0)
        )
        rows.append(
            {
                "subset_mask": subset,
                "bit_positions": ",".join(map(str, positions)),
                "case_positive": case_positive,
                "control_positive": control_positive,
                "case_count": case_positive,
                "control_count": control_positive,
            }
        )
    return _attach_statistics(rows, case_total, control_total)
