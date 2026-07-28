from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np
import pytest

from scalable_v1.audit import AuditResult
from scalable_v1.gates import apply_ed_reveal, evaluate_pre_reveal
from scalable_v1.protocol import load_protocol


def estimate(
    mean: float, variance: float = 0.0, error: float = 1.0e-4
) -> dict[str, float]:
    return {
        "mean": mean,
        "variance": variance,
        "standard_error": error,
        "effective_sample_size": 8192.0,
        "maximum_imaginary_part": 0.0,
    }


def passing_evidence() -> dict[str, Any]:
    return {
        "construction": {
            "strict_lll": True,
            "antisymmetric": True,
            "scalable": True,
            "trainable_parameters": 100,
        },
        "statistics": {
            "ground": {"energy": estimate(1.0), "l2": estimate(0.0)},
            "l2_by_m": {
                str(m): {"energy": estimate(1.1), "l2": estimate(6.0)}
                for m in range(-2, 3)
            },
            "gap": {"mean": 0.1, "standard_error": 2.0e-4},
        },
        "diagnostics": {
            "lll_residual": 0.0,
            "particle_swap_residual": 0.0,
            "finite_rotation_residual": 1.0e-8,
            "tower_ladder_residual": 1.0e-10,
        },
        "resources": {
            "placement": "local",
            "wall_seconds": 2.0,
            "peak_rss_bytes": 1024,
            "checkpoint_bytes": 512,
            "n8_smoke_complete": True,
        },
    }


def test_pre_reveal_passes_every_non_oracle_gate() -> None:
    protocol = load_protocol()
    result = evaluate_pre_reveal(
        passing_evidence(),
        protocol,
        AuditResult(True, (), "manifest"),
    )

    assert result["gates"] == {
        "lll_valid": True,
        "antisymmetry_valid": True,
        "so3_equivariance_valid": True,
        "l2_casimir_valid": True,
        "fivefold_multiplet_valid": True,
        "mc_error_valid": True,
        "ed_crosscheck_valid": "pending",
        "reproducible_run_valid": True,
        "scalable_path_valid": True,
        "oracle_isolated": True,
        "blind_training_valid": True,
        "resource_budget_valid": True,
    }
    assert result["diagnostics"]["multiplet_splitting"] == 0.0
    assert result["audit"] == {
        "valid": True,
        "issues": [],
        "manifest_sha256": "manifest",
    }
    assert all(
        type(valid) is bool
        for name, valid in result["gates"].items()
        if name != "ed_crosscheck_valid"
    )


def test_ed_reveal_is_deep_copied_and_completes_the_final_gate() -> None:
    protocol = load_protocol()
    pre_reveal = evaluate_pre_reveal(
        passing_evidence(),
        protocol,
        AuditResult(True, (), "manifest"),
    )
    before = copy.deepcopy(pre_reveal)
    oracle = {
        "ground_energy": 1.0,
        "l2_by_m": {str(m): 1.1 for m in range(-2, 3)},
    }

    result = apply_ed_reveal(pre_reveal, oracle, protocol)

    assert pre_reveal == before
    assert pre_reveal["gates"]["ed_crosscheck_valid"] == "pending"
    assert set(result["gates"]) == set(pre_reveal["gates"]) | {
        "scalable_v1_pass"
    }
    assert result["gates"]["ed_crosscheck_valid"] is True
    assert result["gates"]["scalable_v1_pass"] is True
    assert "scalable_v1_pass" not in result
    assert result["ed_comparison"]["gap_absolute_error"] < 1.0e-12
    assert set(result["ed_comparison"]) == {
        "ground_absolute_error",
        "excited_absolute_error_by_m",
        "gap_absolute_error",
        "gap_z_score",
    }
    assert all(type(valid) is bool for valid in result["gates"].values())
    json.dumps(result, allow_nan=False)


def test_zero_gap_standard_error_uses_numerical_floor_for_finite_z_score() -> None:
    protocol = load_protocol()
    evidence = passing_evidence()
    evidence["statistics"]["gap"]["standard_error"] = 0.0
    pre_reveal = evaluate_pre_reveal(
        evidence,
        protocol,
        AuditResult(True, (), "manifest"),
    )
    oracle = {
        "ground_energy": 1.0,
        "l2_by_m": {str(m): 1.1 for m in range(-2, 3)},
    }

    result = apply_ed_reveal(pre_reveal, oracle, protocol)

    comparison = result["ed_comparison"]
    assert comparison["gap_absolute_error"] > 0.0
    assert math.isfinite(comparison["gap_z_score"])
    assert comparison["gap_z_score"] == pytest.approx(
        comparison["gap_absolute_error"] / protocol.oracle["numerical_floor"]
    )
    assert result["gates"]["ed_crosscheck_valid"] is True


@pytest.mark.parametrize(
    ("path", "value", "field"),
    [
        (("statistics", "gap", "standard_error"), -1.0, "statistics.gap.standard_error"),
        (("statistics", "ground", "energy", "standard_error"), float("nan"), "statistics.ground.energy.standard_error"),
        (("statistics", "l2_by_m", "0", "l2", "variance"), float("nan"), "statistics.l2_by_m.0.l2.variance"),
        (("diagnostics", "finite_rotation_residual"), float("nan"), "diagnostics.finite_rotation_residual"),
        (("resources", "wall_seconds"), float("nan"), "resources.wall_seconds"),
        (("statistics", "ground", "energy", "mean"), True, "statistics.ground.energy.mean"),
        (("construction", "trainable_parameters"), 1.5, "construction.trainable_parameters"),
        (("construction", "trainable_parameters"), 0, "construction.trainable_parameters"),
        (("resources", "peak_rss_bytes"), 1024.5, "resources.peak_rss_bytes"),
        (("resources", "checkpoint_bytes"), 512.5, "resources.checkpoint_bytes"),
    ],
)
def test_invalid_numeric_evidence_is_rejected(
    path: tuple[str, ...], value: object, field: str
) -> None:
    protocol = load_protocol()
    evidence = passing_evidence()
    target: dict[str, Any] = evidence
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValueError, match=field.replace(".", r"\.")):
        evaluate_pre_reveal(
            evidence,
            protocol,
            AuditResult(True, (), "manifest"),
        )


def test_infinite_excited_error_cannot_make_multiplet_and_ed_gates_pass() -> None:
    protocol = load_protocol()
    evidence = passing_evidence()
    energy = evidence["statistics"]["l2_by_m"]["0"]["energy"]
    energy["mean"] = 1.0e300
    energy["standard_error"] = float("inf")

    with pytest.raises(
        ValueError, match=r"statistics\.l2_by_m\.0\.energy\.standard_error"
    ):
        evaluate_pre_reveal(
            evidence,
            protocol,
            AuditResult(True, (), "manifest"),
        )


def test_unknown_resource_placement_is_rejected() -> None:
    protocol = load_protocol()
    evidence = passing_evidence()
    evidence["resources"]["placement"] = "locla"
    evidence["resources"]["wall_seconds"] = 601.0

    with pytest.raises(ValueError, match="resources.placement"):
        evaluate_pre_reveal(
            evidence,
            protocol,
            AuditResult(True, (), "manifest"),
        )


def test_numpy_smoke_boolean_produces_a_python_boolean_gate() -> None:
    protocol = load_protocol()
    evidence = passing_evidence()
    evidence["resources"]["n8_smoke_complete"] = np.bool_(True)

    result = evaluate_pre_reveal(
        evidence,
        protocol,
        AuditResult(True, (), "manifest"),
    )

    assert result["gates"]["scalable_path_valid"] is True
    assert type(result["gates"]["scalable_path_valid"]) is bool
    json.dumps(result, allow_nan=False)

    revealed = apply_ed_reveal(
        result,
        {
            "ground_energy": 1.0,
            "l2_by_m": {str(m): 1.1 for m in range(-2, 3)},
        },
        protocol,
    )
    json.dumps(revealed, allow_nan=False)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("construction", "strict_lll"), "false"),
        (("construction", "strict_lll"), 0),
        (("construction", "strict_lll"), 1),
        (("construction", "antisymmetric"), "false"),
        (("construction", "antisymmetric"), 0),
        (("construction", "antisymmetric"), 1),
        (("construction", "scalable"), "false"),
        (("construction", "scalable"), 0),
        (("construction", "scalable"), 1),
        (("resources", "n8_smoke_complete"), "false"),
        (("resources", "n8_smoke_complete"), 0),
        (("resources", "n8_smoke_complete"), 1),
    ],
)
def test_non_boolean_gate_inputs_are_rejected(
    path: tuple[str, ...], value: object
) -> None:
    protocol = load_protocol()
    evidence = passing_evidence()
    target: dict[str, Any] = evidence
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValueError, match=r"\.".join(path)):
        evaluate_pre_reveal(
            evidence,
            protocol,
            AuditResult(True, (), "manifest"),
        )


def test_numpy_planned_scalars_are_canonicalized_for_strict_json() -> None:
    protocol = load_protocol()
    evidence = passing_evidence()
    evidence["construction"]["trainable_parameters"] = np.float64(100.0)
    states = [
        evidence["statistics"]["ground"],
        *evidence["statistics"]["l2_by_m"].values(),
    ]
    for state in states:
        for estimate_record in state.values():
            for name, value in estimate_record.items():
                estimate_record[name] = np.float64(value)
    for name, value in evidence["statistics"]["gap"].items():
        evidence["statistics"]["gap"][name] = np.float64(value)
    for name, value in evidence["diagnostics"].items():
        evidence["diagnostics"][name] = np.float64(value)
    evidence["resources"].update(
        wall_seconds=np.float64(2.0),
        peak_rss_bytes=np.float64(1024.0),
        checkpoint_bytes=np.float64(512.0),
        n8_smoke_complete=np.bool_(True),
        future_scalar=np.float64(1.25),
    )

    pre_reveal = evaluate_pre_reveal(
        evidence,
        protocol,
        AuditResult(True, (), "manifest"),
    )
    json.dumps(pre_reveal, allow_nan=False)
    assert type(pre_reveal["construction"]["trainable_parameters"]) is int
    assert type(pre_reveal["resources"]["peak_rss_bytes"]) is int
    assert type(pre_reveal["resources"]["future_scalar"]) is float

    revealed = apply_ed_reveal(
        pre_reveal,
        {
            "ground_energy": np.float64(1.0),
            "l2_by_m": {str(m): np.float64(1.1) for m in range(-2, 3)},
        },
        protocol,
    )
    json.dumps(revealed, allow_nan=False)


def test_multiplet_tie_breaking_is_independent_of_python_hash_seed() -> None:
    script = "\n".join(
        [
            "import json",
            "from scalable_v1.audit import AuditResult",
            "from scalable_v1.gates import evaluate_pre_reveal",
            "from scalable_v1.protocol import load_protocol",
            "from tests.test_scalable_gates import passing_evidence",
            "evidence = passing_evidence()",
            "values = {",
            "    '-2': (1.1003, 1.0e-3),",
            "    '-1': (1.1003, 1.0e-5),",
            "    '0': (1.1, 1.0e-3),",
            "    '1': (1.1, 1.0e-5),",
            "    '2': (1.10015, 1.0e-4),",
            "}",
            "for m, (mean, error) in values.items():",
            "    energy = evidence['statistics']['l2_by_m'][m]['energy']",
            "    energy['mean'] = mean",
            "    energy['standard_error'] = error",
            "result = evaluate_pre_reveal(",
            "    evidence, load_protocol(), AuditResult(True, (), 'manifest')",
            ")",
            "print(json.dumps(result['gates']['fivefold_multiplet_valid']))",
        ]
    )
    solution_root = Path(__file__).resolve().parents[1]
    outcomes = []
    for seed in (1, 2):
        environment = dict(os.environ, PYTHONHASHSEED=str(seed))
        output = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=solution_root,
            env=environment,
            text=True,
        )
        outcomes.append(json.loads(output))

    assert outcomes == [True, True]


def test_reveal_rejects_an_incomplete_pre_reveal_gate_schema() -> None:
    protocol = load_protocol()
    pre_reveal = evaluate_pre_reveal(
        passing_evidence(),
        protocol,
        AuditResult(True, (), "manifest"),
    )
    del pre_reveal["gates"]["lll_valid"]

    with pytest.raises(ValueError, match="pre-reveal gate schema"):
        apply_ed_reveal(
            pre_reveal,
            {
                "ground_energy": 1.0,
                "l2_by_m": {str(m): 1.1 for m in range(-2, 3)},
            },
            protocol,
        )


@pytest.mark.parametrize(
    "oracle",
    [
        {"ground_energy": float("nan"), "l2_by_m": {str(m): 1.1 for m in range(-2, 3)}},
        {"ground_energy": 1.0, "l2_by_m": {**{str(m): 1.1 for m in range(-2, 3)}, "0": float("inf")}},
        {"ground_energy": 1.0, "l2_by_m": {str(m): 1.1 for m in range(-2, 3)}, "extra": 0.0},
        {"l2_by_m": {str(m): 1.1 for m in range(-2, 3)}},
        {"ground_energy": 1.0},
    ],
)
def test_reveal_rejects_invalid_oracle_schema_or_values(
    oracle: dict[str, Any],
) -> None:
    protocol = load_protocol()
    pre_reveal = evaluate_pre_reveal(
        passing_evidence(),
        protocol,
        AuditResult(True, (), "manifest"),
    )

    with pytest.raises(ValueError, match="ED oracle"):
        apply_ed_reveal(pre_reveal, oracle, protocol)


def test_reveal_rejects_an_audit_that_failed_oracle_isolation() -> None:
    protocol = load_protocol()
    pre_reveal = evaluate_pre_reveal(
        passing_evidence(),
        protocol,
        AuditResult(False, ("forbidden oracle access",), "manifest"),
    )

    with pytest.raises(
        ValueError, match="ED oracle cannot be loaded before oracle isolation passes"
    ):
        apply_ed_reveal(
            pre_reveal,
            {
                "ground_energy": 1.0,
                "l2_by_m": {str(m): 1.1 for m in range(-2, 3)},
            },
            protocol,
        )


@pytest.mark.parametrize(
    ("path", "value", "failed_gate"),
    [
        (("construction", "strict_lll"), False, "lll_valid"),
        (("statistics", "l2_by_m", "0", "l2", "variance"), 0.01, "l2_casimir_valid"),
        (("statistics", "ground", "energy", "effective_sample_size"), 100.0, "mc_error_valid"),
        (("resources", "wall_seconds"), 601.0, "resource_budget_valid"),
        (("construction", "trainable_parameters"), 262_145, "scalable_path_valid"),
    ],
)
def test_one_bad_measurement_fails_only_its_gate(
    path: tuple[str, ...], value: object, failed_gate: str
) -> None:
    protocol = load_protocol()
    evidence = copy.deepcopy(passing_evidence())
    target: dict[str, Any] = evidence
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    result = evaluate_pre_reveal(
        evidence,
        protocol,
        AuditResult(True, (), "manifest"),
    )

    assert {
        name for name, valid in result["gates"].items() if valid is False
    } == {failed_gate}
    assert result["gates"]["ed_crosscheck_valid"] == "pending"


def test_incomplete_l2_multiplet_is_rejected() -> None:
    protocol = load_protocol()
    evidence = copy.deepcopy(passing_evidence())
    del evidence["statistics"]["l2_by_m"]["2"]

    with pytest.raises(ValueError, match="complete L=2 multiplet is required"):
        evaluate_pre_reveal(
            evidence,
            protocol,
            AuditResult(True, (), "manifest"),
        )
