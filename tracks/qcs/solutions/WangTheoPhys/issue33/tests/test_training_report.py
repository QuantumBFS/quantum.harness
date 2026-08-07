from vqetape.spec import (
    SpatialProgramConfig,
    TFIMVQESpec,
)
from vqetape.training_report import benchmark_requests
from vqetape.training_spec import (
    VQETrainingRequest,
    VQETrainingResult,
)


def _source() -> VQETrainingResult:
    request = VQETrainingRequest(
        spec=TFIMVQESpec(nqubits=3, depth=1),
        program=SpatialProgramConfig(
            "greedy",
            "default",
        ),
        optimizer="lbfgs",
        initialization="random",
        target_energy_error=0.1,
        max_steps=2,
    )
    parameters = (
        (
            (0.1, 0.2, 0.0),
            (0.3, 0.4, 0.5),
        ),
    )
    return VQETrainingResult(
        request=request,
        converged=True,
        evaluations=1,
        optimizer_steps=0,
        compile_seconds=0.1,
        first_execute_seconds=0.01,
        optimization_seconds=0.01,
        time_to_target_seconds=0.11,
        total_seconds=0.11,
        peak_rss_bytes=1,
        ground_energy=-3.0,
        target_energy=-2.9,
        final_energy=-2.95,
        final_parameters=parameters,
        trace=(),
    )


def test_benchmark_matrix_covers_optimizers_and_programs():
    requests = dict(benchmark_requests(_source()))

    assert len(requests) == 11
    assert {
        request.optimizer for request in requests.values()
    } == {"adam", "lbfgs", "natural-gradient"}
    assert {
        request.initialization
        for request in requests.values()
    } == {"zeros", "random", "recycled"}
    assert "program-statevector" in requests
    assert "program-z2-native" in requests


def test_recycled_rows_use_serialized_source():
    source = _source()
    requests = dict(benchmark_requests(source))
    recycled = requests["optimizer-lbfgs-recycled"]

    assert recycled.recycled_source_spec == source.request.spec
    assert (
        recycled.recycled_parameters
        == source.final_parameters
    )
    assert recycled.spec == TFIMVQESpec(
        nqubits=4,
        depth=2,
    )
