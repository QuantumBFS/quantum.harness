import jax
import jax.numpy as jnp
import numpy as np
import pytest

from qcontrol.config import SystemConfig
from qcontrol.objectives import normalized_infidelity, process_infidelity_from_unitary
from qcontrol.propagation import propagate
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system


jax.config.update("jax_enable_x64", True)


def test_normalized_coordinates_round_trip() -> None:
    space = PulseSpace.from_system(
        make_system(SystemConfig("two_qubit", 20, 4.0)),
        20,
    )
    pulse = jnp.linspace(-0.8, 0.8, space.parameter_count)
    np.testing.assert_allclose(space.to_normalized(space.to_physical(pulse)), pulse)
    assert space.to_physical(pulse).shape == (4, 20)


@pytest.mark.parametrize(
    "pulse",
    [
        jnp.zeros(23),
        jnp.zeros((2, 12)),
        jnp.full(24, jnp.nan),
        jnp.full(24, jnp.inf),
        jnp.full(24, 1.01),
        jnp.full(24, -1.01),
    ],
)
def test_normalized_coordinates_reject_invalid_values(pulse: jax.Array) -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    with pytest.raises(ValueError, match="normalized"):
        space.to_physical(pulse)


@pytest.mark.parametrize(
    ("control_count", "segments", "scales", "bound"),
    [
        (0, 12, (4.0,), 1.0),
        (1, 0, (4.0,), 1.0),
        (2, 12, (4.0,), 1.0),
        (1, 12, (0.0,), 1.0),
        (1, 12, (np.inf,), 1.0),
        (1, 12, (4.0,), 0.0),
        (1, 12, (4.0,), np.nan),
    ],
)
def test_pulse_space_rejects_invalid_construction(
    control_count: int,
    segments: int,
    scales: tuple[float, ...],
    bound: float,
) -> None:
    with pytest.raises(ValueError):
        PulseSpace(control_count, segments, scales, bound)


def test_physical_coordinates_reject_wrong_shape_nonfinite_and_out_of_bounds() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    invalid = (
        jnp.zeros(24),
        jnp.zeros((2, 11)),
        jnp.full((2, 12), jnp.nan),
        jnp.full((2, 12), 4.01),
    )
    for pulse in invalid:
        with pytest.raises(ValueError, match="physical"):
            space.to_normalized(pulse)


def test_propagator_is_unitary() -> None:
    system = make_system(SystemConfig("two_qubit", 20, 4.0))
    pulse = jnp.zeros((4, 20))
    unitary = propagate(system, pulse)
    np.testing.assert_allclose(
        unitary.conj().T @ unitary,
        jnp.eye(4),
        rtol=0.0,
        atol=1e-12,
    )
    assert unitary.dtype == jnp.complex128


def test_propagator_uses_segment_order_and_duration() -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0))
    pulse = jnp.array([[0.2, -0.3], [0.4, 0.1]], dtype=jnp.float64)
    forward = propagate(system, pulse, duration=0.7)
    reversed_pulse = propagate(system, pulse[:, ::-1], duration=0.7)
    assert not np.allclose(forward, reversed_pulse)
    np.testing.assert_allclose(
        propagate(system, pulse, duration=0.0),
        jnp.eye(system.dimension),
        rtol=0.0,
        atol=1e-15,
    )


@pytest.mark.parametrize(
    ("pulse", "duration"),
    [
        (jnp.zeros(24), 1.0),
        (jnp.zeros((3, 12)), 1.0),
        (jnp.zeros((2, 0)), 1.0),
        (jnp.full((2, 12), jnp.nan), 1.0),
        (jnp.zeros((2, 12)), -1.0),
        (jnp.zeros((2, 12)), np.inf),
        (jnp.zeros((2, 12)), True),
    ],
)
def test_propagator_rejects_invalid_inputs(
    pulse: jax.Array,
    duration: object,
) -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    with pytest.raises(ValueError):
        propagate(system, pulse, duration=duration)  # type: ignore[arg-type]


def test_infidelity_is_global_phase_invariant() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    pulse = jnp.zeros((2, 12))
    unitary = propagate(system, pulse)
    assert np.isclose(
        process_infidelity_from_unitary(unitary, system.target),
        process_infidelity_from_unitary(jnp.exp(0.3j) * unitary, system.target),
    )


def test_reported_infidelity_is_bounded_but_internal_loss_is_unclipped() -> None:
    target = jnp.eye(2, dtype=jnp.complex128)
    nonunitary = 2.0 * target
    assert process_infidelity_from_unitary(nonunitary, target) == 0.0

    system = make_system(SystemConfig("one_qubit", 1, 4.0))
    space = PulseSpace.from_system(system, 1)
    value = normalized_infidelity(jnp.zeros(space.parameter_count), system, space)
    expected_unitary = propagate(system, jnp.zeros((2, 1)))
    overlap = jnp.trace(jnp.asarray(system.target).conj().T @ expected_unitary)
    expected = 1.0 - jnp.real(overlap.conj() * overlap) / system.dimension**2
    np.testing.assert_allclose(value, expected, rtol=0.0, atol=1e-15)


def test_gradient_matches_central_difference_and_is_real_float64() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    x = jnp.linspace(-0.1, 0.1, space.parameter_count)
    value, gradient = jax.value_and_grad(normalized_infidelity)(x, system, space)
    direction = jnp.arange(space.parameter_count, dtype=jnp.float64)
    direction /= jnp.linalg.norm(direction)
    step = 1e-5
    finite = (
        normalized_infidelity(x + step * direction, system, space)
        - normalized_infidelity(x - step * direction, system, space)
    ) / (2 * step)
    np.testing.assert_allclose(
        jnp.vdot(gradient, direction),
        finite,
        rtol=1e-6,
        atol=1e-8,
    )
    assert value.dtype == jnp.float64
    assert gradient.dtype == jnp.float64
    assert not jnp.iscomplexobj(gradient)
