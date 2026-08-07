from vqetape.benchmark import (
    benchmark_candidate,
    benchmark_spatial_candidate,
)
from vqetape.spec import (
    ProgramConfig,
    SpatialProgramConfig,
    TFIMVQESpec,
)


def test_candidate_runs_in_fresh_process_and_returns_finite_metrics():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    result = benchmark_candidate(
        spec=spec,
        config=ProgramConfig(
            control_flow="scan",
            adjoint="default",
            unroll=1,
        ),
        seed=7,
        warm_repeats=2,
        timeout_seconds=120,
    )
    assert result.valid, result.failure
    assert result.compile_seconds >= 0
    assert result.first_execute_seconds >= 0
    assert result.warm_seconds_median > 0
    assert result.peak_rss_bytes > 0
    assert result.energy is not None
    assert result.gradient is not None
    assert result.worker_pid != result.parent_pid


def test_segmented_worker_executes_non_divisible_depth():
    spec = TFIMVQESpec(nqubits=3, depth=3)
    result = benchmark_candidate(
        spec=spec,
        config=ProgramConfig(
            control_flow="scan",
            adjoint="segmented",
            unroll=1,
            segment_length=2,
        ),
        seed=9,
        warm_repeats=1,
        timeout_seconds=120,
    )
    assert result.valid, result.failure


def test_spatial_candidate_runs_in_fresh_worker():
    spec = TFIMVQESpec(nqubits=4, depth=1)
    result = benchmark_spatial_candidate(
        spec=spec,
        config=SpatialProgramConfig("greedy", "default"),
        seed=0,
        warm_repeats=1,
        timeout_seconds=120,
    )

    assert result.valid, result.failure
    assert result.worker_pid != result.parent_pid
    assert result.energy is not None
    assert result.gradient is not None
    assert result.static_estimate["boundary_dimension"] == 12
    assert result.static_estimate["boundary_bytes"] == 96
    assert result.static_estimate["bulk_columns"] == 2
    assert result.static_estimate["bulk_path_flops"] > 0
    assert result.static_estimate["estimated_energy_flops"] > 0
    assert result.static_estimate["modeled_checkpoint_boundaries"] == 2
    differentiated = result.static_estimate[
        "differentiated_cost"
    ]
    assert differentiated["total_forward_flops"] > 0
    assert differentiated["total_backward_flops"] > 0
    assert differentiated["total_traffic_bytes"] > 0
    assert differentiated["peak_role_residual_elements"] > 0
    assert differentiated["static_score"] > 0
    assert result.static_estimate["residual_profile"]["total_bytes"] > 0


def test_blocked_spatial_worker_reports_block_metrics():
    spec = TFIMVQESpec(nqubits=6, depth=1)
    result = benchmark_spatial_candidate(
        spec=spec,
        config=SpatialProgramConfig(
            "greedy",
            "default",
            block_width=2,
        ),
        seed=0,
        warm_repeats=1,
        timeout_seconds=120,
    )

    assert result.valid, result.failure
    assert result.static_estimate["block_width"] == 2
    assert result.static_estimate["bulk_blocks"] == 2
    assert result.static_estimate["tail_width"] == 0
    assert result.static_estimate["bulk_block_path_flops"] > 0
    assert result.static_estimate["estimated_energy_flops"] > 0


def test_segmented_spatial_worker_handles_partial_segment():
    spec = TFIMVQESpec(nqubits=7, depth=1)
    result = benchmark_spatial_candidate(
        spec=spec,
        config=SpatialProgramConfig(
            "greedy",
            "segmented",
            segment_length=2,
        ),
        seed=3,
        warm_repeats=1,
        timeout_seconds=120,
    )

    assert result.valid, result.failure
    assert result.config.adjoint == "segmented"
    assert result.static_estimate["bulk_columns"] == 5
    assert result.static_estimate["modeled_checkpoint_boundaries"] == 5


def test_native_symmetry_worker_reports_compressed_sector():
    spec = TFIMVQESpec(nqubits=5, depth=1)
    result = benchmark_spatial_candidate(
        spec=spec,
        config=SpatialProgramConfig(
            "greedy",
            "default",
            symmetry="z2-native",
        ),
        seed=0,
        warm_repeats=1,
        timeout_seconds=120,
    )

    assert result.valid, result.failure
    estimate = result.static_estimate
    assert estimate["symmetry"] == "z2-native"
    assert estimate["symmetry_execution"] == "bcoo-native"
    assert estimate["boundary_dimension"] == 12
    assert estimate["recurrent_boundary_dimension"] == 6
    assert estimate["boundary_bytes"] == 96
    assert estimate["recurrent_boundary_bytes"] == 48
    assert estimate["symmetry_sector"]["active_fraction"] == 0.5
