import numpy as np
from numpy.testing import assert_allclose

from floquet_if_manybody.config import BathConfig
from floquet_if_manybody.correlations import CorrelationResult, DeltaCorrelationPeak
from floquet_if_manybody.heat_current import heat_current_spectrum


def test_coherent_delta_peak_is_not_smeared_into_continuum():
    delays = np.linspace(0, 20, 2001)
    weight = 0.18
    frequency = 1.7
    coherent = weight * np.cos(frequency * delays)
    correlation = CorrelationResult(
        delays,
        coherent.astype(complex),
        np.zeros_like(delays, dtype=complex),
        coherent,
        (DeltaCorrelationPeak(1, frequency, weight),),
        "analytic_test",
        {},
    )
    bath = BathConfig(alpha=0.05, cutoff=2.5)
    result = heat_current_spectrum(correlation, bath, np.linspace(0, 4, 101))
    assert_allclose(result.continuous, 0)
    expected = (
        np.pi
        * bath.alpha
        * frequency
        * np.exp(-frequency / bath.cutoff)
        * frequency
        * weight
    )
    assert_allclose(result.delta_peaks[0].weight, expected)
