from __future__ import annotations

import math

import pytest

from benchmark_v0.conventions import (
    background_energy,
    density_shift_factor,
    energy_conventions,
)


def test_uniform_background_energy_on_sphere() -> None:
    assert background_energy(6, 7.5) == pytest.approx(
        -36.0 / (2.0 * math.sqrt(7.5))
    )


def test_density_shift_factor_at_nu_one_third() -> None:
    assert density_shift_factor(6, 15, 1.0 / 3.0) == pytest.approx(
        math.sqrt(5.0 / 6.0)
    )


def test_energy_views_preserve_raw_values_and_correct_the_gap() -> None:
    excited = {m: -0.8 for m in range(-2, 3)}

    views = energy_conventions(
        ground_energy=-1.0,
        excited_energies_by_m=excited,
        n_electrons=6,
        two_q=15,
        filling=1.0 / 3.0,
    )

    factor = math.sqrt(5.0 / 6.0)
    background = -36.0 / (2.0 * math.sqrt(7.5))
    assert views["raw_lll"]["ground_energy"] == -1.0
    assert views["raw_lll"]["excited_energies_by_m"] == excited
    assert views["raw_lll"]["gap"] == pytest.approx(0.2)
    paper = views["paper_convention"]
    assert paper["total"]["ground_energy"] == pytest.approx(
        factor * (-1.0 + background)
    )
    assert paper["total"]["gap"] == pytest.approx(factor * 0.2)
    assert paper["per_particle"]["ground_energy"] == pytest.approx(
        factor * (-1.0 + background) / 6.0
    )
    assert paper["per_particle"]["gap"] == pytest.approx(factor * 0.2 / 6.0)
    assert excited == {m: -0.8 for m in range(-2, 3)}
