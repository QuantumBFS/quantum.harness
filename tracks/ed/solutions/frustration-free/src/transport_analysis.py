"""Small data-normalization helpers for transport analysis."""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def efficiency(charge: float) -> float:
    """Return center-of-mass displacement in two-site unit-cell lengths."""
    return float(charge) / 2.0


def merge_center_and_new_rows(
    center_rows: Iterable[dict],
    new_rows: Iterable[dict],
    *,
    key_fields: Sequence[str],
) -> list[dict]:
    """Merge records with new calculations replacing identical old keys."""
    new = [dict(row, provenance="new-l8") for row in new_rows]
    new_keys = {tuple(row[field] for field in key_fields) for row in new}
    retained = [
        dict(row, provenance="existing-l8")
        for row in center_rows
        if tuple(row[field] for field in key_fields) not in new_keys
    ]
    return retained + new


def group_path_rows(
    center_rows: Iterable[dict],
    local_rows: Iterable[dict],
    refined_rows: Iterable[dict],
    *,
    path_ids: Sequence[str],
    critical_u: dict[str, Sequence[float]],
    replacement_half_width: float,
) -> dict[str, list[dict]]:
    """Group plot rows, replacing coarse data around refined transitions."""
    if replacement_half_width <= 0.0:
        raise ValueError("replacement_half_width must be positive")
    local = list(local_rows)
    refined = list(refined_rows)
    center_by_u = {
        float(row["U"]): dict(row, path_id="center")
        for row in center_rows
        if float(row["t"]) == 1.0
    }
    center_by_u.update(
        {
            float(row["U"]): dict(row)
            for row in refined
            if row["path_id"] == "center"
        }
    )
    grouped = {
        "center": [center_by_u[value] for value in sorted(center_by_u)]
    }
    for path_id in path_ids:
        transitions = tuple(float(value) for value in critical_u[path_id])
        retained = {
            float(row["U"]): dict(row)
            for row in local
            if row["path_id"] == path_id
            and all(
                abs(float(row["U"]) - transition) > replacement_half_width
                for transition in transitions
            )
        }
        retained.update(
            {
                float(row["U"]): dict(row)
                for row in refined
                if row["path_id"] == path_id
            }
        )
        grouped[path_id] = [retained[value] for value in sorted(retained)]
    return grouped
