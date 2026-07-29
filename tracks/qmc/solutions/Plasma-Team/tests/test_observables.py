import numpy as np

from chiral_graviton.basis import SphereSystem
from chiral_graviton.ed import interaction_pair_table, solve_fixed_l
from chiral_graviton.observables import chirality_ratio, multiplet_report


def test_l2_multiplet_has_five_degenerate_components():
    system = SphereSystem.from_electron_count(3)
    table = interaction_pair_table(system, "coulomb")
    highest = solve_fixed_l(system, 2, "coulomb", pair_table=table)
    report = multiplet_report(highest.basis, highest.vector, 2, table)
    assert report.m_values == (2, 1, 0, -1, -2)
    assert report.energy_spread < 1e-10
    np.testing.assert_allclose(report.l2_expectations, [6.0] * 5, atol=1e-9)


def test_chirality_ratio_handles_dark_channel():
    assert np.isinf(chirality_ratio(1.0, 0.0))
    assert chirality_ratio(3.0, 0.5) == 6.0
