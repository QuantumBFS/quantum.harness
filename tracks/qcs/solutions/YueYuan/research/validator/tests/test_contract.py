import json
import pathlib
import subprocess
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "validate.py"
HEADLINE = "two_qubit_cz_minimal"


def _run_validator(candidate, *args):
    out = candidate / "report.json"
    cmd = [
        sys.executable,
        str(VALIDATE),
        str(candidate),
        "--instances",
        "dev",
        "--out",
        str(out),
        "--timeout-seconds",
        "2",
        *args,
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert out.exists(), result.stderr
    return result, json.loads(out.read_text())


def _row(method, k, gap, seed, queries, final_infidelity, claim_success=True):
    return {
        "instance": HEADLINE,
        "method": method,
        "k": k,
        "model_truth_gap": gap,
        "shots_per_query": 1024,
        "seed": seed,
        "queries_to_target": queries,
        "shot_count": queries * 1024 if queries is not None else 400 * 1024,
        "query_budget": 400,
        "final_exact_true_infidelity": final_infidelity,
        "stopped_on_exact_check": True,
        "claim_success": claim_success,
        "initial_pulse_id": "cz-shared-dev-v1",
        "stopping_rule": "exact-final-guard",
        "optimizer": "Nelder-Mead",
    }


def _valid_submission():
    runs = []
    full_queries = [260, 250, 270, 240, 280]
    hessian_queries = [96, 92, 100, 94, 98]
    random_queries = [190, 205, 210, 200, 215]
    for gap in (0.03, 0.08):
        for seed in range(5):
            runs.append(_row("full_raw_nelder_mead", 48, gap, seed, full_queries[seed], 7e-4))
            runs.append(_row("random_subspace_nelder_mead", 15, gap, seed, random_queries[seed], 8e-4))
            for k in (0, 3, 8):
                runs.append(_row("hessian_subspace_nelder_mead", k, gap, seed, None, 2e-2, False))
            for k in (15, 24, 48):
                queries = hessian_queries[seed] + (0 if k == 15 else 12)
                runs.append(_row("hessian_subspace_nelder_mead", k, gap, seed, queries, 6e-4))
    return {"schema_version": 1, "runs": runs}


def _write_submission(candidate, payload):
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / "submission.json").write_text(json.dumps(payload, indent=2) + "\n")


def test_gate_infidelity_is_global_phase_invariant():
    sys.path.insert(0, str(ROOT))
    from physics import gate_infidelity, target_gate

    cz = target_gate("CZ")
    assert gate_infidelity(np.exp(0.37j) * cz, cz) < 1e-12


def test_valid_synthetic_submission_scores_success(tmp_path):
    candidate = tmp_path / "candidate"
    _write_submission(candidate, _valid_submission())

    result, report = _run_validator(candidate)

    assert result.returncode == 0, result.stderr
    assert report["status"] == "accepted"
    assert report["score"] >= 2.0
    assert report["per_instance"][HEADLINE]["median_query_speedup"] >= 2.0
    assert report["errors"] == []
    assert report["environment"]["engine"] == "python-subprocess"


def test_precheck_is_structural_and_free(tmp_path):
    candidate = tmp_path / "candidate"
    _write_submission(candidate, _valid_submission())

    result, report = _run_validator(candidate, "--precheck")

    assert result.returncode == 0, result.stderr
    assert report["status"] == "precheck_passed"
    assert report["score"] is None
    assert report["per_instance"] == {}


def test_rejects_named_guard_failures(tmp_path):
    cases = {}

    missing_method = _valid_submission()
    missing_method["runs"] = [
        row for row in missing_method["runs"] if row["method"] != "full_raw_nelder_mead"
    ]
    cases["weak_baseline"] = (missing_method, "missing_required_method")

    one_seed = _valid_submission()
    one_seed["runs"] = [row for row in one_seed["runs"] if row["seed"] == 0]
    cases["one_seed"] = (one_seed, "insufficient_seeds")

    cherry = _valid_submission()
    cherry["runs"] = [
        row
        for row in cherry["runs"]
        if not (
            row["method"] == "hessian_subspace_nelder_mead"
            and row["k"] in {0, 3, 8, 24, 48}
        )
    ]
    cases["cherry_picked_k"] = (cherry, "missing_k_sweep")

    easy_gap = _valid_submission()
    easy_gap["runs"] = [row for row in easy_gap["runs"] if row["model_truth_gap"] == 0.03]
    cases["too_easy_gap"] = (easy_gap, "insufficient_gap_sweep")

    lucky = _valid_submission()
    for row in lucky["runs"]:
        if row["method"] == "hessian_subspace_nelder_mead" and row["claim_success"]:
            row["stopped_on_exact_check"] = False
            break
    cases["lucky_noisy_fidelity"] = (lucky, "no_exact_final_check")

    no_plateau = _valid_submission()
    for row in no_plateau["runs"]:
        if row["method"] == "hessian_subspace_nelder_mead" and row["k"] in {0, 3, 8}:
            row["claim_success"] = True
            row["queries_to_target"] = 90
            row["final_exact_true_infidelity"] = 7e-4
    cases["missing_small_k_failure"] = (no_plateau, "missing_small_k_failure")

    wrong = _valid_submission()
    for row in wrong["runs"]:
        if row["method"] == "hessian_subspace_nelder_mead" and row["claim_success"]:
            row["final_exact_true_infidelity"] = 2e-3
            break
    cases["wrong_answer"] = (wrong, "final_infidelity_above_threshold")

    for name, (payload, expected_code) in cases.items():
        candidate = tmp_path / name
        _write_submission(candidate, payload)
        result, report = _run_validator(candidate)
        assert result.returncode == 1, name
        assert report["status"] == "rejected"
        assert any(error["code"] == expected_code for error in report["errors"]), report


def test_static_scan_blocks_escape_and_cheat_signals(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "run_candidate.py").write_text(
        "import socket\nlookup_table = {'hidden': 0}\n"
    )

    result, report = _run_validator(candidate, "--precheck")

    assert result.returncode == 1
    assert report["status"] == "rejected"
    assert any(error["code"] == "forbidden_source" for error in report["errors"])


def test_timeout_candidate_is_rejected(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "run_candidate.py").write_text("while True:\n    pass\n")

    result, report = _run_validator(candidate, "--timeout-seconds", "1")

    assert result.returncode == 1
    assert report["status"] == "rejected"
    assert any(error["code"] == "candidate_timeout" for error in report["errors"])
