#!/usr/bin/env python3
"""Shared execution and indexing for ALF path-archive runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from path_archive import ArchiveReader
from prepare_alf_chain import atomic_json
from prepare_archive_run import prepare_archive_batch
from run_alf_batch import run_batch


def validate_archive_request(
    manifest: dict[str, Any],
    *,
    phase: str,
    ensemble: str,
    theta: int,
    chains: int,
    nsweep: int,
    stride: int,
    after_sweep: int,
    chain_offset: int = 0,
    nwrap: int | None = None,
) -> None:
    expected = {
        "archive_phase": phase,
        "ensemble": ensemble,
        "theta": theta,
        "chain_count": chains,
        "nsweep": nsweep,
        "archive_stride": stride,
        "archive_after_sweep": after_sweep,
        "chain_offset": chain_offset,
        "sample_id_layout": "chain11_sequence49",
    }
    if nwrap is not None:
        expected["nwrap"] = nwrap
    mismatches = {
        key: {"found": manifest.get(key), "expected": value}
        for key, value in expected.items()
        if manifest.get(key) != value
    }
    if mismatches:
        raise RuntimeError(
            "existing archive batch does not match request: "
            + ", ".join(sorted(mismatches))
        )


def header_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.sha256(handle.read(256)).hexdigest()


def scan_archive_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    expected_code = 1 if manifest["ensemble"] == "II" else 2
    for item in manifest["archives"]:
        path = Path(item["path"])
        reader = ArchiveReader(path, expected={
            "ensemble_code": expected_code,
            "ltrot": int(manifest["ltrot"]),
            "selected_projection_sha256": manifest[
                "selected_projection_sha256"
            ],
            "trial_manifest_sha256": manifest["trial_manifest_sha256"],
        })
        scan = reader.scan()
        if scan.truncated_tail:
            raise RuntimeError(f"truncated archive tail: {path}")
        entries.append({
            "path": str(path.resolve()),
            "ensemble": manifest["ensemble"],
            "chain": int(item["chain"]),
            "records": scan.complete_records,
            "header_sha256": header_sha256(path),
        })
    return entries


def run_archive_phase(
    *,
    run_root: Path,
    archive_root: Path,
    phase: str,
    theta: int,
    nsweep: int,
    stride: int,
    after_sweep: int,
    executable: Path,
    selected_projection: Path,
    master_seed: int,
    ensembles: Sequence[str] = ("II", "TI"),
    direct: bool = False,
    batch: int = 0,
    chains: int = 6,
    chain_offset: int = 0,
    nwrap: int | None = None,
) -> list[dict[str, Any]]:
    all_entries: list[dict[str, Any]] = []
    invalid = set(ensembles) - {"II", "TI"}
    if invalid:
        raise ValueError(f"unknown archive ensemble(s): {sorted(invalid)}")
    for ensemble in ensembles:
        ensemble_index = {"II": 0, "TI": 1}[ensemble]
        batch_dir = (
            run_root / ensemble / f"theta_{theta:03d}"
            / f"batch_{batch:03d}"
        )
        if not (batch_dir / "batch_manifest.json").exists():
            prepare_archive_batch(
                run_root, archive_root, phase=phase, ensemble=ensemble,
                theta=theta, batch=batch, nsweep=nsweep, stride=stride,
                after_sweep=after_sweep,
                master_seed=master_seed + ensemble_index * 100_000,
                executable=executable,
                selected_projection=selected_projection,
                chains=chains,
                chain_offset=chain_offset,
                nwrap=nwrap,
            )
        manifest = json.loads(
            (batch_dir / "batch_manifest.json").read_text()
        )
        validate_archive_request(
            manifest,
            phase=phase,
            ensemble=ensemble,
            theta=theta,
            chains=chains,
            nsweep=nsweep,
            stride=stride,
            after_sweep=after_sweep,
            chain_offset=chain_offset,
            nwrap=nwrap,
        )
        launcher: Sequence[str] = () if direct else ("mpirun", "-np", "1")
        state = run_batch(
            batch_dir, launcher=launcher, bind_cpus=True
        )
        if state["status"] != "complete":
            raise RuntimeError(f"{phase} {ensemble} ALF run failed")
        entries = scan_archive_manifest(manifest)
        all_entries.extend(entries)
        print(
            f"{phase} {ensemble}: "
            f"{sum(entry['records'] for entry in entries)} records",
            flush=True,
        )
    return all_entries


def write_archive_index(
    path: Path, entries: list[dict[str, Any]], **metadata: Any
) -> None:
    atomic_json(path, {
        "schema_version": 1,
        **metadata,
        "entries": sorted(
            entries, key=lambda row: (row["ensemble"], row["chain"])
        ),
    })
