#!/usr/bin/env python3
"""Prepare six-chain ALF runs with immutable QHPATH01 archive settings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from prepare_alf_chain import (
    DEFAULT_TRIAL_ASSETS,
    atomic_json,
    prepare_batch,
    sha256_file,
)


def append_archive_namelist(
    parameters: str,
    *,
    stride: int,
    after_sweep: int,
    ensemble_code: int,
    chain: int,
    archive_file: Path,
    selected_hash: str,
    trial_hash: str,
) -> str:
    if stride <= 0 or after_sweep < 0:
        raise ValueError("invalid archive stride/burn-in")
    if ensemble_code not in (1, 2) or not 0 <= chain < 2048:
        raise ValueError("invalid archive ensemble/chain")
    for value in (selected_hash, trial_hash):
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("archive hashes must be lowercase SHA-256")
    start = parameters.index("&VAR_QMC")
    match = re.search(r"(?m)^/\s*$", parameters[start:])
    if match is None:
        raise RuntimeError("unterminated VAR_QMC namelist")
    end = start + match.start()
    assignments = (
        "Archive_paths = .T.\n"
        f"Archive_stride = {stride}\n"
        f"Archive_after_sweep = {after_sweep}\n"
        f"Archive_ensemble = {ensemble_code}\n"
        f"Archive_chain_id = {chain}\n"
        f"Archive_file = \"{archive_file}\"\n"
        f"Archive_selected_hash = \"{selected_hash}\"\n"
        f"Archive_trial_hash = \"{trial_hash}\"\n"
    )
    return parameters[:end] + assignments + parameters[end:]


def prepare_archive_batch(
    run_root: Path,
    archive_root: Path,
    *,
    phase: str,
    ensemble: str,
    theta: int,
    batch: int,
    nsweep: int,
    stride: int,
    after_sweep: int,
    master_seed: int,
    executable: Path,
    selected_projection: Path,
    trial_assets: Path = DEFAULT_TRIAL_ASSETS,
    chains: int = 6,
    chain_offset: int = 0,
    nwrap: int | None = None,
) -> dict[str, Any]:
    ensemble = ensemble.upper()
    if phase not in {"pilot", "production", "direct_reweight"}:
        raise ValueError(
            "archive phase must be pilot, production, or direct_reweight"
        )
    selected = json.loads(selected_projection.read_text())
    if int(selected["theta_star"]) != theta:
        raise ValueError("archive theta differs from selected projection")
    trial_manifest = trial_assets / "trial_manifest.json"
    selected_hash = sha256_file(selected_projection)
    trial_hash = sha256_file(trial_manifest)
    manifest = prepare_batch(
        run_root,
        ensemble=ensemble,
        theta=theta,
        batch=batch,
        nbin=1,
        nsweep=nsweep,
        master_seed=master_seed,
        executable=executable,
        trial_assets=trial_assets,
        chains=chains,
        nwrap=(
            int(selected.get("nwrap", 5))
            if nwrap is None else nwrap
        ),
        chain_offset=chain_offset,
    )
    phase_archive_root = archive_root / phase / ensemble
    phase_archive_root.mkdir(parents=True, exist_ok=True)
    batch_dir = (
        run_root / ensemble / f"theta_{theta:03d}" / f"batch_{batch:03d}"
    )
    archives: list[dict[str, Any]] = []
    for local_chain in range(chains):
        chain = chain_offset + local_chain
        archive_path = (phase_archive_root / f"chain_{chain}.qhpath").resolve()
        if archive_path.exists() and archive_path.stat().st_size < 256:
            raise RuntimeError(f"truncated pre-existing archive: {archive_path}")
        parameter_path = batch_dir / f"chain_{chain}" / "parameters"
        parameters = append_archive_namelist(
            parameter_path.read_text(),
            stride=stride,
            after_sweep=after_sweep,
            ensemble_code=1 if ensemble == "II" else 2,
            chain=chain,
            archive_file=archive_path,
            selected_hash=selected_hash,
            trial_hash=trial_hash,
        )
        parameter_path.write_text(parameters)
        archives.append({
            "local_chain": local_chain,
            "chain": chain,
            "path": str(archive_path),
        })
    manifest.update({
        "archive_phase": phase,
        "archive_stride": stride,
        "archive_after_sweep": after_sweep,
        "selected_projection": str(selected_projection.resolve()),
        "selected_projection_sha256": selected_hash,
        "trial_manifest_sha256": trial_hash,
        "chain_offset": chain_offset,
        "sample_id_layout": "chain11_sequence49",
        "archives": archives,
    })
    manifest["parameter_sha256_by_chain"] = {
        str(chain): hashlib.sha256(
            (batch_dir / f"chain_{chain}" / "parameters").read_bytes()
        ).hexdigest()
        for chain in range(chain_offset, chain_offset + chains)
    }
    atomic_json(batch_dir / "batch_manifest.json", manifest)
    return manifest
