#!/usr/bin/env python3
"""Run one node-local direct-reweighting production replica."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from alf_statistics import parse_replica
from archive_runs import run_archive_phase, write_archive_index
from direct_reweight_statistics import read_summary_rows
from prepare_alf_chain import (
    DEFAULT_TRIAL_ASSETS,
    atomic_json,
    sha256_file,
)
from run_bulk_replay import compare_summaries
from run_parallel_replay import run_parallel_replay
from select_replay_samples import archive_rows, write_sample_manifest
from verify_archive_replay import (
    load_sources,
    trial_log_shifts,
    validate_rows,
)


def replica_contract(
    replica_id: int,
    *,
    replicas: int = 10,
    chains: int = 192,
    paths_per_chain: int = 50,
    burn_sweeps: int = 2000,
    stride: int = 239,
    master_seed: int = 3_700_090,
    nwrap: int = 5,
) -> dict[str, int | str]:
    if (
        replicas <= 0
        or not 0 <= replica_id < replicas
        or chains < 6
        or paths_per_chain <= 0
        or burn_sweeps < 0
        or stride <= 0
        or master_seed <= 0
        or nwrap <= 0
    ):
        raise ValueError("invalid replica production coordinates")
    chain_offset = replica_id * chains
    chain_stop = chain_offset + chains
    if chain_stop > 2048:
        raise ValueError("replica global chain range exceeds archive contract")
    return {
        "schema_version": 1,
        "phase": "direct_reweight",
        "replica_id": replica_id,
        "replicas": replicas,
        "chains": chains,
        "chain_offset": chain_offset,
        "chain_stop": chain_stop,
        "paths_per_chain": paths_per_chain,
        "burn_sweeps": burn_sweeps,
        "stride": stride,
        "nsweep": burn_sweeps + paths_per_chain * stride,
        "master_seed": master_seed,
        "nwrap": nwrap,
        "sample_id_layout": "chain11_sequence49",
    }


def validate_archive_entries(
    entries: Sequence[Mapping[str, object]],
    *,
    chain_offset: int,
    chains: int,
    paths_per_chain: int,
) -> None:
    if len(entries) != chains:
        raise RuntimeError("archive entry count differs from chain count")
    found = sorted(int(entry["chain"]) for entry in entries)
    expected = list(range(chain_offset, chain_offset + chains))
    if found != expected:
        raise RuntimeError("archive global chain range is incomplete")
    for entry in entries:
        if str(entry["ensemble"]) != "TI":
            raise RuntimeError("direct production archive is not TI")
        if int(entry["records"]) != paths_per_chain:
            raise RuntimeError(
                f"archive record count differs from {paths_per_chain}: "
                f"chain {entry['chain']}"
            )


def guard_incomplete_replica_resume(
    replica_root: Path,
    *,
    replica_id: int,
) -> None:
    """Refuse to append a fresh full run onto an incomplete Markov chain."""
    batch_dir = (
        replica_root / "runs/TI/theta_010"
        / f"batch_{replica_id:03d}"
    )
    state_path = batch_dir / "batch_state.json"
    if not state_path.is_file():
        return
    state = json.loads(state_path.read_text())
    if state.get("status") == "complete":
        return
    archive_dir = replica_root / "archives/direct_reweight/TI"
    nonempty = [
        path for path in archive_dir.glob("chain_*.qhpath")
        if path.stat().st_size > 256
    ]
    if nonempty:
        raise RuntimeError(
            "incomplete replica already has path records; isolate it instead "
            "of appending a fresh full Markov-chain run"
        )


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return (
        ordered[lower] * (1.0 - fraction)
        + ordered[upper] * fraction
    )


def collect_green_diagnostics(
    batch_dir: Path,
    manifest: Mapping[str, object],
    output_dir: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in manifest["chains"]:  # type: ignore[index]
        chain = int(item["chain"])
        parsed = parse_replica(
            batch_dir / f"chain_{chain}",
            {
                **manifest,
                "chain": chain,
                "seed": int(item["seed"]),
            },
        )
        location = parsed.green_location
        rows.append({
            "chain": chain,
            "max_delta_g": parsed.max_green_precision,
            "pass_1e-8": parsed.max_green_precision <= 1.0e-8,
            "bin": location[0],
            "sweep": location[1],
            "direction": location[2],
            "slice": location[3],
            "i": location[4],
            "j": location[5],
            "flavor": location[6],
        })
    values = [float(row["max_delta_g"]) for row in rows]
    failed = [
        int(row["chain"]) for row in rows if not bool(row["pass_1e-8"])
    ]
    summary: dict[str, object] = {
        "chains": len(rows),
        "maximum_delta_g": max(values),
        "median_delta_g": _percentile(values, 0.5),
        "p95_delta_g": _percentile(values, 0.95),
        "failed_chains": failed,
        "alf_green_stability_pass": not failed,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "green_stability.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    atomic_json(output_dir / "green_stability.json", summary)
    return rows, summary


def _write_selected_manifest(
    path: Path,
    identities: Mapping[int, tuple[str, int]],
    sample_ids: Sequence[int],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("sample_id", "ensemble", "chain"))
        for sample_id in sorted(sample_ids):
            writer.writerow((sample_id, *identities[sample_id]))


def _write_selected_summary(
    source: Path, output: Path, sample_ids: set[int]
) -> None:
    with source.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            row for row in reader if int(row["sample_id"]) in sample_ids
        ]
        fieldnames = reader.fieldnames
    if not rows or fieldnames is None:
        raise RuntimeError("flagged replay summary is empty")
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def validate_and_replay_stability(
    *,
    archive_index: Path,
    sample_manifest: Path,
    baseline_summary: Path,
    selected_projection: Path,
    trial_manifest: Path,
    field_order: Path,
    executable: Path,
    replay_dir: Path,
    workers: int,
) -> dict[str, object]:
    sources, identities = load_sources(archive_index, sample_manifest)
    shifts = trial_log_shifts(trial_manifest)
    with baseline_summary.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["_alf_to_raw_log_shift"] = repr(shifts[str(row["ensemble"])])
    baseline = validate_rows(rows, sources)
    flagged = sorted(set(baseline["failed_sample_ids"]) | set(
        baseline["numerically_ambiguous_sample_ids"]
    ))
    comparison: dict[str, object] = {
        "passed": True,
        "samples": 0,
        "reason": "no flagged paths",
    }
    if flagged:
        manifest = replay_dir / "flagged_samples.csv"
        baseline_flagged = replay_dir / "replay_summary_s5_flagged.csv"
        _write_selected_manifest(manifest, identities, flagged)
        _write_selected_summary(
            baseline_summary, baseline_flagged, set(flagged)
        )
        summaries = [baseline_flagged]
        for interval in (1, 10):
            summary, _prefix = run_parallel_replay(
                executable=executable,
                archive_index=archive_index,
                sample_manifest=manifest,
                selected_projection=selected_projection,
                trial_manifest=trial_manifest,
                field_order=field_order,
                output_dir=replay_dir,
                stabilize_every=interval,
                workers=min(workers, len(flagged)),
                summary_only=True,
            )
            summaries.append(summary)
        comparison = compare_summaries(summaries)
        comparison["samples"] = len(flagged)
    result: dict[str, object] = {
        "schema_version": 1,
        "baseline": baseline,
        "flagged_sample_ids": flagged,
        "stabilization": comparison,
        "replay_stability_pass": (
            not baseline["failed_sample_ids"]
            and bool(comparison["passed"])
        ),
    }
    atomic_json(replay_dir / "replay_stability.json", result)
    return result


def run_replica(
    *,
    production_root: Path,
    replica_id: int,
    alf_executable: Path,
    replay_executable: Path,
    selected_projection: Path,
    trial_manifest: Path,
    field_order: Path,
    workers: int,
    replicas: int = 10,
    chains: int = 192,
    paths_per_chain: int = 50,
    burn_sweeps: int = 2000,
    stride: int = 239,
    master_seed: int = 3_700_090,
    nwrap: int = 5,
) -> dict[str, object]:
    contract = replica_contract(
        replica_id,
        replicas=replicas,
        chains=chains,
        paths_per_chain=paths_per_chain,
        burn_sweeps=burn_sweeps,
        stride=stride,
        master_seed=master_seed,
        nwrap=nwrap,
    )
    selected = json.loads(selected_projection.read_text())
    if (
        int(selected.get("theta_star", -1)) != 10
        or int(selected.get("ltrot_star", -1)) != 420
        or abs(float(selected.get("dt", math.nan)) - 0.05) > 1.0e-14
        or abs(float(selected.get("beta", math.nan)) - 1.0) > 1.0e-14
        or int(selected.get("nwrap", -1)) != 5
        or not 1 <= nwrap <= int(selected["nwrap"])
    ):
        raise RuntimeError("selected projection differs from frozen production")
    default_trial = DEFAULT_TRIAL_ASSETS / "trial_manifest.json"
    if sha256_file(trial_manifest) != sha256_file(default_trial):
        raise RuntimeError(
            "replay trial manifest differs from ALF archive trial assets"
        )
    contract.update({
        "selected_projection_sha256": sha256_file(selected_projection),
        "trial_manifest_sha256": sha256_file(trial_manifest),
        "alf_executable_sha256": sha256_file(alf_executable),
        "replay_executable_sha256": sha256_file(replay_executable),
    })
    replica_root = production_root / "replicas" / f"replica_{replica_id:03d}"
    contract_path = replica_root / "replica_contract.json"
    if contract_path.is_file():
        if json.loads(contract_path.read_text()) != contract:
            raise RuntimeError("existing replica contract differs from request")
    else:
        atomic_json(contract_path, contract)
    guard_incomplete_replica_resume(
        replica_root, replica_id=replica_id
    )

    entries = run_archive_phase(
        run_root=replica_root / "runs",
        archive_root=replica_root / "archives",
        phase="direct_reweight",
        theta=10,
        nsweep=int(contract["nsweep"]),
        stride=stride,
        after_sweep=burn_sweeps,
        executable=alf_executable,
        selected_projection=selected_projection,
        master_seed=master_seed,
        ensembles=("TI",),
        direct=True,
        batch=replica_id,
        chains=chains,
        chain_offset=int(contract["chain_offset"]),
        nwrap=nwrap,
    )
    validate_archive_entries(
        entries,
        chain_offset=int(contract["chain_offset"]),
        chains=chains,
        paths_per_chain=paths_per_chain,
    )
    archive_index = replica_root / "archive_index.json"
    write_archive_index(
        archive_index,
        entries,
        **contract,
        records=chains * paths_per_chain,
    )
    all_archive_rows = archive_rows(archive_index)
    sample_manifest = replica_root / "all_samples.csv"
    write_sample_manifest(
        sample_manifest,
        all_archive_rows,
        [int(row["sample_id"]) for row in all_archive_rows],
    )

    replay_dir = replica_root / "replay"
    baseline_summary = replay_dir / "replay_summary_s5.csv"
    if (
        not baseline_summary.is_file()
        or len(read_summary_rows([baseline_summary]))
        != chains * paths_per_chain
    ):
        baseline_summary, _prefix = run_parallel_replay(
            executable=replay_executable,
            archive_index=archive_index,
            sample_manifest=sample_manifest,
            selected_projection=selected_projection,
            trial_manifest=trial_manifest,
            field_order=field_order,
            output_dir=replay_dir,
            stabilize_every=5,
            workers=workers,
            summary_only=True,
        )

    batch_dir = (
        replica_root / "runs/TI/theta_010"
        / f"batch_{replica_id:03d}"
    )
    manifest = json.loads(
        (batch_dir / "batch_manifest.json").read_text()
    )
    _green_rows, green = collect_green_diagnostics(
        batch_dir, manifest, replica_root
    )
    replay_stability = validate_and_replay_stability(
        archive_index=archive_index,
        sample_manifest=sample_manifest,
        baseline_summary=baseline_summary,
        selected_projection=selected_projection,
        trial_manifest=trial_manifest,
        field_order=field_order,
        executable=replay_executable,
        replay_dir=replay_dir,
        workers=workers,
    )
    status: dict[str, object] = {
        **contract,
        "status": "complete",
        "archive_index": str(archive_index.resolve()),
        "sample_manifest": str(sample_manifest.resolve()),
        "replay_summary": str(baseline_summary.resolve()),
        "green_stability_csv": str(
            (replica_root / "green_stability.csv").resolve()
        ),
        "alf_green_stability_pass": green["alf_green_stability_pass"],
        "replay_stability_pass": replay_stability[
            "replay_stability_pass"
        ],
        "green_stability_pass": (
            bool(green["alf_green_stability_pass"])
            and bool(replay_stability["replay_stability_pass"])
        ),
    }
    atomic_json(replica_root / "replica_status.json", status)
    print(
        f"replica {replica_id} complete: paths={chains * paths_per_chain} "
        f"green_stability_pass={status['green_stability_pass']}",
        flush=True,
    )
    return status


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-root", type=Path, required=True)
    parser.add_argument("--replica-id", type=int, required=True)
    parser.add_argument("--alf-executable", type=Path, required=True)
    parser.add_argument(
        "--replay-executable",
        type=Path,
        default=root / "test/cpmc_path_audit/build/cpmc_audit",
    )
    parser.add_argument(
        "--selected-projection",
        type=Path,
        default=bridge / "results/selected_projection.json",
    )
    parser.add_argument(
        "--trial-manifest",
        type=Path,
        default=bridge / "assets/trials/trial_manifest.json",
    )
    parser.add_argument(
        "--field-order",
        type=Path,
        default=bridge / "contracts/field_order.json",
    )
    parser.add_argument("--workers", type=int, default=192)
    parser.add_argument("--replicas", type=int, default=10)
    parser.add_argument("--chains", type=int, default=192)
    parser.add_argument("--paths-per-chain", type=int, default=50)
    parser.add_argument("--burn-sweeps", type=int, default=2000)
    parser.add_argument("--stride", type=int, default=239)
    parser.add_argument("--master-seed", type=int, default=3_700_090)
    parser.add_argument("--nwrap", type=int, default=5)
    args = parser.parse_args()
    if args.workers <= 0:
        parser.error("workers must be positive")
    run_replica(
        production_root=args.production_root,
        replica_id=args.replica_id,
        alf_executable=args.alf_executable,
        replay_executable=args.replay_executable,
        selected_projection=args.selected_projection,
        trial_manifest=args.trial_manifest,
        field_order=args.field_order,
        workers=args.workers,
        replicas=args.replicas,
        chains=args.chains,
        paths_per_chain=args.paths_per_chain,
        burn_sweeps=args.burn_sweeps,
        stride=args.stride,
        master_seed=args.master_seed,
        nwrap=args.nwrap,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
