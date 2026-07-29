import json
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


def test_nonzero_disjoint_givens_is_non_induced_but_zero_control_is_not():
    candidate = construct_candidate(BASE_PARAMS)
    control = construct_candidate(CONTROL_PARAMS)

    assert runner.klein_pluecker_residual(candidate["exact_gauges"][2]) > 0.0
    assert runner.klein_pluecker_residual(control["exact_gauges"][2]) == 0.0


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
        for index in range(4)
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
        json.dumps({"compute_success": True, "sentinel": "reuse"}),
        encoding="utf-8",
    )
    retry = run_dir / "cells" / "cell-2" / "manifest.json"
    retry.parent.mkdir(parents=True)
    retry.write_text(
        json.dumps({"compute_success": False, "sentinel": "replace"}),
        encoding="utf-8",
    )

    summary = run_spec(
        spec_path,
        workers=1,
        worker_index=0,
        worker_count=2,
        stress_fn=_passed_stress,
    )

    assert summary == {
        "selected": 2,
        "completed": 1,
        "reused": 1,
        "compute_errors": 0,
    }
    assert json.loads(reused.read_text(encoding="utf-8"))["sentinel"] == "reuse"
    manifest = json.loads(retry.read_text(encoding="utf-8"))
    assert manifest["params"] == cells[2]["params"]
    assert manifest["classification"] == "candidate-survivor"
    assert not list(Path(run_dir).rglob("*.tmp"))


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
    assert len(axes["givens_plane"]) == 6
    assert all(len(plane) == 2 for plane in axes["givens_plane"])
    assert axes["two_atom_scale_ratio"] == ["1/2", "4/5", "1", "5/4", "2"]
    assert 4 * 4 * 6 * 3 * 6 * 6 * 5 == 51_840
    assert control["classification"] == "known-tn-control"
    assert control["params"]["chord_shear_magnitude"] == "0"
    assert control["params"]["givens_half_angle"] == "0"
