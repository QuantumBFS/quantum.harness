import numpy as np
import pytest

from qcontrol.config import SystemConfig
from qcontrol.systems import (
    ControlSystem,
    _PerturbationDescriptor,
    lie_algebra_dimension,
    make_system,
    perturb_system,
)


def test_one_qubit_system_is_su2_controllable() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    assert system.dimension == 2
    assert len(system.controls) == 2
    assert lie_algebra_dimension(system) == 3


def test_two_qubit_system_is_su4_controllable() -> None:
    system = make_system(SystemConfig("two_qubit", 20, 4.0))
    assert system.dimension == 4
    assert len(system.controls) == 4
    assert lie_algebra_dimension(system) == 15


def test_gap_zero_preserves_model_and_nonzero_gap_is_reproducible() -> None:
    model = make_system(SystemConfig("two_qubit", 20, 4.0))
    zero_gap = perturb_system(model, 0.0, 3)
    np.testing.assert_allclose(zero_gap.drift, model.drift)
    for actual, expected in zip(zero_gap.controls, model.controls, strict=True):
        np.testing.assert_allclose(actual, expected)
    truth_a = perturb_system(model, 0.05, 3)
    truth_b = perturb_system(model, 0.05, 3)
    np.testing.assert_allclose(truth_a.drift, truth_b.drift)
    assert not np.allclose(truth_a.drift, model.drift)


def test_system_matrices_use_complex128_normalized_hermitian_products() -> None:
    system = make_system(SystemConfig("two_qubit", 20, 4.0))
    assert system.drift.dtype == np.complex128
    assert all(control.dtype == np.complex128 for control in system.controls)
    for control in system.controls:
        np.testing.assert_allclose(control, control.conj().T, rtol=0.0, atol=1e-15)
        np.testing.assert_allclose(np.linalg.norm(control, "fro"), 1.0, rtol=0.0, atol=1e-15)
    identity = np.eye(system.dimension, dtype=np.complex128)
    np.testing.assert_allclose(system.target.conj().T @ system.target, identity, atol=1e-15)


def test_nonzero_gap_has_exact_relative_drift_norm_and_independent_gain_errors() -> None:
    model = make_system(SystemConfig("two_qubit", 20, 4.0))
    gap = 0.05
    truth = perturb_system(model, gap, 13)
    relative_norm = np.linalg.norm(truth.drift - model.drift, "fro") / np.linalg.norm(
        model.drift, "fro"
    )
    np.testing.assert_allclose(relative_norm, gap, rtol=0.0, atol=1e-12)
    assert all(
        not np.allclose(actual, expected)
        for actual, expected in zip(truth.controls, model.controls, strict=True)
    )
    gain_ratios = np.array(
        [
            np.vdot(expected, actual).real / np.vdot(expected, expected).real
            for actual, expected in zip(truth.controls, model.controls, strict=True)
        ]
    )
    assert np.unique(gain_ratios).size == len(model.controls)


def test_control_system_defensively_copies_and_freezes_all_arrays() -> None:
    drift = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)
    control = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
    target = np.eye(2, dtype=np.complex128)
    system = ControlSystem(drift, (control,), target, (4.0,), "custom")

    drift[0, 0] = 9.0
    control[0, 1] = 9.0
    target[0, 0] = 9.0
    assert system.drift[0, 0] == 1.0
    assert system.controls[0][0, 1] == 1.0
    assert system.target[0, 0] == 1.0

    for matrix in (system.drift, *system.controls, system.target):
        assert not matrix.flags.writeable
        with pytest.raises(ValueError):
            matrix.flat[0] = 0.0
        with pytest.raises(ValueError):
            matrix.setflags(write=True)


def test_control_system_equality_never_compares_ndarrays() -> None:
    first = make_system(SystemConfig("one_qubit", 12, 4.0))
    second = make_system(SystemConfig("one_qubit", 12, 4.0))
    assert first == first
    assert first != second


def test_perturbation_descriptor_is_complete_reproducible_and_private() -> None:
    model = make_system(SystemConfig("two_qubit", 20, 4.0))
    truth = perturb_system(model, np.float64(0.05), np.int64(17))
    repeated = perturb_system(model, np.float64(0.05), np.int64(17))
    descriptor = truth._perturbation
    repeated_descriptor = repeated._perturbation

    assert descriptor is not None
    assert repeated_descriptor is not None
    assert descriptor.gap == 0.05
    assert descriptor.seed == 17
    np.testing.assert_array_equal(
        descriptor.drift_direction,
        repeated_descriptor.drift_direction,
    )
    np.testing.assert_array_equal(
        descriptor.control_gain_deltas,
        repeated_descriptor.control_gain_deltas,
    )
    np.testing.assert_array_equal(
        descriptor.unmodeled_direction,
        repeated_descriptor.unmodeled_direction,
    )
    for direction in (descriptor.drift_direction, descriptor.unmodeled_direction):
        np.testing.assert_allclose(direction, direction.conj().T, atol=1e-15)
        np.testing.assert_allclose(np.trace(direction), 0.0, atol=1e-15)
        np.testing.assert_allclose(np.linalg.norm(direction, "fro"), 1.0, atol=1e-15)
        assert not direction.flags.writeable
    assert not descriptor.control_gain_deltas.flags.writeable

    aggregate = descriptor.drift_direction + descriptor.unmodeled_direction
    aggregate /= np.linalg.norm(aggregate, "fro")
    expected_drift = (
        model.drift
        + descriptor.gap * np.linalg.norm(model.drift, "fro") * aggregate
    )
    np.testing.assert_allclose(truth.drift, expected_drift, rtol=0.0, atol=1e-15)
    for actual, expected, delta in zip(
        truth.controls,
        model.controls,
        descriptor.control_gain_deltas,
        strict=True,
    ):
        np.testing.assert_allclose(actual, (1.0 + delta) * expected)


def test_perturbation_descriptor_defensively_copies_and_freezes_arrays() -> None:
    direction = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)
    gains = np.array([0.1, -0.2], dtype=np.float64)
    descriptor = _PerturbationDescriptor(direction, gains, direction, 0.1, 5)

    direction[0, 0] = 7.0
    gains[0] = 7.0
    assert descriptor.drift_direction[0, 0] == 1.0
    assert descriptor.unmodeled_direction[0, 0] == 1.0
    assert descriptor.control_gain_deltas[0] == 0.1
    for array in (
        descriptor.drift_direction,
        descriptor.control_gain_deltas,
        descriptor.unmodeled_direction,
    ):
        assert not array.flags.writeable
        with pytest.raises(ValueError):
            array.flat[0] = 0.0
        with pytest.raises(ValueError):
            array.setflags(write=True)


def test_zero_gap_preserves_complete_system_and_uses_no_descriptor() -> None:
    model = make_system(SystemConfig("two_qubit", 20, 4.0))
    truth = perturb_system(model, np.float64(0.0), np.int64(3))
    np.testing.assert_array_equal(truth.drift, model.drift)
    for actual, expected in zip(truth.controls, model.controls, strict=True):
        np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(truth.target, model.target)
    assert truth.amplitude_scales == model.amplitude_scales
    assert truth.name == model.name
    assert truth._perturbation is None


def test_positive_gap_rejects_zero_drift_model() -> None:
    model = make_system(SystemConfig("one_qubit", 12, 4.0))
    zero_drift = ControlSystem(
        np.zeros_like(model.drift),
        model.controls,
        model.target,
        model.amplitude_scales,
        model.name,
    )
    with pytest.raises(ValueError, match="drift Frobenius norm"):
        perturb_system(zero_drift, 0.05, 3)


@pytest.mark.parametrize("gap", [-0.1, np.nan, np.inf, True, "0.1"])
def test_perturb_system_rejects_invalid_gap(gap: object) -> None:
    model = make_system(SystemConfig("one_qubit", 12, 4.0))
    with pytest.raises(ValueError, match="gap"):
        perturb_system(model, gap, 3)  # type: ignore[arg-type]


@pytest.mark.parametrize("seed", [-1, True, 1.5, np.float64(2.0)])
def test_perturb_system_rejects_invalid_seed(seed: object) -> None:
    model = make_system(SystemConfig("one_qubit", 12, 4.0))
    with pytest.raises(ValueError, match="seed"):
        perturb_system(model, 0.05, seed)  # type: ignore[arg-type]


@pytest.mark.parametrize("tolerance", [0.0, -1.0, np.nan, np.inf, True, "1e-10"])
def test_lie_algebra_dimension_rejects_invalid_tolerance(tolerance: object) -> None:
    model = make_system(SystemConfig("one_qubit", 12, 4.0))
    with pytest.raises(ValueError, match="tolerance"):
        lie_algebra_dimension(model, tolerance)  # type: ignore[arg-type]


def test_numpy_real_tolerance_is_accepted() -> None:
    model = make_system(SystemConfig("two_qubit", 20, 4.0))
    assert lie_algebra_dimension(model, np.float64(1e-10)) == 15


def test_make_system_rejects_unknown_name_when_config_validation_is_bypassed() -> None:
    config = object.__new__(SystemConfig)
    object.__setattr__(config, "name", "unknown")
    object.__setattr__(config, "segments", 12)
    object.__setattr__(config, "amplitude_bound", 4.0)
    with pytest.raises(ValueError, match="system name"):
        make_system(config)
