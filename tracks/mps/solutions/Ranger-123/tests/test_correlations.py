import numpy as np
from numpy.testing import assert_allclose

from floquet_if_manybody.correlations import coherent_decomposition


def test_single_cosine_has_one_coherent_harmonic():
    steps = 128
    omega = 1.7
    amplitude = 0.6
    period = 2 * np.pi / omega
    times = np.arange(steps) * period / steps
    delays = np.linspace(0, 3 * period, 301)
    coherent, peaks = coherent_decomposition(amplitude * np.cos(omega * times), omega, delays)
    assert len(peaks) == 1
    assert peaks[0].harmonic == 1
    assert_allclose(peaks[0].correlation_weight, amplitude**2 / 2, atol=1e-14)
    assert_allclose(coherent, amplitude**2 / 2 * np.cos(omega * delays), atol=1e-14)


def test_half_period_antisymmetry_removes_even_harmonics():
    steps = 128
    times = np.arange(steps) * 2 * np.pi / steps
    signal = 0.4 * np.cos(times) + 0.1 * np.cos(3 * times)
    _, peaks = coherent_decomposition(signal, 1.0, times)
    assert {peak.harmonic for peak in peaks} == {1, 3}
