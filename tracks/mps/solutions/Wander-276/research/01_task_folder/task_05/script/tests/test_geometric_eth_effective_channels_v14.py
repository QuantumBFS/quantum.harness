"""Cross-model mapping and Paper-II title-gate contracts."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from analyze_geometric_eth_effective_channels_v14 import (
    evaluate_archival_mapping,
    evaluate_theory_gate,
)


REPO = Path(__file__).resolve().parents[4]
OUTPUT = REPO / "01_task_folder/task_05/script/output"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_archival_mapping_excludes_missing_independent_covariance_units() -> None:
    registry = _load(OUTPUT / "paper1_prb_v13/evidence_registry_v13.json")
    mapping = evaluate_archival_mapping(registry)

    assert mapping["mapped_cases"] == []
    assert set(mapping["excluded_models"]) == set(registry["models"])
    assert mapping["imputed_values"] == []
    assert mapping["retrospective_support_used_for_title_gate"] is False
    assert all(
        record["eligible"] is False and record["reason"]
        for record in mapping["excluded_models"].values()
    )


def test_real_title_gate_fails_closed_on_prospective_random_channel_result() -> None:
    theory = _load(OUTPUT / "geometric_eth_theory_v14/channel_theory_v14.json")
    chiral = _load(OUTPUT / "geometric_eth_theory_v14/chiral_inference_v14.json")
    registry = _load(OUTPUT / "paper1_prb_v13/evidence_registry_v13.json")
    archival = evaluate_archival_mapping(registry)
    gate = evaluate_theory_gate(theory, chiral, archival)

    assert gate["components"]["analytic_channel_theorem"] is True
    assert gate["components"]["exact_chiral_index_and_seal"] is True
    assert gate["components"]["random_chiral_validation"] is False
    assert gate["components"]["structured_control_separation"] is True
    assert gate["passed"] is False
    assert gate["selected_title"] == (
        "Geometric Response of Exactly Degenerate Quantum State Bundles"
    )
    assert gate["forbidden_positive_title"] == (
        "The Geometric ETH: Statistical Closure on Degenerate Quantum State Bundles"
    )
    assert gate["selected_branch"] == "random_channel_failure"


def test_title_gate_requires_every_mandatory_component() -> None:
    theory = _load(OUTPUT / "geometric_eth_theory_v14/channel_theory_v14.json")
    chiral = _load(OUTPUT / "geometric_eth_theory_v14/chiral_inference_v14.json")
    archival = {"retrospective_support_used_for_title_gate": False}
    positive = deepcopy(chiral)
    positive["checks"]["all_exact_index_gates_pass"] = True
    positive["random_primary"]["all_validation_points_inside_band"] = True
    positive["structured_control"]["at_least_one_control_separates"] = True
    positive["quantitative_prediction_available"] = True
    positive["selected_branch"] = "deformed_locality_class"

    gate = evaluate_theory_gate(theory, positive, archival)
    assert gate["passed"] is True
    assert gate["selected_title"].startswith("The Geometric ETH:")

    for component_path in (
        ("checks", "all_exact_index_gates_pass"),
        ("random_primary", "all_validation_points_inside_band"),
        ("structured_control", "at_least_one_control_separates"),
    ):
        corrupted = deepcopy(positive)
        corrupted[component_path[0]][component_path[1]] = False
        assert evaluate_theory_gate(theory, corrupted, archival)["passed"] is False


def test_failed_analytic_audit_has_precedence_over_favorable_chiral_fixture() -> None:
    theory = _load(OUTPUT / "geometric_eth_theory_v14/channel_theory_v14.json")
    chiral = _load(OUTPUT / "geometric_eth_theory_v14/chiral_inference_v14.json")
    bad_theory = deepcopy(theory)
    bad_theory["all_checks_pass"] = False
    gate = evaluate_theory_gate(
        bad_theory,
        chiral,
        {"retrospective_support_used_for_title_gate": False},
    )
    assert gate["passed"] is False
    assert gate["components"]["analytic_channel_theorem"] is False
