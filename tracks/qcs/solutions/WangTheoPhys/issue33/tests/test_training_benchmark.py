import numpy as np
import pytest

from vqetape.spec import (
    SpatialProgramConfig,
    TFIMVQESpec,
)
from vqetape.training_benchmark import (
    run_training_fresh_process,
)
from vqetape.training_spec import VQETrainingRequest


def _request() -> VQETrainingRequest:
    return VQETrainingRequest(
        spec=TFIMVQESpec(nqubits=2, depth=1),
        program=SpatialProgramConfig(
            "greedy",
            "default",
            symmetry="z2-native",
        ),
        optimizer="adam",
        initialization="zeros",
        target_energy_error=0.3,
        max_steps=2,
    )


def test_training_runs_in_fresh_process():
    result = run_training_fresh_process(
        _request(),
        timeout_seconds=120,
    )

    assert result.converged
    assert result.evaluations == 1
    assert np.isfinite(result.compile_seconds)


def test_training_fresh_process_rejects_bad_timeout():
    with pytest.raises(ValueError, match="positive"):
        run_training_fresh_process(
            _request(),
            timeout_seconds=0,
        )
