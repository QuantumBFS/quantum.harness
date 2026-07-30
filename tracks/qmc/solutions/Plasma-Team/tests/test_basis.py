from math import comb

import numpy as np
import pytest

from chiral_graviton.basis import (
    FockBasis,
    SphereSystem,
    apply_annihilation,
    apply_creation,
    apply_two_body,
)


def test_laughlin_shift_and_orbitals():
    system = SphereSystem.from_electron_count(6)
    assert system.two_q == 15
    assert system.n_orbitals == 16
    assert system.radius_over_lb == pytest.approx(np.sqrt(7.5))


def test_fixed_lz_sectors_partition_full_fock_space():
    system = SphereSystem(n_electrons=3, two_q=5)
    dimensions = 0
    for two_lz in range(-15, 16):
        try:
            dimensions += FockBasis(system, two_lz).dimension
        except ValueError:
            pass
    assert dimensions == comb(6, 3)


def test_creation_annihilation_signs():
    state = (1 << 0) | (1 << 2) | (1 << 4)
    assert apply_annihilation(state, 2) == (state ^ (1 << 2), -1)
    assert apply_creation(state, 3) == (state | (1 << 3), 1)
    assert apply_annihilation(state, 1) is None
    assert apply_creation(state, 2) is None


def test_two_body_operator_on_its_own_pair_has_unit_sign():
    state = (1 << 1) | (1 << 4)
    assert apply_two_body(state, 1, 4, 1, 4) == (state, 1)


def test_invalid_sector_parity_is_rejected():
    with pytest.raises(ValueError, match="CG002"):
        FockBasis(SphereSystem(n_electrons=2, two_q=3), two_lz=1)
