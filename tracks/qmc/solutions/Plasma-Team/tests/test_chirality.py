import numpy as np

from chiral_graviton.angular_momentum import angular_momentum_raising, l2_operator
from chiral_graviton.basis import FockBasis, SphereSystem
from chiral_graviton.chirality import (
    build_pair_transition_operator,
    chiral_metric_operator,
    chiral_graviton_response,
    chiral_weights,
    laughlin_chiral_pair_transitions,
    rank_two_pair_transition,
)
from chiral_graviton.ed import solve_fixed_l


def test_pair_helicities_are_exact_adjoints():
    system = SphereSystem.from_electron_count(3)
    source = FockBasis(system, two_lz=0)
    plus_two = FockBasis(system, two_lz=4)
    bright, dark = laughlin_chiral_pair_transitions(system.two_q)
    dark_many_body = build_pair_transition_operator(source, plus_two, dark)
    bright_many_body = build_pair_transition_operator(plus_two, source, bright)
    np.testing.assert_allclose(
        bright_many_body.toarray(), dark_many_body.toarray().T, atol=1e-13
    )


def test_pair_transition_obeys_rank_two_raising_commutator():
    system = SphereSystem(n_electrons=2, two_q=6)
    source = FockBasis(system, two_lz=0)
    source_raised = FockBasis(system, two_lz=2)

    for component in range(-2, 2):
        target = FockBasis(system, two_lz=2 * component)
        target_raised = FockBasis(system, two_lz=2 * (component + 1))
        # Use all five components of the same m=1 -> 3 irreducible tensor,
        # not just the helicity endpoint returned by the convenience helper.
        tensor_q = build_pair_transition_operator(
            source,
            target,
            rank_two_pair_transition(system.two_q, 1, 3, component),
        )
        tensor_q_after_raising = build_pair_transition_operator(
            source_raised,
            target_raised,
            rank_two_pair_transition(system.two_q, 1, 3, component),
        )
        tensor_q_plus_one = build_pair_transition_operator(
            source,
            target_raised,
            rank_two_pair_transition(system.two_q, 1, 3, component + 1),
        )
        commutator = (
            angular_momentum_raising(target, target_raised) @ tensor_q
            - tensor_q_after_raising
            @ angular_momentum_raising(source, source_raised)
        )
        coefficient = np.sqrt((2 - component) * (2 + component + 1))
        np.testing.assert_allclose(
            commutator.toarray(),
            coefficient * tensor_q_plus_one.toarray(),
            atol=1e-12,
        )


def test_parent_laughlin_state_has_bright_spin_two_and_zero_dark_weight():
    system = SphereSystem.from_electron_count(4)
    ground = solve_fixed_l(system, total_l=0, interaction="v1")
    weights = chiral_weights(ground.basis, ground.vector)

    assert weights.bright_minus > 1e-8
    assert weights.dark_plus < 1e-24
    assert weights.bright_to_dark > 1e20

    bright = chiral_metric_operator(ground.basis, "bright_minus")
    excited = bright.matrix @ ground.vector
    excited /= np.linalg.norm(excited)
    l2_expectation = float(np.real(np.vdot(excited, l2_operator(bright.target) @ excited)))
    np.testing.assert_allclose(l2_expectation, 6.0, atol=1e-10)

    graviton = solve_fixed_l(system, total_l=2, interaction="v1")
    response = chiral_graviton_response(
        ground.basis, ground.vector, graviton.basis, graviton.vector
    )
    assert response.bright_graviton_fraction > 0.98
    assert response.dark_graviton_weight < 1e-24


def test_dark_channel_is_zero_before_squaring_the_norm():
    system = SphereSystem.from_electron_count(3)
    ground = solve_fixed_l(system, total_l=0, interaction="v1")
    dark = chiral_metric_operator(ground.basis, "dark_plus")
    assert np.linalg.norm(dark.matrix @ ground.vector) < 1e-12


def test_coulomb_parent_channel_has_suppressed_but_nonzero_dark_weight():
    system = SphereSystem.from_electron_count(4)
    ground = solve_fixed_l(system, total_l=0, interaction="coulomb")
    weights = chiral_weights(ground.basis, ground.vector)

    assert weights.dark_plus > 1e-8
    assert weights.bright_minus > 100.0 * weights.dark_plus
