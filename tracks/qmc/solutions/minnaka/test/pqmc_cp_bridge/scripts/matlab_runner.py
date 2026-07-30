#!/usr/bin/env python3
"""Run resumable CPMC config waves through one MATLAB process."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from typing import Iterable, Mapping


def base_config(
    bridge: Path,
    contract,
    *,
    mode: str,
    run_id: str,
    seed: int,
    nwalkers: int,
    pc_every: int,
    output_dir: Path,
    n_blksteps: int = 20,
    n_eqblk: int | None = None,
    n_blk: int = 50,
) -> dict:
    return {
        "package_dir": str(
            (bridge / "runs/matlab_cp/package").resolve()
        ),
        "trial_dir": str((bridge / "assets/trials").resolve()),
        "output_dir": str(output_dir.resolve()),
        "run_id": run_id,
        "mode": mode,
        "seed": seed,
        "ltrot": contract.ltrot,
        "N_wlk": nwalkers,
        "N_blksteps": n_blksteps,
        "N_eqblk": (
            n_eqblk if n_eqblk is not None
            else (contract.ltrot + n_blksteps - 1) // n_blksteps
        ),
        "N_blk": n_blk,
        "itv_modsvd": contract.stabilize_every,
        "itv_pc": pc_every,
        "itv_Em": contract.energy_every,
        "diagnostics": True,
        "contract_hashes": {
            "selected_projection": contract.input_sha256[
                "selected_projection"
            ],
            "trial_manifest": contract.input_sha256["trial_manifest"],
            "field_order": contract.input_sha256["field_order"],
            "strata_contract": contract.input_sha256["strata_contract"],
        },
    }


def run_wave(
    bridge: Path,
    configs: Iterable[Mapping[str, object]],
    *,
    matlab: Path = Path("/home/minnaka/.local/bin/matlab"),
) -> float:
    configs = list(configs)
    pending = [
        dict(config) for config in configs
        if not (
            Path(str(config["output_dir"])) / f"{config['run_id']}.mat"
        ).is_file()
    ]
    if not pending:
        return 0.0
    manifest_dir = bridge / "runs/matlab_cp/manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / f"wave_{pending[0]['run_id']}.json"
    manifest.write_text(json.dumps({"configs": pending}, indent=2) + "\n")
    matlab_dir = bridge / "matlab"
    expression = (
        f"addpath('{matlab_dir}'); "
        f"run_cpmc_wave('{manifest.resolve()}')"
    )
    started = time.monotonic()
    subprocess.run(
        [str(matlab), "-batch", expression],
        check=True,
    )
    elapsed = time.monotonic() - started
    missing = [
        config["run_id"] for config in pending
        if not (
            Path(str(config["output_dir"])) / f"{config['run_id']}.mat"
        ).is_file()
    ]
    if missing:
        raise RuntimeError(f"MATLAB wave lacks outputs: {missing}")
    return elapsed
