from __future__ import annotations

import hashlib
import math
import shutil
from pathlib import Path

import pytest

pytest.importorskip("block2")

from src.dmrg_runner import run_dmrg
from src.verify_checkpoint import verify_checkpoint


FIXTURE = Path(__file__).parent / "data" / "hubbard_dimer.FCIDUMP"


@pytest.mark.integration
def test_block2_runner_reaches_exact_hubbard_dimer_energy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    inputs = run_dir / "inputs"
    inputs.mkdir(parents=True)
    destination = inputs / FIXTURE.name
    shutil.copy2(FIXTURE, destination)
    checksum = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    config = tmp_path / "tiny.toml"
    config.write_text(
        f"""
[instance]
name = "hubbard-dimer"
filename = "{FIXTURE.name}"
sha256 = "{checksum}"
norb = 2
nelec = 2
ms2 = 0

[dmrg]
symmetry = "SU2"
spin = 0
seed = 1234
threads = 1
stack_mem_gb = 1.0
bond_dimensions = [8]
n_sweeps_per_m = 4
tolerance = 1e-10
iprint = 0
stage_noise = 1e-4
final_stage_noise = 1e-5

[ordering]
method = "none"
""",
        encoding="utf-8",
    )

    result = run_dmrg(config, run_dir)

    expected = (4.0 - math.sqrt(4.0**2 + 16.0)) / 2.0
    assert abs(result["headline"]["energy_hartree"] - expected) < 1.0e-9
    assert (run_dir / "checkpoints" / "block2" / "KET-mps_info.bin").exists()
    assert (run_dir / "sweeps.csv").exists()

    verification = verify_checkpoint(run_dir)

    assert verification["verified"] is True
    assert abs(
        verification["normalized_energy_hartree"]
        - result["headline"]["energy_hartree"]
    ) < 1.0e-10
