from __future__ import annotations

from copy import deepcopy

from floquet_if_manybody.n3_heat import N3HeatPoint, prepare_n3_sector
from floquet_if_manybody.paper_extension import (
    _odd_equivalent_payload,
    n2_correlation_delay_periods,
    uniform_error_schedule,
    uniform_publication_schedule,
)


def test_odd_equivalent_payload_reuses_only_the_projected_model() -> None:
    point = N3HeatPoint(j=0.25, sector="odd", backend="uniform_tempo")
    prepared = prepare_n3_sector(point)
    reference = {
        "fingerprint": "a" * 64,
        "source_commit": "test",
        "point": {"j": 0.25},
        "final_point": {
            **point.__dict__,
            "steps_per_period": 60,
            "phase_samples": 3,
        },
        "model": {
            "n": 3,
            "j": 0.25,
            "drive_frequency": prepared.model.drive_frequency,
        },
        "model_hash": "b" * 64,
        "projected_model_hash": "c" * 64,
        "bright_gap": prepared.bright_gap,
        "continuous": [0.0, 1.0],
        "adaptive_converged": True,
    }
    untouched = deepcopy(reference)
    target = _odd_equivalent_payload(reference, 1.0)
    assert reference == untouched
    assert target["point"]["j"] == 1.0
    assert target["final_point"]["j"] == 1.0
    assert target["model"]["j"] == 1.0
    assert target["continuous"] == reference["continuous"]
    assert target["projected_model_hash"] == reference["projected_model_hash"]
    assert target["numerical_reuse"]["h0_frobenius_residual"] < 1e-13
    assert target["numerical_reuse"]["coupling_frobenius_residual"] < 1e-13


def test_n2_correlation_window_grows_at_weak_coupling() -> None:
    assert n2_correlation_delay_periods(0.1) == 4
    assert n2_correlation_delay_periods(0.05) == 6
    assert n2_correlation_delay_periods(0.025) == 12


def test_n2_error_grid_has_a_deeper_compression_ladder() -> None:
    publication = uniform_publication_schedule()
    error = uniform_error_schedule()
    assert error.steps_per_period == publication.steps_per_period
    assert error.phase_samples == publication.phase_samples
    assert error.tolerances[: len(publication.tolerances)] == publication.tolerances
    assert error.tolerances[-1] < publication.tolerances[-1]
