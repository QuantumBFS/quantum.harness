from __future__ import annotations

from numpy.testing import assert_allclose

from floquet_if_manybody.n2_heat import N2HeatPoint, prepare_n2_triplet


def test_n2_triplet_preparation_tracks_exact_low_gap() -> None:
    prepared = prepare_n2_triplet(N2HeatPoint(j=0.5))
    assert prepared.dimension == 3
    assert_allclose(prepared.bright_gap, (1.25) ** 0.5 - 0.5)
    assert_allclose(prepared.model.drive_frequency, prepared.bright_gap)


def test_n2_drive_ratio_and_counterterm_are_explicit() -> None:
    prepared = prepare_n2_triplet(
        N2HeatPoint(
            j=0.5,
            drive_ratio=1.25,
            alpha=0.1,
            cutoff=2.5,
            counterterm=True,
        )
    )
    assert_allclose(prepared.model.drive_frequency, 1.25 * prepared.bright_gap)
    assert prepared.model.counterterm_strength == 0.25
