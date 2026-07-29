import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "plan_phase8_scaling.py"


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


def _fit_summary(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "sigma": 1.75,
                "primary": {
                    "num_exponentials": 24,
                    "alpha": 0.5,
                    "r_fit": 2048,
                },
                "fits": [
                    {
                        "num_exponentials": 24,
                        "alpha": 0.5,
                        "r_fit": 2048,
                        "lambdas": [0.9],
                        "coefficients": [1.0],
                    }
                ],
            }
        )
    )


def _summary(path: Path, length: int, gamma: float, r_xi: float) -> None:
    path.mkdir(parents=True)
    (path / "summary.json").write_text(
        json.dumps(
            {
                "status": "success",
                "settings": {
                    "sigma": 1.75,
                    "length": length,
                    "gamma": gamma,
                    "num_exponentials": 24,
                    "alpha": 0.5,
                    "r_fit": 2048,
                    "chi_schedule": [64],
                    "sectors": ["even"],
                    "direct_only": True,
                },
                "mpo": {
                    "pruned": True,
                    "approximate_compression": False,
                },
                "raw_observables": {"r_xi": r_xi},
            }
        )
    )


def test_crossing_cli_writes_two_resumable_commands(tmp_path: Path):
    fit_summary = tmp_path / "fit-summary.json"
    _fit_summary(fit_summary)
    output = tmp_path / "crossing" / "run_spec.json"

    completed = run_cli(
        "crossing",
        "--fit-summary",
        str(fit_summary),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    spec = json.loads(output.read_text())
    assert len(spec["cells"]) == 2
    assert all("--chi-schedule" in cell["command"] for cell in spec["cells"])
    assert all(
        cell["command"][cell["command"].index("--chi-schedule") + 1] == "64"
        for cell in spec["cells"]
    )
    assert all("--direct-only" in cell["command"] for cell in spec["cells"])
    assert all(
        cell["command"][cell["command"].index("--sectors") + 1] == "even"
        for cell in spec["cells"]
    )
    assert not list(tmp_path.rglob("*.h5"))


def test_decide_cli_records_unresolved_without_writing_gap_spec(
    tmp_path: Path,
):
    fit_summary = tmp_path / "fit-summary.json"
    _fit_summary(fit_summary)
    crossing_spec = tmp_path / "crossing" / "run_spec.json"
    assert (
        run_cli(
            "crossing",
            "--fit-summary",
            str(fit_summary),
            "--output",
            str(crossing_spec),
        ).returncode
        == 0
    )

    phase7_decision = tmp_path / "phase7-decision.json"
    phase7_decision.write_text(
        json.dumps(
            {
                "sigma": 1.75,
                "status": "ready",
                "broad_bracket": [1.55, 1.60],
                "broad_Gamma_x": 1.5679,
            }
        )
    )
    phase7_root = tmp_path / "phase7"
    phase8_root = tmp_path / "phase8"
    for gamma, r64, r128 in (
        (1.55, 0.41, 0.44),
        (1.60, 0.43, 0.45),
    ):
        _summary(phase7_root / f"L64-Gamma{gamma}", 64, gamma, r64)
        _summary(phase8_root / f"L128-Gamma{gamma}", 128, gamma, r128)

    decision_path = tmp_path / "analysis" / "crossing-decision.json"
    completed = run_cli(
        "decide",
        "--crossing-spec",
        str(crossing_spec),
        "--phase7-decision",
        str(phase7_decision),
        "--phase7-summary-root",
        str(phase7_root),
        "--summary-root",
        str(phase8_root),
        "--output",
        str(decision_path),
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(decision_path.read_text())["status"].startswith(
        "unresolved"
    )
    assert not (tmp_path / "gaps" / "run_spec.json").exists()
