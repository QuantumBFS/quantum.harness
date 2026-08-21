import json
import os
from pathlib import Path
import subprocess
import sys

from lrtfim.phase7_protocol import SIGMAS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "plan_phase7_scan.py"


def fit_map() -> dict:
    return {
        f"{sigma:.2f}": {
            "path": f"fits/sigma-{sigma:.2f}.json",
            "fit_hash": f"fit-{sigma:.2f}",
            "coefficient_hash": f"coeff-{sigma:.2f}",
            "sigma": sigma,
            "K": 24,
            "alpha": 0.5,
            "r_fit": 2048,
        }
        for sigma in SIGMAS
    }


def run_cli(*arguments: str) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}:{PROJECT_ROOT}"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_broad_cli_writes_resumable_plan_without_running_cells(
    tmp_path: Path,
) -> None:
    fit_path = tmp_path / "fit-map.json"
    fit_path.write_text(json.dumps(fit_map()))
    output = tmp_path / "broad" / "run_spec.json"

    completed = run_cli(
        "broad",
        "--fit-map",
        str(fit_path),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    spec = json.loads(output.read_text())
    assert len(spec["cells"]) == 210
    assert all(cell["status"] == "pending" for cell in spec["cells"])
    for cell in spec["cells"]:
        command = cell["command"]
        assert command[command.index("--chi-schedule") :][:2] == [
            "--chi-schedule",
            "64",
        ]
        assert "--direct-only" in command
        sector_index = command.index("--sectors")
        assert command[sector_index + 1] == "even"
        assert command[command.index("--output-dir") + 1].endswith(
            cell["cell_id"]
        )
    assert not list(tmp_path.rglob("*.h5"))


def test_estimate_cli_reads_explicit_calibration(tmp_path: Path) -> None:
    fit_path = tmp_path / "fit-map.json"
    fit_path.write_text(json.dumps(fit_map()))
    run_spec = tmp_path / "run_spec.json"
    assert run_cli(
        "broad",
        "--fit-map",
        str(fit_path),
        "--output",
        str(run_spec),
    ).returncode == 0
    records = [
        {
            "L": length,
            "sector": sector,
            "chi": 128,
            "wall_seconds": seconds,
            "peak_memory_gib": 1.3,
            "path": f"L{length}-{sector}.json",
            "code_hash": "code",
            "hardware": {"mode": "local"},
        }
        for length, sector, seconds in (
            (32, "even", 190.0),
            (32, "odd", 200.0),
            (64, "even", 600.0),
            (64, "odd", 650.0),
        )
    ]
    timing_path = tmp_path / "timings.json"
    timing_path.write_text(json.dumps(records))
    output = tmp_path / "cost.json"

    completed = run_cli(
        "estimate",
        "--run-spec",
        str(run_spec),
        "--timing-records",
        str(timing_path),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    estimate = json.loads(output.read_text())
    assert estimate["stages"]["broad"]["cells"] == 210
    assert estimate["combined"]["safety_wall_seconds"] > 0
