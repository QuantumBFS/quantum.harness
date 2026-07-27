import importlib.util
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-001"
VALIDATE = ROOT / "tracks/qcs/solutions/YueYuan/research/validator/validate.py"


def _load_attempt_model():
    spec = importlib.util.spec_from_file_location("attempt_001_model", ATTEMPT / "attempt_model.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_surrogate_model_has_rank_15_visible_curvature():
    attempt_model = _load_attempt_model()

    model = attempt_model.build_model(seed=113)

    assert model.raw_dim == 48
    assert model.visible_rank == 15
    assert model.hessian_eigenvalues_above(1e-9) == 15


def test_generated_submission_has_hessian_speedup_and_small_k_failure():
    attempt_model = _load_attempt_model()

    payload = attempt_model.build_submission()
    summary = attempt_model.summarize_submission(payload)

    assert summary["minimum_hessian_speedup"] >= 2.0
    assert summary["has_small_k_failure"] is True
    assert summary["nonzero_gaps"] == [0.03, 0.08]


def test_generated_submission_passes_committed_validator(tmp_path):
    attempt_model = _load_attempt_model()
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "submission.json").write_text(
        json.dumps(attempt_model.build_submission(), indent=2, sort_keys=True) + "\n"
    )
    report_path = candidate / "report.json"

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATE),
            str(candidate),
            "--instances",
            "dev",
            "--out",
            str(report_path),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(report_path.read_text())
    assert report["status"] == "accepted"
    assert report["score"] >= 2.0
