import numpy as np
import pytest

from lrtfim.gap_scaling import effective_z, gap_chi_status, z_effective_series


def test_effective_z_for_exact_power_law():
    z = 0.73
    lengths = np.array([32, 64, 128, 256])
    gaps = 2.1 * lengths ** (-z)
    np.testing.assert_allclose(z_effective_series(lengths, gaps), z, atol=1e-14)
    assert effective_z(gaps[0], gaps[1]) == pytest.approx(z)


def test_gap_chi_rule_checks_gap_and_both_states():
    ok = gap_chi_status(
        {256: 0.01000, 384: 0.010005},
        {256: {"even": 1e-10, "odd": 2e-10}, 384: {"even": 1e-10, "odd": 2e-10}},
    )
    assert ok.converged
    request = gap_chi_status(
        {256: 0.01000, 384: 0.01003},
        {256: {"even": 1e-10, "odd": 2e-10}, 384: {"even": 1e-10, "odd": 2e-10}},
    )
    assert request.next_chi == 512
    discarded = gap_chi_status(
        {256: 0.01000, 384: 0.010005},
        {256: {"even": 1e-8, "odd": 2e-10}, 384: {"even": 1e-10, "odd": 2e-10}},
    )
    assert discarded.next_chi == 512
