import json
import os
from pathlib import Path
import subprocess
import sys

from lrtfim.exponential_fit import fit_power_law


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_prepare_local_k_comparison_reuses_k24_and_fits_k32(
    tmp_path: Path,
) -> None:
    fit24 = fit_power_law(
        sigma=1.75,
        num_exponentials=24,
        r_fit=32,
        min_rate_scale=0.5,
    )
    source = tmp_path / "summary_K24.json"
    source.write_text(
        json.dumps(
            {
                "K": 24,
                "p": 2.75,
                "r_fit": 32,
                "min_rate_scale": 0.5,
                "lambdas": fit24.lambdas.tolist(),
                "coefficients": fit24.coefficients.tolist(),
            }
        )
    )
    output = tmp_path / "fits"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "prepare_local_k_comparison.py"),
            "--k24-summary",
            str(source),
            "--sigma",
            "1.75",
            "--lengths",
            "4",
            "8",
            "--l-max",
            "4",
            "--output-dir",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((output / "fit-summary.json").read_text())
    assert summary["K24"]["source_sha256"]
    assert summary["K24"]["coefficients"] == fit24.coefficients.tolist()
    assert len(summary["K32"]["lambdas"]) == 32
    assert summary["K32"]["alpha"] == 0.5
    assert summary["K32"]["r_fit"] == 32
    for length in ("4", "8"):
        assert summary["coupling_comparison"][length]["K24"][
            "max_relative_error"
        ] >= 0.0
        assert (
            output / f"couplings_K32_L{length}.csv"
        ).is_file()
