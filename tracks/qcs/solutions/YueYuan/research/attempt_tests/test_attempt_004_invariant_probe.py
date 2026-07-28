import csv
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import invariant_probe


def test_attempt_004_invariant_probe_reports_su_dimensions():
    assert invariant_probe.su_dimension(2) == 3
    assert invariant_probe.su_dimension(4) == 15
    assert invariant_probe.su_dimension(8) == 63
    rows = invariant_probe.rank_probe_rows()
    by_d = {row["hilbert_dim"]: row for row in rows}
    assert by_d[2]["benchmark_rank"] == 3
    assert by_d[4]["benchmark_rank"] == 15
    assert by_d[8]["benchmark_rank"] == 63
    assert by_d[2]["evidence_type"] == "attempt_004_model_hessian_smoke"
    assert by_d[4]["evidence_type"] == "attempt_004_model_hessian_smoke"
    assert by_d[2]["rank_metric"] == "k_for_95pct_curvature"
    assert by_d[4]["rank_metric"] == "k_for_95pct_curvature"
    assert by_d[2]["curvature_at_benchmark_rank"] >= 0.95
    assert by_d[4]["curvature_at_benchmark_rank"] >= 0.95
    assert by_d[2]["formal_effective_rank"] > by_d[2]["benchmark_rank"]
    assert by_d[4]["formal_effective_rank"] > by_d[4]["benchmark_rank"]
    assert by_d[8]["evidence_type"] == "local_unitary_chart"
    assert by_d[8]["rank_metric"] == "exact_chart_curved_rank"


def test_attempt_004_invariant_probe_runner_writes_csv_and_figure(tmp_path):
    out_dir = tmp_path / "invariant"
    result = subprocess.run(
        [sys.executable, str(ATTEMPT / "run_invariant_probe.py"), "--out", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    csv_path = out_dir / "invariant_rank_probe.csv"
    assert csv_path.exists()
    assert (out_dir / "figures" / "invariant_rank_probe.png").exists()
    rows = list(csv.DictReader(csv_path.open()))
    assert {"2", "4", "8"} <= {row["hilbert_dim"] for row in rows}
    by_d = {row["hilbert_dim"]: row for row in rows}
    assert by_d["2"]["evidence_type"] == "attempt_004_model_hessian_smoke"
    assert by_d["4"]["evidence_type"] == "attempt_004_model_hessian_smoke"
    assert by_d["8"]["evidence_type"] == "local_unitary_chart"
