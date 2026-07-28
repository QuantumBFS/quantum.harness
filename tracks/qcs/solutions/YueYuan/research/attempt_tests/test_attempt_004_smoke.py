import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"


def test_attempt_004_local_smoke_emits_required_records(tmp_path):
    out_dir = tmp_path / "smoke"
    result = subprocess.run(
        [sys.executable, str(ATTEMPT / "run_local_smoke.py"), "--out", str(out_dir), "--fast"],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    runs = out_dir / "runs.jsonl"
    assert runs.exists()
    rows = [json.loads(line) for line in runs.read_text().splitlines() if line.strip()]
    assert rows
    assert {"one_qubit_x", "two_qubit_cz"} <= {row["system"] for row in rows}
    assert {
        "model_only",
        "full_space_nelder_mead",
        "random_subspace_nelder_mead",
        "hessian_subspace_nelder_mead",
    } <= {row["method"] for row in rows}
    assert {"small", "medium", "large"} <= {row["mismatch"] for row in rows}
    assert {128, 512, 2048} <= {row["shots_per_query"] for row in rows}


def test_attempt_004_make_figures_writes_required_pngs(tmp_path):
    out_dir = tmp_path / "smoke"
    smoke = subprocess.run(
        [sys.executable, str(ATTEMPT / "run_local_smoke.py"), "--out", str(out_dir), "--fast"],
        text=True,
        capture_output=True,
    )
    assert smoke.returncode == 0, smoke.stderr
    figs = subprocess.run(
        [sys.executable, str(ATTEMPT / "make_figures.py"), "--results", str(out_dir)],
        text=True,
        capture_output=True,
    )
    assert figs.returncode == 0, figs.stderr
    expected = {
        "model_optimization_history.png",
        "hessian_spectrum.png",
        "queries_to_target_vs_k.png",
        "shots_to_target_vs_k.png",
        "advantage_vs_gap.png",
        "success_rate_vs_shots.png",
        "failure_mode.png",
    }
    actual = {path.name for path in (out_dir / "figures").glob("*.png")}
    assert expected <= actual
    assert (out_dir / "summary.json").exists()


def test_attempt_004_candidate_export_has_challenge_methods(tmp_path):
    out_file = tmp_path / "submission.json"
    result = subprocess.run(
        [sys.executable, str(ATTEMPT / "run_candidate.py"), "--out", str(out_file), "--fast"],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_file.read_text())
    assert payload["schema_version"] == 1
    assert payload["attempt"] == "attempt-004-full-checklist"
    methods = {group["method"] for group in payload["results"]}
    assert {
        "full_space_nelder_mead",
        "random_subspace_nelder_mead",
        "hessian_subspace_nelder_mead",
    } <= methods


def test_attempt_004_slurm_scripts_are_capped_and_secret_free():
    slurm_dir = ATTEMPT / "slurm"
    cpu = (slurm_dir / "cpu_sweep.sbatch").read_text()
    gpu = (slurm_dir / "gpu_verify.sbatch").read_text()
    combined = cpu + "\n" + gpu

    assert "#SBATCH --cpus-per-task=4" in cpu
    assert "%25" in cpu
    assert "#SBATCH --gres=gpu:1" in gpu
    assert "%1" in gpu
    forbidden = ["password", "ssh ", "IdentityFile", "id_ed25519", "HostName", "User "]
    assert not any(marker in combined for marker in forbidden)
