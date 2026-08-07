import pytest

from vqetape.benchmark import benchmark_tn_candidate
from vqetape.spec import CompileRequest, TFIMVQESpec, TensorProgramConfig
from vqetape.tn_candidates import enumerate_tn_candidates


def test_tensor_candidate_enumeration_is_unique_and_covers_strategies():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=3, depth=1),
        memory_budget_bytes=1024**3,
        expected_vqe_steps=10,
    )
    candidates = enumerate_tn_candidates(request)
    assert len(candidates) == len(set(candidates))
    assert {item.path_strategy for item in candidates} == {
        "greedy",
        "random-greedy",
        "auto-hq",
    }
    assert {item.remat_policy for item in candidates} == {
        "none",
        "named",
    }
    assert {item.gate_representation for item in candidates} == {
        "dense",
    }
    assert {item.hamiltonian_representation for item in candidates} == {
        "pauli_sum",
        "mpo",
    }
    assert len(candidates) == 24
    for representation in ("pauli_sum", "mpo"):
        for strategy in {item.path_strategy for item in candidates}:
            matching = [
                item
                for item in candidates
                if item.hamiltonian_representation == representation
                and item.path_strategy == strategy
            ]
            paths = {item.path for item in matching}
            assert len(paths) == 1
            assert next(iter(paths))
            named = [
                item for item in matching if item.remat_policy == "named"
            ]
            assert len(named) == 3
            assert named[0].save_names is not None


def test_operator_schmidt_search_remains_available():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=3, depth=1),
        memory_budget_bytes=1024**3,
        expected_vqe_steps=10,
    )
    candidates = enumerate_tn_candidates(
        request,
        strategies=("greedy",),
        gate_representations=("dense", "operator_schmidt"),
        hamiltonian_representations=("pauli_sum",),
    )
    assert len(candidates) == 8
    assert {item.gate_representation for item in candidates} == {
        "dense",
        "operator_schmidt",
    }
    assert {item.hamiltonian_representation for item in candidates} == {
        "pauli_sum",
    }


@pytest.mark.parametrize(
    "gate_representation",
    ["dense", "operator_schmidt"],
)
def test_direct_tn_candidate_runs_in_fresh_process(gate_representation):
    spec = TFIMVQESpec(nqubits=3, depth=1)
    result = benchmark_tn_candidate(
        spec=spec,
        config=TensorProgramConfig(
            "greedy",
            "none",
            gate_representation=gate_representation,
        ),
        seed=3,
        warm_repeats=1,
        timeout_seconds=180,
    )
    assert result.valid, result.failure
    assert result.worker_pid != result.parent_pid
    assert result.config.gate_representation == gate_representation
    assert result.static_estimate["gate_representation"] == gate_representation
    assert result.static_estimate["path_flops"] > 0
    assert result.static_estimate["largest_intermediate_elements"] > 0
    assert result.static_estimate["tensor_count"] > 0
    assert result.static_estimate["input_tensor_elements"] > 0
    assert result.static_estimate["residual_profile"]["total_bytes"] > 0
    assert result.jax_memory_analysis


@pytest.mark.parametrize(
    ("hamiltonian_representation", "expected_contractions"),
    [
        ("pauli_sum", 5),
        ("mpo", 1),
    ],
)
def test_worker_reports_energy_level_costs(
    hamiltonian_representation,
    expected_contractions,
):
    spec = TFIMVQESpec(nqubits=3, depth=1)
    result = benchmark_tn_candidate(
        spec=spec,
        config=TensorProgramConfig(
            "greedy",
            "none",
            hamiltonian_representation=hamiltonian_representation,
        ),
        seed=1,
        warm_repeats=1,
        timeout_seconds=180,
    )
    assert result.valid, result.failure
    estimate = result.static_estimate
    assert (
        estimate["hamiltonian_representation"]
        == hamiltonian_representation
    )
    assert estimate["contractions_per_energy"] == expected_contractions
    assert estimate["estimated_energy_flops"] == (
        estimate["path_flops"] * expected_contractions
    )
    assert estimate["estimated_energy_tensor_bindings"] == (
        estimate["tensor_count"] * expected_contractions
    )
