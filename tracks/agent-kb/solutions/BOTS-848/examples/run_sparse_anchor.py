#!/usr/bin/env python3
"""Fit and score the transparent sparse-anchor synthetic contract case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
if str(SOLUTION_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLUTION_ROOT))

from src.cost_model import compare_corrected_to_baselines
from src.response_model import error_metrics, fit_response_matrix, predict_coefficients


DEFAULT_CASE = SOLUTION_ROOT / "examples" / "sparse_anchor_response.yaml"


def run_case(path: Path) -> dict[str, object]:
    case = json.loads(path.read_text(encoding="utf-8"))
    model = fit_response_matrix(
        case["training_inputs"],
        case["training_targets"],
        ridge=case["ridge"],
    )
    held_out_prediction = predict_coefficients(model, case["held_out_inputs"])
    held_out_metrics = error_metrics(held_out_prediction, case["held_out_targets"])
    cost = compare_corrected_to_baselines(**case["cost_assumptions"])
    anchor_accounting_matches = (
        model["anchor_count"] == case["cost_assumptions"]["high_level_anchors"]
    )
    passed = (
        held_out_metrics["relative_rmse"] is not None
        and held_out_metrics["relative_rmse"]
        <= case["software_relative_rmse_tolerance"]
        and anchor_accounting_matches
        and cost["is_faster_than_dense_high_level"]
        == case["expected_is_faster_than_dense_high_level"]
        and cost["is_faster_than_dfpt"] == case["expected_is_faster_than_dfpt"]
        and case["validation_scope"] == "software-contract-only"
        and not case["measured_runtime"]
        and not case["physical_accuracy_established"]
    )
    return {
        "name": case["name"],
        "validation_scope": case["validation_scope"],
        "model": model,
        "held_out_prediction": held_out_prediction,
        "held_out_metrics": held_out_metrics,
        "cost": cost,
        "anchor_accounting_matches": anchor_accounting_matches,
        "measured_runtime": case["measured_runtime"],
        "physical_accuracy_established": case["physical_accuracy_established"],
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", nargs="?", type=Path, default=DEFAULT_CASE)
    args = parser.parse_args()
    result = run_case(args.case)
    metrics = result["held_out_metrics"]
    cost = result["cost"]
    print(
        f"{result['name']}: anchors={result['model']['anchor_count']}, "
        f"channels={result['model']['channel_count']}"
    )
    print(
        "held-out synthetic: "
        f"rmse={metrics['rmse']:.3e}, "
        f"relative_rmse={metrics['relative_rmse']:.3e}, "
        f"max_abs_error={metrics['max_abs_error']:.3e}"
    )
    print(
        "declared cost model: "
        f"dfpt_only={cost['dfpt_only_cost']:.3f}, "
        f"dense_high_level={cost['dense_high_level_cost']:.3f}, "
        f"corrected={cost['corrected_cost']:.3f}, "
        f"speedup_vs_dense_high_level={cost['speedup_vs_dense_high_level']:.3f}, "
        f"is_faster_than_dense_high_level={cost['is_faster_than_dense_high_level']}, "
        f"is_faster_than_dfpt={cost['is_faster_than_dfpt']}, "
        f"measured_runtime={result['measured_runtime']}"
    )
    print(f"physical_accuracy_established={result['physical_accuracy_established']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
