import json
import subprocess
from pathlib import Path


def test_test_config_produces_complete_artifact_tree(tmp_path):
    completed = subprocess.run(
        ["bash", "run.sh", "configs/test.toml", str(tmp_path / "run")],
        check=False,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    for relative in [
        "manifest.json",
        "raw/exact.jsonl",
        "raw/mc_blocks.jsonl",
        "processed/central_charge_fits.csv",
        "report.json",
        "report.html",
    ]:
        assert (tmp_path / "run" / relative).is_file()


def test_scientific_failure_still_finalizes_runtime(tmp_path):
    solution_dir = Path(__file__).resolve().parents[2]
    run_dir = tmp_path / "failed-run"
    processed = run_dir / "processed"
    processed.mkdir(parents=True)
    manifest = run_dir / "manifest.json"
    metadata = processed / "analysis_metadata.json"
    report = run_dir / "report.json"
    manifest.write_text(
        json.dumps(
            {
                "config": {"production_gates": True},
                "total_elapsed_s": None,
            }
        ),
        encoding="utf-8",
    )
    metadata.write_text(
        json.dumps({"gates": {"runtime": True}}),
        encoding="utf-8",
    )
    report.write_text(
        json.dumps(
            {
                "title": "failure fixture",
                "lede": "Overall verification: FAIL",
                "sections": [
                    {
                        "title": "Verification",
                        "blocks": [
                            {
                                "kind": "verdict",
                                "status": "good",
                                "label": "PASS",
                                "why": "Runtime: below limit.",
                            },
                            {
                                "kind": "table",
                                "columns": ["Stage", "Seconds"],
                                "rows": [["Total", "pending"]],
                                "numeric": [False, True],
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    renderer = tmp_path / "renderer.py"
    renderer.write_text("raise SystemExit(0)\n", encoding="utf-8")
    failing_analysis = tmp_path / "failing-analysis.sh"
    failing_analysis.write_text("#!/usr/bin/env bash\nexit 2\n", encoding="utf-8")
    failing_analysis.chmod(0o755)
    monotonic_now = float(
        subprocess.check_output(
            [
                "perl",
                "-MTime::HiRes=clock_gettime,CLOCK_MONOTONIC",
                "-e",
                "print clock_gettime(CLOCK_MONOTONIC)",
            ],
            text=True,
        )
    )

    completed = subprocess.run(
        [
            "bash",
            str(solution_dir / "analysis" / "run_analysis_stage.sh"),
            str(run_dir),
            str(monotonic_now - 1.0),
            str(renderer),
            str(solution_dir / ".venv" / "bin" / "python"),
            str(solution_dir / "analysis" / "finalize_runtime.py"),
            str(failing_analysis),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2, completed.stderr
    assert json.loads(manifest.read_text(encoding="utf-8"))["total_elapsed_s"] > 0.0
    runtime_rows = json.loads(report.read_text(encoding="utf-8"))["sections"][0][
        "blocks"
    ][1]["rows"]
    assert runtime_rows[0][1] != "pending"
