from __future__ import annotations

import copy
import math

from initial_code import build_candidate
from verify_candidate import evaluate


def test_seed_has_exact_certificate_and_improvable_gap() -> None:
    result = evaluate(build_candidate())
    assert result["certificate_valid"] is True
    assert result["sandwich_valid"] is True
    assert result["passed"] is False
    assert 0.8 < result["score"] < 1.0
    assert 0.01 < result["sandwich_gap"] < 0.1


def test_optimal_strategy_closes_known_sandwich() -> None:
    candidate = build_candidate()
    candidate["strategy"]["bob_angles"] = [math.pi / 4.0, -math.pi / 4.0]
    result = evaluate(candidate)
    assert result["passed"] is True
    assert result["score"] > 0.999999
    assert abs(result["sandwich_gap"]) < 1e-12


def test_invalid_certificate_cannot_outrank_valid_one() -> None:
    candidate = copy.deepcopy(build_candidate())
    candidate["sos"][0]["weight"] = {"rational": "1", "sqrt2": "0"}
    result = evaluate(candidate)
    assert result["certificate_valid"] is False
    assert result["score"] < 0.8
    assert result["residual_terms"] > 0
