import numpy as np

from qh147.qmc_pilot_analysis import analyze_bins


def _stable_bins(*, drift=0.0):
    beta = 0.5
    m_values = np.asarray([32, 64, 128], dtype=float)
    bins = np.empty((3, 4, 80), dtype=float)
    for m_index, m_value in enumerate(m_values):
        center = -3.0 + 120.0 * (beta / m_value) ** 2
        for chain in range(4):
            rng = np.random.default_rng(100 * m_index + chain)
            values = center + rng.normal(0.0, 0.04, size=80)
            values[40:] += drift
            bins[m_index, chain] = values
    return beta, m_values, bins


def test_stable_pilot_passes_all_gates_and_recovers_limit():
    beta, m_values, bins = _stable_bins()

    result = analyze_bins(
        beta, m_values, bins, bootstrap_samples=500, seed=147
    )

    assert result["accepted"]
    assert set(result["gates"].values()) == {True}
    assert abs(result["fit"]["u_infinity"] + 3.0) < 0.03
    assert result["fit"]["ci95"][0] < result["fit"]["u_infinity"]
    assert result["fit"]["ci95"][1] > result["fit"]["u_infinity"]


def test_split_half_drift_rejects_pilot():
    beta, m_values, bins = _stable_bins(drift=0.2)

    result = analyze_bins(
        beta, m_values, bins, bootstrap_samples=100, seed=147
    )

    assert not result["accepted"]
    assert not result["gates"]["split_half"]
