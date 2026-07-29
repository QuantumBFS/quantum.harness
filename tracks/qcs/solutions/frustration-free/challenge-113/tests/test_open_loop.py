import numpy as np
import pytest
from scipy.optimize import OptimizeResult

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


def test_duration_one_two_qubit_runs_all_starts_and_fails_closed() -> None:
    system = make_system(SystemConfig("two_qubit", 20, 4.0, duration=1.0))
    space = PulseSpace.from_system(system, 20)

    with pytest.raises(OpenLoopAcceptanceError) as raised:
        optimize_open_loop(system, space, seed=5, starts=2)

    diagnostics = raised.value.diagnostics
    assert len(diagnostics) == 2
    assert [item.index for item in diagnostics] == [0, 1]
    for item in diagnostics:
        assert item.loss > 1e-8
        assert item.success in {True, False}
        assert isinstance(item.status, int)
        assert item.message
        assert item.evaluations > 0


def test_evaluations_match_per_start_scipy_nfev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0))
    space = PulseSpace.from_system(system, 2)
    expected_nfev = [2, 3]
    scipy_results: list[OptimizeResult] = []

    def fake_minimize(fun: object, x0: np.ndarray, **kwargs: object) -> OptimizeResult:
        start_index = len(scipy_results)
        evaluations = expected_nfev[start_index]
        value = 0.0
        gradient = np.zeros_like(x0)
        for _ in range(evaluations):
            value, gradient = fun(x0)  # type: ignore[operator]
            assert isinstance(value, float)
            assert gradient.dtype == np.float64
            assert gradient.flags.c_contiguous
        result = OptimizeResult(
            x=x0,
            fun=max(float(value), 0.5),
            jac=gradient,
            success=False,
            status=9,
            message=f"failed start {start_index}",
            nfev=evaluations,
        )
        scipy_results.append(result)
        return result

    monkeypatch.setattr("qcontrol.open_loop.minimize", fake_minimize)
    with pytest.raises(OpenLoopAcceptanceError) as raised:
        optimize_open_loop(system, space, seed=3, starts=2)

    assert [result.nfev for result in scipy_results] == expected_nfev
    assert [item.evaluations for item in raised.value.diagnostics] == expected_nfev
    assert [item.message for item in raised.value.diagnostics] == [
        "failed start 0",
        "failed start 1",
    ]


def test_unexpected_scipy_exception_fails_closed_with_prior_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0))
    space = PulseSpace.from_system(system, 2)
    calls = 0

    def fake_minimize(fun: object, x0: np.ndarray, **kwargs: object) -> OptimizeResult:
        nonlocal calls
        calls += 1
        value, gradient = fun(x0)  # type: ignore[operator]
        if calls == 2:
            raise RuntimeError("scipy exploded")
        return OptimizeResult(
            x=x0,
            fun=max(float(value), 0.5),
            jac=gradient,
            success=False,
            status=7,
            message="first start failed",
            nfev=1,
        )

    monkeypatch.setattr("qcontrol.open_loop.minimize", fake_minimize)
    with pytest.raises(OpenLoopAcceptanceError) as raised:
        optimize_open_loop(system, space, seed=3, starts=3)

    assert calls == 2
    assert [item.index for item in raised.value.diagnostics] == [0, 1]
    assert raised.value.diagnostics[0].status == 7
    assert raised.value.diagnostics[0].evaluations == 1
    exceptional = raised.value.diagnostics[1]
    assert exceptional.success is False
    assert exceptional.status == -1
    assert exceptional.message == "RuntimeError: scipy exploded"
    assert exceptional.evaluations == 1


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit])
def test_process_control_exceptions_are_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[BaseException],
) -> None:
    system = make_system(SystemConfig("one_qubit", 2, 4.0))
    space = PulseSpace.from_system(system, 2)

    def fake_minimize(*args: object, **kwargs: object) -> OptimizeResult:
        raise exception_type()

    monkeypatch.setattr("qcontrol.open_loop.minimize", fake_minimize)
    with pytest.raises(exception_type):
        optimize_open_loop(system, space, seed=3, starts=2)


@pytest.mark.integration
def test_two_qubit_open_loop_reaches_development_acceptance() -> None:
    system = make_system(SystemConfig("two_qubit", 20, 4.0))
    space = PulseSpace.from_system(system, 20)
    result = optimize_open_loop(system, space, seed=5, starts=5)
    assert result.loss <= 1e-8
    assert result.gradient_norm <= 1e-5
