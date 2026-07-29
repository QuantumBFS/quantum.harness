import numpy as np
import pytest

from vqetape.spec import (
    ProgramConfig,
    SpatialProgramConfig,
    TFIMVQESpec,
)
from vqetape.training import train_vqe
from vqetape.training_spec import VQETrainingRequest


def _request(
    *,
    optimizer="adam",
    program=None,
    target=0.3,
    max_steps=20,
    initialization="zeros",
):
    spec = TFIMVQESpec(nqubits=2, depth=1)
    return VQETrainingRequest(
        spec=spec,
        program=(
            program
            if program is not None
            else ProgramConfig("scan", "default")
        ),
        optimizer=optimizer,
        initialization=initialization,
        target_energy_error=target,
        max_steps=max_steps,
        learning_rate=0.08,
        seed=3,
    )


def test_training_stops_on_initial_target_and_accounts_time():
    result = train_vqe(_request(target=0.3))

    assert result.converged
    assert result.evaluations == 1
    assert result.optimizer_steps == 0
    assert len(result.trace) == 1
    assert result.compile_seconds >= 0
    assert result.first_execute_seconds > 0
    assert result.optimization_seconds >= (
        result.first_execute_seconds
    )
    assert result.time_to_target_seconds is not None
    assert result.time_to_target_seconds >= (
        result.compile_seconds
    )
    assert result.total_seconds == pytest.approx(
        result.compile_seconds
        + result.optimization_seconds,
    )


def test_nonconverged_adam_uses_max_steps_plus_initial_call():
    request = _request(
        target=1e-12,
        max_steps=2,
        initialization="random",
    )
    result = train_vqe(request)

    assert not result.converged
    assert result.evaluations == 3
    assert result.optimizer_steps == 2
    assert len(result.trace) == 3
    assert result.time_to_target_seconds is None
    assert np.allclose(
        np.asarray(result.final_parameters)[:, 0, -1],
        0,
    )


@pytest.mark.parametrize(
    "program",
    [
        SpatialProgramConfig(
            "greedy",
            "default",
            symmetry="none",
        ),
        SpatialProgramConfig(
            "greedy",
            "default",
            symmetry="z2-native",
        ),
    ],
)
def test_training_supports_spatial_programs(program):
    result = train_vqe(
        _request(
            program=program,
            target=0.3,
        )
    )

    assert result.converged
    assert result.request.program == program
    assert np.isfinite(result.final_energy)


def test_lbfgs_training_converges_to_tighter_target():
    pytest.importorskip("scipy")
    result = train_vqe(
        _request(
            optimizer="lbfgs",
            target=0.01,
            max_steps=30,
            initialization="random",
        )
    )

    assert result.converged, result.failure
    assert result.trace[-1].energy_error <= 0.01


def test_natural_gradient_records_metric_condition():
    result = train_vqe(
        _request(
            optimizer="natural-gradient",
            target=0.2,
            max_steps=8,
            initialization="random",
        )
    )

    assert any(
        step.metric_condition is not None
        for step in result.trace
    )
    assert result.evaluations == len(result.trace)
