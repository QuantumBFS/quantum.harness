#!/usr/bin/env python3
"""Append one bounded production-archive segment per requested ensemble."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archive_runs import (
    run_archive_phase,
    scan_archive_manifest,
    write_archive_index,
)
from prepare_alf_chain import atomic_json
from estimate_archive_stride import required_sweeps


def _partial_index(archive_root: Path, ensemble: str) -> Path:
    return archive_root / f"production_index.{ensemble}.json"


def segment_nsweep(
    stride: int, *, burn: int = 2000, max_sweeps: int = 5000
) -> int:
    if (
        stride <= 0 or burn < 0 or max_sweeps <= burn
        or stride > max_sweeps - burn
    ):
        raise ValueError("invalid bounded production segment")
    exports = (max_sweeps - burn) // stride
    return burn + stride * exports


def production_nsweep(
    *,
    stride: int,
    target_records: int,
    chains: int,
    burn: int = 2000,
    max_sweeps: int = 5000,
) -> int:
    bounded = segment_nsweep(
        stride, burn=burn, max_sweeps=max_sweeps
    )
    required = required_sweeps(
        target_records, stride, chains, burn
    )
    return min(bounded, required)


def _next_batch(run_root: Path, ensemble: str, theta: int) -> int:
    root = run_root / ensemble / f"theta_{theta:03d}"
    for path in sorted(root.glob("batch_*")):
        state_path = path / "batch_state.json"
        state = json.loads(state_path.read_text()) if state_path.is_file() else {}
        if state.get("status") != "complete":
            return int(path.name.split("_")[-1])
    return len(list(root.glob("batch_*")))


def _latest_entries(
    run_root: Path, ensemble: str, theta: int
) -> list[dict]:
    root = run_root / ensemble / f"theta_{theta:03d}"
    complete = []
    for path in sorted(root.glob("batch_*")):
        state_path = path / "batch_state.json"
        if not state_path.is_file():
            continue
        if json.loads(state_path.read_text()).get("status") == "complete":
            complete.append(path)
    if not complete:
        return []
    manifest = json.loads(
        (complete[-1] / "batch_manifest.json").read_text()
    )
    return scan_archive_manifest(manifest)


def _merge_if_complete(
    archive_root: Path,
    *,
    theta: int,
    stride: int,
    burn: int,
    target: int,
) -> tuple[Path, dict[str, int]] | None:
    partials = [_partial_index(archive_root, item) for item in ("II", "TI")]
    if not all(path.is_file() for path in partials):
        return None
    entries = []
    counts: dict[str, int] = {}
    segments: dict[str, int] = {}
    for path in partials:
        document = json.loads(path.read_text())
        ensemble = str(document["ensemble"])
        counts[ensemble] = int(document["records"])
        segments[ensemble] = int(document["segments"])
        entries.extend(document["entries"])
    if min(counts.values()) < target:
        return None
    index = archive_root / "archive_index.json"
    write_archive_index(
        index, entries, phase="production", theta=theta,
        stride=stride, after_sweep=burn,
        target_records_per_ensemble=target,
        records_by_ensemble=counts,
        segments_by_ensemble=segments,
    )
    return index, counts


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    bridge = root / "test/pqmc_cp_bridge"
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected-projection", type=Path, required=True)
    parser.add_argument(
        "--stride-contract", type=Path,
        default=bridge / "results/archive_stride.json",
    )
    parser.add_argument(
        "--target-records-per-ensemble", type=int, default=1024,
    )
    parser.add_argument("--chains", type=int, default=128)
    parser.add_argument(
        "--executable", type=Path,
        default=root / "test/alf_hirsch_binary/run/binary/bin/ALF.binary.out",
    )
    parser.add_argument(
        "--run-root", type=Path, default=bridge / "runs/archive_production",
    )
    parser.add_argument(
        "--archive-root", type=Path, default=bridge / "archives",
    )
    parser.add_argument(
        "--ensemble", choices=("II", "TI", "both"), default="both",
    )
    parser.add_argument(
        "--max-sweeps-per-job", type=int, default=5000,
    )
    parser.add_argument(
        "--direct", action="store_true",
        help="run the serial/noMPI ALF executable without mpirun",
    )
    args = parser.parse_args()
    if args.target_records_per_ensemble <= 0 or not 6 <= args.chains <= 256:
        parser.error("target records/chains are outside supported bounds")
    selected = json.loads(args.selected_projection.read_text())
    stride_contract = json.loads(args.stride_contract.read_text())
    stride = int(stride_contract["stride"])
    burn = 2000
    theta = int(selected["theta_star"])
    nsweep = production_nsweep(
        stride=stride,
        target_records=args.target_records_per_ensemble,
        chains=args.chains,
        burn=burn,
        max_sweeps=args.max_sweeps_per_job,
    )
    ensembles = ("II", "TI") if args.ensemble == "both" \
        else (args.ensemble,)
    for ensemble in ensembles:
        entries = _latest_entries(args.run_root, ensemble, theta)
        records = sum(int(row["records"]) for row in entries)
        if records < args.target_records_per_ensemble:
            batch = _next_batch(args.run_root, ensemble, theta)
            entries = run_archive_phase(
                run_root=args.run_root,
                archive_root=args.archive_root,
                phase="production",
                theta=theta,
                nsweep=nsweep,
                stride=stride,
                after_sweep=burn,
                executable=args.executable,
                selected_projection=args.selected_projection,
                master_seed=2_700_090,
                ensembles=(ensemble,),
                direct=args.direct,
                batch=batch,
                chains=args.chains,
            )
            records = sum(int(row["records"]) for row in entries)
        segments = _next_batch(args.run_root, ensemble, theta)
        write_archive_index(
            _partial_index(args.archive_root, ensemble),
            entries, phase="production", ensemble=ensemble,
            theta=theta, stride=stride, after_sweep=burn,
            segment_nsweep=nsweep, segments=segments, records=records,
            chains=args.chains,
            target_records_per_ensemble=args.target_records_per_ensemble,
        )
        print(
            f"production {ensemble}: {records}/"
            f"{args.target_records_per_ensemble} records "
            f"after {segments} segment(s)",
            flush=True,
        )
    merged = _merge_if_complete(
        args.archive_root,
        theta=theta,
        stride=stride,
        burn=burn,
        target=args.target_records_per_ensemble,
    )
    if merged is None:
        print("PRODUCTION_PENDING: submit the next bounded segment", flush=True)
        return 0
    index, counts = merged
    atomic_json(bridge / "results/archive_summary.json", {
        "schema_version": 1,
        "theta": theta,
        "stride": stride,
        "burn_sweeps": burn,
        "sweeps_per_segment": nsweep,
        "target_records_per_ensemble": args.target_records_per_ensemble,
        "chains": args.chains,
        "records_by_ensemble": counts,
        "archive_index": str(index.resolve()),
    })
    print(f"production archives complete: {counts}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
