import hashlib
from pathlib import Path


TRACK = Path(__file__).resolve().parents[1]
SMOKE_JOB = TRACK / "jobs" / "hard_goal_driver_smoke.slurm"
PT_SMOKE_JOB = TRACK / "jobs" / "hard_goal_pt_smoke.slurm"
PILOT_JOB = TRACK / "jobs" / "hard_goal_pilot.slurm"
PRODUCTION_JOB = TRACK / "jobs" / "hard_goal_array.slurm"
SMOKE_REQUIREMENTS = TRACK / "containers" / "hg3d-a800-requirements.txt"


def test_container_venv_python_may_be_a_host_dangling_symlink() -> None:
    script = SMOKE_JOB.read_text(encoding="ascii")
    assert '[[ -L "$PYTHON" ]]' in script
    assert '[[ -x "$PYTHON" ]]' not in script


def test_smoke_environment_pins_eager_vmcrg_import_dependency() -> None:
    requirements = SMOKE_REQUIREMENTS.read_text(encoding="ascii").splitlines()
    assert "numba==0.66.0" in requirements


def test_smoke_job_locks_the_exact_requirements_file() -> None:
    digest = hashlib.sha256(SMOKE_REQUIREMENTS.read_bytes()).hexdigest()
    script = SMOKE_JOB.read_text(encoding="ascii")
    assert f'EXPECTED_REQUIREMENTS_SHA256="{digest}"' in script


def test_pt_smoke_job_uses_full_ladder_and_profile_owned_resources() -> None:
    script = PT_SMOKE_JOB.read_text(encoding="ascii")
    assert "#SBATCH --partition" not in script
    assert "#SBATCH --gres" not in script
    assert "--temperatures 48" in script
    assert "--chain-pairs 4" in script
    assert "JAX_PLATFORM_NAME=gpu" in script
    assert "scripts/hard_goal_pt_smoke.py" in script


def test_pilot_job_is_profile_neutral_checkpointed_and_opaque() -> None:
    script = PILOT_JOB.read_text(encoding="ascii")
    assert "#SBATCH --partition" not in script
    assert "#SBATCH --gres" not in script
    assert "HARNESS_RUN_SPEC" in script
    assert "SLURM_ARRAY_TASK_ID" in script
    assert "apptainer exec --nv" in script
    assert "scripts/hard_goal_pilot_cell.py" in script
    assert "--checkpoint-every 256" in script


def test_nounset_slurm_wrappers_never_expand_an_empty_argument_array() -> None:
    for path in (PILOT_JOB, PRODUCTION_JOB):
        script = path.read_text(encoding="ascii")
        assert "resume_args=()" not in script
        assert '"${resume_args[@]}"' not in script
        assert "command_args=(" in script
        assert '"${command_args[@]}"' in script
