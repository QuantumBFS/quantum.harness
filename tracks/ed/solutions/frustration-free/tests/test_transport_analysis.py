from __future__ import annotations

import pytest

from src.transport_analysis import (
    efficiency,
    group_path_rows,
    merge_center_and_new_rows,
)


def test_efficiency_is_center_of_mass_shift_in_unit_cells():
    assert efficiency(2.0) == pytest.approx(1.0)
    assert efficiency(0.0) == pytest.approx(0.0)
    assert efficiency(-2.0) == pytest.approx(-1.0)


def test_new_rows_replace_duplicate_center_path_records():
    center = [
        {"U": "0", "Delta0": "3", "t": "1", "value": "old"},
        {"U": "2", "Delta0": "3", "t": "1", "value": "keep"},
    ]
    new = [
        {"U": "0", "Delta0": "3", "t": "1", "value": "new"}
    ]

    merged = merge_center_and_new_rows(center, new, key_fields=("U", "Delta0", "t"))

    assert [row["value"] for row in merged] == ["keep", "new"]
    assert [row["provenance"] for row in merged] == ["existing-l8", "new-l8"]


def test_path_grouping_keeps_full_center_slice_and_replaces_refined_windows():
    center = [
        {"U": "0", "t": "1"},
        {"U": "1", "t": "1"},
        {"U": "2", "t": "0.5"},
    ]
    local = [
        {"path_id": "shift", "U": "0"},
        {"path_id": "shift", "U": "4"},
    ]
    refined = [
        {"path_id": "center", "U": "0.8", "t": "1"},
        {"path_id": "shift", "U": "3.8"},
        {"path_id": "shift", "U": "4.2"},
    ]

    grouped = group_path_rows(
        center,
        local,
        refined,
        path_ids=("shift",),
        critical_u={"shift": (4.0,)},
        replacement_half_width=0.5,
    )

    assert [float(row["U"]) for row in grouped["center"]] == [0.0, 0.8, 1.0]
    assert [float(row["U"]) for row in grouped["shift"]] == [0.0, 3.8, 4.2]
