import math

import numpy as np
import pytest

from chiral_graviton.independent_oracle import (
    fermionic_coulomb_pseudopotentials,
    oracle_neutral_gap,
)


def test_s_one_coulomb_v1_matches_closed_form():
    pseudopotentials = fermionic_coulomb_pseudopotentials(
        1, x_order=64, phi_points=256
    )
    assert pseudopotentials[1] == pytest.approx(2.0 * math.sqrt(2.0) / 3.0, abs=5e-7)


@pytest.mark.parametrize(
    ("n_electrons", "expected_l0", "expected_l2", "expected_gap"),
    [
        (3, 1.0867373948033172, 1.2057289712621748, 0.1189915764588576),
        (4, 1.8711384121456018, 2.0029951670726250, 0.1318567549270231),
    ],
)
def test_independent_oracle_reproduces_small_system_coulomb_spectrum(
    n_electrons, expected_l0, expected_l2, expected_gap
):
    result = oracle_neutral_gap(n_electrons, x_order=64, phi_points=256)

    assert result.e_l0 == pytest.approx(expected_l0, abs=2e-5)
    assert result.e_l2 == pytest.approx(expected_l2, abs=2e-5)
    assert result.gap == pytest.approx(expected_gap, abs=2e-5)
    assert result.residual_l0 < 1e-10
    assert result.residual_l2 < 1e-10
    assert result.pair_completeness_error < 1e-10
    assert result.hermiticity_error < 1e-12
    assert set(result.pseudopotentials) == set(range(1, result.two_q + 1, 2))
    assert np.all(np.isfinite(list(result.pseudopotentials.values())))


def test_independent_oracle_is_explicitly_small_system_only():
    with pytest.raises(ValueError, match="limited"):
        oracle_neutral_gap(5)
