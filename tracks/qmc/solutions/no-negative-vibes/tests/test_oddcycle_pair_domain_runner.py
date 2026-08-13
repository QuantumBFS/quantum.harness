import json
from pathlib import Path

import numpy as np
import pytest

import oracle.oddcycle_pair_domain_runner as pair_runner
from oracle.oddcycle_pair_domain_runner import (
    numerical_time_orientation,
    run_cell,
    run_spec,
)


CONTROL_PARAMS = {"p_low": 0.001, "p_high": 0.8, "q": 1.0, "r": 1.0}


def _positive_words(points, **settings):
    return {
        "status": "all-tested-words-positive",
        "minimum_determinant": 0.25,
        "points": points,
        "settings_seen": settings,
    }


def _endpoint_metric(p, q, r, **settings):
    return {
        "status": "strict-common-metric-found",
        "verified_margin": 0.15,
        "parameters": {"p": p, "q": q, "r": r},
        "settings_seen": settings,
    }


def _joint_metric(points, **settings):
    return {
        "status": "no-strict-common-metric-numerically",
        "verified_margin": 0.0,
        "points": points,
        "settings_seen": settings,
    }


def _path_metric(points, **settings):
    return {
        "status": "strict-last-letter-path-metric-found",
        "verified_margin": 0.125,
        "correct_split_inertia": True,
        "metrics": ["test-metrics"],
        "points": points,
        "settings_seen": settings,
    }


def _oriented(points, metrics, **settings):
    return {
        "status": "time-orientation-passed",
        "all_inverse_transitions_future_preserving": True,
        "minimum_oriented_scalar": 0.5,
        "points": points,
        "metrics_seen": metrics,
        "settings_seen": settings,
    }


def _runner_dependencies():
    return {
        "joint_words_fn": _positive_words,
        "endpoint_metric_fn": _endpoint_metric,
        "joint_metric_fn": _joint_metric,
        "path_metric_fn": _path_metric,
        "orientation_fn": _oriented,
    }


def _dependency_override(stage, result):
    dependencies = _runner_dependencies()
    names = {
        "short_words": "joint_words_fn",
        "endpoint_metric": "endpoint_metric_fn",
        "joint_metric": "joint_metric_fn",
        "path_metric": "path_metric_fn",
        "time_orientation": "orientation_fn",
    }
    dependencies[names[stage]] = lambda *_args, **_kwargs: result
    return dependencies


def test_cell_runs_pair_gates_and_records_compact_score():
    manifest = run_cell(
        "control",
        CONTROL_PARAMS,
        {"short_word_depth": 6, "sdp_solver": "MOCK"},
        {"source_commit": "abc123"},
        **_runner_dependencies(),
    )

    assert manifest["classification"] == "candidate-survivor"
    assert manifest["compute_success"] is True
    assert manifest["first_failure"] is None
    assert manifest["points"] == [[0.001, 1.0, 1.0], [0.8, 1.0, 1.0]]
    assert manifest["short_words"]["settings_seen"] == {
        "max_depth": 6,
        "max_level_matrices": 2_000_000,
        "determinant_tolerance": 1.0e-10,
    }
    assert manifest["endpoint_metrics"]["p_low"]["settings_seen"] == {
        "solver": "MOCK",
        "validation_tolerance": 1.0e-7,
        "solver_options": {},
    }
    assert manifest["joint_metric"]["settings_seen"] == {
        "solver": "MOCK",
        "validation_tolerance": 1.0e-7,
        "solver_options": {},
    }
    assert manifest["path_metric"]["settings_seen"] == {
        "solver": "MOCK",
        "validation_tolerance": 1.0e-7,
    }
    assert manifest["time_orientation"]["metrics_seen"] == ["test-metrics"]
    assert manifest["time_orientation"]["settings_seen"] == {
        "tolerance": 1.0e-7
    }
    assert manifest["candidate_score"] == {
        "endpoint_minimum_margin": 0.15,
        "joint_metric_margin": 0.0,
        "minimum_determinant": 0.25,
        "path_metric_margin": 0.125,
        "time_orientation_minimum": 0.5,
    }


@pytest.mark.parametrize(
    ("status", "compute_success", "classification"),
    [
        ("exact-nonpositive-word-found", True, "short-word-failed"),
        ("resource-limit", False, "short-word-incomplete"),
        ("nonfinite", False, "short-word-incomplete"),
        ("floating-point-resolution-limit", False, "short-word-incomplete"),
        ("solver-inconclusive", False, "short-word-incomplete"),
        ("unrecognized-status", False, "short-word-incomplete"),
    ],
)
def test_short_word_statuses_distinguish_terminal_from_retryable(
    status,
    compute_success,
    classification,
):
    manifest = run_cell(
        f"short-{status}",
        CONTROL_PARAMS,
        {},
        {},
        **_dependency_override(
            "short_words",
            {"status": status, "minimum_determinant": 0.0},
        ),
    )

    assert manifest["classification"] == classification
    assert manifest["compute_success"] is compute_success
    assert manifest["first_failure"] == "short-word-gate"


@pytest.mark.parametrize(
    ("stage", "status", "compute_success", "classification"),
    [
        (
            "endpoint_metric",
            "no-strict-common-metric-numerically",
            True,
            "endpoint-metric-failed",
        ),
        (
            "endpoint_metric",
            "solver-inconclusive",
            False,
            "endpoint-metric-inconclusive",
        ),
        (
            "endpoint_metric",
            "nonfinite",
            False,
            "endpoint-metric-inconclusive",
        ),
        (
            "endpoint_metric",
            "unrecognized-status",
            False,
            "endpoint-metric-inconclusive",
        ),
        (
            "joint_metric",
            "strict-common-metric-found",
            True,
            "joint-common-metric",
        ),
        (
            "joint_metric",
            "solver-inconclusive",
            False,
            "joint-metric-inconclusive",
        ),
        (
            "joint_metric",
            "nonfinite",
            False,
            "joint-metric-inconclusive",
        ),
        (
            "joint_metric",
            "unrecognized-status",
            False,
            "joint-metric-inconclusive",
        ),
        (
            "path_metric",
            "no-strict-path-metric-numerically",
            True,
            "path-metric-failed",
        ),
        (
            "path_metric",
            "solver-inconclusive",
            False,
            "path-metric-inconclusive",
        ),
        (
            "path_metric",
            "nonfinite",
            False,
            "path-metric-inconclusive",
        ),
        (
            "path_metric",
            "unrecognized-status",
            False,
            "path-metric-inconclusive",
        ),
        (
            "time_orientation",
            "time-orientation-failed",
            True,
            "time-orientation-failed",
        ),
        (
            "time_orientation",
            "nonfinite",
            False,
            "time-orientation-inconclusive",
        ),
        (
            "time_orientation",
            "unrecognized-status",
            False,
            "time-orientation-inconclusive",
        ),
    ],
)
def test_numerical_gate_statuses_distinguish_terminal_from_retryable(
    stage,
    status,
    compute_success,
    classification,
):
    result = {"status": status}
    if stage == "path_metric":
        result["correct_split_inertia"] = False
    if stage == "time_orientation":
        result["all_inverse_transitions_future_preserving"] = False
    manifest = run_cell(
        f"{stage}-{status}",
        CONTROL_PARAMS,
        {},
        {},
        **_dependency_override(stage, result),
    )

    assert manifest["classification"] == classification
    assert manifest["compute_success"] is compute_success


def test_cell_rejects_any_short_word_depth_other_than_six():
    def forbidden_words(*args, **kwargs):
        raise AssertionError("a nonbinding depth must not invoke the oracle")

    manifest = run_cell(
        "shallow-depth",
        CONTROL_PARAMS,
        {"short_word_depth": 5},
        {},
        joint_words_fn=forbidden_words,
        endpoint_metric_fn=_endpoint_metric,
        joint_metric_fn=_joint_metric,
        path_metric_fn=_path_metric,
        orientation_fn=_oriented,
    )

    assert manifest["classification"] == "compute-error"
    assert manifest["compute_success"] is False
    assert manifest["first_failure"] == "settings-error"
    assert manifest["settings_validation"]["error_type"] == "ValueError"


def test_joint_common_metric_stops_before_path_metric():
    def forbidden_path(*args, **kwargs):
        raise AssertionError("path metric must not run after a joint metric")

    manifest = run_cell(
        "joint-known",
        CONTROL_PARAMS,
        {},
        {},
        joint_words_fn=_positive_words,
        endpoint_metric_fn=_endpoint_metric,
        joint_metric_fn=lambda *args, **kwargs: {
            "status": "strict-common-metric-found",
            "verified_margin": 0.2,
        },
        path_metric_fn=forbidden_path,
        orientation_fn=_oriented,
    )

    assert manifest["classification"] == "joint-common-metric"
    assert manifest["compute_success"] is True
    assert manifest["first_failure"] == "joint-common-metric"
    assert manifest["path_metric"] == {
        "status": "not-run",
        "reason": "joint-common-metric",
    }


def test_solver_exception_is_a_compute_error_not_scientific_failure():
    manifest = run_cell(
        "solver-error",
        CONTROL_PARAMS,
        {},
        {},
        joint_words_fn=_positive_words,
        endpoint_metric_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("solver unavailable")
        ),
        joint_metric_fn=_joint_metric,
        path_metric_fn=_path_metric,
        orientation_fn=_oriented,
    )

    assert manifest["classification"] == "compute-error"
    assert manifest["compute_success"] is False
    assert manifest["first_failure"] == "endpoint-metric-error"
    assert manifest["endpoint_metrics"]["p_low"]["error_type"] == "RuntimeError"


def test_cell_fingerprint_covers_schema_cell_params_and_resolved_settings(
    monkeypatch,
):
    base = pair_runner.cell_fingerprint("cell-a", CONTROL_PARAMS, {})

    assert pair_runner.cell_fingerprint(
        "cell-a",
        {**CONTROL_PARAMS, "p_low": "0.001", "q": 1},
        {
            "short_word_depth": 6,
            "max_level_matrices": 2_000_000,
            "determinant_tolerance": 1.0e-10,
            "sdp_solver": "CLARABEL",
            "sdp_validation_tolerance": 1.0e-7,
            "sdp_solver_options": {},
            "time_orientation_tolerance": 1.0e-7,
        },
    ) == base
    assert pair_runner.cell_fingerprint("cell-b", CONTROL_PARAMS, {}) != base
    assert pair_runner.cell_fingerprint(
        "cell-a",
        {**CONTROL_PARAMS, "p_high": 0.825},
        {},
    ) != base
    assert pair_runner.cell_fingerprint(
        "cell-a",
        CONTROL_PARAMS,
        {"max_level_matrices": 1_000_000},
    ) != base
    monkeypatch.setattr(pair_runner, "SCHEMA", "changed-schema")
    assert pair_runner.cell_fingerprint("cell-a", CONTROL_PARAMS, {}) != base


def test_run_spec_reuses_only_matching_identity_and_replaces_bad_manifests(
    tmp_path,
):
    run_dir = tmp_path / "pair-run"
    spec_path = run_dir / "run_spec.json"
    run_dir.mkdir()
    cells = [
        {"cell_id": f"cell-{index}", "params": {**CONTROL_PARAMS, "q": index}}
        for index in range(5)
    ]
    spec_path.write_text(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "settings": {"short_word_depth": 6, "sdp_solver": "MOCK"},
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
                "schema": pair_runner.SCHEMA,
                "cell_id": "cell-0",
                "cell_fingerprint": pair_runner.cell_fingerprint(
                    "cell-0",
                    cells[0]["params"],
                    {"short_word_depth": 6, "sdp_solver": "MOCK"},
                ),
                "compute_success": True,
                "classification": "scientific-terminal",
            }
        ),
        encoding="utf-8",
    )
    retry = run_dir / "cells" / "cell-1" / "manifest.json"
    retry.parent.mkdir(parents=True)
    retry.write_text(
        json.dumps({"compute_success": False, "legacy": "replace"}),
        encoding="utf-8",
    )
    stale = run_dir / "cells" / "cell-2" / "manifest.json"
    stale.parent.mkdir(parents=True)
    stale.write_text(
        json.dumps(
            {
                "schema": pair_runner.SCHEMA,
                "cell_id": "cell-2",
                "cell_fingerprint": "stale",
                "compute_success": True,
            }
        ),
        encoding="utf-8",
    )
    malformed = run_dir / "cells" / "cell-3" / "manifest.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("{malformed", encoding="utf-8")
    non_mapping = run_dir / "cells" / "cell-4" / "manifest.json"
    non_mapping.parent.mkdir(parents=True)
    non_mapping.write_text("[]", encoding="utf-8")

    summary = run_spec(
        spec_path,
        workers=1,
        **_runner_dependencies(),
    )

    assert summary == {
        "selected": 5,
        "completed": 4,
        "reused": 1,
        "compute_errors": 0,
    }
    assert json.loads(reused.read_text(encoding="utf-8"))["classification"] == (
        "scientific-terminal"
    )
    for path in (retry, stale, malformed, non_mapping):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert manifest["schema"] == pair_runner.SCHEMA
        assert manifest["classification"] == "candidate-survivor"
        assert manifest["cell_fingerprint"]
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
            {"cells": [{"cell_id": cell_id, "params": CONTROL_PARAMS}]}
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cell_id"):
        run_spec(spec_path, **_runner_dependencies())
    assert not (tmp_path.parent / "escape").exists()


def test_omitted_run_dir_defaults_to_nested_spec_directory(tmp_path):
    spec_directory = tmp_path / "nested" / "spec"
    spec_directory.mkdir(parents=True)
    spec_path = spec_directory / "run_spec.json"
    spec_path.write_text(
        json.dumps(
            {"cells": [{"cell_id": "only", "params": CONTROL_PARAMS}]}
        ),
        encoding="utf-8",
    )

    summary = run_spec(spec_path, **_runner_dependencies())

    assert summary["completed"] == 1
    assert (spec_directory / "cells" / "only" / "manifest.json").is_file()
    assert not (
        spec_directory / "nested" / "spec" / "cells" / "only" / "manifest.json"
    ).exists()


def test_run_spec_rejects_invalid_shared_or_cell_depth_and_duplicate_ids(tmp_path):
    spec_path = tmp_path / "run_spec.json"

    def write_spec(settings, cells):
        spec_path.write_text(
            json.dumps({"settings": settings, "cells": cells}),
            encoding="utf-8",
        )

    write_spec({"short_word_depth": 5}, [{"cell_id": "one", "params": CONTROL_PARAMS}])
    with pytest.raises(ValueError, match="short_word_depth"):
        run_spec(spec_path, **_runner_dependencies())

    write_spec(
        {"short_word_depth": 6},
        [
            {"cell_id": "one", "params": CONTROL_PARAMS},
            {
                "cell_id": "two",
                "params": CONTROL_PARAMS,
                "settings": {"short_word_depth": 7},
            },
        ],
    )
    with pytest.raises(ValueError, match="short_word_depth"):
        run_spec(spec_path, **_runner_dependencies())

    write_spec(
        {"short_word_depth": 6},
        [
            {"cell_id": "duplicate", "params": CONTROL_PARAMS},
            {"cell_id": "duplicate", "params": CONTROL_PARAMS},
        ],
    )
    with pytest.raises(ValueError, match="duplicate cell_id"):
        run_spec(spec_path, **_runner_dependencies())


def _positive_split_metric():
    return np.diag([-1.0, -1.0, -1.0, -1.0, 1.0])


def test_numerical_time_orientation_accepts_synchronized_future_sheets(monkeypatch):
    monkeypatch.setattr(
        pair_runner,
        "joint_alphabet",
        lambda points: tuple(np.eye(5) for _ in range(4)),
    )

    result = numerical_time_orientation(
        ((0.001, 1.0, 1.0), (0.8, 1.0, 1.0)),
        [_positive_split_metric() for _ in range(4)],
    )

    assert result["status"] == "time-orientation-passed"
    assert result["all_inverse_transitions_future_preserving"] is True
    assert result["minimum_oriented_scalar"] == 1.0


def test_numerical_time_orientation_rejects_unsynchronized_transition(monkeypatch):
    atoms = [np.eye(5) for _ in range(4)]
    atoms[2] = np.diag([1.0, 1.0, 1.0, -1.0, -1.0])
    monkeypatch.setattr(pair_runner, "joint_alphabet", lambda points: tuple(atoms))

    result = numerical_time_orientation(
        ((0.001, 1.0, 1.0), (0.8, 1.0, 1.0)),
        [_positive_split_metric() for _ in range(4)],
    )

    assert result["status"] == "time-orientation-failed"
    assert result["all_inverse_transitions_future_preserving"] is False
    assert result["minimum_oriented_scalar"] == -1.0


def test_numerical_time_orientation_rejects_invalid_metric_inertia(monkeypatch):
    monkeypatch.setattr(
        pair_runner,
        "joint_alphabet",
        lambda points: tuple(np.eye(5) for _ in range(4)),
    )

    result = numerical_time_orientation(
        ((0.001, 1.0, 1.0), (0.8, 1.0, 1.0)),
        [np.eye(5) for _ in range(4)],
    )

    assert result["status"] == "time-orientation-failed"
    assert result["metric_inertias"] == [
        {"positive": 5, "negative": 0, "zero": 0}
        for _ in range(4)
    ]


def test_numerical_time_orientation_reports_nonfinite_atom_data(monkeypatch):
    atoms = [np.eye(5) for _ in range(4)]
    atoms[0][0, 0] = np.inf
    monkeypatch.setattr(pair_runner, "joint_alphabet", lambda points: tuple(atoms))

    result = numerical_time_orientation(
        ((0.001, 1.0, 1.0), (0.8, 1.0, 1.0)),
        [_positive_split_metric() for _ in range(4)],
    )

    assert result["status"] == "nonfinite"
    assert result["finite_orientation_data"] is False
    assert result["all_inverse_transitions_future_preserving"] is False


def test_protocol_axes_include_the_successful_control_fixture():
    protocol = (
        Path(__file__).resolve().parents[1]
        / "protocols"
        / "oddcycle-pair-frontier-v1"
    )
    axes = json.loads((protocol / "axes.json").read_text(encoding="utf-8"))
    fixture = json.loads(
        (protocol / "control-fixture.json").read_text(encoding="utf-8")
    )

    assert axes == {
        "p_low": [
            0.00001,
            0.00002,
            0.00005,
            0.0001,
            0.0002,
            0.0005,
            0.001,
            0.002,
            0.003,
            0.005,
            0.0075,
            0.01,
            0.015,
            0.02,
            0.03,
            0.04,
            0.05,
        ],
        "p_high": [
            0.55,
            0.575,
            0.6,
            0.625,
            0.65,
            0.675,
            0.7,
            0.725,
            0.75,
            0.775,
            0.8,
            0.825,
            0.85,
            0.875,
            0.9,
            0.925,
            0.95,
            0.975,
            1.0,
            1.025,
            1.05,
            1.075,
            1.1,
            1.125,
            1.15,
            1.175,
            1.2,
            1.225,
            1.25,
        ],
        "q": [0.9, 0.95, 1.0, 1.05, 1.1],
        "r": [0.9, 0.95, 1.0, 1.05, 1.1],
    }
    assert len(axes["p_low"]) == 17
    assert len(axes["p_high"]) == 29
    assert len(axes["q"]) == 5
    assert len(axes["r"]) == 5
    assert 17 * 29 * 5 * 5 == 12325
    assert fixture["params"] == CONTROL_PARAMS
