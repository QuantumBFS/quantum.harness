import numpy as np
import pytest

from xxzcert.rg_dual_barrier import (
    RGConvergenceError,
    _strictly_interior_start,
    _warm_start_from_duals,
    build_rg_dual_barrier_model,
    qualify_rg_candidate,
    rg_barrier_hessian_product,
    rg_barrier_value_gradient,
    rg_dual_slacks,
    solve_rg_dual_barrier,
)
from xxzcert.rg_relaxation import (
    RGRelaxationCandidate,
    alternating_neel_mps,
    solve_rg_lti,
)


def _candidate_with(**changes):
    payload = {
        "delta": 1.0,
        "depth": 4,
        "bond_dimension": 2,
        "raw_lower": -0.6,
        "status": "barrier-ok",
        "omega_dimension": 16,
        "rho3": np.empty((0, 0), dtype=np.complex128),
        "omegas": (),
        "max_equality_residual": 0.0,
        "minimum_primal_eigenvalue": np.nan,
        "dual_objective": -0.6,
        "dual_slack_min_eigenvalues": (1e-6, 2e-6),
        "dual_stationarity_residual": 0.0,
        "equality_duals": (0.6, np.eye(4), np.eye(8), np.eye(8)),
    }
    payload.update(changes)
    return RGRelaxationCandidate(**payload)


@pytest.mark.parametrize(
    "candidate",
    [
        _candidate_with(raw_lower=np.nan),
        _candidate_with(equality_duals=(np.inf,)),
        _candidate_with(dual_slack_min_eigenvalues=(-1e-6, 1e-6)),
        _candidate_with(status="barrier-line-search-stopped"),
        _candidate_with(raw_lower=-5.673211000495852),
    ],
)
def test_unstable_rg_candidates_are_rejected(candidate):
    with pytest.raises(RGConvergenceError):
        qualify_rg_candidate(candidate)


def test_finite_feasible_rg_candidate_is_qualified():
    assert qualify_rg_candidate(_candidate_with()).raw_lower == -0.6


def test_shallower_duals_give_a_strictly_feasible_deeper_warm_start():
    tensor = alternating_neel_mps()
    shallow_model = build_rg_dual_barrier_model(
        1.0, tensor, depth=4, use_symmetry=True
    )
    shallow_parameters = _strictly_interior_start(shallow_model)
    shallow_y, shallow_matrices = shallow_model.unpack(shallow_parameters)
    deep_model = build_rg_dual_barrier_model(
        1.0, tensor, depth=5, use_symmetry=True
    )
    cold = _strictly_interior_start(deep_model)
    warm = _warm_start_from_duals(
        deep_model, (shallow_y - 0.1, *shallow_matrices)
    )
    assert warm.shape == (deep_model.parameter_count,)
    assert min(
        np.linalg.eigvalsh(slack)[0]
        for slack in rg_dual_slacks(deep_model, warm)
    ) > 0
    assert warm[0] < cold[0]


def test_rg_barrier_gradient_and_hessian_products():
    model = build_rg_dual_barrier_model(
        1.0, alternating_neel_mps(), depth=4
    )
    parameters = _strictly_interior_start(model)
    direction = np.linspace(-0.01, 0.01, model.parameter_count)
    step = 1e-6
    value, gradient, minimum = rg_barrier_value_gradient(
        model, parameters, 1e-2
    )
    assert np.isfinite(value)
    assert minimum > 0
    numerical_gradient = np.empty_like(gradient)
    for index in range(model.parameter_count):
        basis = np.zeros(model.parameter_count)
        basis[index] = step
        forward = rg_barrier_value_gradient(
            model, parameters + basis, 1e-2
        )[0]
        backward = rg_barrier_value_gradient(
            model, parameters - basis, 1e-2
        )[0]
        numerical_gradient[index] = (forward - backward) / (2 * step)
    assert np.allclose(
        gradient, numerical_gradient, rtol=3e-5, atol=3e-7
    )
    analytic_hessian = rg_barrier_hessian_product(
        model,
        parameters,
        direction,
        1e-2,
        regularization=0,
    )
    forward_gradient = rg_barrier_value_gradient(
        model, parameters + step * direction, 1e-2
    )[1]
    backward_gradient = rg_barrier_value_gradient(
        model, parameters - step * direction, 1e-2
    )[1]
    numerical_hessian = (
        forward_gradient - backward_gradient
    ) / (2 * step)
    assert np.allclose(
        analytic_hessian, numerical_hessian, rtol=3e-5, atol=3e-7
    )


def test_matrix_free_rg_dual_matches_small_conic_problem():
    tensor = alternating_neel_mps()
    conic = solve_rg_lti(1.0, tensor, depth=4)
    barrier = solve_rg_dual_barrier(
        1.0,
        tensor,
        depth=4,
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
    )
    assert barrier.raw_lower <= conic.raw_lower + 1e-6
    assert conic.raw_lower - barrier.raw_lower < 2e-4
    assert min(barrier.dual_slack_min_eigenvalues) > 0
