from vqetape.candidates import enumerate_candidates, segment_lengths
from vqetape.estimate import estimate_program
from vqetape.spec import CompileRequest, ProgramConfig, TFIMVQESpec


def test_segment_lengths_include_endpoints_divisors_and_sqrt_neighbors():
    assert segment_lengths(10) == (1, 2, 3, 4, 5, 10)


def test_segmented_estimate_is_smaller_than_save_all_for_deep_chain():
    spec = TFIMVQESpec(nqubits=8, depth=100)
    default = estimate_program(
        spec,
        ProgramConfig(control_flow="scan", adjoint="default", unroll=1),
    )
    segmented = estimate_program(
        spec,
        ProgramConfig(
            control_flow="scan",
            adjoint="segmented",
            unroll=1,
            segment_length=10,
        ),
    )
    assert (
        segmented.saved_boundary_upper_bound_bytes
        < default.saved_boundary_upper_bound_bytes
    )
    assert (
        segmented.estimated_recompute_gate_applications
        > default.estimated_recompute_gate_applications
    )


def test_candidate_enumeration_is_unique_and_memory_filtered():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=6, depth=8),
        memory_budget_bytes=2 * 1024**3,
        expected_vqe_steps=100,
    )
    candidates = enumerate_candidates(request)
    assert len(candidates) == len(set(candidates))
    assert all(
        estimate_program(
            request.spec,
            item,
        ).saved_boundary_upper_bound_bytes
        <= request.memory_budget_bytes
        for item in candidates
    )
