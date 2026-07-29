from __future__ import annotations

from itertools import product

import numpy as np
from scipy.linalg import expm

from oracle.adjoint_lift import (
    adjoint_cosh_decomposition,
    adjoint_lift,
    adjoint_lift_history,
    adjoint_lifted_generator,
    commutation_metric,
    commutation_metric_residual,
)


def test_adjoint_lift_is_closed_and_has_nonnegative_weight() -> None:
    factors = (
        expm(np.asarray([[0.2, 0.4, 0.0], [0.1, -0.3, 0.2], [0.0, 0.5, 0.1]])),
        expm(np.asarray([[-0.4, 0.0, 0.3], [0.2, 0.5, -0.1], [0.4, 0.0, 0.2]])),
        expm(np.asarray([[0.1, -0.2, 0.0], [0.6, 0.3, 0.4], [0.0, -0.1, -0.2]])),
    )
    history = adjoint_lift_history(factors)

    assert history.closure_residual < 1e-12
    assert history.weight >= -1e-10
    assert abs(history.weight - history.pairing_formula) < 1e-8


def test_adjoint_lift_preserves_the_swap_metric() -> None:
    matrix = expm(
        np.asarray(
            [
                [0.2, 0.4, -0.1],
                [0.0, -0.3, 0.7],
                [0.5, 0.0, 0.1],
            ]
        )
    )
    metric = commutation_metric(3)
    eigenvalues = np.linalg.eigvalsh(metric)

    assert np.count_nonzero(eigenvalues > 0.0) == 6
    assert np.count_nonzero(eigenvalues < 0.0) == 3
    assert commutation_metric_residual(matrix) < 1e-12


def test_exponential_generator_identity() -> None:
    generator = np.asarray(
        [
            [0.3, 0.5, 0.0],
            [0.5, -0.4, 0.2],
            [0.0, 0.2, 0.7],
        ]
    )
    coupling = 0.37

    assert np.allclose(
        adjoint_lift(expm(coupling * generator)),
        expm(coupling * adjoint_lifted_generator(generator)),
        atol=1e-12,
    )


def test_adjoint_cosh_is_an_exact_positive_hermitian_gate() -> None:
    kinetic = np.asarray([[0.2, 0.7], [0.7, -0.1]])
    channel = np.asarray([[1.0, 0.3], [0.3, -0.6]])
    decomposition = adjoint_cosh_decomposition(
        time_step=0.15,
        kinetic_generator=kinetic,
        channel_generator=channel,
        field_coupling=0.55,
    )
    auxiliary_average = 0.5 * sum(
        decomposition.fock_field_gates,
        start=np.zeros_like(decomposition.fock_half_kinetic),
    )
    target = (
        decomposition.fock_half_kinetic
        @ decomposition.interaction_gate
        @ decomposition.fock_half_kinetic
    )

    assert np.allclose(auxiliary_average, target, atol=1e-11)
    assert np.allclose(auxiliary_average, auxiliary_average.T, atol=1e-11)
    assert np.min(np.linalg.eigvalsh(auxiliary_average)) > 0.0


def test_short_noncommuting_adjoint_histories_are_positive() -> None:
    decomposition = adjoint_cosh_decomposition(
        time_step=0.15,
        kinetic_generator=np.asarray([[0.2, 0.7], [0.7, -0.1]]),
        channel_generator=np.asarray([[1.0, 0.3], [0.3, -0.6]]),
        field_coupling=0.55,
    )
    factors = decomposition.base_field_propagators

    assert np.linalg.norm(factors[0] @ factors[1] - factors[1] @ factors[0]) > 0.1
    for depth in range(1, 9):
        for word in product(range(2), repeat=depth):
            history = adjoint_lift_history(
                tuple(factors[index] for index in word)
            )
            assert history.weight > 0.0
