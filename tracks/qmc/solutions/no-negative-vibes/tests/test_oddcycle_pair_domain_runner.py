import json
from pathlib import Path

from oracle.oddcycle_pair_domain_runner import run_cell, run_spec


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
    assert manifest["short_words"]["settings_seen"] == {"max_depth": 6}
    assert manifest["endpoint_metrics"]["p_low"]["settings_seen"] == {
        "solver": "MOCK"
    }
    assert manifest["joint_metric"]["settings_seen"] == {"solver": "MOCK"}
    assert manifest["path_metric"]["settings_seen"] == {"solver": "MOCK"}
    assert manifest["time_orientation"]["metrics_seen"] == ["test-metrics"]
    assert manifest["candidate_score"] == {
        "endpoint_minimum_margin": 0.15,
        "joint_metric_margin": 0.0,
        "minimum_determinant": 0.25,
        "path_metric_margin": 0.125,
        "time_orientation_minimum": 0.5,
    }


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


def test_run_spec_uses_virtual_worker_sharding_and_reuses_only_success(tmp_path):
    run_dir = tmp_path / "pair-run"
    spec_path = run_dir / "run_spec.json"
    run_dir.mkdir()
    cells = [
        {"cell_id": f"cell-{index}", "params": {**CONTROL_PARAMS, "q": index}}
        for index in range(4)
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
    reused.write_text(json.dumps({"compute_success": True, "sentinel": "reuse"}))
    retry = run_dir / "cells" / "cell-2" / "manifest.json"
    retry.parent.mkdir(parents=True)
    retry.write_text(json.dumps({"compute_success": False, "sentinel": "replace"}))

    summary = run_spec(
        spec_path,
        workers=1,
        worker_index=0,
        worker_count=2,
        **_runner_dependencies(),
    )

    assert summary == {
        "selected": 2,
        "completed": 1,
        "reused": 1,
        "compute_errors": 0,
    }
    assert json.loads(reused.read_text())["sentinel"] == "reuse"
    manifest = json.loads(retry.read_text())
    assert manifest["params"] == cells[2]["params"]
    assert manifest["classification"] == "candidate-survivor"
    assert not list(Path(run_dir).rglob("*.tmp"))


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

    assert 0.001 in axes["p_low"]
    assert 0.8 in axes["p_high"]
    assert 1.0 in axes["q"]
    assert 1.0 in axes["r"]
    assert fixture["params"] == CONTROL_PARAMS
