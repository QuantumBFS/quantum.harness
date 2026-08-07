import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from analysis.tests.test_bootstrap import synthetic_blocks


def test_analysis_cli_writes_processed_data_plots_and_offline_report(tmp_path):
    blocks, manifest = synthetic_blocks()
    manifest.update(
        {
            "config_path": "configs/test.toml",
            "exact_command": "clean-ising exact --config configs/test.toml",
            "mc_command": "clean-ising mc --config configs/test.toml",
            "rust_version": "rustc test",
            "cargo_lock_sha256": "test",
            "python_version": None,
            "python_requirements_sha256": None,
            "started_at": "unix:0",
            "completed_at": "unix:1",
            "thread_count": 1,
            "exact_elapsed_s": 0.1,
            "mc_elapsed_s": 0.2,
            "total_elapsed_s": 0.3,
        }
    )
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    _write_jsonl(raw_dir / "mc_blocks.jsonl", blocks)
    exact_records = []
    for width in manifest["config"]["widths"]:
        per_site = (
            -0.9296953983
            - np.pi * 0.5 / (6.0 * width**2)
            + 0.07 / width**4
        )
        g_value = width * per_site
        exact_records.append(
            {
                "schema_version": 1,
                "l": width,
                "k": manifest["config"]["critical_k"],
                "boundary_conditions": "periodic-cylinder",
                "lambda0": float(np.exp(-g_value)),
                "g_exact": g_value,
                "iterations": 10,
                "relative_change": 1.0e-14,
                "residual": 1.0e-13,
                "elapsed_s": 0.01,
            }
        )
    _write_jsonl(raw_dir / "exact.jsonl", exact_records)

    solution_dir = Path(__file__).resolve().parents[2]
    repository_root = Path(__file__).resolve().parents[7]
    completed = subprocess.run(
        [
            sys.executable,
            str(solution_dir / "analysis" / "run_analysis.py"),
            str(tmp_path),
            "--renderer",
            str(repository_root / "skills" / "report" / "render_report.py"),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    for relative in [
        "processed/free_energies.csv",
        "processed/central_charge_fits.csv",
        "processed/energy_vs_k.csv",
        "processed/diagnostics.csv",
        "processed/analysis_metadata.json",
        "report.json",
        "report.html",
    ]:
        assert (tmp_path / relative).is_file(), relative


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
