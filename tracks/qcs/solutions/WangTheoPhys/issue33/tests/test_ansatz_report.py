from vqetape.ansatz_report import (
    audited_ansatz_requests,
    run_ansatz_fresh_process,
)
from vqetape.ansatz_training import AnsatzGrowthRequest
from vqetape.spec import TFIMVQESpec


def test_audited_requests_have_equal_budgets():
    requests = audited_ansatz_requests()

    assert [request.policy for request in requests] == [
        "fixed",
        "gradient-only",
        "contraction-aware",
    ]
    assert len(
        {
            (
                request.target_energy_error,
                request.max_growth_rounds,
                request.optimizer_steps_per_round,
                request.seed,
            )
            for request in requests
        }
    ) == 1


def test_ansatz_worker_runs_in_fresh_process():
    request = AnsatzGrowthRequest(
        spec=TFIMVQESpec(
            nqubits=3,
            depth=1,
            dtype="complex128",
        ),
        policy="contraction-aware",
        target_energy_error=0.05,
        max_growth_rounds=5,
        optimizer_steps_per_round=5,
        seed_depth=1,
        fixed_depth=2,
    )
    result = run_ansatz_fresh_process(
        request,
        timeout_seconds=120,
    )

    assert result.request == request
    assert result.compiled_structures >= 1
