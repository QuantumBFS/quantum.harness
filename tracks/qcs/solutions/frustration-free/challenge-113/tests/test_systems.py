import numpy as np

from qcontrol.config import SystemConfig
from qcontrol.systems import lie_algebra_dimension, make_system, perturb_system


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
