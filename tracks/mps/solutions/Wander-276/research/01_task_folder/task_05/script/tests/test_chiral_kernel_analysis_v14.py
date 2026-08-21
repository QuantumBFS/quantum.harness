"""Post-seal inference contracts for the chiral-index calculation."""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from analyze_chiral_kernel_geometric_eth_v14 import (
    analyze_chiral_files,
    evaluate_chiral_prediction,
)


REPO = Path(__file__).resolve().parents[4]
OUTPUT = REPO / "01_task_folder/task_05/script/output/geometric_eth_theory_v14"
PREDICTION = OUTPUT / "chiral_prediction_v14.json"
SIDECAR = OUTPUT / "chiral_prediction_v14.sha256"
OUTCOMES = OUTPUT / "chiral_outcomes_v14.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_sealed_result_selects_the_frozen_failure_branch() -> None:
    result = analyze_chiral_files(
        repo_root=REPO,
        prediction_path=PREDICTION,
        sidecar_path=SIDECAR,
        outcomes_path=OUTCOMES,
        output_path=None,
    )

    assert result["checks"]["prediction_hash_matches_outcomes"] is True
    assert result["checks"]["seal_precedes_outcomes"] is True
    assert result["checks"]["all_exact_index_gates_pass"] is True
    assert result["random_primary"]["all_validation_points_inside_band"] is False
    assert result["selected_branch"] == "random_channel_failure"
    assert result["title_component_pass"] is False
    assert result["exponent_fit_performed"] is False
    assert len(result["random_primary"]["cases"]) == 3
    assert all(
        case["point_estimate"] > result["random_primary"]["band"]["upper"]
        for case in result["random_primary"]["cases"]
    )


def test_branch_precedence_is_exact_and_not_reinterpreted() -> None:
    prediction = _load(PREDICTION)
    outcomes = _load(OUTCOMES)
    digest = hashlib.sha256(PREDICTION.read_bytes()).hexdigest()

    feasibility = deepcopy(outcomes)
    feasibility["checks"]["all_exact_index_gates_pass"] = False
    result = evaluate_chiral_prediction(
        prediction, feasibility, prediction_file_sha256=digest
    )
    assert result["selected_branch"] == "feasibility_failure"

    random_failure = evaluate_chiral_prediction(
        prediction, outcomes, prediction_file_sha256=digest
    )
    assert random_failure["selected_branch"] == "random_channel_failure"


def test_corrupted_seal_timestamp_grid_and_hash_are_rejected() -> None:
    prediction = _load(PREDICTION)
    outcomes = _load(OUTCOMES)
    digest = hashlib.sha256(PREDICTION.read_bytes()).hexdigest()

    bad_hash = deepcopy(outcomes)
    bad_hash["prediction_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="prediction hash"):
        evaluate_chiral_prediction(
            prediction, bad_hash, prediction_file_sha256=digest
        )

    bad_time = deepcopy(outcomes)
    bad_time["generated_utc"] = prediction["sealed_utc"]
    with pytest.raises(RuntimeError, match="later than"):
        evaluate_chiral_prediction(
            prediction, bad_time, prediction_file_sha256=digest
        )

    bad_grid = deepcopy(outcomes)
    bad_grid["execution"]["sizes"] = [[48, 72], [64, 96]]
    with pytest.raises(RuntimeError, match="validation grid"):
        evaluate_chiral_prediction(
            prediction, bad_grid, prediction_file_sha256=digest
        )


def test_bootstrap_is_deterministic_and_uses_base_means() -> None:
    prediction = _load(PREDICTION)
    outcomes = _load(OUTCOMES)
    digest = hashlib.sha256(PREDICTION.read_bytes()).hexdigest()
    first = evaluate_chiral_prediction(
        prediction, outcomes, prediction_file_sha256=digest
    )
    second = evaluate_chiral_prediction(
        prediction, outcomes, prediction_file_sha256=digest
    )

    assert first == second
    for class_result in first["class_inference"].values():
        for case in class_result["cases"]:
            assert case["base_count"] == 64
            assert case["tangents_averaged_per_base"] == 16
            assert case["bootstrap_replicates"] == 10_000
            assert case["interval_low"] <= case["point_estimate"] <= case["interval_high"]
