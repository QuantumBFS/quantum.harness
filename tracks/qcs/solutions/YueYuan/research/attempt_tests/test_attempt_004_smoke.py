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
