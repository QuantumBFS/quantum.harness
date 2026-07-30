import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from lrtfim.fit_protocol import regenerate_sigma_fits
from scripts.benchmark_phase6_optimizations import select_fit


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_select_fit_uses_exact_requested_tuple() -> None:
    summary = regenerate_sigma_fits(sigma=1.75, lengths=[4], l_max=4)

    selected = select_fit(
        summary,
        num_exponentials=32,
        alpha=0.5,
        r_fit=32,
    )

    assert selected["num_exponentials"] == 32
    assert selected["alpha"] == 0.5
    assert selected["r_fit"] == 32
    assert len(selected["lambdas"]) == 32


def test_select_fit_rejects_missing_tuple() -> None:
    summary = regenerate_sigma_fits(sigma=1.75, lengths=[4], l_max=4)

    with pytest.raises(ValueError, match="fit tuple not found"):
        select_fit(
            summary,
            num_exponentials=31,
            alpha=0.5,
            r_fit=32,
        )


def test_fixture_benchmark_writes_stages_checkpoints_and_raw_observables(
    tmp_path: Path,
) -> None:
    fit_path = tmp_path / "fit-summary.json"
    fit_path.write_text(
        json.dumps(
            regenerate_sigma_fits(sigma=1.75, lengths=[4], l_max=4),
            indent=2,
        )
        + "\n"
    )
    output = tmp_path / "benchmark"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "benchmark_phase6_optimizations.py"),
        "--fit-summary",
        str(fit_path),
        "--length",
        "4",
        "--gamma",
        "1.56",
        "--r-fit",
        "32",
        "--chi-schedule",
        "8",
        "16",
        "128",
        "--run-direct",
        "--output-dir",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "success"
    assert summary["mpo"]["pruned"]
    assert summary["mpo"]["active_channels"]
    assert summary["mpo"]["chi"] <= 2 * summary["fit"]["K"] + 2
    for sector in ("even", "odd"):
        assert len(summary["staged"][sector]["stages"]) == 3
        assert (output / "checkpoints" / sector / "chi128" / "state.h5").is_file()
        assert summary["direct"][sector]["sweeps"] > 0
    raw = summary["raw_observables"]
    assert len(raw["correlations"]) == 4
    assert raw["s_zero"] > 0
    assert raw["s_k_min"] > 0


def test_direct_only_mode_checkpoints_both_sectors(tmp_path: Path) -> None:
    fit_path = tmp_path / "fit-summary.json"
    fit_path.write_text(
        json.dumps(
            regenerate_sigma_fits(sigma=1.75, lengths=[4], l_max=4),
            indent=2,
        )
        + "\n"
    )
    output = tmp_path / "direct"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "benchmark_phase6_optimizations.py"),
            "--fit-summary",
            str(fit_path),
            "--length",
            "4",
                "--gamma",
                "1.56",
                "--r-fit",
                "32",
            "--chi-schedule",
            "8",
            "16",
            "128",
            "--direct-only",
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
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "success"
    assert summary["staged"] == {}
    for sector in ("even", "odd"):
        assert summary["direct"][sector]["sweeps"] > 0
        checkpoint = output / "checkpoints" / sector / "chi128"
        assert (checkpoint / "state.h5").is_file()
        assert (checkpoint / "checkpoint.json").is_file()
    assert len(summary["raw_observables"]["correlations"]) == 4


def test_direct_only_can_run_one_sector_and_resume(tmp_path: Path) -> None:
    fit_path = tmp_path / "fit-summary.json"
    fit_path.write_text(
        json.dumps(
            regenerate_sigma_fits(sigma=1.75, lengths=[4], l_max=4),
            indent=2,
        )
        + "\n"
    )
    output = tmp_path / "even"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "benchmark_phase6_optimizations.py"),
        "--fit-summary",
        str(fit_path),
        "--length",
        "4",
        "--gamma",
        "1.56",
        "--r-fit",
        "32",
        "--chi-schedule",
        "8",
        "16",
        "128",
        "--direct-only",
        "--sectors",
        "even",
        "--output-dir",
        str(output),
    ]
    first = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert first.returncode == 0, first.stderr
    before = (output / "summary.json").read_text()
    summary = json.loads(before)
    assert set(summary["direct"]) == {"even"}
    assert "gap" not in summary["raw_observables"]
    second = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert second.returncode == 0, second.stderr
    assert "reusing successful benchmark" in second.stdout
    assert (output / "summary.json").read_text() == before


def test_direct_only_refines_from_audited_checkpoint(tmp_path: Path) -> None:
    fit_path = tmp_path / "fit-summary.json"
    fit_path.write_text(
        json.dumps(
            regenerate_sigma_fits(sigma=1.75, lengths=[4], l_max=4),
            indent=2,
        )
        + "\n"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    baseline = tmp_path / "baseline"
    common = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "benchmark_phase6_optimizations.py"),
        "--fit-summary",
        str(fit_path),
        "--length",
        "4",
        "--gamma",
        "1.56",
        "--r-fit",
        "32",
        "--direct-only",
        "--sectors",
        "even",
        "--max-sweeps",
        "2",
    ]
    first = subprocess.run(
        [*common, "--chi-schedule", "8", "--output-dir", str(baseline)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert first.returncode == 0, first.stderr
    legacy_summary_path = baseline / "summary.json"
    legacy_summary = json.loads(legacy_summary_path.read_text())
    for field in ("num_exponentials", "alpha", "r_fit"):
        legacy_summary["settings"].pop(field)
    legacy_summary_path.write_text(json.dumps(legacy_summary))

    refined = tmp_path / "refined"
    second = subprocess.run(
        [
            *common,
            "--chi-schedule",
            "16",
            "--initial-checkpoint-root",
            str(baseline / "checkpoints"),
            "--initial-chi",
            "8",
            "--initial-summary",
            str(baseline / "summary.json"),
            "--output-dir",
            str(refined),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert second.returncode == 0, second.stderr
    summary = json.loads((refined / "summary.json").read_text())
    initialization = summary["initialization"]["even"]
    assert initialization["mode"] == "audited_initialization_only"
    assert initialization["fully_reoptimize_required"] is True
    assert initialization["source_summary"]["mpo_pruned"] is True
    assert initialization["source_summary"]["approximate_compression"] is False
    assert initialization["source_summary"]["mpo_chi"] >= 2
    assert summary["direct"]["even"]["requested_chi"] == 16
    assert (
        refined / "checkpoints" / "even" / "chi16" / "state.h5"
    ).is_file()
