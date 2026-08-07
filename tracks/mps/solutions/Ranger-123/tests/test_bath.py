from numpy.testing import assert_allclose

from floquet_if_manybody.bath import bath_correlation
from floquet_if_manybody.config import BathConfig


def test_zero_temperature_ohmic_correlation():
    bath = BathConfig(alpha=0.05, cutoff=2.5)
    for time in [0, 0.1, 1.0, 3.0]:
        expected = bath.alpha * bath.cutoff**2 / (1 + 1j * bath.cutoff * time) ** 2
        assert_allclose(bath_correlation(time, bath), expected)
        assert_allclose(bath_correlation(-time, bath), expected.conjugate())
