from __future__ import annotations

import copy

import pytest

from spinglass3d.stage6_aggregate import summarize_equilibration


OBSERVABLES = ("energy", "q2", "q4", "chi0", "chik_x", "chik_y", "chik_z")


def _manifest(cell_id: str, *, trip_count: int = 12) -> dict[str, object]:
    reports = []
    for index in range(2):
        components = {
            "edge_acceptance": [0.27, 0.31],
            "round_trips": [trip_count, trip_count + 1, trip_count + 2, trip_count],
            "extension_count": 2,
            "tmax_forgetting_passed": True,
            "thermal_error_fraction": 0.12,
        }
        components.update(
            {
                name: {"rhat": 1.02, "minimum_ess": 240.0}
                for name in OBSERVABLES
            }
        )
        reports.append(
            {
                "j_id": f"{cell_id}@T{index:03d}",
                "passed": True,
                "failed_gates": [],
                "components": components,
                "disorder_count": 1,
            }
        )
    return {
        "classification": "PILOT_PASS",
        "cell_id": cell_id,
        "spec": {"temperatures": [2.0, 0.8]},
        "progress": {"elapsed_seconds": 10.0},
        "equilibration": {"passed": True, "reports": reports},
    }


def test_cross_j_summary_uses_cells_as_disorder_units() -> None:
    summary = summarize_equilibration(
        [_manifest("L12-J0000"), _manifest("L12-J0001", trip_count=10)],
        expected_cell_ids=("L12-J0000", "L12-J0001"),
    )
    assert summary.passed is True
    assert summary.expected_cell_count == summary.completed_cell_count == 2
    assert summary.round_trips_min == 10
    assert summary.swap_acceptance_min == pytest.approx(0.27)
    assert summary.swap_acceptance_max == pytest.approx(0.31)
    assert summary.rhat_max == pytest.approx(1.02)
    assert summary.ess_min == pytest.approx(240.0)
    assert summary.thermal_error_fraction_max == pytest.approx(0.12)
    assert summary.extension_count_max == 2
    assert summary.elapsed_seconds == pytest.approx(20.0)


def test_cross_j_summary_preserves_missing_and_rejects_substitution() -> None:
    summary = summarize_equilibration(
        [_manifest("L12-J0000")],
        expected_cell_ids=("L12-J0000", "L12-J0001"),
    )
    assert summary.passed is False
    assert summary.missing_cell_ids == ("L12-J0001",)
    with pytest.raises(ValueError, match="substitutes"):
        summarize_equilibration(
            [_manifest("L12-J9999")],
            expected_cell_ids=("L12-J0000",),
        )


def test_cross_j_summary_rejects_duplicate_or_missing_temperature_rows() -> None:
    duplicate = _manifest("L12-J0000")
    duplicate["equilibration"]["reports"][1]["j_id"] = "L12-J0000@T000"
    with pytest.raises(ValueError, match="IDs"):
        summarize_equilibration(
            [duplicate],
            expected_cell_ids=("L12-J0000",),
        )

    missing = _manifest("L12-J0000")
    missing["equilibration"]["reports"].pop()
    with pytest.raises(ValueError, match="count"):
        summarize_equilibration(
            [missing],
            expected_cell_ids=("L12-J0000",),
        )


def test_cross_j_summary_rejects_nonfinite_diagnostics() -> None:
    manifest = _manifest("L12-J0000")
    manifest["equilibration"]["reports"][0]["components"]["q2"]["rhat"] = "Infinity"
    with pytest.raises(ValueError, match="finite"):
        summarize_equilibration(
            [manifest],
            expected_cell_ids=("L12-J0000",),
        )
