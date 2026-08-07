from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from src.cluster_entrypoint import preflight_cluster_run


FIXTURE = Path(__file__).parent / "data" / "hubbard_dimer.FCIDUMP"


def _write_config(path: Path, *, threads: int = 2, stack_mem_gb: float = 1.0) -> None:
    checksum = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    path.write_text(
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
seed = 1234
threads = {threads}
stack_mem_gb = {stack_mem_gb}
bond_dimensions = [8, 16]
n_sweeps_per_m = 4
tolerance = 1e-9
iprint = 0

[ordering]
method = "none"
""",
        encoding="utf-8",
    )


def _staged_run(tmp_path: Path) -> tuple[Path, Path]:
    config = tmp_path / "config.toml"
    run_dir = tmp_path / "run"
    inputs = run_dir / "inputs"
    inputs.mkdir(parents=True)
    shutil.copy2(FIXTURE, inputs / FIXTURE.name)
    _write_config(config)
    return config, run_dir


def test_preflight_reports_the_pinned_sector_target_and_resources(
    tmp_path: Path,
) -> None:
    config, run_dir = _staged_run(tmp_path)

    report = preflight_cluster_run(
        config,
        run_dir,
        target_m=16,
        environment={
            "SLURM_JOB_ID": "12345",
            "SLURM_CPUS_PER_TASK": "2",
            "SLURM_MEM_PER_NODE": "4096",
        },
    )

    assert report["status"] == "ready"
    assert report["sector"] == {
        "norb": 2,
        "nelec": 2,
        "ms2": 0,
        "spin": 0,
        "symmetry": "SU2",
    }
    assert report["bond_dimensions"] == [8, 16]
    assert report["target_m"] == 16
    assert report["resources"]["cpus_per_task"] == 2
    assert report["resources"]["memory_mb"] == 4096
    assert report["input"]["sha256"] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()


def test_preflight_rejects_fewer_slurm_cpus_than_block2_threads(
    tmp_path: Path,
) -> None:
    config, run_dir = _staged_run(tmp_path)

    with pytest.raises(ValueError, match="SLURM_CPUS_PER_TASK=1"):
        preflight_cluster_run(
            config,
            run_dir,
            target_m=16,
            environment={
                "SLURM_JOB_ID": "12345",
                "SLURM_CPUS_PER_TASK": "1",
                "SLURM_MEM_PER_NODE": "4096",
            },
        )


def test_preflight_rejects_memory_below_the_block2_stack_allocation(
    tmp_path: Path,
) -> None:
    config, run_dir = _staged_run(tmp_path)

    with pytest.raises(ValueError, match="smaller than block2 stack_mem_gb"):
        preflight_cluster_run(
            config,
            run_dir,
            target_m=16,
            environment={
                "SLURM_JOB_ID": "12345",
                "SLURM_CPUS_PER_TASK": "2",
                "SLURM_MEM_PER_NODE": "512",
            },
        )


def test_preflight_requires_a_real_slurm_allocation(tmp_path: Path) -> None:
    config, run_dir = _staged_run(tmp_path)

    with pytest.raises(ValueError, match="SLURM_JOB_ID"):
        preflight_cluster_run(
            config,
            run_dir,
            target_m=16,
            environment={},
        )
