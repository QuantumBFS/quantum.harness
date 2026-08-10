import json
import subprocess
from pathlib import Path


def test_test_configuration_produces_complete_artifact_tree(tmp_path):
    solution_dir = Path(__file__).resolve().parents[2]
    run_dir = tmp_path / "run"
    completed = subprocess.run(
        [
            "bash",
            str(solution_dir / "run.sh"),
            str(solution_dir / "configs" / "test.toml"),
            str(run_dir),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    for relative in [
        "manifest.json",
        "raw/oracles.json",
        "raw/replicas/replica-000.json",
        "processed/summary.json",
        "processed/free_energy.csv",
        "processed/central_charge_bootstrap.csv",
        "report.json",
        "report.html",
    ]:
        assert (run_dir / relative).is_file(), relative
    assert len(list((run_dir / "figures").glob("*.png"))) == 6
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["total_elapsed_s"] > 0.0
