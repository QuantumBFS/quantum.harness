from fractions import Fraction

import numpy as np

from xxzcert.lti_su2_reflection import (
    lift_su2_reflection_dual_to_u1,
    solve_su2_reflection_lti,
)
from xxzcert.lti_su2_reflection_dual import (
    barrier_hessian_product,
    barrier_value_gradient,
    build_su2_reflection_dual_model,
    solve_su2_reflection_dual_barrier,
)
from xxzcert.lti_u1_rational import (
    make_u1_lti_dual_witness,
    verify_u1_lti_dual_witness,
)


def test_logdet_gradient_matches_central_difference():
    model = build_su2_reflection_dual_model(5)
    parameters = np.zeros(model.parameter_count)
    parameters[0] = 1.0
    parameters[1:] = np.linspace(
        -1e-3, 1e-3, model.parameter_count - 1
    )
    value, gradient, minimum = barrier_value_gradient(
        model, parameters, 1e-2
    )
    assert np.isfinite(value)
    assert minimum > 0
    step = 1e-6
    for index in range(model.parameter_count):
        forward = parameters.copy()
        backward = parameters.copy()
        forward[index] += step
        backward[index] -= step
        forward_value = barrier_value_gradient(
            model, forward, 1e-2
        )[0]
        backward_value = barrier_value_gradient(
            model, backward, 1e-2
        )[0]
        numerical = (forward_value - backward_value) / (2 * step)
        assert np.isclose(
            gradient[index], numerical, rtol=2e-5, atol=2e-7
        )


def test_logdet_hessian_product_matches_gradient_difference():
    model = build_su2_reflection_dual_model(5)
    parameters = np.zeros(model.parameter_count)
    parameters[0] = 1.0
    direction = np.linspace(-0.1, 0.1, model.parameter_count)
    analytic = barrier_hessian_product(
        model,
        parameters,
        direction,
        1e-2,
        regularization=0.0,
    )
    step = 1e-6
    forward = barrier_value_gradient(
        model, parameters + step * direction, 1e-2
    )[1]
    backward = barrier_value_gradient(
        model, parameters - step * direction, 1e-2
    )[1]
    numerical = (forward - backward) / (2 * step)
    assert np.allclose(analytic, numerical, rtol=2e-5, atol=2e-7)


def test_matrix_free_dual_produces_exact_witness():
    conic = solve_su2_reflection_lti(
        5,
        solver_options={"eps": 1e-7, "max_iters": 20_000},
    )
    candidate = solve_su2_reflection_dual_barrier(
        5,
        barrier_parameters=(
            1e-1,
            3e-2,
            1e-2,
            3e-3,
            1e-3,
            3e-4,
            1e-4,
            3e-5,
            1e-5,
        ),
        max_iterations=80,
    )
    lifted = lift_su2_reflection_dual_to_u1(candidate)
    witness = make_u1_lti_dual_witness(
        Fraction(1), lifted, scale=10**8
    )
    assert verify_u1_lti_dual_witness(Fraction(1), witness)
    assert (
        conic.raw_lower - float(witness.energy_density_lower)
        < 2e-4
    )
