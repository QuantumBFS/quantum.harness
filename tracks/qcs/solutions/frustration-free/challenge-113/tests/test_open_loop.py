import numpy as np
import pytest

from qcontrol.config import SystemConfig
from qcontrol.open_loop import OpenLoopAcceptanceError, optimize_open_loop
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system


def test_one_qubit_open_loop_reaches_acceptance() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    result = optimize_open_loop(system, space, seed=5, starts=5)
    assert result.loss <= 1e-8
    assert result.gradient_norm <= 1e-5
    assert result.starts == 5
    assert result.evaluations > 0
    assert np.asarray(result.normalized_pulse).dtype == np.float64
    assert np.all(np.abs(result.normalized_pulse) <= 1.0)


def test_open_loop_is_reproducible() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    assert optimize_open_loop(system, space, 5) == optimize_open_loop(system, space, 5)


def test_duration_one_two_qubit_fails_closed_with_single_start() -> None:
    system = make_system(SystemConfig("two_qubit", 20, 4.0, duration=1.0))
    space = PulseSpace.from_system(system, 20)

    with pytest.raises(OpenLoopAcceptanceError) as raised:
        optimize_open_loop(system, space, seed=5, starts=1)

    assert len(raised.value.diagnostics) == 1
    assert raised.value.diagnostics[0].loss > 1e-8
    assert raised.value.diagnostics[0].evaluations > 0


@pytest.mark.integration
def test_two_qubit_open_loop_reaches_development_acceptance() -> None:
    system = make_system(SystemConfig("two_qubit", 20, 4.0))
    space = PulseSpace.from_system(system, 20)
    result = optimize_open_loop(system, space, seed=5, starts=5)
    assert result.loss <= 1e-8
    assert result.gradient_norm <= 1e-5
