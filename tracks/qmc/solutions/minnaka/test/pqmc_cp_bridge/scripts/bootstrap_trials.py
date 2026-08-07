#!/usr/bin/env python3
"""Create the single shared ALF-free / C++-UHF trial asset set."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ALF_PROJECT = REPO / "test" / "alf_hirsch_binary"
ALF_ROOT = ALF_PROJECT / "ALF"
ALF_EXECUTABLE = ALF_PROJECT / "run" / "binary" / "bin" / "ALF.binary.out"
CPMC_AUDIT = REPO / "test" / "cpmc_path_audit" / "build" / "cpmc_audit"
ASSETS = ROOT / "assets" / "trials"
RUNS = ROOT / "runs" / "bootstrap_trials"

sys.path.insert(0, str(ALF_PROJECT / "scripts"))
import analyze as alf_analyze  # noqa: E402
import prepare_inputs as alf_inputs  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_orbitals(path: Path) -> list[list[float]]:
    tokens = path.read_text(encoding="utf-8").split()
    if len(tokens) < 2:
        raise RuntimeError(f"missing orbital header: {path}")
    rows, cols = int(tokens[0]), int(tokens[1])
    values = [float(token) for token in tokens[2:]]
    if rows <= 0 or cols <= 0 or len(values) != rows * cols:
        raise RuntimeError(f"invalid orbital shape or value count: {path}")
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"nonfinite orbital value: {path}")
    return [
        values[row * cols : (row + 1) * cols] for row in range(rows)
    ]


def validate_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format_version") != 1:
        raise RuntimeError("unsupported trial manifest version")
    root = path.parent
    expected = {
        "trial_I_up.dat",
        "trial_I_down.dat",
        "trial_T_up.dat",
        "trial_T_down.dat",
        "site_map.dat",
        "uhf_metadata.json",
    }
    hashes = data.get("sha256")
    if not isinstance(hashes, dict) or set(hashes) != expected:
        raise RuntimeError("trial manifest hash set is incomplete")
    for name in sorted(expected):
        file_path = root / name
        if not file_path.is_file() or sha256_file(file_path) != hashes[name]:
            raise RuntimeError(f"trial asset hash mismatch: {name}")
    for name in expected - {"site_map.dat", "uhf_metadata.json"}:
        matrix = read_orbitals(root / name)
        if (len(matrix), len(matrix[0])) != (16, 8):
            raise RuntimeError(f"unexpected trial shape: {name}")
    return data


def oneapi_environment() -> dict[str, str]:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            "source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1; env -0",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    env: dict[str, str] = {}
    for item in completed.stdout.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        env[key.decode()] = value.decode()
    env.update(
        {
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "I_MPI_PIN": "1",
            "I_MPI_PIN_DOMAIN": "core",
        }
    )
    return env


def boundary_parameters(*, mode: int, export: bool) -> str:
    text = alf_inputs.make_parameters(nsweep=2, nbin=1)
    start = text.index("&VAR_Hubbard_Plain_Vanilla")
    end_match = re.search(r"(?m)^/\s*$", text[start:])
    if end_match is None:
        raise RuntimeError("unterminated Plain Vanilla namelist")
    end = start + end_match.start()
    additions = (
        f"Trial_boundary_mode = {mode}\n"
        f"Export_trial_orbitals = {'.T.' if export else '.F.'}\n"
    )
    return text[:end] + additions + text[end:]


def run_alf(run_dir: Path, parameters: str, env: dict[str, str]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    if any((run_dir / name).exists() for name in ("parameters", "info", "Ener_scal")):
        raise RuntimeError(f"refusing to overwrite ALF run: {run_dir}")
    (run_dir / "parameters").write_text(parameters, encoding="utf-8")
    seeds = (
        ALF_ROOT / "Scripts_and_Parameters_files" / "Start" / "seeds"
    ).read_text(encoding="utf-8").splitlines()
    seed = next(line for line in seeds if line.strip())
    (run_dir / "seeds").write_text(seed + "\n", encoding="utf-8")
    completed = subprocess.run(
        ["mpirun", "-np", "1", str(ALF_EXECUTABLE)],
        cwd=run_dir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=300,
    )
    (run_dir / "run.log").write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"ALF trial bootstrap failed in {run_dir}:\n{completed.stdout}"
        )


def bootstrap_trials() -> dict[str, Any]:
    if ASSETS.exists():
        return validate_manifest(ASSETS / "trial_manifest.json")
    if not ALF_EXECUTABLE.is_file() or not CPMC_AUDIT.is_file():
        raise RuntimeError("build ALF and cpmc_audit before bootstrapping trials")

    RUNS.mkdir(parents=True, exist_ok=True)
    env = oneapi_environment()
    with tempfile.TemporaryDirectory(
        prefix="trial-bootstrap-", dir=RUNS
    ) as temporary:
        run_root = Path(temporary)
        export_run = run_root / "export"
        run_alf(
            export_run,
            boundary_parameters(mode=0, export=True),
            env,
        )

        stage = run_root / "assets-stage"
        stage.mkdir()
        for name in ("trial_I_up.dat", "trial_I_down.dat", "site_map.dat"):
            shutil.copy2(export_run / name, stage / name)

        command = [
            str(CPMC_AUDIT),
            "export-uhf",
            "--lx",
            "4",
            "--ly",
            "4",
            "--t",
            "1",
            "--u",
            "4",
            "--dt",
            "0.05",
            "--n-up",
            "8",
            "--n-down",
            "8",
            "--initial-up",
            str(stage / "trial_I_up.dat"),
            "--initial-down",
            str(stage / "trial_I_down.dat"),
            "--site-map",
            str(stage / "site_map.dat"),
            "--output-dir",
            str(stage),
        ]
        completed = subprocess.run(
            command,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=300,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"UHF export failed:\n{completed.stdout}")

        mixed_run = run_root / "mixed"
        mixed_run.mkdir()
        shutil.copy2(stage / "trial_T_up.dat", mixed_run / "trial_T_up.dat")
        shutil.copy2(
            stage / "trial_T_down.dat", mixed_run / "trial_T_down.dat"
        )
        run_alf(
            mixed_run,
            boundary_parameters(mode=1, export=False),
            env,
        )
        info = (mixed_run / "info").read_text(encoding="utf-8")
        for marker in (
            "Trial boundary mode: 1",
            "WF_R: free",
            "WF_L: UHF file",
            "Explicit flavor propagation: T",
        ):
            if marker not in info:
                raise RuntimeError(f"mixed-boundary info missing: {marker}")
        signs = [
            sign
            for _value, sign in alf_analyze.parse_scalar_file(
                mixed_run / "Ener_scal"
            )
        ]
        if not signs or min(signs) < 0.0:
            raise RuntimeError("mixed-boundary smoke has a negative mean sign")

        metadata = json.loads(
            (stage / "uhf_metadata.json").read_text(encoding="utf-8")
        )
        metadata.update(
            {
                "format_version": 1,
                "site_order": "ALF exported; explicit site_map.dat",
                "trial_right": "ALF stock free, Delta=0.01",
                "trial_left": "collinear Neel UHF",
                "alf_executable_sha256": sha256_file(ALF_EXECUTABLE),
                "cpmc_audit_sha256": sha256_file(CPMC_AUDIT),
                "mixed_smoke_min_sign": min(signs),
                "sha256": {
                    name: sha256_file(stage / name)
                    for name in (
                        "trial_I_up.dat",
                        "trial_I_down.dat",
                        "trial_T_up.dat",
                        "trial_T_down.dat",
                        "site_map.dat",
                        "uhf_metadata.json",
                    )
                },
            }
        )
        manifest_temp = stage / "trial_manifest.json.tmp"
        manifest_temp.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_temp.replace(stage / "trial_manifest.json")
        ASSETS.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, ASSETS)
    return validate_manifest(ASSETS / "trial_manifest.json")


def main() -> None:
    manifest = bootstrap_trials()
    print(
        "PASS: trial assets "
        f"SCF iterations={manifest['scf_iterations']} "
        f"residual={manifest['scf_residual']:.3e}",
        flush=True,
    )


if __name__ == "__main__":
    main()
