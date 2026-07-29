from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from qcontrol.closed_loop import make_full_space, make_model_hessian_space
from qcontrol.config import SystemConfig
from qcontrol.landscape import (
    EndpointPolishingError,
    _leading_eigenpairs,
    _matrix_free_rank_diagnostics,
    analyze_landscape,
    dense_hessian,
    endpoint_jacobian,
    hessian_vector_product,
    polish_endpoint,
)
from qcontrol.objectives import normalized_infidelity
from qcontrol.open_loop import OpenLoopResult, optimize_open_loop
from qcontrol.propagation import propagate
from qcontrol.pulses import PulseSpace
from qcontrol.systems import ControlSystem, make_system


@pytest.fixture(scope="module")
def accepted_one_qubit() -> tuple[
    ControlSystem,
    PulseSpace,
    OpenLoopResult,
    Callable[[jax.Array], jax.Array],
]:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    accepted = optimize_open_loop(system, space, seed=5, starts=5)
    loss_fn = lambda point: normalized_infidelity(point, system, space)
    return system, space, accepted, loss_fn


@pytest.fixture(scope="module")
def accepted_two_qubit() -> tuple[ControlSystem, PulseSpace, OpenLoopResult]:
    system = make_system(SystemConfig("two_qubit", 20, 4.0))
    space = PulseSpace.from_system(system, 20)
    accepted = optimize_open_loop(system, space, seed=5, starts=5)
    return system, space, accepted


def test_hvp_matches_dense_hessian(
    accepted_one_qubit: tuple[
        ControlSystem,
        PulseSpace,
        OpenLoopResult,
        Callable[[jax.Array], jax.Array],
    ],
) -> None:
    _, _, accepted, loss_fn = accepted_one_qubit
    point = jnp.asarray(accepted.normalized_pulse, dtype=jnp.float64)
    dense = dense_hessian(loss_fn, point)
    vector = jnp.linspace(-1.0, 1.0, point.size, dtype=jnp.float64)

    actual = jax.jit(hessian_vector_product, static_argnums=0)(
        loss_fn,
        point,
        vector,
    )

    np.testing.assert_allclose(actual, dense @ np.asarray(vector), rtol=1e-7, atol=1e-9)


def test_dense_hessian_is_bounded_to_eighty_parameters() -> None:
    point = jnp.zeros(81, dtype=jnp.float64)
    with pytest.raises(ValueError, match="at most 80"):
        dense_hessian(lambda x: jnp.vdot(x, x), point)


def test_matrix_free_spectrum_includes_large_negative_modes() -> None:
    diagonal = jnp.asarray([5.0, 2.0, 0.1, -12.0, -3.0, 0.01])
    point = jnp.zeros(diagonal.size, dtype=jnp.float64)
    loss_fn = lambda x: 0.5 * jnp.vdot(x, diagonal * x)

    values, vectors = _leading_eigenpairs(loss_fn, point, count=4)
    ranks, lower_bounds = _matrix_free_rank_diagnostics(
        values,
        spectrum_truncated=True,
    )

    np.testing.assert_allclose(values, [-12.0, 5.0, -3.0, 2.0], atol=1e-12)
    np.testing.assert_allclose(vectors.T @ vectors, np.eye(4), atol=1e-12)
    assert ranks == {1e-6: 4, 1e-8: 4, 1e-10: 4}
    assert lower_bounds == {1e-6: True, 1e-8: True, 1e-10: True}


def test_one_qubit_geometry_has_primary_rank_three(
    accepted_one_qubit: tuple[
        ControlSystem,
        PulseSpace,
        OpenLoopResult,
        Callable[[jax.Array], jax.Array],
    ],
) -> None:
    system, space, accepted, _ = accepted_one_qubit
    result = analyze_landscape(system, space, accepted, leading_count=6)

    assert set(result.hessian_ranks) == {1e-6, 1e-8, 1e-10}
    assert set(result.jacobian_ranks) == {1e-6, 1e-8, 1e-10}
    assert result.hessian_ranks[1e-8] == 3
    assert result.jacobian_ranks[1e-8] == 3
    assert result.eigenvalue_ordering == "descending absolute"
    assert result.polishing.loss <= 1e-12
    assert result.polishing.gradient_norm <= 1e-10
    assert result.polishing.residual_norm <= 1e-12
    assert not any(result.hessian_rank_is_lower_bound.values())
    np.testing.assert_allclose(
        result.model_basis.T @ result.model_basis,
        np.eye(24),
        rtol=0.0,
        atol=1e-10,
    )
    assert result.model_basis.shape == (24, 24)
    assert result.search_basis_available_columns == 24
    assert np.all(
        np.abs(result.dense_eigenvalues[:-1])
        >= np.abs(result.dense_eigenvalues[1:])
    )
    np.testing.assert_allclose(
        result.endpoint_basis.T @ result.endpoint_basis,
        np.eye(3),
        rtol=0.0,
        atol=1e-10,
    )
    assert result.dense_hessian is not None
    assert result.dense_eigenvalues is not None
    assert result.dense_eigenvectors is not None
    assert result.dense_hvp_projector_residuals[1e-8] <= 1e-7
    assert (
        float(np.max(result.dense_hvp_principal_angles[1e-8]))
        <= 1e-6
    )


@pytest.mark.integration
def test_dense_search_basis_supports_all_high_k_spaces(
    accepted_one_qubit,
    accepted_two_qubit,
) -> None:
    one_system, one_space, one_accepted, _ = accepted_one_qubit
    one = analyze_landscape(one_system, one_space, one_accepted, leading_count=6)
    one_k24 = make_model_hessian_space(
        np.asarray(one.polishing.normalized_pulse),
        one.model_basis,
        dimension=24,
    )
    assert one_k24.dimension == 24
    assert one.hessian_ranks[1e-8] == 3

    two_system, two_space, two_accepted = accepted_two_qubit
    two = analyze_landscape(two_system, two_space, two_accepted, leading_count=20)
    assert two.model_basis.shape == (80, 80)
    assert two.search_basis_available_columns == 80
    assert two.hessian_ranks[1e-8] == 15
    spaces = [
        make_model_hessian_space(
            np.asarray(two.polishing.normalized_pulse),
            two.model_basis,
            dimension=dimension,
        )
        for dimension in (20, 30, 80)
    ]
    assert [space.dimension for space in spaces] == [20, 30, 80]
    for left, right in ((spaces[0], spaces[1]),):
        np.testing.assert_allclose(
            left.basis @ left.basis.T,
            right.basis[:, : left.dimension] @ right.basis[:, : left.dimension].T,
            atol=1e-10,
        )
    full = make_full_space(spaces[-1].origin)
    delta = np.linspace(-0.01, 0.01, 80)
    np.testing.assert_allclose(
        full.to_pulse(delta),
        spaces[-1].to_pulse(spaces[-1].basis.T @ delta),
        atol=1e-10,
    )


def test_endpoint_jacobian_is_branch_free_and_has_expected_shape(
    accepted_one_qubit: tuple[
        ControlSystem,
        PulseSpace,
        OpenLoopResult,
        Callable[[jax.Array], jax.Array],
    ],
) -> None:
    system, space, accepted, _ = accepted_one_qubit
    point = np.asarray(accepted.normalized_pulse)
    jacobian = endpoint_jacobian(system, space, point)

    assert jacobian.shape == (3, 24)
    assert np.all(np.isfinite(jacobian))
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    assert (
        np.linalg.matrix_rank(jacobian, tol=1e-10 * singular_values[0]) == 3
    )


@pytest.mark.integration
def test_two_qubit_unpolished_hessian_exposes_residual_curvature(
    accepted_two_qubit: tuple[ControlSystem, PulseSpace, OpenLoopResult],
) -> None:
    system, space, accepted = accepted_two_qubit
    result = analyze_landscape(
        system,
        space,
        accepted,
        leading_count=20,
        polish=False,
    )

    assert result.polishing is None
    assert result.hessian_ranks[1e-8] == 19
    assert result.jacobian_ranks[1e-8] == 15


@pytest.mark.integration
def test_endpoint_polishing_is_bounded_and_reproducible(
    accepted_two_qubit: tuple[ControlSystem, PulseSpace, OpenLoopResult],
) -> None:
    system, space, accepted = accepted_two_qubit

    first = analyze_landscape(system, space, accepted, leading_count=20)
    second = analyze_landscape(system, space, accepted, leading_count=20)
    assert first.polishing is not None
    assert second.polishing is not None
    first_polish = first.polishing
    second_polish = second.polishing

    np.testing.assert_allclose(
        first_polish.normalized_pulse,
        second_polish.normalized_pulse,
        rtol=0.0,
        atol=1e-13,
    )
    assert first_polish.loss == pytest.approx(second_polish.loss, abs=1e-15)
    assert first_polish.residual_norm == pytest.approx(
        second_polish.residual_norm,
        abs=1e-15,
    )
    assert first.hessian_ranks == second.hessian_ranks
    assert first.jacobian_ranks == second.jacobian_ranks
    assert first.hessian_ranks == {1e-6: 15, 1e-8: 15, 1e-10: 15}
    assert first_polish.converged
    assert second_polish.converged
    for polishing in (first_polish, second_polish):
        assert polishing.evaluations > 0
        assert polishing.jacobian_evaluations > 0
        assert polishing.evaluations >= polishing.jacobian_evaluations
        assert polishing.status > 0
        assert polishing.message
    assert first_polish.loss <= 1e-12
    assert first_polish.gradient_norm <= 1e-10
    assert first_polish.projected_gradient_norm <= 1e-10
    assert first_polish.residual_norm <= 1e-12
    assert first_polish.phase_consistency_error <= 1e-12
    assert first_polish.step_norm > 0.0
    assert np.all(np.abs(first_polish.normalized_pulse) <= 1.0)


@pytest.mark.integration
def test_endpoint_polishing_fails_closed_when_budget_is_exhausted(
    accepted_two_qubit: tuple[ControlSystem, PulseSpace, OpenLoopResult],
) -> None:
    system, space, accepted = accepted_two_qubit

    with pytest.raises(EndpointPolishingError, match="did not converge") as raised:
        polish_endpoint(system, space, accepted, max_nfev=1)

    assert not raised.value.diagnostics.converged
    assert 0 < raised.value.diagnostics.evaluations <= 1
    assert raised.value.diagnostics.residual_norm > 1e-12


@pytest.mark.parametrize(
    ("candidate", "message"),
    [
        (np.full(80, 1.01), "bounds"),
        (np.zeros(80), "target"),
    ],
)
def test_endpoint_polishing_rejects_invalid_solver_candidate(
    accepted_two_qubit: tuple[ControlSystem, PulseSpace, OpenLoopResult],
    monkeypatch: pytest.MonkeyPatch,
    candidate: np.ndarray,
    message: str,
) -> None:
    system, space, accepted = accepted_two_qubit
    fake_result = SimpleNamespace(
        x=candidate,
        success=True,
        status=1,
        message="fake convergence",
        nfev=1,
        njev=1,
        cost=0.0,
        optimality=0.0,
    )
    monkeypatch.setattr("qcontrol.landscape.least_squares", lambda *args, **kwargs: fake_result)

    with pytest.raises(EndpointPolishingError, match=message) as raised:
        polish_endpoint(system, space, accepted)

    assert not raised.value.diagnostics.converged


@pytest.mark.parametrize(
    "replacement",
    [
        SimpleNamespace(),
        SimpleNamespace(x=object()),
        SimpleNamespace(x=np.zeros((24, 1))),
        SimpleNamespace(x=np.zeros(23)),
        SimpleNamespace(
            x=np.zeros(24),
            success=True,
            status=np.nan,
            message="bad status",
            nfev=1,
            njev=1,
            cost=0.0,
            optimality=0.0,
        ),
        SimpleNamespace(
            x=np.zeros(24),
            success=True,
            status=1,
            message="bad cost",
            nfev=1,
            njev=1,
            cost=np.nan,
            optimality=0.0,
        ),
        SimpleNamespace(
            x=np.zeros(24),
            success=True,
            status=1,
            message="bad optimality",
            nfev=1,
            njev=1,
            cost=0.0,
            optimality=np.inf,
        ),
    ],
)
def test_endpoint_polishing_fails_closed_for_malformed_scipy_result(
    accepted_one_qubit: tuple[
        ControlSystem,
        PulseSpace,
        OpenLoopResult,
        Callable[[jax.Array], jax.Array],
    ],
    monkeypatch: pytest.MonkeyPatch,
    replacement: SimpleNamespace,
) -> None:
    system, space, accepted, _ = accepted_one_qubit
    monkeypatch.setattr(
        "qcontrol.landscape.least_squares",
        lambda *args, **kwargs: replacement,
    )

    with pytest.raises(EndpointPolishingError, match="malformed") as raised:
        polish_endpoint(system, space, accepted)

    diagnostics = raised.value.diagnostics
    assert not diagnostics.converged
    assert diagnostics.status == -1
    assert diagnostics.message
    assert len(diagnostics.normalized_pulse) == space.parameter_count
    assert np.all(np.isfinite(diagnostics.normalized_pulse))


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit])
def test_endpoint_polishing_preserves_process_control_exceptions(
    accepted_one_qubit: tuple[
        ControlSystem,
        PulseSpace,
        OpenLoopResult,
        Callable[[jax.Array], jax.Array],
    ],
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[BaseException],
) -> None:
    system, space, accepted, _ = accepted_one_qubit

    def interrupt(*args: object, **kwargs: object) -> object:
        raise exception_type()

    monkeypatch.setattr("qcontrol.landscape.least_squares", interrupt)
    with pytest.raises(exception_type):
        polish_endpoint(system, space, accepted)


@pytest.mark.integration
def test_two_qubit_scientific_geometry_and_held_pulse_refinement(
    accepted_two_qubit: tuple[ControlSystem, PulseSpace, OpenLoopResult],
) -> None:
    system, space, accepted = accepted_two_qubit
    coarse = analyze_landscape(system, space, accepted, leading_count=20)

    assert coarse.polishing is not None
    coarse_point = np.asarray(coarse.polishing.normalized_pulse).reshape(
        space.control_count,
        space.segments,
    )
    refined_point = np.repeat(coarse_point, 2, axis=1).reshape(-1)
    refined_space = PulseSpace.from_system(system, 2 * space.segments)
    np.testing.assert_allclose(
        propagate(system, refined_space.to_physical(refined_point)),
        propagate(system, space.to_physical(coarse_point.reshape(-1))),
        rtol=0.0,
        atol=2e-12,
    )
    refined_loss = float(normalized_infidelity(refined_point, system, refined_space))
    refined = analyze_landscape(
        system,
        refined_space,
        OpenLoopResult(
            normalized_pulse=tuple(refined_point),
            loss=refined_loss,
            gradient_norm=float("nan"),
            starts=accepted.starts,
            evaluations=accepted.evaluations,
        ),
        leading_count=20,
        dense_validation=False,
        polish=False,
    )

    assert coarse.hessian_ranks == {1e-6: 15, 1e-8: 15, 1e-10: 15}
    assert coarse.jacobian_ranks == {1e-6: 15, 1e-8: 15, 1e-10: 15}
    assert refined.hessian_ranks == {1e-6: 15, 1e-8: 15, 1e-10: 15}
    assert refined.jacobian_ranks == {1e-6: 15, 1e-8: 15, 1e-10: 15}
    assert refined.dense_hessian is None
    assert refined.search_basis_available_columns == 20
    assert refined.model_basis.shape == (160, 20)
    assert refined.dense_hvp_projector_residuals == {}
    assert not any(refined.hessian_rank_is_lower_bound.values())
    assert coarse.dense_hvp_projector_residuals[1e-8] <= 1e-7
