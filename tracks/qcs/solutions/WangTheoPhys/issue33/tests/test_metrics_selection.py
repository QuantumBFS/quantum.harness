from vqetape.metrics import median_and_mad
from vqetape.selection import (
    CandidateResult,
    correctness_error,
    pareto_frontier,
    select_for_horizon,
)
from vqetape.spec import ProgramConfig, SpatialProgramConfig


def make_result(label, compile_seconds, warm_seconds, memory):
    control_flow = "unrolled" if label == "unrolled" else "scan"
    return CandidateResult(
        config=ProgramConfig(
            control_flow=control_flow,
            adjoint="default",
            unroll=1,
        ),
        compile_seconds=compile_seconds,
        first_execute_seconds=0.1,
        warm_seconds_median=warm_seconds,
        warm_seconds_mad=0.0,
        peak_rss_bytes=memory,
        energy_abs_error=0.0,
        gradient_relative_l2_error=0.0,
        valid=True,
    )


def test_median_and_mad():
    assert median_and_mad([1.0, 2.0, 100.0]) == (2.0, 1.0)


def test_correctness_error_uses_stable_gradient_denominator():
    energy_error, gradient_error = correctness_error(
        1.1,
        [0.1, 0.0],
        1.0,
        [0.0, 0.0],
    )
    assert abs(energy_error - 0.1) < 1e-12
    assert abs(gradient_error - 0.1) < 1e-12


def test_pareto_frontier_removes_dominated_result():
    fast = make_result("unrolled", 2.0, 1.0, 100)
    dominated = make_result("scan", 3.0, 2.0, 120)
    assert pareto_frontier([fast, dominated]) == [fast]


def test_horizon_selection_accounts_for_compile_amortization():
    low_cold = make_result("unrolled", 1.0, 2.0, 100)
    high_throughput = make_result("scan", 20.0, 1.0, 100)
    assert (
        select_for_horizon([low_cold, high_throughput], 2).config
        == low_cold.config
    )
    assert (
        select_for_horizon([low_cold, high_throughput], 100).config
        == high_throughput.config
    )


def test_candidate_result_round_trip():
    candidate = make_result("scan", 3.0, 2.0, 120)
    assert CandidateResult.from_dict(candidate.to_dict()) == candidate


def test_spatial_candidate_result_round_trip():
    candidate = CandidateResult(
        config=SpatialProgramConfig(
            "random-greedy",
            "segmented",
            unroll=2,
            segment_length=3,
        ),
        compile_seconds=1.0,
        first_execute_seconds=0.1,
        warm_seconds_median=0.01,
        warm_seconds_mad=0.001,
        peak_rss_bytes=1024,
        energy_abs_error=0.0,
        gradient_relative_l2_error=0.0,
        valid=True,
    )
    assert CandidateResult.from_dict(candidate.to_dict()) == candidate
