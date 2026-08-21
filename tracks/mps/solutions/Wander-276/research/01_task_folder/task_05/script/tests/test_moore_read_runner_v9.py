"""Registration and reproducibility tests for the Moore--Read v9 runner."""

from __future__ import annotations

from pathlib import Path

from lgeth.combinatorics import clustered_zero_mode_count
from run_moore_read_geometric_eth_v9 import (
    OPENED_PILOT_CASES,
    PROSPECTIVE_CASES,
    case_for_particle_number,
    run_pilot,
    scientific_projection,
)


def test_opened_pilot_and_prospective_cases_are_disjoint() -> None:
    assert set(OPENED_PILOT_CASES).isdisjoint(PROSPECTIVE_CASES)


def test_case_rank_is_generated_from_clustered_rule() -> None:
    case = case_for_particle_number(4, prospective=False)
    assert case.expected_rank == clustered_zero_mode_count(
        case.N,
        case.n_flux,
    )


def test_pilot_runner_is_reproducible(tmp_path: Path) -> None:
    configuration = {
        "cases": ((4, 6),),
        "panels": 1,
        "panel_size": 4,
        "seed": 2026081609,
    }
    first = run_pilot(tmp_path / "first", **configuration)
    second = run_pilot(tmp_path / "second", **configuration)
    assert scientific_projection(first) == scientific_projection(second)
    assert first["all_checks_pass"]
