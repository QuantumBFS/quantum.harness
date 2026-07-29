import numpy as np
import pytest

from analysis.integrate import free_energy_from_energy, simpson_uniform


def test_simpson_integrates_cubic_exactly():
    x = np.linspace(0.0, 1.0, 33)
    assert simpson_uniform(x, x**3) == pytest.approx(0.25, abs=1.0e-14)


def test_free_energy_uses_the_infinite_temperature_anchor():
    k = np.array([0.0, 0.25, 0.5])
    mean_h = np.array([0.0, -4.0, -8.0])
    expected = -16.0 * np.log(2.0) + simpson_uniform(k, mean_h)
    assert free_energy_from_energy(k, mean_h, 16) == pytest.approx(expected)


def test_simpson_rejects_an_even_number_of_points():
    with pytest.raises(ValueError, match="odd"):
        simpson_uniform(np.linspace(0.0, 1.0, 4), np.ones(4))
