import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
JULIA_PROJECT = ROOT / "julia-env"
MOMENT_SDP = ROOT / "research" / "nc_moment_sdp"


def run_julia(script, *arguments, timeout=300):
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
    assert len(report["instances"]) == 12
    instances = {(instance["name"], instance["order"], instance["formulation"]): instance
                 for instance in report["instances"]}

    complex_pauli = instances[("complex Pauli imaginary moment", 1, "dense")]
    assert abs(complex_pauli["objective"] - 1.0) <= 1e-8
    assert abs(complex_pauli["complex_probe"]["real"]) <= 1e-8
    assert abs(complex_pauli["complex_probe"]["imaginary"] - 1.0) <= 1e-8
    assert complex_pauli["real_coordinate_count"] == 4

    constrained = instances[("equality and localizer", 2, "dense")]
    assert abs(constrained["objective"] - 1.0) <= 1e-8
    assert len(constrained["minimum_localizer_eigenvalues"]) == 1
    assert constrained["minimum_localizer_eigenvalues"][0] >= -1e-8

    for name, order in (("CHSH / Z2", 1), ("CHSH / Z2", 2), ("CHSH / Z2", 3),
                        ("two-site Pauli / Z2xZ2", 2),
                        ("equality and localizer / Z2", 2)):
        dense = instances[(name, order, "dense")]
        reduced = instances[(name, order, "symmetry")]
        assert abs(dense["objective"] - reduced["objective"]) <= 1e-7
        assert max(reduced["moment_cone_sizes"]) < dense["moment_cone_sizes"][0]
        assert reduced["real_coordinate_count"] <= dense["real_coordinate_count"]
        assert reduced["block_cubic_proxy"] > 1.0
    assert len(instances[("equality and localizer / Z2", 2, "symmetry")]["localizer_cone_sizes"][0]) > 1

    for instance in instances.values():
        assert instance["compile_seconds"] >= 0
        assert instance["model_build_seconds"] >= 0
        assert instance["optimize_seconds"] >= instance["solver_solve_seconds"] >= 0
        assert instance["barrier_iterations"] >= 0
        assert instance["jump_variable_count"] == instance["real_coordinate_count"]
        assert instance["minimum_moment_matrix_eigenvalue"] >= -1e-8
        assert instance["coordinate_consistency_residual"] <= 1e-10
        assert instance["hermiticity_residual"] <= 1e-10
        assert instance["equality_residual"] <= 1e-8
        assert instance["localizer_residual"] <= 1e-8
        assert instance["objective_residual"] <= 1e-8
