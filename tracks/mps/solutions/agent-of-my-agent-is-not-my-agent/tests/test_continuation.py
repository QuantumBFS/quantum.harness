import numpy as np
import pytest

from lrtfim.dmrg_workflow import build_mpo_model, default_dmrg_options
from lrtfim.mpo import build_rotated_nearest_neighbor_tfim_mpo
from lrtfim.parity_dmrg import (
    _initial_state,
    physical_correlations_rotated,
    run_parity_spectrum,
    validate_initial_state,
)


def _model(length: int, gamma: float):
    return build_mpo_model(build_rotated_nearest_neighbor_tfim_mpo(length, gamma))


def test_initial_state_validation_rejects_wrong_length_and_sector() -> None:
    target = _model(8, 1.0)
    wrong_length = _initial_state(_model(6, 1.0), "even")
    with pytest.raises(ValueError, match="length"):
        validate_initial_state(target, wrong_length, "even")

    odd = _initial_state(target, "odd")
    with pytest.raises(ValueError, match="sector"):
        validate_initial_state(target, odd, "even")


def test_neighbor_gamma_warm_start_matches_cold_solution() -> None:
    options = default_dmrg_options(64)
    options["max_sweeps"] = 16
    source = run_parity_spectrum(_model(8, 0.99), options)
    target = _model(8, 1.0)

    warm = run_parity_spectrum(
        target,
        options,
        even_initial=source.ground.psi,
        odd_initial=source.excited.psi,
    )
    cold = run_parity_spectrum(target, options)

    assert warm.ground.energy == pytest.approx(cold.ground.energy, abs=1e-10)
    assert warm.excited.energy == pytest.approx(cold.excited.energy, abs=1e-10)
    assert warm.gap == pytest.approx(cold.gap, abs=1e-10)
    np.testing.assert_allclose(
        physical_correlations_rotated(warm.ground.psi),
        physical_correlations_rotated(cold.ground.psi),
        atol=1e-9,
    )
