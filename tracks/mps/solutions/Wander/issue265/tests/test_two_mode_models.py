from __future__ import annotations

import numpy as np
import pytest

from src.two_mode_models import (
    free_parameter_names,
    hidden_mode_initial_condition,
    initial_hidden_field,
    parameters_for_model,
)


def test_registered_model_constraints_are_exact() -> None:
    gaussian = parameters_for_model("gaussian_diffusion", np.asarray([1.2]))
    assert gaussian.Dm == gaussian.Dphi == 1.2
    assert gaussian.lambda_m == gaussian.lambda_phi == gaussian.alpha == 0.0

    scalar = parameters_for_model("scalar_surrogate", np.asarray([1.1, 0.3]))
    assert scalar.lambda_m == 0.3
    assert scalar.lambda_phi == scalar.alpha == 0.0

    independent = parameters_for_model(
        "independent_two_burgers", np.asarray([0.9, 0.4])
    )
    assert independent.Dm == independent.Dphi == 0.9
    assert independent.lambda_m == independent.lambda_phi == 0.4
    assert independent.alpha == 0.0

    coupled = parameters_for_model(
        "coupled_two_mode", np.asarray([0.9, 1.2, 0.4, 0.7, -0.2])
    )
    assert coupled.Dm == 0.9
    assert coupled.Dphi == 1.2
    assert coupled.lambda_m == 0.4
    assert coupled.lambda_phi == 0.7
    assert coupled.alpha == -0.2


def test_coupled_reduces_to_independent_on_registered_manifold() -> None:
    independent = parameters_for_model(
        "independent_two_burgers", np.asarray([0.8, 0.6])
    )
    coupled = parameters_for_model(
        "coupled_two_mode", np.asarray([0.8, 0.8, 0.6, 0.6, 0.0])
    )
    assert coupled == independent


def test_hidden_initial_field_is_spin_flip_even_and_zero_mean() -> None:
    m0 = np.asarray([-0.2, -0.1, 0.3, 0.4])
    up = hidden_mode_initial_condition(m0, 0.7)
    down = hidden_mode_initial_condition(-m0, 0.7)
    np.testing.assert_array_equal(up, down)
    assert np.mean(up) == pytest.approx(0.0, abs=1e-15)


def test_response_and_equilibrium_force_zero_hidden_field() -> None:
    m0 = np.asarray([-0.2, 0.1, 0.3])
    for role in ("two_mode_response", "two_mode_equilibrium"):
        np.testing.assert_array_equal(
            initial_hidden_field(m0, alpha=9.0, role=role),
            np.zeros_like(m0),
        )


def test_parameter_bounds_fail_closed() -> None:
    with pytest.raises(ValueError, match="outside"):
        parameters_for_model("gaussian_diffusion", np.asarray([0.0]))
    with pytest.raises(ValueError, match="requires"):
        parameters_for_model("coupled_two_mode", np.ones(4))
