import numpy as np
import pytest

from challenge15.fermions import (
    DeterminantBasis,
    apply_annihilation,
    apply_creation,
    apply_one_body,
)
from challenge15.spec import SphereSpec


def test_creation_annihilation_obey_car():
    basis = DeterminantBasis.full(SphereSpec(3))
    for state in basis.states[:20]:
        for orbital in range(basis.spec.orbital_count):
            lhs = 0.0

            first = apply_annihilation(state, orbital)
            if first is not None:
                second = apply_creation(first.state, orbital)
                assert second is not None
                lhs += first.sign * second.sign

            first = apply_creation(state, orbital)
            if first is not None:
                second = apply_annihilation(first.state, orbital)
                assert second is not None
                lhs += first.sign * second.sign

            assert lhs == 1.0


def test_basis_states_are_sorted_and_particle_conserving():
    basis = DeterminantBasis.full(SphereSpec(3))
    assert basis.dimension == basis.spec.full_dimension
    assert list(basis.states) == sorted(basis.states)
    assert all(state.bit_count() == basis.spec.particles for state in basis.states)
    assert basis.states[0] == 0b0000111
    assert basis.states[-1] == 0b1110000


def test_one_body_move_uses_ordered_fermion_sign():
    state = (1 << 0) | (1 << 2) | (1 << 4)
    moved = apply_one_body(state, source=4, target=1)
    assert moved is not None
    assert moved.state == ((1 << 0) | (1 << 1) | (1 << 2))
    assert moved.sign == -1.0


def test_negative_bit_patterns_are_rejected():
    with pytest.raises(ValueError, match="state must be a nonnegative integer bit pattern"):
        apply_creation(-1, 0)


@pytest.mark.parametrize(
    ("two_m", "message"),
    [
        (True, "two_m must be a Python integer"),
        (0.5, "two_m must be a Python integer"),
        ("0", "two_m must be a Python integer"),
        (1, "two_m must lie on the doubled many-body M lattice"),
        (38, "two_m must satisfy \\|two_m\\| <= particles \\* two_q"),
        (-38, "two_m must satisfy \\|two_m\\| <= particles \\* two_q"),
    ],
)
def test_with_two_m_rejects_invalid_doubled_quantum_numbers(two_m, message):
    with pytest.raises(ValueError, match=message):
        DeterminantBasis.with_two_m(SphereSpec(4), two_m)
