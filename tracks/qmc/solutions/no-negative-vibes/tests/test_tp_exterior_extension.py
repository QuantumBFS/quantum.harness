import json
from math import prod
from pathlib import Path

import pytest
import sympy as sp

import oracle.tp_exterior_extension as runner
from oracle.exterior_exact5_shared_cone import exact_compound_matrix
from oracle.tp_exterior_extension import (
    construct_candidate,
    hodge_basis_map,
    run_cell,
    run_spec,
    strict_totally_positive_core,
)


BASE_PARAMS = {
    "jacobi_strength": "1/2",
    "diagonal_condition_ratio": "2",
    "chord_shear_magnitude": "1/32",
    "chord_pattern": [[0, 2], [3, 1]],
    "givens_half_angle": "1/16",
    "givens_plane": [0, 7],
    "two_atom_scale_ratio": "5/4",
}

CONTROL_PARAMS = {
    **BASE_PARAMS,
    "chord_shear_magnitude": "0",
    "givens_half_angle": "0",
}


def _passed_atom_gate(_atoms, _settings):
    return {
        "passed": True,
        "status": "passed",
        "maximum_condition_number": 12.0,
        "minimum_determinant": 0.5,
    }


def _passed_compound_gate(_atoms, _gauges, _settings):
    return {
        "passed": True,
        "status": "passed",
        "minimum_relative_entry_margin": 0.25,
        "minimum_entry": 0.125,
    }


def _passed_minor_gate(_atoms, _settings):
    return {
        "passed": True,
        "status": "passed",
        "minimum_order2_minor": -0.25,
    }


def _passed_gauge_gate(_gauge, _settings):
    return {
        "passed": True,
        "status": "passed",
        "klein_pluecker_residual": 0.125,
    }


def _passed_stress(_atoms, **options):
    return {
        "passed": True,
        "completed_requested_depth": True,
        "status": "all-tested-words-positive",
        "minimum_determinant": 1.25,
        "settings_seen": options,
    }


def _patch_pre_stress_gates(monkeypatch):
    monkeypatch.setattr(runner, "atom_admissibility_gate", _passed_atom_gate)
    monkeypatch.setattr(runner, "transformed_compound_gate", _passed_compound_gate)
    monkeypatch.setattr(runner, "non_tn_minor_gate", _passed_minor_gate)
    monkeypatch.setattr(runner, "non_induced_gauge_gate", _passed_gauge_gate)


def test_strict_core_uses_complete_positive_jacobi_factorization():
    core = strict_totally_positive_core(
        jacobi_strength=sp.Rational(1, 2),
        diagonal_condition_ratio=sp.Rational(4),
    )

    assert core.shape == (5, 5)
    assert core.det() > 0
    for grade in range(1, 5):
        compound = exact_compound_matrix(core, grade)
        assert all(entry > 0 for entry in compound)


def test_candidate_is_exact_transpose_closed_and_identity_is_canonical():
    candidate = construct_candidate(BASE_PARAMS)
    equivalent = construct_candidate(
        {
            **BASE_PARAMS,
            "jacobi_strength": {"numerator": 2, "denominator": 4},
            "two_atom_scale_ratio": "10/8",
        }
    )

    atoms = candidate["exact_atoms"]
    assert len(atoms) == 4
    assert atoms[1] == atoms[0].T
    assert atoms[3] == atoms[2].T
    assert candidate["candidate_id"] == equivalent["candidate_id"]
    assert candidate["candidate_card"] == equivalent["candidate_card"]
    assert candidate["candidate_card"]["parameters"]["jacobi_strength"] == {
        "numerator": 1,
        "denominator": 2,
    }
    replay = construct_candidate(candidate["candidate_card"]["parameters"])
    assert replay["candidate_id"] == candidate["candidate_id"]
    assert replay["exact_atoms"] == candidate["exact_atoms"]


def test_cell_fingerprint_covers_schema_cell_params_and_resolved_settings(
    monkeypatch,
):
    base = runner.cell_fingerprint("cell-a", BASE_PARAMS, {})

    assert runner.cell_fingerprint(
        "cell-a",
        {**BASE_PARAMS, "jacobi_strength": "2/4"},
        {
            "condition_number_limit": 1.0e10,
            "relative_entry_margin_threshold": 1.0e-8,
            "negative_minor_threshold": 1.0e-6,
            "non_induced_residual_threshold": 1.0e-6,
            "mixed_word_depth": 6,
            "max_level_matrices": 2_000_000,
        },
    ) == base
    assert runner.cell_fingerprint("cell-b", BASE_PARAMS, {}) != base
    assert runner.cell_fingerprint(
        "cell-a",
        {**BASE_PARAMS, "jacobi_strength": "1"},
        {},
    ) != base
    assert runner.cell_fingerprint(
        "cell-a",
        BASE_PARAMS,
        {"mixed_word_depth": 5},
    ) != base
    monkeypatch.setattr(runner, "SCHEMA", "changed-schema")
    assert runner.cell_fingerprint("cell-a", BASE_PARAMS, {}) != base


def test_grade_gauges_use_fixed_hodge_conjugation_and_are_orthogonal():
    candidate = construct_candidate(BASE_PARAMS)
    gauges = candidate["exact_gauges"]
    hodge = hodge_basis_map()

    assert gauges[1] == sp.eye(5)
    assert gauges[4] == sp.eye(5)
    assert gauges[2].T * gauges[2] == sp.eye(10)
    assert hodge.T * hodge == sp.eye(10)
    assert gauges[3] == hodge * gauges[2] * hodge.T
    assert gauges[3].T * gauges[3] == sp.eye(10)


def test_hodge_basis_map_has_the_documented_signed_entries():
    hodge = hodge_basis_map()

    assert {
        (row, column): int(hodge[row, column])
        for row in range(10)
        for column in range(10)
        if hodge[row, column] != 0
    } == {
        (0, 9): 1,
        (1, 8): -1,
        (2, 7): 1,
        (3, 6): 1,
        (4, 5): -1,
        (5, 4): 1,
        (6, 3): -1,
        (7, 2): 1,
        (8, 1): -1,
        (9, 0): 1,
    }


def test_transformed_compounds_follow_the_declared_q_transpose_formula():
    candidate = construct_candidate(BASE_PARAMS)
    transformed = runner.exact_transformed_compounds(
        candidate["exact_atoms"],
        candidate["exact_gauges"],
    )

    for atom_index, atom in enumerate(candidate["exact_atoms"]):
        for grade in range(1, 5):
            gauge = candidate["exact_gauges"][grade]
            assert transformed[grade][atom_index] == (
                gauge.T * exact_compound_matrix(atom, grade) * gauge
            )


@pytest.mark.parametrize(
    "plane",
    ([0, 7], [0, 8], [0, 9], [1, 5], [1, 6], [1, 9]),
)
def test_each_frozen_disjoint_givens_plane_is_non_induced(plane):
    candidate = construct_candidate({**BASE_PARAMS, "givens_plane": plane})

    assert runner.klein_pluecker_residual(candidate["exact_gauges"][2]) > 0.0


def test_zero_givens_and_nonidentity_induced_exterior_square_have_zero_residual():
    control = construct_candidate(CONTROL_PARAMS)
    one_particle = sp.eye(5)
    one_particle[0, 0] = sp.Rational(3, 5)
    one_particle[0, 1] = -sp.Rational(4, 5)
    one_particle[1, 0] = sp.Rational(4, 5)
    one_particle[1, 1] = sp.Rational(3, 5)
    induced = exact_compound_matrix(one_particle, 2)

    assert runner.klein_pluecker_residual(control["exact_gauges"][2]) == 0.0
    assert induced != sp.eye(10)
    assert runner.klein_pluecker_residual(induced) == 0.0


def test_real_mixed_word_stress_reaches_depth_and_counts_all_words():
    result = runner.mixed_word_determinant_stress(
        (sp.eye(5),) * 4,
        max_depth=3,
        max_level_matrices=64,
    )

    assert result["passed"] is True
    assert result["completed_requested_depth"] is True
    assert result["status"] == "all-tested-words-positive"
    assert result["max_depth_reached"] == 3
    assert result["word_count"] == 4 + 16 + 64
    assert result["minimum_determinant"] == 32.0


def test_real_mixed_word_stress_stops_on_a_nonpositive_word():
    result = runner.mixed_word_determinant_stress(
        (-sp.eye(5), sp.eye(5), sp.eye(5), sp.eye(5)),
        max_depth=3,
        max_level_matrices=64,
    )

    assert result["passed"] is False
    assert result["completed_requested_depth"] is False
    assert result["status"] == "nonpositive-word-found"
    assert result["max_depth_reached"] == 1
    assert result["word_count"] == 4
    assert result["minimum_determinant"] == 0.0
    assert result["witness"] == "0"


def test_real_mixed_word_stress_reports_resource_limit_as_incomplete():
    result = runner.mixed_word_determinant_stress(
        (sp.eye(5),) * 4,
        max_depth=3,
        max_level_matrices=15,
    )

    assert result["passed"] is False
    assert result["completed_requested_depth"] is False
    assert result["status"] == "resource-limit"
    assert result["max_depth_reached"] == 1
    assert result["word_count"] == 4
    assert result["next_level_matrices"] == 16


def test_cell_runs_all_gates_then_mixed_word_stress(monkeypatch):
    _patch_pre_stress_gates(monkeypatch)

    manifest = run_cell(
        "survivor",
        BASE_PARAMS,
        {"mixed_word_depth": 5, "max_level_matrices": 10_000},
        {"protocol": "test"},
        stress_fn=_passed_stress,
    )

    assert manifest["classification"] == "candidate-survivor"
    assert manifest["compute_success"] is True
    assert manifest["first_failure"] is None
    assert manifest["candidate_card"]["schema"] == "tp-exterior-candidate-v1"
    assert manifest["cell_fingerprint"] == runner.cell_fingerprint(
        "survivor",
        BASE_PARAMS,
        {"mixed_word_depth": 5, "max_level_matrices": 10_000},
    )
    assert manifest["mixed_word_stress"]["settings_seen"] == {
        "max_depth": 5,
        "max_level_matrices": 10_000,
    }
    assert manifest["candidate_score"] == {
        "klein_pluecker_residual": 0.125,
        "maximum_condition_number": 12.0,
        "minimum_determinant": 0.5,
        "minimum_mixed_word_determinant": 1.25,
        "minimum_order2_minor": -0.25,
        "minimum_relative_entry_margin": 0.25,
    }


def test_resource_limited_stress_is_an_incomplete_retryable_cell(monkeypatch):
    _patch_pre_stress_gates(monkeypatch)

    manifest = run_cell(
        "resource-limited",
        BASE_PARAMS,
        {},
        {},
        stress_fn=lambda *_args, **_kwargs: {
            "passed": False,
            "completed_requested_depth": False,
            "status": "resource-limit",
            "max_depth_requested": 6,
            "max_depth_reached": 5,
        },
    )

    assert manifest["classification"] == "mixed-word-stress-incomplete"
    assert manifest["compute_success"] is False
    assert manifest["first_failure"] == "mixed-word-stress-incomplete"


@pytest.mark.parametrize(
    ("stress_result", "classification", "compute_success"),
    [
        (
            {
                "passed": True,
                "completed_requested_depth": True,
                "status": "all-tested-words-positive",
            },
            "candidate-survivor",
            True,
        ),
        (
            {
                "passed": True,
                "completed_requested_depth": False,
                "status": "all-tested-words-positive",
            },
            "mixed-word-stress-incomplete",
            False,
        ),
        (
            {
                "passed": False,
                "completed_requested_depth": False,
                "status": "nonpositive-word-found",
            },
            "determinant-stress-failed",
            True,
        ),
        (
            {
                "passed": False,
                "completed_requested_depth": False,
                "status": "nonfinite-or-complex",
            },
            "mixed-word-stress-incomplete",
            False,
        ),
        (
            {
                "passed": False,
                "completed_requested_depth": False,
                "status": "resource-limit",
            },
            "mixed-word-stress-incomplete",
            False,
        ),
        (
            {
                "passed": False,
                "completed_requested_depth": False,
                "status": "unrecognized-status",
            },
            "mixed-word-stress-incomplete",
            False,
        ),
        ({}, "mixed-word-stress-incomplete", False),
        ([], "mixed-word-stress-incomplete", False),
    ],
)
def test_run_cell_classifies_stress_status_before_declaring_a_survivor(
    monkeypatch,
    stress_result,
    classification,
    compute_success,
):
    _patch_pre_stress_gates(monkeypatch)

    manifest = run_cell(
        f"stress-{classification}",
        BASE_PARAMS,
        {},
        {},
        stress_fn=lambda *_args, **_kwargs: stress_result,
    )

    assert manifest["classification"] == classification
    assert manifest["compute_success"] is compute_success
    assert manifest["first_failure"] == (
        None
        if classification == "candidate-survivor"
        else (
            "mixed-word-stress-gate"
            if classification == "determinant-stress-failed"
            else "mixed-word-stress-incomplete"
        )
    )


@pytest.mark.parametrize(
    ("failed_gate", "classification", "first_failure"),
    [
        ("atom", "atom-admissibility-failed", "atom-admissibility-gate"),
        (
            "compound",
            "structural-compound-failed",
            "structural-compound-gate",
        ),
        ("minor", "known-tn-or-minor-failed", "non-tn-minor-gate"),
        (
            "gauge",
            "induced-or-near-induced-gauge",
            "non-induced-gauge-gate",
        ),
    ],
)
def test_failed_pre_stress_gate_never_runs_mixed_words(
    monkeypatch,
    failed_gate,
    classification,
    first_failure,
):
    _patch_pre_stress_gates(monkeypatch)
    gate_names = {
        "atom": "atom_admissibility_gate",
        "compound": "transformed_compound_gate",
        "minor": "non_tn_minor_gate",
        "gauge": "non_induced_gauge_gate",
    }
    monkeypatch.setattr(
        runner,
        gate_names[failed_gate],
        lambda *_args, **_kwargs: {"passed": False, "status": "failed"},
    )

    def forbidden_stress(*_args, **_kwargs):
        raise AssertionError("mixed-word stress ran before every structural gate")

    manifest = run_cell(
        f"fails-{failed_gate}",
        BASE_PARAMS,
        {},
        {},
        stress_fn=forbidden_stress,
    )

    assert manifest["classification"] == classification
    assert manifest["compute_success"] is True
    assert manifest["first_failure"] == first_failure
    assert manifest["mixed_word_stress"] == {
        "status": "not-run",
        "reason": first_failure,
    }


def test_zero_shear_zero_angle_control_is_known_tn_not_a_survivor(monkeypatch):
    def forbidden_stress(*_args, **_kwargs):
        raise AssertionError("known TN control must not enter mixed-word stress")

    manifest = run_cell(
        "tn-control",
        CONTROL_PARAMS,
        {},
        {"fixture": "known-tn-control"},
        stress_fn=forbidden_stress,
    )

    assert manifest["classification"] == "known-tn-control"
    assert manifest["compute_success"] is True
    assert manifest["first_failure"] == "known-tn-control"
    assert manifest["known_mechanism"] == "strict-totally-positive"
    assert manifest["atom_admissibility"]["passed"] is True
    assert manifest["structural_compounds"]["passed"] is True
    assert manifest["mixed_word_stress"]["status"] == "not-run"


def test_binding_gate_thresholds_cannot_be_relaxed(monkeypatch):
    _patch_pre_stress_gates(monkeypatch)

    manifest = run_cell(
        "relaxed",
        BASE_PARAMS,
        {"relative_entry_margin_threshold": 1.0e-9},
        {},
        stress_fn=_passed_stress,
    )

    assert manifest["classification"] == "compute-error"
    assert manifest["compute_success"] is False
    assert manifest["first_failure"] == "settings-error"


def test_run_spec_shards_atomically_and_reuses_only_success(
    tmp_path,
    monkeypatch,
):
    _patch_pre_stress_gates(monkeypatch)
    run_dir = tmp_path / "tp-run"
    run_dir.mkdir()
    spec_path = run_dir / "run_spec.json"
    cells = [
        {
            "cell_id": f"cell-{index}",
            "params": {
                **BASE_PARAMS,
                "two_atom_scale_ratio": str(index + 1),
            },
        }
        for index in range(8)
    ]
    spec_path.write_text(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "settings": {"mixed_word_depth": 4},
                "provenance": {"protocol": "test"},
                "cells": cells,
            }
        ),
        encoding="utf-8",
    )
    reused = run_dir / "cells" / "cell-0" / "manifest.json"
    reused.parent.mkdir(parents=True)
    reused.write_text(
        json.dumps(
            {
                "schema": runner.SCHEMA,
                "cell_id": "cell-0",
                "cell_fingerprint": runner.cell_fingerprint(
                    "cell-0",
                    cells[0]["params"],
                    {"mixed_word_depth": 4},
                ),
                "compute_success": True,
                "sentinel": "reuse",
            }
        ),
        encoding="utf-8",
    )
    retry = run_dir / "cells" / "cell-2" / "manifest.json"
    retry.parent.mkdir(parents=True)
    retry.write_text(
        json.dumps({"compute_success": False, "sentinel": "replace"}),
        encoding="utf-8",
    )
    stale = run_dir / "cells" / "cell-4" / "manifest.json"
    stale.parent.mkdir(parents=True)
    stale.write_text(
        json.dumps(
            {
                "schema": runner.SCHEMA,
                "cell_id": "cell-4",
                "cell_fingerprint": "stale-fingerprint",
                "compute_success": True,
                "sentinel": "replace-stale",
            }
        ),
        encoding="utf-8",
    )
    malformed = run_dir / "cells" / "cell-6" / "manifest.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("{malformed", encoding="utf-8")

    summary = run_spec(
        spec_path,
        workers=1,
        worker_index=0,
        worker_count=2,
        stress_fn=_passed_stress,
    )

    assert summary == {
        "selected": 4,
        "completed": 3,
        "reused": 1,
        "compute_errors": 0,
    }
    assert json.loads(reused.read_text(encoding="utf-8"))["sentinel"] == "reuse"
    manifest = json.loads(retry.read_text(encoding="utf-8"))
    assert manifest["params"] == cells[2]["params"]
    assert manifest["classification"] == "candidate-survivor"
    assert json.loads(stale.read_text(encoding="utf-8"))["classification"] == (
        "candidate-survivor"
    )
    assert json.loads(malformed.read_text(encoding="utf-8"))["classification"] == (
        "candidate-survivor"
    )
    assert not list(Path(run_dir).rglob("*.tmp"))


@pytest.mark.parametrize(
    "cell_id",
    (
        "",
        ".",
        "..",
        "prefix..suffix",
        "../escape",
        "nested/escape",
        r"nested\escape",
        "drive:escape",
    ),
)
def test_run_spec_rejects_cell_ids_that_are_not_one_safe_component(
    tmp_path,
    cell_id,
):
    spec_path = tmp_path / "run_spec.json"
    spec_path.write_text(
        json.dumps(
            {"cells": [{"cell_id": cell_id, "params": BASE_PARAMS}]}
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cell_id"):
        run_spec(spec_path, stress_fn=_passed_stress)
    assert not (tmp_path.parent / "escape").exists()


def test_run_spec_rejects_duplicate_ids_and_invalid_worker_shards(tmp_path):
    spec_path = tmp_path / "run_spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "cells": [
                    {"cell_id": "same", "params": BASE_PARAMS},
                    {"cell_id": "same", "params": BASE_PARAMS},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate cell_id"):
        run_spec(spec_path, stress_fn=_passed_stress)
    with pytest.raises(ValueError, match="worker_index"):
        run_spec(
            spec_path,
            worker_index=2,
            worker_count=2,
            stress_fn=_passed_stress,
        )


def test_protocol_axes_and_control_are_explicit_and_machine_readable():
    protocol = (
        Path(__file__).resolve().parents[1]
        / "protocols"
        / "tp-exterior-extension-v1"
    )
    axes = json.loads((protocol / "axes.json").read_text(encoding="utf-8"))
    control = json.loads(
        (protocol / "control-fixture.json").read_text(encoding="utf-8")
    )

    assert axes["jacobi_strength"] == ["1/4", "1/2", "1", "2"]
    assert axes["diagonal_condition_ratio"] == ["1", "2", "4", "8"]
    assert axes["chord_shear_magnitude"] == [
        "1/64",
        "1/32",
        "1/16",
        "1/8",
        "1/4",
        "1/2",
    ]
    assert axes["chord_pattern"] == [
        [[0, 2], [3, 1]],
        [[0, 3], [4, 2]],
        [[0, 2], [2, 4], [4, 0]],
    ]
    assert axes["givens_half_angle"] == [
        "0",
        "1/64",
        "1/32",
        "1/16",
        "1/8",
        "1/4",
    ]
    assert axes["givens_plane"] == [
        [0, 7],
        [0, 8],
        [0, 9],
        [1, 5],
        [1, 6],
        [1, 9],
    ]
    assert len({tuple(plane) for plane in axes["givens_plane"]}) == 6
    assert axes["two_atom_scale_ratio"] == ["1/2", "4/5", "1", "5/4", "2"]
    assert prod(
        len(axes[name])
        for name in (
            "jacobi_strength",
            "diagonal_condition_ratio",
            "chord_shear_magnitude",
            "chord_pattern",
            "givens_half_angle",
            "givens_plane",
            "two_atom_scale_ratio",
        )
    ) == 51_840
    assert control["classification"] == "known-tn-control"
    assert control["params"]["chord_shear_magnitude"] == "0"
    assert control["params"]["givens_half_angle"] == "0"
