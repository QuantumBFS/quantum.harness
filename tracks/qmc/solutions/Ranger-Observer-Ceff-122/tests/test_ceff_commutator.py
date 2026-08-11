import numpy as np

from ceffflow.commutator import (
    hadamard_z_commutator_example,
    relative_entropy_deficiency,
    self_dual_block_deficiency,
    self_dual_trajectory_block_deficiency,
    statistical_deficiency,
)
from ceffflow.self_dual import SELF_DUAL_BETA


def test_deficiency_vanishes_for_a_classical_postprocessing():
    fine = np.asarray([[0.8, 0.2], [0.1, 0.9], [0.4, 0.6]])
    kernel = np.asarray([[0.7, 0.3], [0.2, 0.8]])
    target = fine @ kernel
    result = statistical_deficiency(fine, target)
    assert result.deficiency < 1e-9
    assert np.allclose(np.sum(result.stochastic_map, axis=1), 1.0)


def test_hadamard_and_z_measurement_have_nonzero_commutator():
    result = hadamard_z_commutator_example()
    assert np.isclose(result.deficiency, 0.5, atol=1e-10)


def test_relative_entropy_deficiency_vanishes_for_classical_postprocessing():
    fine = np.asarray([[0.8, 0.2], [0.1, 0.9], [0.4, 0.6]])
    kernel = np.asarray([[0.7, 0.3], [0.2, 0.8]])
    result = relative_entropy_deficiency(fine, fine @ kernel)
    assert result.deficiency < 1e-9
    assert np.allclose(np.sum(result.stochastic_map, axis=1), 1.0)


def test_self_dual_block_witness_has_exact_tv_obstruction():
    one_site = self_dual_block_deficiency(record_range=1)
    two_sites = self_dual_block_deficiency(record_range=2)
    tanh_beta = np.tanh(SELF_DUAL_BETA)
    assert np.isclose(one_site.tv.deficiency, tanh_beta / 2.0, atol=1e-10)
    assert np.isclose(
        two_sites.tv.deficiency,
        (tanh_beta - tanh_beta**2) / 2.0,
        atol=1e-10,
    )
    assert np.isclose(two_sites.diamond_distance, two_sites.tv.deficiency)
    assert np.isclose(two_sites.diamond_norm, 2.0 * two_sites.tv.deficiency)
    assert 0.0 < two_sites.kl.deficiency < one_site.kl.deficiency


def test_self_dual_block_witness_rejects_unsupported_record_range():
    with np.testing.assert_raises(ValueError):
        self_dual_block_deficiency(record_range=3)


def test_self_dual_critical_trajectory_witness_survives_small_widths():
    for length in (3, 4, 5):
        one_site = self_dual_trajectory_block_deficiency(
            length, record_range=1, trajectories=4, rows=2
        )
        two_sites = self_dual_trajectory_block_deficiency(
            length, record_range=2, trajectories=4, rows=2
        )
        assert one_site.state_count == 9
        assert 0.0 < two_sites.tv.deficiency < one_site.tv.deficiency
        assert 0.0 < two_sites.kl.deficiency < one_site.kl.deficiency
