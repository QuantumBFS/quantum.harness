import os
from pathlib import Path
import subprocess


def test_slurm_wrapper_uses_deployed_python_and_source_commit(tmp_path):
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    (project / "src").mkdir()
    (project / "results" / "ceffflow-production" / "logs").mkdir(
        parents=True
    )
    capture = tmp_path / "capture.txt"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-c\" ]; then\n"
        "  expected=\"$CEFFFLOW_PROJECT_ROOT/.deps\"\n"
        "  [ \"${PYTHONPATH%%:*}\" = \"$expected\" ] || exit 42\n"
        "  exit 0\n"
        "fi\n"
        "printf '%s\\n' \"$CEFFFLOW_SOURCE_COMMIT\" \"$PYTHONPATH\" \"$*\" "
        f"> {capture}\n"
    )
    fake_python.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "CEFFFLOW_PROJECT_ROOT": str(project),
            "CEFFFLOW_PYTHON": str(fake_python),
            "CEFFFLOW_RUN_SPEC": "results/ceffflow-production/run_spec.json",
            "CEFFFLOW_SOURCE_COMMIT": "b" * 40,
            "SLURM_ARRAY_TASK_ID": "2",
        }
    )
    script = Path(__file__).parents[1] / "scripts/slurm/ceffflow_array.sh"
    subprocess.run(["bash", str(script)], check=True, env=environment)

    lines = capture.read_text().splitlines()
    assert lines[0] == "b" * 40
    python_path = lines[1].split(":")
    assert python_path[:2] == [str(project / ".deps"), str(project / "src")]
    assert lines[2].endswith("--cell-id cell-0003")


def test_environment_bootstrap_pins_binary_dependencies(tmp_path):
    project = tmp_path / "project"
    (project / "scripts" / "slurm").mkdir(parents=True)
    capture = tmp_path / "capture.txt"
    fake_python = tmp_path / "python"
    fake_python.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> {capture}\n"
    )
    fake_python.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "CEFFFLOW_PROJECT_ROOT": str(project),
            "CEFFFLOW_PYTHON": str(fake_python),
        }
    )
    script = (
        Path(__file__).parents[1]
        / "scripts/slurm/bootstrap_ceffflow_env.sh"
    )
    subprocess.run(["bash", str(script)], check=True, env=environment)

    invocations = capture.read_text().splitlines()
    install = invocations[0]
    assert "--only-binary=:all:" in install
    assert f"--target {project / '.deps'}" in install
    assert "numpy==2.2.6" in install
    assert "scipy==1.15.3" in install
    assert "pydantic==2.12.5" in install
