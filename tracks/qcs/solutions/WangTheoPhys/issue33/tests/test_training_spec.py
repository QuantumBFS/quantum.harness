import math

import pytest

from vqetape.spec import (
    ProgramConfig,
    SpatialProgramConfig,
    TFIMVQESpec,
)
from vqetape.training_spec import (
    VQEStep,
    VQETrainingRequest,
    VQETrainingResult,
)


@pytest.mark.parametrize(
    "program",
    [
        ProgramConfig("scan", "remat"),
        SpatialProgramConfig(
            "greedy",
            "default",
            symmetry="z2-native",
        ),
    ],
)
def test_training_request_round_trip(program):
    request = VQETrainingRequest(
        spec=TFIMVQESpec(nqubits=4, depth=2),
        program=program,
        optimizer="adam",
        initialization="random",
        target_energy_error=0.1,
        max_steps=20,
        seed=7,
        learning_rate=0.03,
    )

    assert VQETrainingRequest.from_dict(
        request.to_dict()
    ) == request


def test_recycled_request_round_trip():
    source = TFIMVQESpec(nqubits=3, depth=1)
    parameters = (
        (
            (0.1, 0.2, 0.0),
            (0.3, 0.4, 0.5),
        ),
    )
    request = VQETrainingRequest(
        spec=TFIMVQESpec(nqubits=5, depth=2),
        program=ProgramConfig("scan", "default"),
        optimizer="lbfgs",
        initialization="recycled",
        target_energy_error=0.2,
        max_steps=30,
        recycled_source_spec=source,
        recycled_parameters=parameters,
    )

    assert VQETrainingRequest.from_dict(
        request.to_dict()
    ) == request


@pytest.mark.parametrize(
    "kwargs",
    [
        {"optimizer": "unknown"},
        {"initialization": "unknown"},
        {"target_energy_error": 0},
        {"max_steps": 0},
        {"learning_rate": 0},
        {"damping": 0},
        {"ground_energy": math.inf},
        {
            "initialization": "recycled",
            "recycled_source_spec": None,
            "recycled_parameters": None,
        },
    ],
)
def test_training_request_rejects_invalid_values(kwargs):
    values = {
        "spec": TFIMVQESpec(nqubits=4, depth=1),
        "program": ProgramConfig("scan", "default"),
        "optimizer": "adam",
        "initialization": "zeros",
        "target_energy_error": 0.1,
        "max_steps": 10,
    }
    values.update(kwargs)
    with pytest.raises(ValueError):
        VQETrainingRequest(**values)


def test_training_result_round_trip():
    request = VQETrainingRequest(
        spec=TFIMVQESpec(nqubits=3, depth=1),
        program=ProgramConfig("scan", "default"),
        optimizer="adam",
        initialization="zeros",
        target_energy_error=0.2,
        max_steps=10,
    )
    result = VQETrainingResult(
        request=request,
        converged=True,
        evaluations=2,
        optimizer_steps=1,
        compile_seconds=0.2,
        first_execute_seconds=0.01,
        optimization_seconds=0.03,
        time_to_target_seconds=0.23,
        total_seconds=0.24,
        peak_rss_bytes=1024,
        ground_energy=-3.0,
        target_energy=-2.8,
        final_energy=-2.9,
        final_parameters=(
            ((0.0, 0.0, 0.0), (0.1, 0.2, 0.3)),
        ),
        trace=(
            VQEStep(
                evaluation=1,
                optimizer_step=0,
                energy=-2.7,
                energy_error=0.3,
                gradient_norm=0.4,
                elapsed_seconds=0.01,
            ),
            VQEStep(
                evaluation=2,
                optimizer_step=1,
                energy=-2.9,
                energy_error=0.1,
                gradient_norm=0.2,
                elapsed_seconds=0.03,
            ),
        ),
    )

    assert VQETrainingResult.from_dict(
        result.to_dict()
    ) == result
