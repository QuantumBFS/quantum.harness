import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[2] / "skills/phase-diagram/scripts/phase_diagram.py"
SPEC = importlib.util.spec_from_file_location("phase_diagram", MODULE_PATH)
phase = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(phase)


UV_COMMAND = ["uv", "run", "--script", str(MODULE_PATH)]


def run_cli(*args, check=True):
    return subprocess.run(
        [*UV_COMMAND, *map(str, args)], check=check, capture_output=True, text=True,
        cwd=MODULE_PATH.parents[3],
    )


def policy(slices=None):
    axes = {
        "control": {"name": "g", "bounds": [0.0, 1.0], "initial_points": [0.0, 0.5, 1.0]},
        "size": {"name": "L", "values": [8, 12, 16], "initial_count": 2},
    }
    if slices is not None:
        axes["slice"] = {"name": "temperature", "values": slices}
    return {
        "schema_version": 1,
        "goal_id": "test-boundary",
        "pattern": "finite_size_crossing",
        "axes": axes,
        "observable": {"name": "ratio", "value_field": "value", "error_field": "error"},
        "criteria": {"sigma": 2.0, "target_width": 0.1, "max_statistics_multiplier": 4,
                     "final_pair_required": True},
        "execution": {"controller": "local", "runner": "uv", "base_budget": 1000,
                      "poll_seconds": 60, "max_actions": 50},
    }


def record(g, size, value, error=0.01, budget=1000, temperature=None):
    params = {"g": g, "L": size}
    if temperature is not None:
        params["temperature"] = temperature
    return {"params": params, "status": "success", "value": value, "error": error,
            "budget": budget, "artifact": f"results/g{g}-L{size}.json"}


def observations(records):
    return {"schema_version": 1, "records": records}


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_empty_observations_plan_coarse_grid():
    report = phase.decide(policy(), observations([]))
    assert report["status"] == "ACTION_REQUIRED"
    specs = [item["spec"] for item in report["actions"]]
    assert len(specs) == 6
    assert {item["params"]["L"] for item in specs} == {8, 12}
    assert {item["params"]["g"] for item in specs} == {0.0, 0.5, 1.0}


def test_crossing_pattern_refines_then_promotes_then_completes():
    base = []
    for g, delta in ((0.0, -0.4), (0.5, 0.1), (1.0, 0.5)):
        base.extend([record(g, 8, 0.5), record(g, 12, 0.5 + delta)])

    refine = phase.decide(policy(), observations(base))
    assert refine["status"] == "ACTION_REQUIRED"
    assert {item["spec"]["params"]["g"] for item in refine["actions"]} == {0.25}

    refined = base + [record(0.25, 8, 0.5), record(0.25, 12, 0.3)]
    next_refine = phase.decide(policy(), observations(refined))
    assert {item["spec"]["params"]["g"] for item in next_refine["actions"]} == {0.375}

    narrowed = refined + [record(0.375, 8, 0.5), record(0.375, 12, 0.46),
                          record(0.4375, 8, 0.5), record(0.4375, 12, 0.54)]
    promote = phase.decide(policy(), observations(narrowed))
    assert promote["status"] == "ACTION_REQUIRED"
    assert {item["spec"]["params"]["L"] for item in promote["actions"]} == {16}
    assert {item["spec"]["params"]["g"] for item in promote["actions"]} == {0.375, 0.4375}

    final = narrowed + [record(0.375, 16, 0.42), record(0.4375, 16, 0.58)]
    complete = phase.decide(policy(), observations(final))
    assert complete["status"] == "COMPLETE"
    assert len(complete["accepted_artifacts"]) == 4
    assert complete["evidence"][0]["size_pair"] == [12, 16]


def test_inconclusive_sign_requests_more_statistics_then_escalates():
    records = []
    for g, delta, error in ((0.0, -0.4, 0.01), (0.5, 0.01, 0.1), (1.0, 0.4, 0.01)):
        records.extend([record(g, 8, 0.5, error), record(g, 12, 0.5 + delta, error)])
    report = phase.decide(policy(), observations(records))
    assert report["status"] == "ACTION_REQUIRED"
    assert {item["spec"]["budget"] for item in report["actions"]} == {2000}
    assert {item["spec"]["params"]["g"] for item in report["actions"]} == {0.5}

    exhausted = [dict(item, budget=4000) if item["params"]["g"] == 0.5 else item for item in records]
    report = phase.decide(policy(), observations(exhausted))
    assert report["status"] == "HUMAN_REQUIRED"


def test_pending_and_failed_records_stop_new_work():
    pending = {"params": {"g": 0.0, "L": 8}, "status": "pending", "budget": 1000}
    assert phase.decide(policy(), observations([pending]))["status"] == "WAITING"
    failed = {"params": {"g": 0.0, "L": 8}, "status": "failed", "artifact": "failure.json"}
    assert phase.decide(policy(), observations([failed]))["status"] == "HUMAN_REQUIRED"


def test_slice_axis_plans_each_boundary_independently():
    report = phase.decide(policy([0.1, 0.2]), observations([]))
    assert len(report["actions"]) == 12
    assert {item["spec"]["params"]["temperature"] for item in report["actions"]} == {0.1, 0.2}


def test_transaction_is_authorized_idempotent_and_crash_visible(tmp_path):
    policy_path, state_path = tmp_path / "policy.json", tmp_path / "state.json"
    report_path, spec_path = tmp_path / "report.json", tmp_path / "spec.json"
    write_json(policy_path, policy())
    phase.initialize(policy_path, state_path)
    report = phase.decide(policy(), observations([]))
    write_json(report_path, report)
    phase.ingest(policy_path, state_path, report_path)
    action_spec = report["actions"][0]["spec"]
    write_json(spec_path, action_spec)
    planned = phase.plan(policy_path, state_path, spec_path)
    assert phase.plan(policy_path, state_path, spec_path)["action_id"] == planned["action_id"]
    phase.advance(policy_path, state_path, planned["action_id"], "PREPARED", None, None)
    phase.advance(policy_path, state_path, planned["action_id"], "SUBMITTING", None, None)
    assert phase.inspect(policy_path, state_path)["unresolved_submitting"][0]["action_id"] == planned["action_id"]
    with pytest.raises(ValueError, match="durable receipt"):
        phase.advance(policy_path, state_path, planned["action_id"], "SUBMITTED", None, None)
    phase.advance(policy_path, state_path, planned["action_id"], "SUBMITTED", "job-42", None)
    assert phase.advance(policy_path, state_path, planned["action_id"], "REGISTERED", None, None)["state"] == "REGISTERED"


def test_unapproved_spec_and_illegal_transition_are_rejected(tmp_path):
    policy_path, state_path = tmp_path / "policy.json", tmp_path / "state.json"
    report_path, spec_path = tmp_path / "report.json", tmp_path / "spec.json"
    write_json(policy_path, policy())
    phase.initialize(policy_path, state_path)
    write_json(spec_path, {"kind": "phase-diagram-cell", "params": {"g": 0.2, "L": 8}, "budget": 1000})
    with pytest.raises(ValueError, match="not authorized"):
        phase.plan(policy_path, state_path, spec_path)
    report = phase.decide(policy(), observations([]))
    write_json(report_path, report)
    phase.ingest(policy_path, state_path, report_path)
    write_json(spec_path, report["actions"][0]["spec"])
    action = phase.plan(policy_path, state_path, spec_path)
    with pytest.raises(ValueError, match="illegal action transition"):
        phase.advance(policy_path, state_path, action["action_id"], "REGISTERED", None, None)


def test_controller_policy_requires_local_uv_execution():
    invalid = policy()
    invalid["execution"] = dict(invalid["execution"], controller="remote")
    with pytest.raises(ValueError, match="controller must be local"):
        phase.decide(invalid, observations([]))

    script = MODULE_PATH.read_text(encoding="utf-8")
    skill = (MODULE_PATH.parents[1] / "SKILL.md").read_text(encoding="utf-8")
    assert '# requires-python = ">=3.11"' in script
    assert "# dependencies = []" in script
    assert "python3 skills/phase-diagram" not in skill
    assert "uv run --script skills/phase-diagram" in skill


def test_cli_scaffold_and_check_work_from_fresh_directory(tmp_path):
    runtime = tmp_path / "fresh-project"
    completed = run_cli("scaffold", "--directory", runtime)
    created = json.loads(completed.stdout)
    assert Path(created["policy"]).is_file()
    assert Path(created["observations"]).is_file()

    cells = runtime / "cells"
    manifest = cells / "cell-0001" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    write_json(manifest, {
        "params": {"coupling": 0.0, "L": 8}, "status": "success",
        "settings": {"budget": 1000},
        "observables": {"ratio": {"value": 0.2, "error": 0.01}},
    })
    completed = run_cli(
        "collect", "--policy", created["policy"], "--cells-dir", cells,
        "--output", created["observations"],
    )
    collected = json.loads(completed.stdout)
    assert collected["records"][0]["value"] == 0.2
    assert collected["records"][0]["artifact"] == str(manifest)

    replacement = cells / "cell-0002" / "manifest.json"
    replacement.parent.mkdir(parents=True)
    write_json(replacement, {
        "params": {"coupling": 0.0, "L": 8}, "status": "success",
        "settings": {"budget": 2000},
        "observables": {"ratio": {"value": 0.21, "error": 0.005}},
    })
    completed = run_cli(
        "collect", "--policy", created["policy"], "--cells-dir", cells,
        "--output", created["observations"],
    )
    collected = json.loads(completed.stdout)
    assert len(collected["records"]) == 1
    assert collected["records"][0]["budget"] == 2000
    assert collected["records"][0]["artifact"] == str(replacement)

    ambiguous = cells / "cell-0003" / "manifest.json"
    ambiguous.parent.mkdir(parents=True)
    write_json(ambiguous, {
        "params": {"coupling": 0.0, "L": 8}, "status": "success",
        "settings": {"budget": 2000},
        "observables": {"ratio": {"value": 0.22, "error": 0.005}},
    })
    completed = run_cli(
        "collect", "--policy", created["policy"], "--cells-dir", cells,
        "--output", created["observations"], check=False,
    )
    assert completed.returncode == 2
    assert "ambiguous manifests" in completed.stderr
    ambiguous.unlink()

    report_path = runtime / "report.json"
    completed = run_cli(
        "check", "--policy", created["policy"], "--observations", created["observations"],
        "--report", report_path,
    )
    assert json.loads(completed.stdout)["status"] == "ACTION_REQUIRED"
    assert json.loads(report_path.read_text())["status"] == "ACTION_REQUIRED"

    state_path = runtime / "state.json"
    run_cli(
        "init", "--policy", created["policy"], "--state", state_path,
    )
    assert json.loads(state_path.read_text())["control_state"] == "RUNNING"
