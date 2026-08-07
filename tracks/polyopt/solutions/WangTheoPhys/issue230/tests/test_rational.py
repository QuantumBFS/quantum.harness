from fractions import Fraction

import numpy as np

from xxzcert.rational import (
    exact_block_product_energy,
    exact_sparse_block_product_energy,
    exact_mps_block_product_energy,
    make_anderson_witness,
    make_lti_dual_witness,
    rationalize_state,
    rationalize_sparse_state,
    rigorous_positive_definite_arb,
    rigorous_positive_definite_arb_ldl,
    rigorous_positive_definite_congruence,
    verify_anderson_witness,
    verify_lti_dual_witness,
    xxz_matrix_fraction,
    xxz_sector_matrix_fraction,
)
from xxzcert.upper import block_product_energy, neel_state, optimize_block_state
from xxzcert.lti import solve_lti


def test_exact_two_site_xxx_matrix_spectrum_structure():
    matrix = xxz_matrix_fraction(Fraction(1), 2)
    assert matrix[0][0] == Fraction(1, 4)
    assert matrix[1][1] == Fraction(-1, 4)
    assert matrix[1][2] == Fraction(1, 2)


def test_arb_positive_definite_check_is_rigorous():
    assert rigorous_positive_definite_arb(
        [[Fraction(2), Fraction(1)], [Fraction(1), Fraction(2)]]
    )
    assert not rigorous_positive_definite_arb(
        [[Fraction(1), Fraction(2)], [Fraction(2), Fraction(1)]]
    )
    assert rigorous_positive_definite_arb_ldl(
        [[Fraction(2), Fraction(1)], [Fraction(1), Fraction(2)]]
    )
    assert not rigorous_positive_definite_arb_ldl(
        [[Fraction(1), Fraction(2)], [Fraction(2), Fraction(1)]]
    )
    assert rigorous_positive_definite_congruence(
        [[Fraction(2), Fraction(1)], [Fraction(1), Fraction(2)]]
    )
    assert not rigorous_positive_definite_congruence(
        [[Fraction(1), Fraction(2)], [Fraction(2), Fraction(1)]]
    )


def test_anderson_witness_is_exactly_positive():
    witness = make_anderson_witness(Fraction(1), 4)
    assert verify_anderson_witness(Fraction(1), witness)
    assert witness.energy_density_lower < Fraction(-44, 100)


def test_magnetization_sectors_partition_full_matrix():
    dimensions = [
        len(xxz_sector_matrix_fraction(Fraction(1), 5, ones))
        for ones in range(6)
    ]
    assert dimensions == [1, 5, 10, 10, 5, 1]
    assert sum(dimensions) == 32


def test_exact_neel_block_energy():
    vector = tuple(int(x.real) for x in neel_state(2))
    assert exact_block_product_energy(Fraction(1), vector) == Fraction(-1, 4)


def test_sparse_and_dense_block_energies_agree():
    vector = neel_state(4)
    dense = rationalize_state(vector)
    indices, values = rationalize_sparse_state(vector)
    assert exact_sparse_block_product_energy(
        Fraction(1), 4, indices, values
    ) == exact_block_product_energy(Fraction(1), dense)


def test_compact_mps_and_dense_block_energies_agree():
    tensor = np.array(
        [
            [[1, 1], [0, 1]],
            [[1, 0], [1, -1]],
        ],
        dtype=int,
    )
    left = (1, 0)
    right = (0, 1)
    sites = 4
    vector = []
    for state in range(1 << sites):
        matrix = np.eye(2, dtype=object)
        for position in range(sites):
            spin = (state >> (sites - 1 - position)) & 1
            matrix = matrix @ tensor[:, spin, :]
        vector.append(int(np.array(left, dtype=object) @ matrix @ np.array(right, dtype=object)))
    assert exact_mps_block_product_energy(
        Fraction(1),
        sites,
        2,
        tuple(int(value) for value in tensor.reshape(-1)),
        left,
        right,
    ) == exact_block_product_energy(Fraction(1), tuple(vector))


def test_rationalized_block_matches_float_energy():
    candidate = optimize_block_state(1.0, 4)
    vector = rationalize_state(candidate.state)
    exact = float(exact_block_product_energy(Fraction(1), vector))
    assert abs(exact - block_product_energy(1.0, candidate.state)) < 1e-7


def test_rational_lti_dual_is_exactly_feasible_and_close_to_raw():
    candidate = solve_lti(1.0, 4)
    witness = make_lti_dual_witness(
        Fraction(1),
        candidate.level,
        candidate.dual_trace,
        candidate.dual_lti,
    )
    assert verify_lti_dual_witness(Fraction(1), witness)
    assert float(witness.energy_density_lower) <= candidate.raw_lower + 1e-6
    assert float(witness.energy_density_lower) >= candidate.raw_lower - 1e-5
