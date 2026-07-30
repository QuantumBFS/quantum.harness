import json

from oracle.symmetric_oddcycle_domain_runner import (
    run_cell,
    run_spec,
)


def _passed_screen(p, q, r, **settings):
    return {
        "status": "passed-all-gates",
        "parameters": {"p": p, "q": q, "r": r},
        "settings_seen": settings,
    }


def test_cell_routes_only_eligible_points_to_common_metric():
    calls = []

    def metric(p, q, r, **settings):
        calls.append((p, q, r, settings))
        return {"status": "no-strict-common-metric-numerically"}

    manifest = run_cell(
        "cell-0001",
        {"p": 1.0, "q": 1.0, "r": 1.0},
        {"short_depth": 7, "sdp_solver": "MOCK"},
        {"source_commit": "abc123"},
        screen_fn=_passed_screen,
        common_metric_fn=metric,
    )

    assert manifest["classification"] == "novelty-survivor"
    assert manifest["compute_success"] is True
    assert manifest["params"] == {"p": 1.0, "q": 1.0, "r": 1.0}
    assert manifest["settings"]["short_depth"] == 7
    assert manifest["provenance"] == {"source_commit": "abc123"}
    assert manifest["screen"]["settings_seen"] == {"short_depth": 7}
    assert manifest["common_metric"]["status"] == (
        "no-strict-common-metric-numerically"
    )
    assert calls == [(1.0, 1.0, 1.0, {"solver": "MOCK"})]
    assert manifest["elapsed_seconds"] >= 0.0


def test_cell_early_stops_before_lazy_sdp():
    def forbidden_metric(*args, **kwargs):
        raise AssertionError("SDP must stay lazy")

    exterior = run_cell(
        "cell-exterior",
        {"p": 1.0, "q": 1.0, "r": -1.0},
        {},
        {},
        screen_fn=lambda *args, **kwargs: {
            "status": "failed",
            "failure_stage": "grade4-atom-nonnegative",
        },
        common_metric_fn=forbidden_metric,
    )
    assert exterior["classification"] == "exterior-failed"
    assert exterior["compute_success"] is True
    assert exterior["common_metric"] == {
        "status": "not-run",
        "reason": "exterior-failed",
    }

    log_gate = run_cell(
        "cell-log",
        {"p": 2.0, "q": 2.0, "r": 2.0},
        {},
        {},
        screen_fn=_passed_screen,
        common_metric_fn=forbidden_metric,
    )
    assert log_gate["classification"] == "log-gate-failed"
    assert log_gate["compute_success"] is True
    assert log_gate["log_gate"]["p_q_r"] == 8.0
    assert log_gate["common_metric"] == {
        "status": "not-run",
        "reason": "p*q*r is not strictly below 8",
    }


def test_strict_metric_is_known_and_solver_errors_are_compute_errors():
    known = run_cell(
        "cell-known",
        {"p": 1.0, "q": 1.0, "r": 1.0},
        {},
        {},
        screen_fn=_passed_screen,
        common_metric_fn=lambda *args, **kwargs: {
            "status": "strict-common-metric-found",
            "verified_margin": 0.1,
        },
    )
    assert known["classification"] == "known-common-metric"
    assert known["compute_success"] is True

    error = run_cell(
        "cell-error",
        {"p": 1.0, "q": 1.0, "r": 1.0},
        {},
        {},
        screen_fn=_passed_screen,
        common_metric_fn=lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("solver unavailable")
        ),
    )
    assert error["classification"] == "compute-error"
    assert error["compute_success"] is False
    assert error["common_metric"]["error_type"] == "RuntimeError"


def test_run_spec_shards_parallel_and_reuses_only_success(tmp_path):
    run_dir = tmp_path / "run"
    spec_path = run_dir / "run_spec.json"
    run_dir.mkdir()
    spec = {
        "run_id": "oddcycle-test",
        "run_dir": str(run_dir),
        "settings": {"short_depth": 3, "sdp_solver": "MOCK"},
        "provenance": {"source_commit": "test-sha"},
        "cells": [
            {
                "cell_id": f"cell-{index:04d}",
                "params": {"p": 1.0 + index / 100.0, "q": 1.0, "r": 1.0},
            }
            for index in range(1, 5)
        ],
    }
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    reused_path = run_dir / "cells" / "cell-0001" / "manifest.json"
    reused_path.parent.mkdir(parents=True)
    reused_path.write_text(
        json.dumps({"compute_success": True, "sentinel": "reuse"}),
        encoding="utf-8",
    )
    retry_path = run_dir / "cells" / "cell-0003" / "manifest.json"
    retry_path.parent.mkdir(parents=True)
    retry_path.write_text(
        json.dumps({"compute_success": False, "sentinel": "replace"}),
        encoding="utf-8",
    )

    summary = run_spec(
        spec_path,
        workers=2,
        shard_index=0,
        shard_count=2,
        screen_fn=_passed_screen,
        common_metric_fn=lambda *args, **kwargs: {
            "status": "no-strict-common-metric-numerically"
        },
    )

    assert summary == {
        "selected": 2,
        "completed": 1,
        "reused": 1,
        "compute_errors": 0,
    }
    assert json.loads(reused_path.read_text())["sentinel"] == "reuse"
    replaced = json.loads(retry_path.read_text())
    assert replaced["compute_success"] is True
    assert replaced["classification"] == "novelty-survivor"
    assert replaced["params"] == spec["cells"][2]["params"]
    assert replaced["settings"]["short_depth"] == 3
    assert replaced["provenance"] == {"source_commit": "test-sha"}
