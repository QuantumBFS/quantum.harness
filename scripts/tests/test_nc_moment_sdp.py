import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
JULIA_PROJECT = ROOT / "julia-env"
MOMENT_SDP = ROOT / "research" / "nc_moment_sdp"


def run_julia(script, *arguments, timeout=120):
    return subprocess.run(
        ["julia", "--startup-file=no", f"--project={JULIA_PROJECT}", str(script), *map(str, arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_julia_nc_moment_sdp_suite():
    process = run_julia(MOMENT_SDP / "runtests.jl")
    assert process.returncode == 0, process.stdout + process.stderr
    assert "Test Summary" in process.stdout


def test_reproducible_runner_reports_complex_and_constrained_evidence(tmp_path):
    report_path = tmp_path / "nc-moment-sdp.json"
    process = run_julia(MOMENT_SDP / "run.jl", report_path)
    assert process.returncode == 0, process.stdout + process.stderr
    report = json.loads(report_path.read_text())
    assert report["solver"] == "Mosek via JuMP/MosekTools"
    assert "strict realification" in report["formulation"]
    assert len(report["instances"]) == 8
    instances = {(instance["name"], instance["formulation"]): instance
                 for instance in report["instances"]}

    complex_pauli = instances[("complex Pauli imaginary moment", "dense")]
    assert abs(complex_pauli["objective"] - 1.0) <= 1e-8
    assert abs(complex_pauli["complex_probe"]["real"]) <= 1e-8
    assert abs(complex_pauli["complex_probe"]["imaginary"] - 1.0) <= 1e-8
    assert complex_pauli["real_coordinate_count"] == 4

    constrained = instances[("equality and localizer", "dense")]
    assert abs(constrained["objective"] - 1.0) <= 1e-8
    assert len(constrained["minimum_localizer_eigenvalues"]) == 1
    assert constrained["minimum_localizer_eigenvalues"][0] >= -1e-8

    for name in ("CHSH / Z2", "two-site Pauli / Z2xZ2", "equality and localizer / Z2"):
        dense = instances[(name, "dense")]
        reduced = instances[(name, "symmetry")]
        assert abs(dense["objective"] - reduced["objective"]) <= 1e-7
        assert max(reduced["moment_cone_sizes"]) < dense["moment_cone_sizes"][0]
        assert reduced["real_coordinate_count"] <= dense["real_coordinate_count"]
        assert reduced["block_cubic_proxy"] > 1.0
    assert len(instances[("equality and localizer / Z2", "symmetry")]["localizer_cone_sizes"][0]) > 1

    for instance in instances.values():
        assert instance["minimum_moment_matrix_eigenvalue"] >= -1e-8
        assert instance["coordinate_consistency_residual"] <= 1e-10
        assert instance["hermiticity_residual"] <= 1e-10
        assert instance["equality_residual"] <= 1e-8
        assert instance["localizer_residual"] <= 1e-8
        assert instance["objective_residual"] <= 1e-8
