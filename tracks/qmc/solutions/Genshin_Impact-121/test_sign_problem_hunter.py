"""Theorem-grade anchors for the sign-problem determinant oracle."""

from fractions import Fraction
from pathlib import Path
import sys

import numpy as np

SOLUTION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SOLUTION_DIR))

import sign_problem_hunter as sph


def test_o11_analytic_benchmark_for_a_product():
    rapidities = np.array([0.7, -0.2, 1.1, -0.4])
    generators = [sph.o11_generator(value) for value in rapidities]

    numeric = sph.determinant_weight(generators)
    analytic = sph.o11_analytic_determinant(rapidities)

    assert np.isclose(numeric, analytic, rtol=1e-13, atol=1e-13)
    assert analytic >= 0.0


def test_o11_generators_satisfy_split_lie_algebra_condition():
    eta = sph.split_metric(1)

    for value in (-2.0, 0.0, 0.3, 4.0):
        generator = sph.o11_generator(value)
        residual = generator.T @ eta + eta @ generator
        assert np.linalg.norm(residual, ord="fro") < 1e-14


def test_fock_lift_preserves_the_matrix_commutator():
    rng = np.random.default_rng(121)
    a = rng.normal(size=(3, 3))
    b = rng.normal(size=(3, 3))

    a_hat = sph.bilinear_fock_operator(a)
    b_hat = sph.bilinear_fock_operator(b)
    matrix_commutator_hat = sph.bilinear_fock_operator(a @ b - b @ a)
    fock_commutator = a_hat @ b_hat - b_hat @ a_hat

    assert np.allclose(
        fock_commutator,
        matrix_commutator_hat,
        rtol=1e-13,
        atol=1e-13,
    )


def test_fock_trace_equals_single_particle_determinant_for_a_product():
    rng = np.random.default_rng(2026)
    generators = [0.2 * rng.normal(size=(3, 3)) for _ in range(4)]

    fock_trace = sph.fock_trace_weight(generators)
    determinant = sph.determinant_weight(generators)

    assert np.isclose(fock_trace, determinant, rtol=1e-12, atol=1e-12)


def test_vacuum_and_one_particle_sectors_have_expected_action():
    a = np.array(
        [
            [0.3, -0.2],
            [0.4, 0.7],
        ]
    )
    a_hat = sph.bilinear_fock_operator(a)

    # Occupation-basis order is |00>, |10>, |01>, |11>.
    assert np.isclose(a_hat[0, 0], 0.0)
    assert np.allclose(a_hat[np.ix_([1, 2], [1, 2])], a)
    assert np.isclose(a_hat[3, 3], np.trace(a))


def test_invalid_generator_shapes_are_rejected():
    for bad in (np.ones(3), np.ones((2, 3))):
        try:
            sph.bilinear_fock_operator(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("a non-square generator must be rejected")


def test_random_split_generators_remain_in_identity_component():
    rng = np.random.default_rng(150605349)

    for n in (1, 2, 3):
        eta = sph.split_metric(n)
        for _ in range(12):
            generators = [
                sph.random_split_generator(n, rng, scale=0.25)
                for _ in range(5)
            ]
            for generator in generators:
                assert sph.split_lie_residual(generator, eta) < 1e-13

            product = sph.product_of_exponentials(generators)
            assert sph.split_group_residual(product, eta) < 1e-11
            assert sph.classify_split_component(product, eta) == "++"
            assert sph.determinant_i_plus(product) >= -1e-11


def test_all_four_o11_components_have_the_theorem_signs():
    # This rational boost obeys M^T eta M = eta exactly:
    # (5/3)^2 - (4/3)^2 = 1.
    boost = np.array([[5 / 3, 4 / 3], [4 / 3, 5 / 3]])
    expected_sign = {"++": 1, "--": -1, "-+": 0, "+-": 0}

    for component, sign in expected_sign.items():
        matrix = sph.split_component_representative(1, component) @ boost
        assert sph.classify_split_component(matrix) == component
        weight = sph.determinant_i_plus(matrix)
        if sign > 0:
            assert weight > 0
        elif sign < 0:
            assert weight < 0
        else:
            assert np.isclose(weight, 0.0, atol=1e-14)


def test_o11_negative_control_has_an_exact_rational_certificate():
    # M = -[[5/3, 4/3], [4/3, 5/3]] is in O^{--}(1,1).
    m00 = Fraction(-5, 3)
    m01 = Fraction(-4, 3)
    m10 = Fraction(-4, 3)
    m11 = Fraction(-5, 3)
    determinant = (1 + m00) * (1 + m11) - m01 * m10

    assert determinant == Fraction(-4, 3)


def test_component_classifier_rejects_a_matrix_outside_the_group():
    not_split_orthogonal = np.array([[1.0, 0.2], [0.0, 1.0]])

    try:
        sph.classify_split_component(not_split_orthogonal)
    except ValueError:
        pass
    else:
        raise AssertionError("classification outside O(n,n) must be rejected")


def test_four_site_hubbard_generators_respect_the_split_grading():
    order = sph.four_site_orbital_order()
    assert order == (
        (0, "up"),
        (2, "up"),
        (1, "down"),
        (3, "down"),
        (1, "up"),
        (3, "up"),
        (0, "down"),
        (2, "down"),
    )

    eta = sph.split_metric(4)
    hopping = sph.four_site_hopping_matrix(t_up=1.0, t_down=0.5)
    assert sph.split_lie_residual(hopping, eta) < 1e-14
    assert hopping[sph.hubbard_orbital_index(0, "up"), sph.hubbard_orbital_index(1, "up")] == -1.0
    assert hopping[sph.hubbard_orbital_index(0, "down"), sph.hubbard_orbital_index(1, "down")] == -0.5

    for site in range(4):
        for field in (-1, 1):
            vertex = sph.spin_flip_vertex(site, field, u=4.0, gamma=2.0)
            assert sph.split_lie_residual(vertex, eta) < 1e-14


def test_local_spin_flip_decomposition_is_an_operator_identity():
    residual = sph.onsite_spin_flip_decomposition_residual(u=4.0, gamma=2.0)
    assert residual < 1e-13


def test_configuration_protocol_covers_orders_zero_through_eight():
    configurations = sph.generate_hubbard_configurations(
        count=18,
        beta=2.0,
        seed=121,
    )

    assert [len(config) for config in configurations] == list(range(9)) * 2
    for config in configurations:
        assert all(0.0 <= vertex.tau <= 2.0 for vertex in config)
        assert all(config[i].tau <= config[i + 1].tau for i in range(len(config) - 1))
        assert all(vertex.site in range(4) for vertex in config)
        assert all(vertex.field in (-1, 1) for vertex in config)


def test_four_site_configuration_matches_direct_fock_trace():
    eta = sph.split_metric(4)
    hopping = sph.four_site_hopping_matrix(t_up=1.0, t_down=0.5)
    vertices = (
        sph.HubbardVertex(tau=0.35, site=2, field=1),
        sph.HubbardVertex(tau=1.40, site=1, field=-1),
    )
    generators = sph.hubbard_configuration_generators(
        vertices,
        beta=2.0,
        hopping=hopping,
        u=4.0,
        gamma=2.0,
    )

    assert all(sph.split_lie_residual(generator, eta) < 1e-13 for generator in generators)
    evolution = sph.product_of_exponentials(generators)
    assert sph.split_group_residual(evolution, eta) < 1e-10
    assert sph.classify_split_component(evolution, eta) == "++"

    determinant = sph.determinant_i_plus(evolution)
    fock_trace = sph.fock_trace_weight(generators)
    assert determinant >= -1e-10
    assert np.isclose(fock_trace, determinant, rtol=1e-10, atol=1e-10)


def test_longdouble_group_diagnostic_handles_the_worst_approved_configuration():
    eta = sph.split_metric(4)
    hopping = sph.four_site_hopping_matrix(t_up=1.0, t_down=0.5)
    vertices = (
        sph.HubbardVertex(0.0687759266190473, 0, -1),
        sph.HubbardVertex(0.6618829428460011, 0, -1),
        sph.HubbardVertex(0.9252722309765289, 1, 1),
        sph.HubbardVertex(1.3853364030460855, 0, 1),
        sph.HubbardVertex(1.73922510662912, 0, 1),
        sph.HubbardVertex(1.9050223820533136, 0, 1),
    )
    generators = sph.hubbard_configuration_generators(
        vertices,
        beta=2.0,
        hopping=hopping,
        u=4.0,
        gamma=2.0,
    )

    evolution, group_residual = sph.product_with_split_group_residual(
        generators,
        eta,
    )

    assert group_residual < 1e-10
    assert sph.classify_split_component(evolution, eta, atol=1e-9) == "++"


def test_structured_hubbard_propagators_match_scipy_expm():
    delta_tau = 0.37
    hopping = sph.four_site_hopping_matrix(t_up=1.0, t_down=0.5)
    free_structured = sph.four_site_free_propagator(
        delta_tau,
        t_up=1.0,
        t_down=0.5,
    )
    assert np.allclose(
        np.asarray(free_structured, dtype=float),
        sph.expm(-delta_tau * hopping),
        rtol=1e-13,
        atol=1e-13,
    )

    vertex_generator = sph.spin_flip_vertex(3, -1, u=4.0, gamma=2.0)
    vertex_structured = sph.spin_flip_propagator(
        3,
        -1,
        u=4.0,
        gamma=2.0,
    )
    assert np.allclose(
        np.asarray(vertex_structured, dtype=float),
        sph.expm(vertex_generator),
        rtol=1e-13,
        atol=1e-13,
    )


def test_structured_evolution_passes_the_worst_k8_absolute_residual():
    vertices = (
        sph.HubbardVertex(0.32142634473061626, 1, 1),
        sph.HubbardVertex(0.49554339080676724, 1, 1),
        sph.HubbardVertex(0.5546101111731154, 1, 1),
        sph.HubbardVertex(0.9122143871600221, 0, -1),
        sph.HubbardVertex(0.9503244428638153, 0, -1),
        sph.HubbardVertex(1.5170827567965983, 3, 1),
        sph.HubbardVertex(1.8229847193141804, 2, 1),
        sph.HubbardVertex(1.854364905203545, 2, -1),
    )
    evolution, group_residual = sph.hubbard_configuration_evolution(
        vertices,
        beta=2.0,
        t_up=1.0,
        t_down=0.5,
        u=4.0,
        gamma=2.0,
    )

    assert group_residual < 1e-10
    assert sph.classify_split_component(evolution, atol=1e-9) == "++"
