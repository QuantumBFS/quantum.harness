from __future__ import annotations

import json

import pytest

from benchmark_v0.nqs_benchmark import run_nqs_benchmark, write_json_report


@pytest.fixture(scope="module")
def benchmark_result() -> dict[str, object]:
    return run_nqs_benchmark(n_samples=20_000)


def test_candidate_uses_shared_projected_neural_family(
    benchmark_result: dict[str, object],
) -> None:
    model = benchmark_result["candidate_model"]

    assert model["family"] == "projected random-feature neural quantum state"
    assert model["input"] == "strict-LLL Slater occupation bitstring"
    assert model["shared_trunk"] == {
        "activation": "tanh",
        "hidden_width": 128,
        "seed": 848,
    }
    assert model["heads"] == {"L=0,M=0": "linear", "L=2,M=0": "linear"}
    assert model["l2_tower"] == "generated from the shared M=0 head by L+/L-"


def test_candidate_reports_complete_l2_tower_and_vmc_statistics(
    benchmark_result: dict[str, object],
) -> None:
    states = benchmark_result["candidate_states"]
    statistics = benchmark_result["statistics"]

    assert states["ground"]["L"] == 0
    assert [state["M"] for state in states["l2_multiplet"]] == [-2, -1, 0, 1, 2]
    assert all(state["L"] == 2 for state in states["l2_multiplet"])
    assert statistics["ground"]["effective_sample_size"] == 20_000
    assert all(
        component["effective_sample_size"] == 20_000
        for component in statistics["l2_by_m"].values()
    )
    assert statistics["sampling"] == "independent categorical determinant samples"
    assert statistics["gap"]["total_uncertainty"] >= 1.0e-12


def test_candidate_passes_physical_residuals_and_ed_crosscheck(
    benchmark_result: dict[str, object],
) -> None:
    diagnostics = benchmark_result["diagnostics"]
    errors = benchmark_result["ed_comparison"]

    assert diagnostics["particle_swap_residual"] < 2.0e-11
    assert diagnostics["finite_rotation_residual"] < 2.0e-10
    assert diagnostics["tower_ladder_residual"] < 2.0e-11
    assert diagnostics["multiplet_splitting"] < 2.0e-10
    assert diagnostics["max_l2_error"] < 2.0e-10
    assert diagnostics["max_l2_variance"] < 2.0e-9
    assert errors["ground_absolute_error"] <= 5 * errors["ground_total_uncertainty"]
    assert errors["gap_absolute_error"] <= 5 * errors["gap_total_uncertainty"]


def test_combined_report_passes_every_frozen_benchmark_gate(
    benchmark_result: dict[str, object],
) -> None:
    gates = benchmark_result["gates"]

    assert set(gates) == {
        "lll_valid",
        "antisymmetry_valid",
        "so3_equivariance_valid",
        "l2_casimir_valid",
        "fivefold_multiplet_valid",
        "mc_error_valid",
        "ed_crosscheck_valid",
        "reproducible_run_valid",
        "benchmark_v0_pass",
    }
    assert all(gates.values())
    assert benchmark_result["benchmark_v0"] == {
        "pass": True,
        "status": "passed",
        "pending": [],
    }


def test_combined_report_round_trips_as_json(
    benchmark_result: dict[str, object], tmp_path
) -> None:
    output = tmp_path / "run.json"

    write_json_report(benchmark_result, output)
    restored = json.loads(output.read_text(encoding="utf-8"))

    assert restored["schema_version"] == "challenge-15-benchmark-v0.2"
    assert restored["gates"]["benchmark_v0_pass"] is True
    assert restored["runtime"]["elapsed_seconds"] > 0.0
