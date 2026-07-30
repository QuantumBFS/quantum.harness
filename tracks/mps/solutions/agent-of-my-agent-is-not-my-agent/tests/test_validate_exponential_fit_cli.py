import csv
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "validate_exponential_fit.py"


def test_cli_writes_k_series_json_and_distance_profiles(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--length",
            "24",
            "--sigma",
            "1.75",
            "--r-fit",
            "128",
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    aggregate = json.loads((tmp_path / "summary.json").read_text())
    assert aggregate["length"] == 24
    assert aggregate["sigma"] == 1.75
    assert aggregate["r_fit"] == 128
    assert [entry["K"] for entry in aggregate["fits"]] == [8, 12, 16, 20, 24]
    assert "max_relative_error" in aggregate["fits"][0]["infinite_kernel"]
    assert "rms_relative_error" in aggregate["fits"][0]["periodized_coupling"]
    periodic = aggregate["fits"][0]["periodized_coupling"]
    assert set(periodic["global_maximum"]) == {
        "distance",
        "relative_error",
        "exact_hurwitz",
        "periodized_fit",
    }
    assert periodic["short_distance"]["distance_min"] == 1
    assert periodic["short_distance"]["distance_max"] == 10
    assert periodic["central_region"]["distances"] == [10, 11, 12, 13, 14]
    assert "max_relative_error" in periodic["short_distance"]
    assert "rms_relative_error" in periodic["central_region"]

    for k in (8, 12, 16, 20, 24):
        summary = json.loads((tmp_path / f"summary_K{k}.json").read_text())
        assert len(summary["lambdas"]) == k
        assert len(summary["coefficients"]) == k
        with (tmp_path / f"kernel_error_K{k}.csv").open(newline="") as stream:
            kernel_rows = list(csv.DictReader(stream))
        with (tmp_path / f"periodic_error_K{k}.csv").open(newline="") as stream:
            periodic_rows = list(csv.DictReader(stream))
        assert len(kernel_rows) == 128
        assert len(periodic_rows) == 23
        assert "relative_error" in kernel_rows[0]
        assert "exact_hurwitz" in periodic_rows[0]
        relative = [float(row["relative_error"]) for row in periodic_rows]
        maximum_index = max(range(len(relative)), key=relative.__getitem__)
        assert summary["periodized_coupling"]["global_maximum"]["distance"] == (
            maximum_index + 1
        )
        assert summary["periodized_coupling"]["global_maximum"][
            "relative_error"
        ] == relative[maximum_index]

    kernel_errors = [
        entry["infinite_kernel"]["rms_relative_error"]
        for entry in aggregate["fits"]
    ]
    assert kernel_errors[1] < kernel_errors[0]
    assert kernel_errors[2] < kernel_errors[1]
    assert "K=8" in result.stdout


def test_cli_records_correlation_length_bound_and_spectrum(tmp_path):
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--length",
            "24",
            "--sigma",
            "1.75",
            "--r-fit",
            "64",
            "--k-values",
            "8",
            "--min-rate-scale",
            "0.5",
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads((tmp_path / "summary_K8.json").read_text())
    assert summary["min_rate_scale"] == 0.5
    assert len(summary["rates"]) == 8
    assert summary["min_rate_times_r_fit"] >= 0.5 * (1.0 - 1.0e-12)
