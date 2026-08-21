import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "plan_phase9_validation.py"


def _run(*arguments: str) -> subprocess.CompletedProcess:
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


def _fit_summary(path: Path, sigma: float) -> None:
    path.write_text(
        json.dumps(
            {
                "sigma": sigma,
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
                        "lambdas": [0.8],
                        "coefficients": [1.0],
                    }
                ],
            }
        )
    )


def test_nn_planner_writes_eighteen_stable_nonexecuted_commands(tmp_path: Path):
    output = tmp_path / "nn-limit" / "run_spec.json"

    completed = _run("nn", "--output", str(output))

    assert completed.returncode == 0, completed.stderr
    spec = json.loads(output.read_text())
    assert len(spec["cells"]) == 18
    assert len({cell["cell_id"] for cell in spec["cells"]}) == 18
    assert all(
        cell["command"][1:3] == ["-u", "scripts/run_phase9_nn_cell.py"]
        for cell in spec["cells"]
    )
    assert all(
        cell["command"][cell["command"].index("--chi") + 1] == "64"
        for cell in spec["cells"]
    )
    assert all("128" not in json.dumps(cell["command"]) for cell in spec["cells"])
    assert spec["settings"]["automatic_chi128"] is False
    assert not list(tmp_path.rglob("*.h5"))
    assert not list(tmp_path.rglob("summary.json"))


def test_mean_field_planner_writes_only_qualified_sigma_two_thirds_commands(
    tmp_path: Path,
):
    fit_two_thirds = tmp_path / "fit-two-thirds.json"
    _fit_summary(fit_two_thirds, 2.0 / 3.0)
    output = tmp_path / "mean-field" / "run_spec.json"

    completed = _run(
        "mean-field",
        "--fit-summary",
        str(fit_two_thirds),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    spec = json.loads(output.read_text())
    assert len(spec["cells"]) == 8
    assert len(spec["provenance"]["fit_summaries"]) == 1
    assert all(
        record["sha256"]
        for record in spec["provenance"]["fit_summaries"].values()
    )
    assert all(
        "scripts/benchmark_phase6_optimizations.py" in cell["command"]
        for cell in spec["cells"]
    )
    assert all(
        cell["command"][cell["command"].index("--chi-schedule") + 1] == "64"
        for cell in spec["cells"]
    )
    assert all("--direct-only" in cell["command"] for cell in spec["cells"])
    assert {cell["sigma"] for cell in spec["cells"]} == {2.0 / 3.0}
    assert all(cell["Gamma"] == 3.673 for cell in spec["cells"])
    assert all("128" not in json.dumps(cell["command"]) for cell in spec["cells"])
    assert spec["settings"]["automatic_chi128"] is False
    assert not list(tmp_path.rglob("*.h5"))
    assert not list(tmp_path.rglob("summary.json"))


def test_mean_field_planner_rejects_incompatible_fit(tmp_path: Path):
    fit_two_thirds = tmp_path / "fit-two-thirds.json"
    _fit_summary(fit_two_thirds, 2.0 / 3.0)
    payload = json.loads(fit_two_thirds.read_text())
    payload["primary"]["r_fit"] = 512
    fit_two_thirds.write_text(json.dumps(payload))

    completed = _run(
        "mean-field",
        "--fit-summary",
        str(fit_two_thirds),
        "--output",
        str(tmp_path / "run_spec.json"),
    )

    assert completed.returncode != 0
    assert "r_fit" in completed.stderr


def test_sigma18_planner_writes_only_ten_fixed_field_commands(tmp_path: Path):
    fit = tmp_path / "fit-sigma18.json"
    _fit_summary(fit, 1.8)
    output = tmp_path / "sigma18-z" / "run_spec.json"

    completed = _run(
        "sigma18-z",
        "--fit-summary",
        str(fit),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    spec = json.loads(output.read_text())
    assert len(spec["cells"]) == 10
    assert all(cell["Gamma"] == 1.5288 for cell in spec["cells"])
    assert all(cell["K"] == 24 and cell["chi"] == 128 for cell in spec["cells"])
    assert all("--direct-only" in cell["command"] for cell in spec["cells"])
    assert all(
        cell["command"][cell["command"].index("--num-exponentials") + 1]
        == "24"
        for cell in spec["cells"]
    )
    assert spec["provenance"]["fit_summary"]["sha256"]
    assert not list(tmp_path.rglob("summary.json"))
    assert not list(tmp_path.rglob("*.h5"))


def test_all_planner_writes_both_specs_without_executing_cells(tmp_path: Path):
    fit_two_thirds = tmp_path / "fit-two-thirds.json"
    _fit_summary(fit_two_thirds, 2.0 / 3.0)
    output_root = tmp_path / "phase9"

    completed = _run(
        "all",
        "--fit-summary",
        str(fit_two_thirds),
        "--output-root",
        str(output_root),
    )

    assert completed.returncode == 0, completed.stderr
    nn = json.loads((output_root / "nn-limit" / "run_spec.json").read_text())
    mean_field = json.loads(
        (
            output_root
            / "mean-field-sigma-2over3"
            / "run_spec.json"
        ).read_text()
    )
    assert len(nn["cells"]) == 18
    assert len(mean_field["cells"]) == 8
    assert not list(output_root.rglob("*.h5"))
    assert not list(output_root.rglob("summary.json"))
