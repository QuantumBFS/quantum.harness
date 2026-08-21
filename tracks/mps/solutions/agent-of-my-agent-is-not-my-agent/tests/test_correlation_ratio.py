from __future__ import annotations

import numpy as np
import pytest
from tenpy.networks.mps import MPS
from tenpy.networks.site import SpinHalfSite

from lrtfim.correlation_ratio import (
    physical_correlations_rotated,
    second_moment_ratio,
)


def test_second_moment_ratio_preserves_raw_audit_values() -> None:
    length = 16
    distance = np.arange(length)
    periodic_distance = np.minimum(distance, length - distance)
    correlations = np.exp(-periodic_distance / 2.5)
    k_min = 2.0 * np.pi / length
    s_zero = float(np.sum(correlations))
    s_k_min = float(np.sum(np.cos(k_min * distance) * correlations))
    xi = np.sqrt(s_zero / s_k_min - 1.0) / (2.0 * np.sin(k_min / 2.0))

    result = second_moment_ratio(correlations)

    assert result.s_zero == pytest.approx(s_zero)
    assert result.s_k_min == pytest.approx(s_k_min)
    assert result.k_min == pytest.approx(k_min)
    assert result.xi == pytest.approx(xi)
    assert result.r_xi == pytest.approx(xi / length)


def test_physical_correlations_use_full_rotated_sigmax_observable() -> None:
    site = SpinHalfSite(conserve="parity")
    # Rotated GHZ-like finite MPS: physical Z correlations are Sigmax-Sigmax.
    psi = MPS.from_product_state(
        [site] * 4,
        ["up", "up", "up", "up"],
        bc="finite",
    )
    correlations = physical_correlations_rotated(psi)

    assert correlations[0] == pytest.approx(1.0)
    np.testing.assert_allclose(correlations[1:], 0.0, atol=1.0e-14)


def test_second_moment_ratio_rejects_invalid_structure_factors() -> None:
    with pytest.raises(ValueError, match="S\\(k_min\\)"):
        second_moment_ratio(np.ones(8))
