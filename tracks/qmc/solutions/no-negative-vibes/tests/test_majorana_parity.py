from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from oracle.majorana import (
    majorana_operators,
    random_reflection_generator,
    spin_trace_weight,
)
from oracle.majorana_parity import (
    fermion_parity_operator,
    parity_resolved_trace,
    protected_sector,
    run_survey,
    scan_case,
)


def test_parity_resolved_trace_sums_to_full_positive_trace() -> None:
    rng = np.random.default_rng(71)
    generators = [
        random_reflection_generator(
            rng,
            block_size=3,
            scale=1.2,
        )
        for _ in range(5)
    ]

    result = parity_resolved_trace(generators)

    assert np.allclose(result.even + result.odd, result.total, atol=1e-14)
    assert result.total_classification == "positive"


def test_scan_case_is_reproducible_and_counts_every_sample() -> None:
    settings = (2, 4, 2.5, 73, 24)
    left = scan_case(*settings)
    right = scan_case(*settings)

    assert left == right
    for sector_counts in left["counts"].values():
        assert sum(sector_counts.values()) == settings[-1]


@pytest.mark.parametrize(
    ("modes", "expected"),
    [
        (2, "odd"),
        (3, "even"),
        (4, "even"),
        (5, "odd"),
        (6, "odd"),
    ],
)
def test_protected_sector_has_period_four_pattern(
    modes: int,
    expected: str,
) -> None:
    assert protected_sector(modes) == expected


@pytest.mark.parametrize(
    ("modes", "seed"),
    [
        (2, 1),
        (3, 3),
        (4, 2),
        (5, 2),
        (6, 5),
    ],
)
def test_seeded_counterexample_regression_hits_only_unprotected_sector(
    modes: int,
    seed: int,
) -> None:
    result = scan_case(
        modes=modes,
        depth=4,
        scale=3.0,
        seed=seed,
        samples=1,
    )
    protected = result["protected_sector"]
    unprotected = "odd" if protected == "even" else "even"

    assert result["counts"][protected]["positive"] == 1
    assert result["counts"][protected]["negative"] == 0
    assert result["counts"][unprotected]["negative"] == 1
    assert result["counts"]["total"]["positive"] == 1


@pytest.mark.parametrize("modes", [1, 2, 3, 4, 5, 6])
def test_canonical_majorana_parity_matches_popcount_basis(modes: int) -> None:
    parity = fermion_parity_operator(modes)
    expected = np.diag(
        [
            (-1.0) ** state.bit_count()
            for state in range(1 << modes)
        ]
    )

    assert np.allclose(parity, expected, atol=1e-14)

    gamma = majorana_operators(modes)
    explicit = ((-1j) ** modes) * np.eye(1 << modes, dtype=complex)
    for operator in gamma:
        explicit = explicit @ operator
    assert np.allclose(parity, explicit, atol=1e-14)


def test_parity_total_matches_production_spin_trace_oracle() -> None:
    rng = np.random.default_rng(77)
    generators = [
        random_reflection_generator(
            rng,
            block_size=4,
            scale=1.7,
        )
        for _ in range(6)
    ]

    parity = parity_resolved_trace(generators)
    production = spin_trace_weight(generators)
    parity_phase = parity.total / abs(parity.total)
    parity_log_abs = parity.log_scale + np.log(abs(parity.total))

    assert np.allclose(parity_phase, production.phase, atol=1e-14)
    assert np.isclose(parity_log_abs, production.log_abs, atol=1e-13)
    assert parity.total_classification == production.classification


def test_invalid_scan_settings_are_rejected() -> None:
    with pytest.raises(ValueError, match="modes"):
        scan_case(0, 2, 1.0, 1, 2)
    with pytest.raises(ValueError, match="depth"):
        scan_case(2, 0, 1.0, 1, 2)
    with pytest.raises(ValueError, match="scale"):
        scan_case(2, 2, -1.0, 1, 2)
    with pytest.raises(ValueError, match="samples"):
        scan_case(2, 2, 1.0, 1, 0)


def test_survey_records_all_requested_mode_counts() -> None:
    result = run_survey(
        modes=[2, 3],
        depth=2,
        scale=0.4,
        seed=79,
        samples=2,
    )

    assert result["schema_version"] == 1
    assert [cell["params"]["modes"] for cell in result["cells"]] == [2, 3]


def test_committed_parity_survey_has_consistent_counts_and_convention() -> None:
    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "majorana_parity_survey.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert payload["protocol"] == "majorana-parity-v1"
    assert payload["history_count"] == 640
    assert payload["convention"]["fermion_parity"].startswith("P=(-i)^m")
    assert len(payload["cells"]) == 5
    for cell in payload["cells"]:
        protected = cell["protected_sector"]
        other = "odd" if protected == "even" else "even"
        assert protected == protected_sector(cell["modes"])
        for counts in cell["counts"].values():
            assert sum(counts.values()) == 128
        assert cell["counts"][protected]["negative"] == 0
        assert cell["counts"][other]["negative"] > 0
        assert cell["counts"]["total"]["positive"] == 128
