import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
JULIA_PROJECT = ROOT / "julia-env"
MOMENT_SDP = ROOT / "research" / "nc_moment_sdp"


def run_julia(script, *arguments, timeout=120):
    return subprocess.run(
        ["julia", f"--project={JULIA_PROJECT}", str(script), *map(str, arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_julia_nc_moment_sdp_suite():
    process = run_julia(MOMENT_SDP / "runtests.jl")
    assert process.returncode == 0, process.stdout + process.stderr
    assert "Test Summary" in process.stdout


def test_reproducible_runner_reports_dense_reduced_evidence(tmp_path):
    report_path = tmp_path / "nc-moment-sdp.json"
    process = run_julia(MOMENT_SDP / "run.jl", report_path)
    assert process.returncode == 0, process.stdout + process.stderr
    report = json.loads(report_path.read_text())
    assert report["solver"] == "Mosek via JuMP/MosekTools"
    assert len(report["instances"]) == 2
    expected_objectives = {
        "CHSH / Z2": 2 * 2**0.5,
        "two-site Pauli-style / Z2xZ2": 2.0,
    }
    for instance in report["instances"]:
        assert instance["order"] in (1, 2)
        assert instance["dense_free_moment_count"] > instance["reduced_free_moment_count"]
        assert abs(instance["dense_objective"] - expected_objectives[instance["name"]]) <= 1e-7
        assert abs(instance["reduced_objective"] - expected_objectives[instance["name"]]) <= 1e-7
        assert instance["objective_difference"] <= 1e-7
        assert instance["dense_minimum_eigenvalue"] >= -1e-7
        assert instance["reduced_minimum_eigenvalue"] >= -1e-7
        assert instance["maximum_equality_residual"] <= 1e-8
        assert instance["maximum_objective_residual"] <= 1e-8
        assert instance["psd_block_cubic_proxy"] > 1
