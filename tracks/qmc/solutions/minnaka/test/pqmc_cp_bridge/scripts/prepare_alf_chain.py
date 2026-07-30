#!/usr/bin/env python3
"""Prepare immutable ALF projector batches for the PQMC/CP bridge."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any

from bridge_config import approved_config, ltrot, theta_candidates


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ALF_CHECKOUT_START_PARAMETERS = (
    REPO / "test" / "alf_hirsch_binary" / "ALF"
    / "Scripts_and_Parameters_files" / "Start" / "parameters"
)
BUNDLED_START_PARAMETERS = ROOT / "assets" / "alf_start_parameters"
ALF_START_PARAMETERS = (
    ALF_CHECKOUT_START_PARAMETERS
    if ALF_CHECKOUT_START_PARAMETERS.is_file()
    else BUNDLED_START_PARAMETERS
)
DEFAULT_TRIAL_ASSETS = ROOT / "assets" / "trials"
RAW_OUTPUT_NAMES = {
    "info",
    "Ener_scal",
    "Kin_scal",
    "Pot_scal",
    "Part_scal",
    "Green_scal",
    "confout_0",
    "run.log",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def replace_assignment(
    text: str, name: str, value: str, *, count: int = 1
) -> str:
    pattern = re.compile(
        rf"(?mi)^(\s*{re.escape(name)}\s*=\s*)[^!\n]*(.*)$"
    )
    updated, replacements = pattern.subn(
        lambda match: f"{match.group(1)}{value}{match.group(2)}",
        text,
        count=count,
    )
    if replacements != count:
        raise RuntimeError(
            f"expected {count} assignment(s) for {name}, found {replacements}"
        )
    return updated


def make_parameters(
    *, theta: int, nbin: int, nsweep: int, boundary: str, nwrap: int = 5
) -> str:
    if theta not in theta_candidates():
        raise ValueError(f"unsupported projection theta: {theta}")
    if nbin < 1 or nsweep < 1 or nwrap < 1:
        raise ValueError("NBin, NSweep, and Nwrap must be positive")
    ensemble = boundary.upper()
    if ensemble not in {"TI", "II"}:
        raise ValueError("boundary must be TI or II")
    text = ALF_START_PARAMETERS.read_text(encoding="utf-8")
    for name, value in (
        ("ham_name", '"Hubbard_Plain_Vanilla"'),
        ("L1", "4"),
        ("L2", "4"),
        ("Nwrap", str(nwrap)),
        ("NSweep", str(nsweep)),
        ("NBin", str(nbin)),
        ("Ltau", "0"),
        ("n_skip", "1"),
        ("N_rebin", "1"),
    ):
        text = replace_assignment(text, name, value)

    start = text.index("&VAR_Hubbard_Plain_Vanilla")
    end_match = re.search(r"(?m)^/\s*$", text[start:])
    if end_match is None:
        raise RuntimeError("unterminated VAR_Hubbard_Plain_Vanilla group")
    end = start + end_match.start()
    group = text[start:end]
    for name, value in (
        ("ham_T", "1.d0"),
        ("ham_chem", "0.d0"),
        ("ham_U", "4.d0"),
        ("Dtau", "0.05d0"),
        ("Beta", "1.d0"),
        ("Projector", ".T."),
        ("Theta", f"{theta}.d0"),
        ("Symm", ".T."),
    ):
        group = replace_assignment(group, name, value)
    mode = 1 if ensemble == "TI" else 0
    group += (
        "Hirsch_binary = .T.\n"
        f"Trial_boundary_mode = {mode}\n"
        "Export_trial_orbitals = .F.\n"
    )
    return text[:start] + group + text[end:]


def deterministic_seed(
    master_seed: int, theta: int, batch: int, chain: int
) -> int:
    if master_seed <= 0 or batch < 0 or chain < 0:
        raise ValueError("seed coordinates are out of range")
    payload = f"{master_seed}:{theta}:{batch}:{chain}".encode()
    value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return 1 + value % 2_000_000_000


def _load_trial_hashes(trial_assets: Path) -> dict[str, str]:
    manifest = json.loads(
        (trial_assets / "trial_manifest.json").read_text(encoding="utf-8")
    )
    hashes = manifest.get("sha256", {})
    required = {"trial_T_up.dat", "trial_T_down.dat"}
    if not required.issubset(hashes):
        raise RuntimeError("trial manifest lacks UHF orbital hashes")
    for name in required:
        path = trial_assets / name
        if not path.is_file() or sha256_file(path) != hashes[name]:
            raise RuntimeError(f"trial asset hash mismatch: {name}")
    return {name: hashes[name] for name in sorted(required)}


def _raw_outputs(run_dir: Path) -> list[str]:
    return sorted(name for name in RAW_OUTPUT_NAMES if (run_dir / name).exists())


def prepare_batch(
    root: Path,
    *,
    ensemble: str,
    theta: int,
    batch: int,
    nbin: int,
    nsweep: int,
    master_seed: int,
    executable: Path,
    trial_assets: Path = DEFAULT_TRIAL_ASSETS,
    chains: int = 6,
    nwrap: int = 5,
    chain_offset: int = 0,
) -> dict[str, Any]:
    if chains < 6:
        raise ValueError("a statistical batch requires at least six chains")
    if chain_offset < 0 or chain_offset + chains > 2048:
        raise ValueError("global chain range must be within [0,2048)")
    ensemble = ensemble.upper()
    parameters = make_parameters(
        theta=theta, nbin=nbin, nsweep=nsweep, boundary=ensemble,
        nwrap=nwrap,
    )
    target = root / ensemble / f"theta_{theta:03d}" / f"batch_{batch:03d}"
    if target.exists():
        present = [
            f"chain_{chain}/{name}"
            for chain in range(chain_offset, chain_offset + chains)
            for name in _raw_outputs(target / f"chain_{chain}")
        ]
        if present:
            raise RuntimeError(
                f"batch contains raw output and cannot be prepared: {present}"
            )
    target.mkdir(parents=True, exist_ok=True)
    trial_hashes = _load_trial_hashes(trial_assets) if ensemble == "TI" else {}
    executable = executable.resolve()
    chain_records: list[dict[str, Any]] = []
    for local_chain in range(chains):
        chain = chain_offset + local_chain
        run_dir = target / f"chain_{chain}"
        run_dir.mkdir(exist_ok=True)
        if _raw_outputs(run_dir):
            raise RuntimeError(f"chain contains raw output: {run_dir}")
        seed = deterministic_seed(master_seed, theta, batch, chain)
        (run_dir / "parameters").write_text(parameters, encoding="utf-8")
        (run_dir / "seeds").write_text(f"{seed}\n", encoding="utf-8")
        if ensemble == "TI":
            for name, expected_hash in trial_hashes.items():
                destination = run_dir / name
                shutil.copy2(trial_assets / name, destination)
                if sha256_file(destination) != expected_hash:
                    raise RuntimeError(f"copied trial hash mismatch: {name}")
        chain_records.append({
            "local_chain": local_chain,
            "chain": chain,
            "seed": seed,
        })
    seeds = [record["seed"] for record in chain_records]
    if len(set(seeds)) != chains:
        raise RuntimeError("deterministic seeds are not unique")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "ensemble": ensemble,
        "theta": theta,
        "ltrot": ltrot(theta, approved_config()),
        "nfield": ltrot(theta, approved_config()) * 16,
        "batch": batch,
        "nbin": nbin,
        "nsweep": nsweep,
        "nwrap": nwrap,
        "master_seed": master_seed,
        "chain_count": chains,
        "chain_offset": chain_offset,
        "sample_id_layout": "chain11_sequence49",
        "chains": chain_records,
        "executable": str(executable),
        "executable_sha256": (
            sha256_file(executable) if executable.is_file() else None
        ),
        "parameter_sha256": hashlib.sha256(parameters.encode()).hexdigest(),
        "trial_sha256": trial_hashes,
    }
    atomic_json(target / "batch_manifest.json", manifest)
    atomic_json(
        target / "batch_state.json",
        {
            "schema_version": 1,
            "status": "prepared",
            "statistics_eligible": False,
            "chains": {},
        },
    )
    return manifest
