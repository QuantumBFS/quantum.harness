from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "scripts"


def _read(name):
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_array_scripts_declare_resources_without_a_partition():
    qmc = _read("issue147-qmc.sbatch")
    pepo = _read("issue147-pepo.sbatch")

    for script in (qmc, pepo):
        assert "set -euo pipefail" in script
        assert "#SBATCH --cpus-per-task=" in script
        assert "#SBATCH --mem=" in script
        assert "#SBATCH --time=" in script
        assert "PYTHONUNBUFFERED=1" in script
        assert "HARNESS_RUN_SPEC" in script
        assert "#SBATCH --partition" not in script
        assert "#SBATCH --gres" not in script
    assert "#SBATCH --cpus-per-task=1" in qmc
    assert "NUMBA_NUM_THREADS=1" in qmc
    assert "--kind qmc" in qmc
    assert "#SBATCH --cpus-per-task=32" in pepo
    assert "JAX_PLATFORM_NAME=cpu" in pepo
    assert 'HARNESS_KIND="${HARNESS_KIND:-pepo}"' in pepo


def test_pepo_probe_is_one_thermodynamic_step_on_the_production_source():
    probe = _read("issue147-pepo-probe.sbatch")

    assert "#SBATCH --partition" not in probe
    assert "#SBATCH --gres" not in probe
    assert "JAX_PLATFORM_NAME=cpu" in probe
    assert "--compression-mode thermodynamic" in probe
    assert "--stop-after-steps 1" in probe
    assert "issue147-pepo/cells/cell-0002" in probe
