import numpy as np

from ceffflow.nishimori import (
    RandomBondIsingCylinder,
    estimate_coupled_nishimori_free_energies,
    nishimori_coupling,
)
from ceffflow.self_dual import (
    SelfDualBornCylinder,
    SelfDualGaussianCylinder,
    estimate_coupled_gaussian_self_dual_record_rates,
)


def test_nishimori_matrix_free_row_matches_dense():
    cylinder = RandomBondIsingCylinder(3, nishimori_coupling(0.1))
    vertical = np.array([1, -1, 1], dtype=np.int8)
    horizontal = np.array([-1, 1, 1], dtype=np.int8)
    vector = np.arange(1, 9, dtype=float)
    assert np.allclose(
        cylinder.apply_row(vector, vertical, horizontal),
        cylinder.dense_row(vertical, horizontal) @ vector,
    )


def test_spin_and_gaussian_self_dual_use_same_born_probabilities():
    uniforms_z = np.array([0.1, 0.7, 0.4])
    uniforms_x = np.array([0.2, 0.9, 0.3])
    spin = SelfDualBornCylinder(3)
    gaussian = SelfDualGaussianCylinder(3)
    _, logp_spin = spin.sample_row(
        spin.plus_state(), uniforms_z, uniforms_x
    )
    _, logp_gaussian = gaussian.sample_row(
        gaussian.plus_covariance(), uniforms_z, uniforms_x
    )
    assert np.isclose(logp_spin, logp_gaussian, atol=1e-12)


def test_coupled_nishimori_is_bitwise_reproducible():
    kwargs = dict(lengths=[3, 4, 5], rows=20, burn_in=2, block_size=5, seed=17)
    first = estimate_coupled_nishimori_free_energies(**kwargs)
    second = estimate_coupled_nishimori_free_energies(**kwargs)
    assert np.array_equal(first.blocks, second.blocks)


def test_coupled_gaussian_self_dual_is_bitwise_reproducible():
    kwargs = dict(lengths=[3, 4, 5], steps=20, burn_in=2, block_size=5, seed=17)
    first = estimate_coupled_gaussian_self_dual_record_rates(**kwargs)
    second = estimate_coupled_gaussian_self_dual_record_rates(**kwargs)
    assert np.array_equal(first.blocks, second.blocks)


def test_gaussian_batch_update_matches_scalar_updates():
    cylinder = SelfDualGaussianCylinder(4)
    states = []
    for first_sign, second_sign in ((1, 1), (1, -1), (-1, 1)):
        state, _ = cylinder.update_zz(
            cylinder.plus_covariance(), 0, first_sign
        )
        state, _ = cylinder.update_x(state, 1, second_sign)
        states.append(state)
    covariances = np.stack(states)
    signs = np.array([1, -1, 1], dtype=np.int8)
    first, second = cylinder._zz_indices(2)

    batch_probabilities = cylinder.bilinear_probability_plus_batch(
        covariances, first, second
    )
    expected_probabilities = np.array(
        [
            cylinder._bilinear_probability_plus(state, first, second)
            for state in states
        ]
    )
    assert np.allclose(batch_probabilities, expected_probabilities, atol=1e-14)

    batch_states, batch_selected_probabilities = (
        cylinder.update_bilinear_batch(
            covariances, first, second, signs
        )
    )
    scalar = [
        cylinder._update_bilinear(state, first, second, int(sign))
        for state, sign in zip(states, signs, strict=True)
    ]
    assert np.allclose(
        batch_states, np.stack([item[0] for item in scalar]), atol=1e-14
    )
    assert np.allclose(
        batch_selected_probabilities,
        [item[1] for item in scalar],
        atol=1e-14,
    )
