import json

from vqetape.ansatz_training import (
    AnsatzGrowthRequest,
    AnsatzGrowthResult,
    run_ansatz_growth,
)
from vqetape.spec import TFIMVQESpec


def _request(policy: str) -> AnsatzGrowthRequest:
    return AnsatzGrowthRequest(
        spec=TFIMVQESpec(nqubits=3, depth=1),
        policy=policy,  # type: ignore[arg-type]
        target_energy_error=0.05,
        max_growth_rounds=5,
        optimizer_steps_per_round=4,
        seed=2,
        seed_depth=1,
        fixed_depth=2,
    )


def test_growth_request_round_trip_and_equal_budget():
    request = _request("contraction-aware")
    restored = AnsatzGrowthRequest.from_dict(
        json.loads(json.dumps(request.to_dict()))
    )

    assert restored == request
    assert (
        request.seed_depth
        * (2 * request.spec.nqubits - 1)
        + request.max_growth_rounds
        == request.fixed_depth
        * (2 * request.spec.nqubits - 1)
    )


def test_fixed_ansatz_runs_one_compiled_structure():
    result = run_ansatz_growth(_request("fixed"))

    assert result.compiled_structures == 1
    assert len(result.rounds) == 1
    assert result.rounds[0].phase == "fixed"
    assert result.final_structure.parameter_count == 10
    assert result.evaluations >= 1


def test_adaptive_growth_serializes_complete_screening():
    result = run_ansatz_growth(
        _request("contraction-aware")
    )
    restored = AnsatzGrowthResult.from_dict(
        json.loads(json.dumps(result.to_dict()))
    )

    assert restored == result
    assert result.rounds[0].phase == "seed"
    assert len(result.rounds) > 1
    for round_result in result.rounds[1:]:
        assert round_result.phase == "growth"
        assert len(round_result.candidates) == 9
        assert sum(
            candidate.selected
            for candidate in round_result.candidates
        ) == 1
        assert (
            round_result.selected_operator
            == round_result.candidates[0].operator
        )
    assert result.compiled_structures == len(result.rounds)
    assert result.screening_seconds >= 0
