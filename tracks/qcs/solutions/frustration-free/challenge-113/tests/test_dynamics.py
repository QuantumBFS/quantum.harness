import jax
import jax.numpy as jnp
import numpy as np
import pytest
from jax.scipy.linalg import expm

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
        (1, 12, (4.0,), 0.5),
        (1, 12, (4.0,), 1.01),
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


def test_propagator_left_multiplies_segments_in_chronological_order() -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0))
    pulse = jnp.array([[0.2, -0.3], [0.4, 0.1]], dtype=jnp.float64)
    duration = 0.7
    controls = jnp.stack(tuple(jnp.asarray(control) for control in system.controls))
    drift = jnp.asarray(system.drift)
    segment_0 = expm(
        -1.0j
        * duration
        / 2
        * (drift + jnp.tensordot(pulse[:, 0], controls, axes=1))
    )
    segment_1 = expm(
        -1.0j
        * duration
        / 2
        * (drift + jnp.tensordot(pulse[:, 1], controls, axes=1))
    )
    actual = propagate(system, pulse, duration=duration)

    np.testing.assert_allclose(
        actual,
        segment_1 @ segment_0,
        rtol=0.0,
        atol=1e-14,
    )
    assert not np.allclose(actual, segment_0 @ segment_1)


def test_propagator_supports_jitted_traced_duration() -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0))
    pulse = jnp.array([[0.2, -0.3], [0.4, 0.1]], dtype=jnp.float64)
    jitted = jax.jit(lambda value: propagate(system, pulse, duration=value))
    expected = propagate(system, pulse, 0.7)
    np.testing.assert_allclose(propagate(system, pulse, jnp.float64(0.7)), expected)
    np.testing.assert_allclose(jitted(jnp.float64(0.7)), expected)


def test_propagator_uses_system_duration_and_allows_explicit_override() -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0, duration=1.7))
    pulse = jnp.array([[0.2, -0.3], [0.4, 0.1]], dtype=jnp.float64)

    np.testing.assert_allclose(propagate(system, pulse), propagate(system, pulse, 1.7))
    assert not np.allclose(propagate(system, pulse), propagate(system, pulse, 0.7))


def test_jitted_propagator_uses_immutable_system_duration() -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0, duration=1.7))
    pulse = jnp.array([[0.2, -0.3], [0.4, 0.1]], dtype=jnp.float64)
    jitted = jax.jit(lambda values: propagate(system, values))

    np.testing.assert_allclose(jitted(pulse), propagate(system, pulse, 1.7))


@pytest.mark.parametrize(
    ("pulse", "duration"),
    [
        (jnp.full((2, 2), jnp.nan), jnp.float64(1.0)),
        (jnp.full((2, 2), jnp.inf), jnp.float64(1.0)),
        (jnp.zeros((2, 2)), jnp.float64(-1.0)),
        (jnp.zeros((2, 2)), jnp.float64(jnp.inf)),
    ],
)
def test_jitted_propagator_returns_nonfinite_sentinel_for_invalid_tracers(
    pulse: jax.Array,
    duration: jax.Array,
) -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0))
    result = jax.jit(lambda values, time: propagate(system, values, time))(
        pulse,
        duration,
    )
    assert jnp.all(~jnp.isfinite(result))


@pytest.mark.parametrize(
    ("pulse", "duration"),
    [
        (jnp.zeros(24), 1.0),
        (jnp.zeros((3, 12)), 1.0),
        (jnp.zeros((2, 0)), 1.0),
        (jnp.full((2, 12), jnp.nan), 1.0),
        (jnp.zeros((2, 12)), -1.0),
        (jnp.zeros((2, 12)), 0.0),
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


def test_normalized_infidelity_uses_system_duration() -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0, duration=1.7))
    space = PulseSpace.from_system(system, 2)
    normalized = jnp.linspace(-0.2, 0.2, space.parameter_count)
    physical = space.to_physical(normalized)
    unitary = propagate(system, physical, duration=system.duration)
    overlap = jnp.trace(jnp.asarray(system.target).conj().T @ unitary)
    expected = 1.0 - jnp.real(overlap.conj() * overlap) / system.dimension**2

    np.testing.assert_allclose(
        normalized_infidelity(normalized, system, space),
        expected,
        rtol=0.0,
        atol=1e-15,
    )


@pytest.mark.parametrize(
    "invalid_value",
    [1.01, -1.01, jnp.nan, jnp.inf, -jnp.inf],
)
def test_jitted_normalized_infidelity_returns_infinity_for_invalid_controls(
    invalid_value: float,
) -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    pulse = jnp.zeros(space.parameter_count).at[3].set(invalid_value)
    jitted = jax.jit(lambda values: normalized_infidelity(values, system, space))
    assert jnp.isposinf(jitted(pulse))


@pytest.mark.parametrize("invalid_value", [1.01, jnp.nan, jnp.inf])
def test_grad_normalized_infidelity_returns_deterministic_invalid_sentinel(
    invalid_value: float,
) -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    pulse = jnp.zeros(space.parameter_count).at[3].set(invalid_value)
    value, gradient = jax.jit(
        jax.value_and_grad(lambda values: normalized_infidelity(values, system, space))
    )(pulse)
    assert jnp.isposinf(value)
    np.testing.assert_array_equal(gradient, jnp.zeros_like(gradient))


def test_normalized_infidelity_rejects_mismatched_pulse_space() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    wrong_controls = PulseSpace(1, 12, (4.0,), 1.0)
    space = PulseSpace.from_system(system, 12)
    wrong_scales = PulseSpace(2, 12, (3.0, 4.0), 1.0)

    with pytest.raises(ValueError, match="control count"):
        normalized_infidelity(
            jnp.zeros(wrong_controls.parameter_count),
            system,
            wrong_controls,
        )
    with pytest.raises(ValueError, match="segment"):
        normalized_infidelity(
            jnp.zeros(space.parameter_count - space.control_count),
            system,
            space,
        )
    with pytest.raises(ValueError, match="amplitude scales"):
        normalized_infidelity(
            jnp.zeros(wrong_scales.parameter_count),
            system,
            wrong_scales,
        )


@pytest.mark.parametrize(
    ("unitary", "target"),
    [
        (
            jnp.zeros((0, 0), dtype=jnp.complex128),
            jnp.zeros((0, 0), dtype=jnp.complex128),
        ),
        (jnp.zeros((2, 3), dtype=jnp.complex128), jnp.eye(2)),
        (jnp.eye(2), jnp.eye(3)),
        (jnp.full((2, 2), jnp.nan + 0.0j), jnp.eye(2)),
        (jnp.eye(2), jnp.full((2, 2), jnp.inf + 0.0j)),
    ],
)
def test_direct_objective_rejects_invalid_eager_inputs(
    unitary: jax.Array,
    target: jax.Array,
) -> None:
    with pytest.raises(ValueError):
        process_infidelity_from_unitary(unitary, target)


@pytest.mark.parametrize("invalid_value", [jnp.nan, jnp.inf])
def test_jitted_direct_objective_returns_infinity_for_nonfinite_inputs(
    invalid_value: float,
) -> None:
    target = jnp.eye(2, dtype=jnp.complex128)
    unitary = target.at[0, 0].set(invalid_value + 0.0j)
    jitted = jax.jit(process_infidelity_from_unitary)
    assert jnp.isposinf(jitted(unitary, target))


def test_grad_direct_objective_has_finite_zero_invalid_gradient() -> None:
    target = jnp.eye(2, dtype=jnp.complex128)

    def loss(value: jax.Array) -> jax.Array:
        unitary = target.at[0, 0].set(value + 0.0j)
        return process_infidelity_from_unitary(unitary, target)

    value, gradient = jax.jit(jax.value_and_grad(loss))(jnp.float64(jnp.nan))
    assert jnp.isposinf(value)
    assert gradient == 0.0


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
    directional = jnp.vdot(gradient, direction)
    assert jnp.linalg.norm(gradient) > 1e-4
    assert jnp.abs(directional) > 1e-5
    assert jnp.abs(finite) > 1e-5
    np.testing.assert_allclose(
        directional,
        finite,
        rtol=1e-6,
        atol=1e-8,
    )
    assert value.dtype == jnp.float64
    assert gradient.dtype == jnp.float64
    assert not jnp.iscomplexobj(gradient)
