from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path


SOLUTION_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "data" / "hubbard_dimer.FCIDUMP"
SBATCH = SOLUTION_ROOT / "cluster" / "anderson_block2.sbatch"
PREFLIGHT_SBATCH = SOLUTION_ROOT / "cluster" / "anderson_block2_preflight.sbatch"


def test_sbatch_wrapper_can_run_a_real_preflight_without_starting_dmrg(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    inputs = run_dir / "inputs"
    inputs.mkdir(parents=True)
    shutil.copy2(FIXTURE, inputs / FIXTURE.name)
    checksum = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[instance]
name = "tiny"
filename = "hubbard_dimer.FCIDUMP"
sha256 = "{checksum}"
norb = 2
nelec = 2
ms2 = 0

[dmrg]
symmetry = "SU2"
spin = 0
threads = 2
stack_mem_gb = 1.0
bond_dimensions = [8, 16]
n_sweeps_per_m = 4
tolerance = 1e-9
iprint = 0

[ordering]
method = "none"
""",
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "CONFIG_PATH": str(config),
        "RUN_DIR": str(run_dir),
        "TARGET_M": "16",
        "PREFLIGHT_ONLY": "1",
        "SLURM_JOB_ID": "12345",
        "SLURM_CPUS_PER_TASK": "2",
        "SLURM_MEM_PER_NODE": "4096",
    }

    completed = subprocess.run(
        ["bash", str(SBATCH)],
        cwd=SOLUTION_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = completed.stdout
    assert '"status": "ready"' in report
    assert '"target_m": 16' in report
    assert not (run_dir / "run.json").exists()


def test_preflight_sbatch_never_starts_dmrg(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    inputs = run_dir / "inputs"
    inputs.mkdir(parents=True)
    shutil.copy2(FIXTURE, inputs / FIXTURE.name)
    checksum = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[instance]
name = "tiny"
filename = "hubbard_dimer.FCIDUMP"
sha256 = "{checksum}"
norb = 2
nelec = 2
ms2 = 0

[dmrg]
symmetry = "SU2"
spin = 0
threads = 2
stack_mem_gb = 1.0
bond_dimensions = [8, 16]
n_sweeps_per_m = 4
tolerance = 1e-9
iprint = 0

[ordering]
method = "none"
""",
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "CONFIG_PATH": str(config),
        "RUN_DIR": str(run_dir),
        "TARGET_M": "16",
        "SLURM_JOB_ID": "12345",
        "SLURM_CPUS_PER_TASK": "2",
        "SLURM_MEM_PER_NODE": "4096",
    }

    completed = subprocess.run(
        ["bash", str(PREFLIGHT_SBATCH)],
        cwd=SOLUTION_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert '"status": "ready"' in completed.stdout
    assert not (run_dir / "run.json").exists()


def test_sbatch_uses_apptainer_without_requiring_a_host_python(
    tmp_path: Path,
) -> None:
    image = tmp_path / "anderson-block2.sif"
    image.touch()
    config = tmp_path / "config.toml"
    config.touch()
    run_dir = tmp_path / "run"
    fake_apptainer = tmp_path / "apptainer"
    fake_apptainer.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\n",
        encoding="utf-8",
    )
    fake_apptainer.chmod(0o755)
    environment = {
        **os.environ,
        "APPTAINER_IMAGE": str(image),
        "APPTAINER_BIN": str(fake_apptainer),
        "PYTHON_BIN": str(tmp_path / "missing-host-python"),
        "CONFIG_PATH": str(config),
        "RUN_DIR": str(run_dir),
        "TARGET_M": "16",
        "PREFLIGHT_ONLY": "1",
    }

    completed = subprocess.run(
        ["bash", str(SBATCH)],
        cwd=SOLUTION_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    arguments = completed.stdout.splitlines()
    assert "exec" in arguments
    assert "--cleanenv" in arguments
    assert str(image) in arguments
    assert "/opt/anderson/.venv/bin/python" in arguments
    assert "src.cluster_entrypoint" in arguments
    assert "--preflight-only" in arguments


def test_sbatch_defaults_to_the_ratified_m1000_target(tmp_path: Path) -> None:
    image = tmp_path / "anderson-block2.sif"
    image.touch()
    config = tmp_path / "config.toml"
    config.touch()
    fake_apptainer = tmp_path / "apptainer"
    fake_apptainer.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\n",
        encoding="utf-8",
    )
    fake_apptainer.chmod(0o755)
    environment = {
        **os.environ,
        "APPTAINER_IMAGE": str(image),
        "APPTAINER_BIN": str(fake_apptainer),
        "PYTHON_BIN": str(tmp_path / "missing-host-python"),
        "CONFIG_PATH": str(config),
        "RUN_DIR": str(tmp_path / "run"),
        "PREFLIGHT_ONLY": "1",
    }
    environment.pop("TARGET_M", None)

    completed = subprocess.run(
        ["bash", str(SBATCH)],
        cwd=SOLUTION_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    arguments = completed.stdout.splitlines()
    target_index = arguments.index("--target-m")
    assert arguments[target_index + 1] == "1000"


def test_sbatch_auto_discovers_the_standard_apptainer_image(
    tmp_path: Path,
) -> None:
    image = tmp_path / "containers" / "anderson-block2-py312.sif"
    image.parent.mkdir()
    image.touch()
    config = tmp_path / "config.toml"
    config.touch()
    fake_apptainer = tmp_path / "apptainer"
    fake_apptainer.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\"\n",
        encoding="utf-8",
    )
    fake_apptainer.chmod(0o755)
    environment = {
        **os.environ,
        "HOME": str(tmp_path),
        "APPTAINER_BIN": str(fake_apptainer),
        "PYTHON_BIN": str(tmp_path / "missing-host-python"),
        "CONFIG_PATH": str(config),
        "RUN_DIR": str(tmp_path / "run"),
        "TARGET_M": "16",
        "PREFLIGHT_ONLY": "1",
    }
    environment.pop("APPTAINER_IMAGE", None)

    completed = subprocess.run(
        ["bash", str(SBATCH)],
        cwd=SOLUTION_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert str(image) in completed.stdout.splitlines()
