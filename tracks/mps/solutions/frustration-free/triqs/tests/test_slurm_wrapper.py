from __future__ import annotations

import os
from pathlib import Path
import subprocess


TRIQS_DIR = Path(__file__).resolve().parents[1]


def test_wrapper_executes_exact_serial_offline_chain(tmp_path):
    fake = tmp_path / "micromamba"
    log = tmp_path / "args"
    fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$LOG\"\n")
    fake.chmod(0o755)
    env = {
        **os.environ,
        "CTHYB_MICROMAMBA": str(fake),
        "CTHYB_ENV": "/opt/triqs",
        "CTHYB_INPUT": "/data/input.json",
        "CTHYB_ROOT": "/data/results",
        "SLURM_ARRAY_TASK_ID": "2",
        "SLURM_NTASKS": "1",
        "SLURM_CPUS_PER_TASK": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "LOG": str(log),
    }
    script = TRIQS_DIR / "cthyb_slurm_array.sh"
    subprocess.run([str(script)], env=env, check=True)
    assert log.read_text().splitlines() == [
        "run",
        "--offline",
        "--prefix",
        "/opt/triqs",
        "python",
        str(TRIQS_DIR / "run_chain.py"),
        "--input",
        "/data/input.json",
        "--chain-index",
        "2",
        "--output-root",
        "/data/results",
    ]
    for key, value in (
        ("SLURM_ARRAY_TASK_ID", "4"),
        ("SLURM_NTASKS", "2"),
        ("SLURM_CPUS_PER_TASK", "2"),
        ("OMP_NUM_THREADS", "2"),
        ("CTHYB_INPUT", "relative"),
    ):
        changed = dict(env)
        changed[key] = value
        assert subprocess.run([str(script)], env=changed).returncode != 0
