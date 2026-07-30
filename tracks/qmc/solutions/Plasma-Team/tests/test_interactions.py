import numpy as np
import pytest

from chiral_graviton.interactions import (
    coulomb_pseudopotentials,
    pair_matrix_elements,
    v1_pseudopotentials,
)


def test_v1_only_penalizes_relative_m_one():
    values = v1_pseudopotentials(5)
    assert values[1] == 1.0
    assert sum(values.values()) == 1.0


def test_pair_table_eigenvalues_match_fermion_pseudopotentials():
    two_q = 3
    pseudo = {0: 7.0, 1: 1.25, 2: 9.0, 3: 0.5}
    table = pair_matrix_elements(two_q, pseudo)
    eigenvalues = np.linalg.eigvalsh(table.matrix)
    expected = sorted([1.25] * 5 + [0.5])
    np.testing.assert_allclose(sorted(eigenvalues), expected, atol=1e-12)


def test_two_particle_q_half_coulomb_singlet():
    # For Q=1/2 the only fermion pair is J=0 (relative m=1). Direct
    # integration of |u1 v2-u2 v1|^2/(2R sin(theta/2)) gives 2/(3R).
    values = coulomb_pseudopotentials(1)
    assert values[1] == pytest.approx(2.0 * np.sqrt(2.0) / 3.0, rel=1e-11)


def test_coulomb_pseudopotentials_are_positive_and_decrease_for_odd_m():
    values = coulomb_pseudopotentials(7)
    odd = [values[m] for m in (1, 3, 5, 7)]
    assert all(value > 0.0 for value in odd)
    assert all(left > right for left, right in zip(odd, odd[1:]))
