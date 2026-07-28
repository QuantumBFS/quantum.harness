from __future__ import annotations

import numpy as np

from oracle.majorana import (
    canonical_reflection_structures,
    majorana_operators,
    plane_rotation,
    random_reflection_generator,
    reflection_structure_residual,
    shared_reality_rotation,
    spin_trace_weight,
)


def test_majorana_operators_obey_clifford_algebra() -> None:
    gamma = majorana_operators(3)
    identity = np.eye(gamma[0].shape[0])
    for left, left_operator in enumerate(gamma):
        for right, right_operator in enumerate(gamma):
            anticommutator = (
                left_operator @ right_operator
                + right_operator @ left_operator
            )
            expected = 2.0 * identity if left == right else np.zeros_like(identity)
            assert np.allclose(anticommutator, expected, atol=1e-14)


def test_reflection_generator_satisfies_complex_majorana_cone() -> None:
    rng = np.random.default_rng(7)
    generator = random_reflection_generator(
        rng,
        block_size=3,
        scale=0.8,
    )
    j1, j2 = canonical_reflection_structures(3)
    assert (
        reflection_structure_residual(
            generator,
            j1=j1,
            j2=j2,
            require_cone=True,
        )
        < 1e-12
    )


def test_fock_trace_squares_to_one_particle_determinant() -> None:
    rng = np.random.default_rng(11)
    generators = [
        random_reflection_generator(
            rng,
            block_size=2,
            scale=0.7,
            cone="indefinite",
        )
        for _ in range(4)
    ]
    result = spin_trace_weight(generators)
    assert result.square_identity_residual < 1e-12
    assert result.determinant_check_reliable


def test_common_and_rotated_common_cones_have_positive_trace() -> None:
    rng = np.random.default_rng(19)
    rotation = plane_rotation(4, angle=0.37)
    base = [
        random_reflection_generator(rng, block_size=2, scale=1.1)
        for _ in range(6)
    ]
    rotated = [rotation @ generator @ rotation.T for generator in base]

    base_result = spin_trace_weight(base)
    rotated_result = spin_trace_weight(rotated)

    assert base_result.classification == "positive"
    assert rotated_result.classification == "positive"
    assert np.allclose(base_result.value, rotated_result.value, rtol=1e-11)


def test_shared_reality_rotation_preserves_j1_but_moves_j2() -> None:
    j1, j2 = canonical_reflection_structures(2)
    rotation = shared_reality_rotation(2, angle=0.43)
    rotated_j2 = rotation @ j2 @ rotation.T

    assert np.allclose(rotation.T @ rotation, np.eye(4), atol=1e-14)
    assert np.allclose(rotation @ j1, j1 @ rotation, atol=1e-14)
    assert not np.allclose(rotated_j2, j2, atol=1e-3)
