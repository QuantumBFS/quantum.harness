from __future__ import annotations

import json
from pathlib import Path

from vmcrg_ref.artifacts import atomic_write_json
from vmcrg_ref.issue28_protocol import load_issue28_protocol
from vmcrg_ref.issue28_workflow import create_stage_manifest


PROTOCOL_PATH = Path("config/issue28_easy_v1.json")


def _write_bundle(
    root: Path,
    bundle_id: str,
    *,
    classification: str = "EASY_GOAL_SUCCESS",
    objective_classification: str = "IDENTIFIABLE",
    scale: float = 1.0,
) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle = root / bundle_id
    autocorrelation_root = bundle / "autocorrelation"
    autocorrelation_root.mkdir(parents=True)
    neural_tau = [scale * value for value in (1.9, 2.0, 2.1, 2.0)]
    linear_tau = [scale * value for value in (2.1, 2.2, 2.2, 2.1)]
    unbiased_tau = [scale * value for value in (3.8, 4.0, 4.1, 4.0)]
    neural_ess = [value / scale for value in (4.1, 4.0, 3.9, 4.0)]
    linear_ess = [value / scale for value in (4.0, 4.0, 3.8, 3.9)]
    unbiased_ess = [value / scale for value in (2.0, 2.1, 1.9, 2.0)]
    autocorrelation = {
        "schema_version": 1,
        "arms": ["neural", "linear", "unbiased"],
        "common_initial_state": True,
        "neural": {
            "tau_int_by_chain": neural_tau,
            "tau_int_mean": sum(neural_tau) / len(neural_tau),
            "ess_per_second_by_chain": neural_ess,
            "ess_per_second_mean": sum(neural_ess) / len(neural_ess),
        },
        "linear": {
            "tau_int_by_chain": linear_tau,
            "tau_int_mean": sum(linear_tau) / len(linear_tau),
            "ess_per_second_by_chain": linear_ess,
            "ess_per_second_mean": sum(linear_ess) / len(linear_ess),
        },
        "unbiased": {
            "tau_int_by_chain": unbiased_tau,
            "tau_int_mean": sum(unbiased_tau) / len(unbiased_tau),
            "ess_per_second_by_chain": unbiased_ess,
            "ess_per_second_mean": sum(unbiased_ess) / len(unbiased_ess),
        },
    }
    atomic_write_json(
        autocorrelation_root / "autocorrelation.json", autocorrelation
    )
    three_arm = {
        "tau_neural_over_unbiased": autocorrelation["neural"]["tau_int_mean"]
        / autocorrelation["unbiased"]["tau_int_mean"],
        "tau_neural_over_linear": autocorrelation["neural"]["tau_int_mean"]
        / autocorrelation["linear"]["tau_int_mean"],
        "ess_neural_over_unbiased": autocorrelation["neural"][
            "ess_per_second_mean"
        ]
        / autocorrelation["unbiased"]["ess_per_second_mean"],
        "ess_neural_over_linear": autocorrelation["neural"][
            "ess_per_second_mean"
        ]
        / autocorrelation["linear"]["ess_per_second_mean"],
    }
    result = {
        "schema_version": 1,
        "stage": "N4",
        "scope": "N4_FORMAL_BUNDLE",
        "bundle_id": bundle_id,
        "rounds_completed": 5,
        "rounds": [
            {
                "round": index,
                "classification": classification,
                "fixed_linear_bias_linf": 0.0,
            }
            for index in range(1, 6)
        ],
        "classification": classification,
        "objective_classification": objective_classification,
        "objective_delta_per_site": -0.01 / scale,
        "three_arm": three_arm,
        "arms": ["neural", "linear", "unbiased"],
        "replacement_seed_allowed": False,
        "postformal_seed_extension_allowed": False,
    }
    atomic_write_json(bundle / "bundle_result.json", result)
    manifest = create_stage_manifest(
        stage="N4",
        protocol=protocol,
        classification=classification,
        reason="TEST_N5_FIXTURE",
        output_root=bundle,
        outputs=("bundle_result.json", "autocorrelation/autocorrelation.json"),
        correctness_gates={"five_rounds": "PASS"},
        scientific_gates={"objective": objective_classification},
        resources={"backend": "slurm"},
        bundle_id=bundle_id,
        round_index=5,
    )
    manifest["scope"] = "N4_FORMAL_BUNDLE"
    atomic_write_json(bundle / "manifest.json", manifest)


def _formal_fixture(root: Path, *, scientific_negative: bool = False) -> Path:
    root.mkdir()
    for index in range(1, 6):
        negative = scientific_negative and index == 4
        _write_bundle(
            root,
            f"formal-{index}",
            classification=("SCIENTIFIC_NEGATIVE" if negative else "EASY_GOAL_SUCCESS"),
            objective_classification=(
                "UNIDENTIFIABLE_OVERLAP" if negative else "IDENTIFIABLE"
            ),
            scale=1.0 + index / 100.0,
        )
    return root


def test_report_preserves_scientific_negative(tmp_path: Path) -> None:
    from scripts.issue28_report import build_issue28_report

    root = _formal_fixture(tmp_path / "cells", scientific_negative=True)
    report = build_issue28_report(
        root,
        load_issue28_protocol(PROTOCOL_PATH),
        output=tmp_path / "N5",
        bootstrap_replicates=1000,
    )
    assert report["classification"] == "SCIENTIFIC_NEGATIVE"
    assert report["formal_seed_count"] == 5
    assert report["postformal_seed_extension_allowed"] is False


def test_success_report_uses_paired_statistics_and_direction_gate(
    tmp_path: Path,
) -> None:
    from scripts.issue28_report import build_issue28_report

    root = _formal_fixture(tmp_path / "cells")
    report = build_issue28_report(
        root,
        load_issue28_protocol(PROTOCOL_PATH),
        output=tmp_path / "N5",
        bootstrap_replicates=1000,
    )
    assert report["classification"] == "EASY_GOAL_SUCCESS"
    assert report["directional_seed_counts"] == {
        "tau_improves_over_unbiased": 5,
        "tau_linear_noninferiority": 5,
        "ess_improves_over_unbiased": 5,
        "ess_linear_noninferiority": 5,
    }
    assert report["statistics"]["tau_neural_over_linear"]["ci95_high_ratio"] < 1.10
    assert report["statistics"]["ess_neural_over_linear"]["ci95_low_ratio"] > 0.90


def test_every_figure_has_exact_source_table_and_render_document(
    tmp_path: Path,
) -> None:
    from scripts.issue28_report import build_issue28_report

    root = _formal_fixture(tmp_path / "cells")
    output = tmp_path / "N5"
    report = build_issue28_report(
        root,
        load_issue28_protocol(PROTOCOL_PATH),
        output=output,
        bootstrap_replicates=1000,
    )
    for figure in report["figures"]:
        assert Path(figure["source_csv"]).is_file()
        assert Path(figure["png"]).is_file()
        assert Path(figure["pdf"]).is_file()
    document = json.loads((output / "report.json").read_text(encoding="ascii"))
    assert document["classification"] == report["classification"]
    assert len(document["sections"]) >= 2
